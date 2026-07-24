"""
bioshareX backend test suite.

The tests are organized by concern:

  test_path_security.py  - path/filename validation, traversal, symlink
                           escapes, whitelist enforcement (unit + HTTP)
  test_api.py            - functional coverage of every API/JSON endpoint
                           and the file-operation views
  test_api_security.py   - authentication, authorization boundaries, share
                           states (secure/read-only/locked), object scoping
                           (IDOR), CSRF, rate limiting
  test_base.py           - shared fixtures (ShareTestBase)

Run everything with:  python manage.py test bioshareX
"""
