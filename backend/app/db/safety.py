from sqlalchemy.engine import make_url


def validate_test_database_url(test_url: str, application_url: str | None = None) -> str:
    """Reject database targets that are not clearly disposable PostgreSQL tests."""
    parsed = make_url(test_url)
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("TEST_DATABASE_URL must use postgresql+psycopg://")
    if not parsed.database or not parsed.database.lower().endswith("_test"):
        raise ValueError("TEST_DATABASE_URL database name must end in '_test'")
    if application_url is not None and make_url(application_url) == parsed:
        raise ValueError("TEST_DATABASE_URL must differ from DATABASE_URL")
    return test_url
