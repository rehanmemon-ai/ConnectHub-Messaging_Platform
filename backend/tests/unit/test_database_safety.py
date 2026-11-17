import pytest

from app.db.safety import validate_test_database_url


def test_test_database_guard_accepts_explicit_test_database() -> None:
    value = "postgresql+psycopg://user:secret@localhost/connecthub_test"
    assert validate_test_database_url(value) == value


@pytest.mark.parametrize(
    "url",
    [
        "sqlite:///connecthub_test.db",
        "postgresql+psycopg://user:secret@localhost/connecthub",
    ],
)
def test_test_database_guard_rejects_unsafe_targets(url: str) -> None:
    with pytest.raises(ValueError):
        validate_test_database_url(url)


def test_test_database_guard_rejects_application_database() -> None:
    value = "postgresql+psycopg://user:secret@localhost/connecthub_test"
    with pytest.raises(ValueError):
        validate_test_database_url(value, value)
