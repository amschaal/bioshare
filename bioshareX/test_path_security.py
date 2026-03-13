"""
Path security tests for bioshareX.

Verifies that no data can be read or written outside permitted share
directories or settings-level whitelisted directories, and that malicious
characters in filenames and paths are rejected.

Run with:  python manage.py test bioshareX.test_path_security
"""

import json
import os
import shutil
import tempfile

from django.conf import settings
from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from bioshareX.exceptions import IllegalPathException
from bioshareX.file_views import clean_filename, handle_uploaded_file
from bioshareX.forms import FolderForm, RenameForm
from bioshareX.models import Filesystem, Share
from bioshareX.utils import (
    check_symlinks_dfs,
    is_realpath,
    path_contains,
    paths_contain,
    search_illegal_symlinks,
    test_path,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _TempDirMixin:
    """Sets up a temporary directory and restores DIRECTORY_WHITELIST/
    LINK_TO_DIRECTORIES after each test."""

    def setUp(self):
        super().setUp()
        self.allowed_dir = tempfile.mkdtemp()
        self.outside_dir = tempfile.mkdtemp()
        self._old_whitelist = getattr(settings, 'DIRECTORY_WHITELIST', [])
        self._old_link_dirs = getattr(settings, 'LINK_TO_DIRECTORIES', [])
        settings.DIRECTORY_WHITELIST = [self.allowed_dir]
        settings.LINK_TO_DIRECTORIES = [self.allowed_dir]

    def tearDown(self):
        super().tearDown()
        settings.DIRECTORY_WHITELIST = self._old_whitelist
        settings.LINK_TO_DIRECTORIES = self._old_link_dirs
        shutil.rmtree(self.allowed_dir, ignore_errors=True)
        shutil.rmtree(self.outside_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# 1. test_path() — core path validation utility
# ---------------------------------------------------------------------------

class TestTestPathFunction(SimpleTestCase):
    """Unit tests for bioshareX.utils.test_path()."""

    # -- valid paths ---------------------------------------------------------

    def test_simple_filename_is_valid(self):
        test_path("file.txt")

    def test_nested_path_is_valid(self):
        test_path("a/b/c")

    def test_path_with_hyphen_and_underscore(self):
        test_path("my_folder/my-file.txt")

    def test_empty_string_is_valid(self):
        # Empty subdir/subpath is a common legitimate value
        test_path("")

    def test_single_dot_component_is_valid(self):
        # '.' is filtered out in component check, not illegal
        test_path("./file.txt")

    def test_hidden_file_is_valid(self):
        # A single leading dot is not '..'
        test_path(".hidden_file")

    def test_absolute_path_when_explicitly_allowed(self):
        test_path("/some/absolute/path", allow_absolute=True)

    # -- directory traversal -------------------------------------------------

    def test_dotdot_alone_raises(self):
        with self.assertRaises(Exception):
            test_path("..")

    def test_dotdot_at_start_raises(self):
        with self.assertRaises(Exception):
            test_path("../etc/passwd")

    def test_dotdot_in_middle_raises(self):
        with self.assertRaises(Exception):
            test_path("subdir/../escape")

    def test_dotdot_at_end_raises(self):
        with self.assertRaises(Exception):
            test_path("subdir/..")

    def test_multiple_dotdot_raises(self):
        with self.assertRaises(Exception):
            test_path("../../etc/shadow")

    def test_dotdot_as_substring_raises(self):
        # "file..name" contains '..' so it should be caught
        with self.assertRaises(Exception):
            test_path("file..name")

    def test_encoded_traversal_substring_raises(self):
        # Pathological: many dots that contain '..'
        with self.assertRaises(Exception):
            test_path("...../sneaky")

    # -- absolute paths ------------------------------------------------------

    def test_absolute_path_raises_by_default(self):
        with self.assertRaises(Exception):
            test_path("/etc/passwd")

    def test_absolute_path_to_root_raises(self):
        with self.assertRaises(Exception):
            test_path("/")

    # -- tilde expansion prevention ------------------------------------------

    def test_tilde_home_shortcut_raises(self):
        with self.assertRaises(Exception):
            test_path("~/.ssh/id_rsa")

    def test_tilde_user_raises(self):
        with self.assertRaises(Exception):
            test_path("~root/secret")

    # -- null bytes ----------------------------------------------------------

    def test_null_byte_in_filename_raises(self):
        with self.assertRaises(Exception):
            test_path("file\x00.txt")

    def test_null_byte_in_path_raises(self):
        with self.assertRaises(Exception):
            test_path("sub\x00dir/file")

    def test_null_byte_at_start_raises(self):
        with self.assertRaises(Exception):
            test_path("\x00evil")

    # -- wildcard injection --------------------------------------------------

    def test_wildcard_alone_raises(self):
        with self.assertRaises(Exception):
            test_path("*")

    def test_wildcard_in_filename_raises(self):
        with self.assertRaises(Exception):
            test_path("file*.txt")

    def test_wildcard_glob_pattern_raises(self):
        with self.assertRaises(Exception):
            test_path("subdir/*")

    def test_wildcard_in_middle_raises(self):
        with self.assertRaises(Exception):
            test_path("sub*/dir")

    # -- combined attacks ----------------------------------------------------

    def test_null_byte_plus_traversal_raises(self):
        with self.assertRaises(Exception):
            test_path("file\x00/../etc/passwd")

    def test_absolute_plus_traversal_raises(self):
        with self.assertRaises(Exception):
            test_path("/tmp/../etc/passwd")


# ---------------------------------------------------------------------------
# 2. path_contains() and paths_contain() — whitelist enforcement
# ---------------------------------------------------------------------------

class TestPathContainment(_TempDirMixin, SimpleTestCase):
    """Tests for path_contains() and paths_contain()."""

    def setUp(self):
        super().setUp()
        self.child_dir = os.path.join(self.allowed_dir, "child")
        os.makedirs(self.child_dir)
        self.nested_dir = os.path.join(self.child_dir, "nested")
        os.makedirs(self.nested_dir)

    # -- path_contains -------------------------------------------------------

    def test_child_inside_parent_is_true(self):
        self.assertTrue(path_contains(self.allowed_dir, self.child_dir))

    def test_deeply_nested_child_is_true(self):
        self.assertTrue(path_contains(self.allowed_dir, self.nested_dir))

    def test_same_path_is_true(self):
        self.assertTrue(path_contains(self.allowed_dir, self.allowed_dir))

    def test_outside_dir_is_false(self):
        self.assertFalse(path_contains(self.allowed_dir, self.outside_dir))

    def test_path_starting_with_parent_name_but_different_is_false(self):
        # /data/share should NOT contain /data/shareX (prefix spoofing)
        sibling = self.allowed_dir + "_sibling"
        os.makedirs(sibling)
        try:
            self.assertFalse(path_contains(self.allowed_dir, sibling))
        finally:
            shutil.rmtree(sibling, ignore_errors=True)

    def test_traversal_path_resolves_outside(self):
        # A raw string with '..' that exits the allowed dir must fail
        traversal = os.path.join(self.child_dir, "..", "..", "etc")
        self.assertFalse(path_contains(self.allowed_dir, traversal))

    def test_symlink_escaping_parent_is_false(self):
        # A symlink inside allowed_dir pointing outside should NOT be
        # considered inside when real_path=True (the default)
        link = os.path.join(self.allowed_dir, "escape_link")
        os.symlink(self.outside_dir, link)
        # The symlink itself lives inside allowed_dir, but its resolved
        # realpath is outside — path_contains with real_path=True uses realpath
        self.assertFalse(path_contains(self.allowed_dir, link))

    # -- paths_contain -------------------------------------------------------

    def test_paths_contain_match_in_list(self):
        whitelist = [self.allowed_dir, self.outside_dir]
        self.assertTrue(paths_contain(whitelist, self.child_dir))

    def test_paths_contain_no_match(self):
        third = tempfile.mkdtemp()
        try:
            self.assertFalse(paths_contain([self.allowed_dir], third))
        finally:
            shutil.rmtree(third, ignore_errors=True)

    def test_paths_contain_empty_whitelist(self):
        self.assertFalse(paths_contain([], self.child_dir))

    def test_paths_contain_returns_matching_path(self):
        result = paths_contain([self.allowed_dir], self.child_dir, get_path=True)
        self.assertEqual(result, self.allowed_dir)

    def test_outside_dir_not_in_whitelist(self):
        self.assertFalse(paths_contain([self.allowed_dir], self.outside_dir))


# ---------------------------------------------------------------------------
# 3. is_realpath() — symlink detection
# ---------------------------------------------------------------------------

class TestIsRealpath(_TempDirMixin, SimpleTestCase):
    """Tests for is_realpath()."""

    def setUp(self):
        super().setUp()
        self.real_subdir = os.path.join(self.allowed_dir, "real")
        os.makedirs(self.real_subdir)
        self.symlink = os.path.join(self.allowed_dir, "symlink")
        os.symlink(self.outside_dir, self.symlink)

    def test_real_directory_is_true(self):
        self.assertTrue(is_realpath(self.real_subdir))

    def test_real_base_dir_is_true(self):
        self.assertTrue(is_realpath(self.allowed_dir))

    def test_symlinked_dir_is_false(self):
        self.assertFalse(is_realpath(self.symlink))

    def test_path_through_symlink_is_false(self):
        deep = os.path.join(self.symlink, "deeper")
        self.assertFalse(is_realpath(deep))

    def test_real_subpath_is_true(self):
        self.assertTrue(is_realpath(self.allowed_dir, "real"))

    def test_symlinked_subpath_is_false(self):
        self.assertFalse(is_realpath(self.allowed_dir, "symlink"))


# ---------------------------------------------------------------------------
# 4. clean_filename() — upload filename sanitisation
# ---------------------------------------------------------------------------

class TestCleanFilename(SimpleTestCase):
    """Tests for file_views.clean_filename()."""

    def test_simple_filename_ok(self):
        self.assertEqual(clean_filename("report.txt"), "report.txt")

    def test_filename_with_spaces_ok(self):
        # Spaces are converted to underscores by the UNDERSCORE_REGEX substitution
        result = clean_filename("my file.txt")
        self.assertNotIn("/", result)
        self.assertNotIn("\x00", result)

    def test_forward_slash_is_stripped(self):
        # STRIP_REGEX removes '/' before the basename check runs, so no
        # exception is raised — but the result must contain no path separator.
        result = clean_filename("dir/file.txt")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)
        self.assertNotIn("\x00", result)

    def test_backslash_is_stripped(self):
        result = clean_filename("dir\\file.txt")
        self.assertNotIn("\\", result)
        self.assertNotIn("/", result)

    def test_null_byte_is_stripped(self):
        result = clean_filename("file\x00.txt")
        self.assertNotIn("\x00", result)

    def test_slash_in_path_component_removed(self):
        result = clean_filename("subdir/evil.txt")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)
        self.assertNotIn("\x00", result)

    def test_dotdot_slash_has_separator_stripped(self):
        # '../escape.txt' — the '/' is stripped, leaving a safe flat filename.
        result = clean_filename("../escape.txt")
        self.assertNotIn("/", result)
        self.assertNotIn("\\", result)


