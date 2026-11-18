import os
import pytest

pytestmark = pytest.mark.skipif(
    not (os.getenv("SUPABASE_TEST_URL") and os.getenv("SUPABASE_TEST_SECRET_KEY")),
    reason="Explicit isolated Supabase test credentials are required",
)


def test_integration_credentials_are_explicit_and_separate():
    assert os.environ["SUPABASE_TEST_URL"]
    assert os.environ["SUPABASE_TEST_SECRET_KEY"]
    assert os.environ["SUPABASE_TEST_URL"] != os.getenv("SUPABASE_URL")
