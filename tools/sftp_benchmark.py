#!/usr/bin/env python3
"""
Benchmark the BioShare SFTP daemon, per the Performance section of
ignore/plans/sftp-server-improvements.md.

Runs two corpora that exercise the two different bottlenecks, each in both
directions:

  big    one large file  -> per-byte cost, i.e. paramiko and upload buffering (§4)
  many   many small files -> per-file cost, i.e. the guardian permission query (§3)

Nothing here changes server settings. To measure what §3 and §4 bought, run the
matrix once as shipped and once with the pre-change behaviour restored in the
server's config.py, restarting the daemon in between:

    SFTP_PERMISSION_CACHE_SECONDS = 0        # was: no memo, one query per file
    SFTP_WRITE_BUFFER_SIZE = 8192            # was: Python's default buffer

then compare the two result files.

Typical use, from a client machine (not the devcontainer):

    ./tools/sftp_benchmark.py build --corpus-dir /tmp/bench
    ./tools/sftp_benchmark.py run --corpus-dir /tmp/bench \\
        --host bioshare.example.edu --port 2200 --user someone@example.edu \\
        --key ~/.ssh/id_ed25519 --share myshare \\
        --label after --results after.json
    # ...restore the old settings on the server, restart the daemon...
    ./tools/sftp_benchmark.py run ... --label before --results before.json
    ./tools/sftp_benchmark.py compare before.json after.json

Requires rclone on the client, and a daemon new enough to accept SETSTAT (it is
how rclone sets the modtime after an upload; before that landed it discarded
every transfer). Checksum verification stays off -- there is no exec channel to
compute one, plan §5.

Wall-clock is noisy; for §3 specifically the
permission-lookup count from

    manage.py start_sftp_instrumented

is the more reliable measurement, since it is not affected by network or disk
variance. Run the "many" corpus against it and read the count off the log.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

BIG = 'big'
MANY = 'many'
UP = 'up'
DOWN = 'down'


def die(message):
    sys.exit('error: %s' % message)


def free_bytes(path):
    """Free space on the filesystem holding `path`, or its nearest parent."""
    while not os.path.exists(path):
        parent = os.path.dirname(path.rstrip(os.sep))
        if parent == path:
            break
        path = parent
    stat = os.statvfs(path)
    return stat.f_bavail * stat.f_frsize


def require_space(path, needed, what):
    """
    Refuse to start rather than fill the disk.

    Both times this benchmark was first run it ran the filesystem out of space,
    and both times the failure reached the client as a bare SFTP "Failure" --
    once from a write, once from a mkdir -- which is an expensive way to learn
    you needed a df. The remote side cannot be checked from here at all: this
    server implements no statvfs (plan §5), so `rclone about` has nothing to
    ask.
    """
    available = free_bytes(path)
    if available >= needed:
        return
    die('not enough space for %s.\n'
        '  %s has %s free, this needs about %s.\n'
        '  Free some space, or use a smaller corpus (--big-gb / --small-count).\n'
        '  Remember the share needs at least as much again for the uploaded\n'
        '  copy, on whatever filesystem backs it -- which may well be this one.'
        % (what, path, human(available), human(needed)))


# -- corpus ------------------------------------------------------------------

def build_corpus(corpus_dir, big_gb, small_count, small_bytes):
    # Before makedirs, not after: on a full disk that call is itself the first
    # thing to fail, with an ENOSPC traceback instead of an explanation.
    needed = big_gb * 1024 ** 3 + small_count * small_bytes
    already = tree_size(corpus_dir)[0] if os.path.isdir(corpus_dir) else 0
    require_space(corpus_dir, int((needed - already) * 1.05), 'the corpus')

    os.makedirs(corpus_dir, exist_ok=True)

    big_path = os.path.join(corpus_dir, 'big.bin')
    want = big_gb * 1024 * 1024 * 1024
    if os.path.exists(big_path) and os.path.getsize(big_path) == want:
        print('big.bin already present at %d GB, keeping it' % big_gb)
    else:
        print('writing %s (%d GB, this takes a while)...' % (big_path, big_gb))
        # /dev/urandom rather than /dev/zero so a filesystem with compression or
        # dedup can't make the transfer look faster than it is.
        subprocess.run(['dd', 'if=/dev/urandom', 'of=%s' % big_path,
                        'bs=1M', 'count=%d' % (big_gb * 1024)], check=True)

    many_dir = os.path.join(corpus_dir, 'many')
    existing = sum(len(files) for _, _, files in os.walk(many_dir)) if os.path.isdir(many_dir) else 0
    if existing == small_count:
        print('many/ already holds %d files, keeping them' % small_count)
    else:
        if os.path.isdir(many_dir):
            print('many/ holds %d files, wanted %d -- rebuilding' % (existing, small_count))
            shutil.rmtree(many_dir)
        print('writing %d files of %d bytes under %s...' % (small_count, small_bytes, many_dir))
        # Spread across subdirectories: a single directory with 50k entries
        # measures the filesystem's directory handling as much as the daemon's.
        per_dir = 500
        for i in range(small_count):
            sub = os.path.join(many_dir, '%03d' % (i // per_dir))
            if i % per_dir == 0:
                os.makedirs(sub, exist_ok=True)
                print('  %d/%d' % (i, small_count), end='\r', flush=True)
            with open(os.path.join(sub, 'f%06d' % i), 'wb') as f:
                f.write(os.urandom(small_bytes))
        print('  %d/%d' % (small_count, small_count))

    print('\ncorpus ready in %s' % corpus_dir)
    print('  big.bin  %s' % human(os.path.getsize(big_path)))
    print('  many/    %d files' % small_count)


def tree_size(path):
    if os.path.isfile(path):
        return os.path.getsize(path), 1
    total = count = 0
    for root, _, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
            count += 1
    return total, count


def human(n):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return '%.1f %s' % (n, unit)
        n /= 1024.0


# -- rclone ------------------------------------------------------------------

def remote_for(args, path):
    """
    An rclone backend connection string, so this never touches the operator's
    rclone config. Key auth only -- §2 exists precisely so a benchmark does not
    pay ~100ms of PBKDF2 per connection.
    """
    spec = ':sftp,host=%s,port=%d,user=%s,key_file=%s:' % (
        args.host, args.port, args.user, os.path.expanduser(args.key))
    return spec + path


def rclone(args, source, dest, extra=None):
    cmd = ['rclone', 'copy', source, dest,
           '--stats', '5s', '--stats-one-line',
           # No exec channel on this server (plan §5), so rclone cannot ask for
           # a remote checksum; without this it errors instead of falling back.
           # Setting modtimes does work -- chattr honours it -- so rclone
           # compares by size and modtime, which costs nothing here since every
           # run writes to a fresh directory anyway.
           '--sftp-disable-hashcheck',
           '--transfers', str(args.transfers)]
    if args.verbose:
        cmd.append('-vv')
    cmd += extra or []
    if args.dry_run:
        print('  would run: %s' % ' '.join(cmd))
        return 0.0
    started = time.monotonic()
    result = subprocess.run(cmd)
    elapsed = time.monotonic() - started
    if result.returncode != 0:
        die('rclone exited %d' % result.returncode)
    return elapsed


def run_matrix(args):
    if not shutil.which('rclone') and not args.dry_run:
        die('rclone not found on PATH')

    corpora = {
        BIG: os.path.join(args.corpus_dir, 'big.bin'),
        MANY: os.path.join(args.corpus_dir, 'many'),
    }
    if args.repeat > 1 and args.direction != DOWN:
        die('--repeat only makes sense with --direction down: repeating an '
            'upload into the same directory is a no-op, since rclone skips '
            'files it already sees on the far end')

    chosen = [args.corpus] if args.corpus else [BIG, MANY]
    for name in chosen:
        if not os.path.exists(corpora[name]) and not args.dry_run:
            die('corpus %r missing -- run the "build" subcommand first' % name)

    # Downloads land locally, so the client needs room for a second copy of
    # everything the run transfers.
    corpus_bytes = sum(tree_size(corpora[n])[0] for n in chosen) if not args.dry_run else 0
    if args.direction != UP:
        require_space(args.corpus_dir, int(corpus_bytes * 1.05), 'the downloaded copy')

    # A fresh remote subdirectory per run, so rclone never skips a file it
    # already sees on the far end, and so nothing existing is ever deleted.
    stamp = time.strftime('%Y%m%d-%H%M%S')
    # strip() both ends: paths in the SFTP virtual root are /<share>/subpath,
    # and the share is prepended below, so this must not carry a leading slash.
    run_root = '%s/%s-%s' % (args.remote_dir.strip('/'), args.label, stamp)
    download_root = os.path.join(args.corpus_dir, 'download-%s-%s' % (args.label, stamp))

    print('remote scratch:   /%s/%s' % (args.share, run_root))
    print('local  scratch:   %s' % download_root)
    if corpus_bytes:
        print('transferring:     %s (the share needs at least this much free;' % human(corpus_bytes))
        print('                  no statvfs on this server, so it cannot be checked from here)')
    print()

    runs = []
    for name in chosen:
        local = corpora[name]
        remote = remote_for(args, '%s/%s/%s' % (args.share, run_root, name))
        size, files = tree_size(local) if not args.dry_run else (0, 0)

        for direction in ([UP, DOWN] if not args.direction else [args.direction]):
            if direction == UP:
                source, dest = local, remote
            else:
                dest = os.path.join(download_root, name)
                if not args.dry_run:
                    os.makedirs(dest, exist_ok=True)
                source = remote

            print('=== %s / %s (%s, %d file%s) ===' % (
                name, direction, human(size), files, '' if files == 1 else 's'))
            for attempt in range(1, args.repeat + 1):
                if args.repeat > 1:
                    print('  attempt %d/%d' % (attempt, args.repeat))
                elapsed = rclone(args, source, dest)
                runs.append({
                    'corpus': name,
                    'direction': direction,
                    'attempt': attempt,
                    'seconds': round(elapsed, 2),
                    'bytes': size,
                    'files': files,
                    'bytes_per_second': round(size / elapsed) if elapsed else None,
                    'files_per_second': round(files / elapsed, 2) if elapsed else None,
                })
                print('  %.1fs  %s/s  %.1f files/s' % (
                    elapsed, human(size / elapsed) if elapsed else '-',
                    files / elapsed if elapsed else 0))
            print()

    result = {
        'label': args.label,
        'started': stamp,
        'host': args.host,
        'share': args.share,
        'transfers': args.transfers,
        'notes': args.notes,
        'runs': runs,
    }
    if args.dry_run:
        print('dry run, not writing %s' % args.results)
    else:
        with open(args.results, 'w') as f:
            json.dump(result, f, indent=2)
        print('wrote %s' % args.results)

    print()
    print('Left behind, delete when done:')
    print('  local:  rm -rf %s' % download_root)
    print('  remote: rclone purge %s' % remote_for(args, '%s/%s' % (args.share, run_root)))
    print('(neither is removed automatically -- check them before deleting)')


# -- compare -----------------------------------------------------------------

def best(runs, corpus, direction):
    """Fastest attempt, which is the least noisy estimate of the real cost."""
    candidates = [r for r in runs
                  if r['corpus'] == corpus and r['direction'] == direction]
    return min(candidates, key=lambda r: r['seconds']) if candidates else None


def compare(paths):
    loaded = []
    for path in paths:
        with open(path) as f:
            loaded.append(json.load(f))

    base, base_runs = loaded[0], loaded[0]['runs']
    print('baseline: %s (%s)' % (loaded[0]['label'], paths[0]))
    for other, path in zip(loaded[1:], paths[1:]):
        print('compared: %s (%s)' % (other['label'], path))
    print()

    header = '%-6s %-5s %12s %12s %10s' % ('corpus', 'dir', 'baseline', 'compared', 'change')
    print(header)
    print('-' * len(header))

    for corpus in (BIG, MANY):
        for direction in (UP, DOWN):
            a = best(base_runs, corpus, direction)
            if not a:
                continue
            for other in loaded[1:]:
                b = best(other['runs'], corpus, direction)
                if not b:
                    continue
                # Negative = faster than baseline.
                change = (b['seconds'] - a['seconds']) / a['seconds'] * 100
                print('%-6s %-5s %11.1fs %11.1fs %+9.1f%%' % (
                    corpus, direction, a['seconds'], b['seconds'], change))
    print()
    print('Negative change means the compared run was faster than the baseline.')
    print('Wall-clock alone will not tell you whether §3 worked -- pair this with')
    print('the permission-lookup count from manage.py start_sftp_instrumented.')


# -- cli ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)

    build = sub.add_parser('build', help='create the two local corpora')
    build.add_argument('--corpus-dir', required=True)
    build.add_argument('--big-gb', type=int, default=10)
    build.add_argument('--small-count', type=int, default=50000)
    build.add_argument('--small-bytes', type=int, default=4096)

    run = sub.add_parser('run', help='run the transfer matrix')
    run.add_argument('--corpus-dir', required=True)
    run.add_argument('--host', required=True)
    run.add_argument('--port', type=int, default=2200)
    run.add_argument('--user', required=True, help='BioShare username (an email address)')
    run.add_argument('--key', required=True, help='private key matching an uploaded SSHKey')
    run.add_argument('--share', required=True, help='share slug or id to transfer into')
    run.add_argument('--remote-dir', default='/benchmark',
                     help='path within the share for scratch data (default: /benchmark)')
    run.add_argument('--label', required=True, help='e.g. before / after')
    run.add_argument('--results', required=True, help='JSON file to write')
    run.add_argument('--corpus', choices=[BIG, MANY], help='default: both')
    run.add_argument('--direction', choices=[UP, DOWN], help='default: both')
    run.add_argument('--transfers', type=int, default=4,
                     help='rclone --transfers, i.e. concurrent sessions (default: 4)')
    run.add_argument('--repeat', type=int, default=1, help='attempts per download')
    run.add_argument('--notes', default='', help='recorded verbatim in the results file')
    run.add_argument('-v', '--verbose', action='store_true', help='pass -vv to rclone')
    run.add_argument('--dry-run', action='store_true', help='print commands, transfer nothing')

    cmp_ = sub.add_parser('compare', help='compare two or more result files')
    cmp_.add_argument('results', nargs='+')

    args = parser.parse_args()
    if args.command == 'build':
        build_corpus(args.corpus_dir, args.big_gb, args.small_count, args.small_bytes)
    elif args.command == 'run':
        run_matrix(args)
    else:
        if len(args.results) < 2:
            die('compare needs at least two result files')
        compare(args.results)


if __name__ == '__main__':
    main()
