"""Run every test against a throw-away database, never the real aquasentry.db that ships with the app.

This file is loaded by pytest before any test module imports app.main, so DATABASE_URL is set in time.
Set AQUASENTRY_TEST_DATABASE_URL to use a different test database.
"""
import os
import tempfile

# The v5.2-v5.6 tests post "hardware" readings from imaginary devices that predate v5.7 scan QC and check
# standards. Production requires both (QC_REQUIRE_FOR_HARDWARE defaults to on); tests/test_v57_safety.py
# switches it back on and checks every rule.
os.environ.setdefault("QC_REQUIRE_FOR_HARDWARE", "0")

_tmp_dir = tempfile.mkdtemp(prefix="aquasentry_tests_")
os.environ["DATABASE_URL"] = os.environ.get(
    "AQUASENTRY_TEST_DATABASE_URL", "sqlite:///" + os.path.join(_tmp_dir, "aquasentry_test.db")
)