# ---------------------------------------------------------------------------
# 5. handle_uploaded_file() — upload blocked through symlinks
# ---------------------------------------------------------------------------

class TestHandleUploadedFile(_TempDirMixin, SimpleTestCase):
    """Tests that file upload is blocked when the target path is a symlink."""

    def setUp(self):
        super().setUp()
        self.real_dir = os.path.join(self.allowed_dir, "uploads")
        os.makedirs(self.real_dir)
        self.symlink_dir = os.path.join(self.allowed_dir, "linked_uploads")
        os.symlink(self.outside_dir, self.symlink_dir)

    class _FakeFile:
        def chunks(self):
            yield b"malicious data"

    def test_upload_to_real_path_succeeds(self):
        dest = os.path.join(self.real_dir, "test_upload.txt")
        handle_uploaded_file(dest, self._FakeFile())
        self.assertTrue(os.path.exists(dest))

    def test_upload_through_symlink_raises(self):
        dest = os.path.join(self.symlink_dir, "escape.txt")
        with self.assertRaises(Exception):
            handle_uploaded_file(dest, self._FakeFile())

    def test_upload_target_is_itself_a_symlink_raises(self):
        # Create a symlink that *is* the file destination
        existing = os.path.join(self.outside_dir, "real.txt")
        open(existing, "w").close()
        link = os.path.join(self.real_dir, "linked.txt")
        os.symlink(existing, link)
        with self.assertRaises(Exception):
            handle_uploaded_file(link, self._FakeFile())


