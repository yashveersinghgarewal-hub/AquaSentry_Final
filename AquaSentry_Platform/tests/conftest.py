"""Run every test against a throw-away database, never the real aquasentry.db that ships with the app.

This file is loaded by pytest before any test module imports app.main, so DATABASE_URL is set in time.
Set AQUASENTRY_TEST_DATABASE_URL to use a different test database.
"""
import os
import tempfile

_tmp_dir = tempfile.mkdtemp(prefix="aquasentry_tests_")
os.environ["DATABASE_URL"] = os.environ.get(
    "AQUASENTRY_TEST_DATABASE_URL", "sqlite:///" + os.path.join(_tmp_dir, "aquasentry_test.db")
)
