"""Static file storage for deploys that serve /static/ with long cache lifetimes.

collectstatic renames every asset to ``name.<12-hex-content-hash>.ext`` and records
the mapping in ``static/staticfiles.json``, so ``{% static %}`` emits a URL that
changes whenever the bytes change. That is what makes the one-year immutable
Cache-Control in apache_example.conf safe.

The frontend is hand-authored ES modules with no bundler, so the entry points named
in the templates are only the tip of the graph: js/app/main.js imports
'/static/js/app/state.js', which imports '/static/lib/vue/vue.esm-browser.prod.js',
and so on. A stock ManifestStaticFilesStorage hashes the *filenames* but leaves
those in-file specifiers pointing at the unhashed, indefinitely-cacheable copies,
which would defeat the entire exercise. Django ships the regexes that rewrite them
(HashedFilesMixin._js_module_import_aggregation_patterns) but leaves them off by
default; support_js_module_import_aggregation turns them on.

Those regexes only rewrite specifiers beginning with '/' or '.'. That is
load-bearing here: 'vue' and 'reka-ui' are bare specifiers resolved by the importmap
in templates/base.html, and rewriting them would send url_converter looking for a
file named js/app/components/vue and abort collectstatic. The importmap's own values
go through {% static %}, so they get hashed the normal way -- and to the same string
the rewriter produces for the modules that import lib/vue by absolute path, so the
browser still sees one Vue instance.

Note for future readers: because the clause group is non-greedy and skips over bare
specifiers, a single match can span several statements. In
components/ConfirmDialog.vue.js the match covers the 'vue' import, the multi-line
'reka-ui' import, and the '/static/js/app/state.js' import that follows them. This
is lossless -- the replacement template re-emits the captured clause verbatim and
only the final specifier changes -- but it is surprising if you step through it, so
don't "fix" the regex.
"""

from django.contrib.staticfiles.storage import ManifestStaticFilesStorage


class ESMManifestStaticFilesStorage(ManifestStaticFilesStorage):
    # Rewrite ES module specifiers, not just CSS url()/@import and
    # //# sourceMappingURL=. Off by default in Django. There is no bundler here,
    # so without it only the entry points named in the templates would be
    # cache-busted and every module they pull in would stay stale.
    support_js_module_import_aggregation = True

    # Each pass propagates hashed names up one level of the import graph. The
    # deepest chain today is pages/*.js -> components/DataTable.vue.js -> api.js
    # -> state.js -> lib/vue/vue.esm-browser.prod.js, which sits right at the
    # default of 5. Passes stop as soon as a pass substitutes nothing, so raising
    # the ceiling costs nothing on a shallow graph and buys headroom for one more
    # layer of components without a confusing "Max post-process passes exceeded".
    max_post_process_passes = 10

    # Known cost, in case collectstatic ever feels slow: Django applies the *.js
    # rules to every collected JS file, including lib/reka-ui/reka-ui.bundle.esm.js
    # -- 721 KiB on one line with ~477 literal "import" tokens and ~476 bare
    # `from"vue"`. Because the url group demands a leading '/' or '.', the engine
    # backtracks each of those to end of file: measured at ~3.2 s per pass, and it
    # is rescanned every pass for zero rewrites, so roughly 20 s of a deploy.
    # If that ever matters, leave the flag off and register
    # _js_module_import_aggregation_patterns[1] under a narrower "js/app/*.js" glob
    # instead (fnmatch's * crosses /, so that still covers components/ and pages/).
    # Not done here because it couples us to a private Django attribute to save
    # 20 s on a once-per-deploy command.