# ---------------------------------------------------------------------------
# 6. FolderForm — folder name validation
# ---------------------------------------------------------------------------

class TestFolderFormValidation(SimpleTestCase):
    """Tests that FolderForm rejects illegal folder names."""

    def _valid(self, name):
        form = FolderForm({"name": name})
        self.assertTrue(form.is_valid(), f"Expected '{name}' to be valid, errors: {form.errors}")

    def _invalid(self, name):
        form = FolderForm({"name": name})
        self.assertFalse(form.is_valid(), f"Expected '{name}' to be invalid")

    def test_simple_name_valid(self):
        self._valid("my_folder")

    def test_name_with_spaces_valid(self):
        self._valid("my folder")

    def test_name_with_hyphen_valid(self):
        self._valid("my-folder")

    def test_name_with_numbers_valid(self):
        self._valid("folder2024")

    def test_empty_name_invalid(self):
        self._invalid("")

    def test_slash_in_name_invalid(self):
        self._invalid("folder/subfolder")

    def test_backslash_in_name_invalid(self):
        self._invalid("folder\\subfolder")

    def test_dotdot_invalid(self):
        self._invalid("..")

    def test_dotdot_in_path_invalid(self):
        self._invalid("../escape")

    def test_null_byte_invalid(self):
        self._invalid("folder\x00")

    def test_semicolon_invalid(self):
        self._invalid("folder;cmd")

    def test_dollar_sign_invalid(self):
        self._invalid("$HOME")

    def test_period_invalid(self):
        # FolderForm regex r'^[\w\d\ \-_]+$' does not allow periods
        self._invalid("folder.name")


