import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_reject_non_postgresql_database() -> None:
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///unsafe.db")


def test_settings_reject_wildcard_origin() -> None:
    with pytest.raises(ValidationError):
        Settings(allowed_origins=["*"])