# ---------------------------------------------------------------------------
# 7. RenameForm — rename validation
# ---------------------------------------------------------------------------

class TestRenameFormValidation(SimpleTestCase):
    """Tests that RenameForm rejects illegal from_name and to_name values."""

    def _form(self, from_name, to_name):
        return RenameForm({"from_name": from_name, "to_name": to_name})

    def test_valid_rename(self):
        self.assertTrue(self._form("old.txt", "new.txt").is_valid())

    def test_valid_rename_with_spaces(self):
        self.assertTrue(self._form("old file.txt", "new file.txt").is_valid())

    # from_name validation (regex: no forward slash)
    def test_from_name_with_slash_invalid(self):
        self.assertFalse(self._form("dir/file.txt", "new.txt").is_valid())

    # to_name validation (regex: word chars, space, hyphen, underscore, period)
    def test_to_name_with_slash_invalid(self):
        self.assertFalse(self._form("old.txt", "dir/new.txt").is_valid())

    def test_to_name_with_dotdot_invalid(self):
        self.assertFalse(self._form("old.txt", "../escape.txt").is_valid())

    def test_to_name_with_null_byte_invalid(self):
        self.assertFalse(self._form("old.txt", "new\x00.txt").is_valid())

    def test_to_name_with_semicolon_invalid(self):
        self.assertFalse(self._form("old.txt", "file;cmd").is_valid())

    def test_to_name_with_backtick_invalid(self):
        self.assertFalse(self._form("old.txt", "file`cmd`").is_valid())

    def test_to_name_with_dollar_invalid(self):
        self.assertFalse(self._form("old.txt", "$HOME").is_valid())


# ---------------------------------------------------------------------------
# 8. Share model path operations
# ---------------------------------------------------------------------------

class _ShareSetupMixin(_TempDirMixin):
    """Creates a User, Filesystem and Share backed by a real temp directory."""

    def setUp(self):
        super().setUp()
        self.user = User.objects.create_user(
            username="testuser", password="testpass", email="test@example.com"
        )
        # django-guardian requires an anonymous user row to exist when it
        # resolves permissions for unauthenticated requests.  The row is
        # normally created by the post_migrate signal, but not in a fresh
        # test database.
        # The lowercase_user signal lowercases usernames on save, so the
        # anonymous user row is stored in lowercase regardless of ANONYMOUS_USER_NAME.
        anon_name = getattr(settings, 'ANONYMOUS_USER_NAME', 'AnonymousUser').lower()
        User.objects.get_or_create(username=anon_name, defaults={'is_active': False})
        self.filesystem = Filesystem.objects.create(
            name="test_fs",
            description="Test filesystem",
            path=self.allowed_dir,
            type=Filesystem.TYPE_STANDARD,
        )
        self.filesystem.users.add(self.user)
        self.share = Share.objects.create(
            name="Test Share",
            owner=self.user,
            filesystem=self.filesystem,
        )
        # Ensure the share directory exists (may already be created by signal)
        os.makedirs(self.share.get_path(), exist_ok=True)


class TestShareModelPathOps(_ShareSetupMixin, TestCase):
    """Tests for Share.create_folder(), delete_path(), and move_path()."""

    # -- create_folder -------------------------------------------------------

    def test_create_folder_creates_directory(self):
        path = self.share.create_folder("safe_folder")
        self.assertTrue(os.path.isdir(path))

    def test_create_folder_is_inside_share(self):
        path = self.share.create_folder("safe_folder")
        self.assertTrue(path.startswith(self.share.get_path()))

    def test_create_folder_in_subdir(self):
        subdir = "level1"
        os.makedirs(os.path.join(self.share.get_path(), subdir))
        path = self.share.create_folder("level2", subdir)
        self.assertTrue(os.path.isdir(path))
        self.assertIn(subdir, path)

    def test_create_folder_duplicate_raises(self):
        self.share.create_folder("dup_folder")
        with self.assertRaises(Exception):
            self.share.create_folder("dup_folder")

    # -- delete_path ---------------------------------------------------------

    def test_delete_file_works(self):
        fp = os.path.join(self.share.get_path(), "todelete.txt")
        open(fp, "w").close()
        result = self.share.delete_path("todelete.txt")
        self.assertTrue(result)
        self.assertFalse(os.path.exists(fp))

    def test_delete_directory_works(self):
        dp = os.path.join(self.share.get_path(), "todelete_dir")
        os.makedirs(dp)
        result = self.share.delete_path("todelete_dir")
        self.assertTrue(result)
        self.assertFalse(os.path.exists(dp))

    def test_delete_path_none_returns_false(self):
        self.assertFalse(self.share.delete_path(None))

    def test_delete_path_empty_string_returns_false(self):
        self.assertFalse(self.share.delete_path(""))

    def test_delete_dotdot_returns_false(self):
        self.assertFalse(self.share.delete_path(".."))

    def test_delete_traversal_returns_false(self):
        # Any subpath containing '..' is blocked inside delete_path
        self.assertFalse(self.share.delete_path("../outside_file"))

    def test_delete_nested_traversal_returns_false(self):
        self.assertFalse(self.share.delete_path("subdir/../../outside"))

    # -- move_path -----------------------------------------------------------

    def test_move_file_to_valid_destination(self):
        src = os.path.join(self.share.get_path(), "moveme.txt")
        open(src, "w").close()
        dest_dir = os.path.join(self.share.get_path(), "dest")
        os.makedirs(dest_dir)
        result = self.share.move_path("moveme.txt", "dest")
        self.assertTrue(result)
        self.assertTrue(os.path.exists(os.path.join(dest_dir, "moveme.txt")))

    def test_move_dotdot_destination_returns_false(self):
        src = os.path.join(self.share.get_path(), "moveme.txt")
        open(src, "w").close()
        result = self.share.move_path("moveme.txt", "../outside")
        self.assertFalse(result)
        self.assertTrue(os.path.exists(src))

    def test_move_to_symlinked_destination_returns_false(self):
        src = os.path.join(self.share.get_path(), "moveme.txt")
        open(src, "w").close()
        link_dest = os.path.join(self.share.get_path(), "linked_dest")
        os.symlink(self.outside_dir, link_dest)
        result = self.share.move_path("moveme.txt", "linked_dest")
        self.assertFalse(result)
        self.assertTrue(os.path.exists(src))

    def test_move_to_nonexistent_destination_returns_false(self):
        src = os.path.join(self.share.get_path(), "moveme.txt")
        open(src, "w").close()
        result = self.share.move_path("moveme.txt", "nonexistent_dest")
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# 9. Symlink validation utilities
# ---------------------------------------------------------------------------

class TestSymlinkValidationUtils(_TempDirMixin, SimpleTestCase):
    """Tests for check_symlinks_dfs() and search_illegal_symlinks()."""

    def test_no_symlinks_passes(self):
        target = os.path.join(self.allowed_dir, "plain_dir")
        os.makedirs(target)
        # Should complete without raising
        check_symlinks_dfs(target)

    def test_symlink_to_allowed_dir_passes(self):
        target = os.path.join(self.allowed_dir, "target_dir")
        os.makedirs(target)
        link = os.path.join(self.allowed_dir, "safe_link")
        os.symlink(target, link)
        # Symlink stays within whitelist — should not raise
        check_symlinks_dfs(target)

    def test_symlink_to_outside_whitelist_raises(self):
        target = os.path.join(self.allowed_dir, "dir_with_bad_link")
        os.makedirs(target)
        bad_link = os.path.join(target, "escape")
        os.symlink(self.outside_dir, bad_link)
        with self.assertRaises(IllegalPathException):
            check_symlinks_dfs(target)

    def test_search_illegal_symlinks_raises_on_escape(self):
        target = os.path.join(self.allowed_dir, "container")
        os.makedirs(target)
        bad_link = os.path.join(target, "bad")
        os.symlink(self.outside_dir, bad_link)
        with self.assertRaises(IllegalPathException):
            search_illegal_symlinks(target)

    def test_search_illegal_symlinks_passes_for_internal_link(self):
        inner = os.path.join(self.allowed_dir, "inner")
        os.makedirs(inner)
        container = os.path.join(self.allowed_dir, "container")
        os.makedirs(container)
        link = os.path.join(container, "ok_link")
        os.symlink(inner, link)
        # inner is within allowed_dir so no exception expected
        search_illegal_symlinks(container)

    def test_circular_symlink_raises(self):
        dir_a = os.path.join(self.allowed_dir, "dir_a")
        os.makedirs(dir_a)
        link_to_a = os.path.join(dir_a, "link_back_to_a")
        os.symlink(dir_a, link_to_a)
        with self.assertRaises(Exception):
            check_symlinks_dfs(dir_a)


# ---------------------------------------------------------------------------
# 10. View-level path security (HTTP integration)
# ---------------------------------------------------------------------------

class TestViewPathSecurity(_ShareSetupMixin, TestCase):
    """
    Integration tests for view endpoints that accept user-supplied paths.
    Verifies that traversal attempts and out-of-whitelist paths are blocked.
    """

    def setUp(self):
        super().setUp()
        # Create a safe subdirectory within the share
        self.safe_subdir = os.path.join(self.share.get_path(), "safe_subdir")
        os.makedirs(self.safe_subdir, exist_ok=True)
        self.client.login(username="testuser", password="testpass")

    # -- get_directories -----------------------------------------------------

    def test_get_directories_valid_path_returns_200(self):
        url = reverse("get_directories", kwargs={"share": self.share.id})
        response = self.client.get(url, {"directory": "safe_subdir"})
        self.assertEqual(response.status_code, 200)

    def test_get_directories_empty_directory_returns_200(self):
        url = reverse("get_directories", kwargs={"share": self.share.id})
        response = self.client.get(url, {"directory": ""})
        self.assertEqual(response.status_code, 200)

    def test_get_directories_traversal_is_blocked(self):
        # test_path() raises an exception for '..' — assertRaises confirms
        # the validation fires regardless of how the HTTP layer handles it.
        url = reverse("get_directories", kwargs={"share": self.share.id})
        with self.assertRaises(Exception):
            self.client.get(url, {"directory": "../../../../etc"})

    def test_get_directories_dotdot_alone_is_blocked(self):
        url = reverse("get_directories", kwargs={"share": self.share.id})
        with self.assertRaises(Exception):
            self.client.get(url, {"directory": ".."})

    def test_get_directories_outside_whitelist_is_blocked(self):
        url = reverse("get_directories", kwargs={"share": self.share.id})
        with self.assertRaises(Exception):
            self.client.get(url, {"directory": "safe_subdir/../../../.."})

    def test_get_directories_requires_login(self):
        self.client.logout()
        url = reverse("get_directories", kwargs={"share": self.share.id})
        # Use the instance attribute (not a per-request kwarg) so exceptions
        # from guardian are suppressed and we get an HTTP response instead.
        self.client.raise_request_exception = False
        try:
            response = self.client.get(url)
            # Unauthenticated request must not return 200
            self.assertNotEqual(response.status_code, 200)
        finally:
            self.client.raise_request_exception = True

    # -- move_paths ----------------------------------------------------------

    def _post_move(self, selection, destination, subdir=None):
        if subdir:
            url = reverse("move_paths", kwargs={"share": self.share.id, "subdir": subdir + "/"})
        else:
            url = reverse("move_paths", kwargs={"share": self.share.id})
        payload = json.dumps({"json": {"selection": selection, "destination": destination}})
        return self.client.post(url, payload, content_type="application/json")

    def test_move_to_valid_destination_succeeds(self):
        src = os.path.join(self.share.get_path(), "movable.txt")
        open(src, "w").close()
        dest = os.path.join(self.share.get_path(), "dest_dir")
        os.makedirs(dest, exist_ok=True)
        response = self._post_move(["movable.txt"], "dest_dir")
        self.assertEqual(response.status_code, 200)

    def test_move_dotdot_destination_is_blocked(self):
        # test_path() raises when destination contains '..'
        with self.assertRaises(Exception):
            self._post_move(["movable2.txt"], "../outside")

    def test_move_null_byte_in_destination_is_blocked(self):
        with self.assertRaises(Exception):
            self._post_move(["movable3.txt"], "dest\x00dir")

    def test_move_wildcard_in_destination_is_blocked(self):
        with self.assertRaises(Exception):
            self._post_move(["movable4.txt"], "dest*dir")

    def test_move_dotdot_in_selection_item_is_blocked(self):
        with self.assertRaises(Exception):
            self._post_move(["../outside.txt"], "safe_subdir")

    # -- upload_file ---------------------------------------------------------

    def test_upload_to_valid_subdir_succeeds(self):
        from io import BytesIO
        url = reverse("upload_file", kwargs={"share": self.share.id, "subdir": "safe_subdir/"})
        f = BytesIO(b"hello world")
        f.name = "test_upload.txt"
        response = self.client.post(url, {"file": f})
        self.assertEqual(response.status_code, 200)

    def test_upload_to_symlinked_subdir_is_blocked(self):
        from io import BytesIO
        # Create a symlinked subdir within the share pointing outside.
        # safe_path_decorator(write=True) calls is_realpath() and returns a
        # JSON error response (no exception), so we check the status code.
        link = os.path.join(self.share.get_path(), "linked_upload")
        os.symlink(self.outside_dir, link)
        url = reverse("upload_file", kwargs={"share": self.share.id, "subdir": "linked_upload/"})
        f = BytesIO(b"evil data")
        f.name = "evil.txt"
        response = self.client.post(url, {"file": f})
        self.assertNotEqual(response.status_code, 200)

    def test_upload_with_traversal_subdir_is_blocked(self):
        # safe_path_decorator calls test_path() on the subdir kwarg, which
        # raises an exception for paths containing '..'.
        url = reverse("upload_file", kwargs={"share": self.share.id, "subdir": "../../outside/"})
        with self.assertRaises(Exception):
            self.client.post(url, {})
