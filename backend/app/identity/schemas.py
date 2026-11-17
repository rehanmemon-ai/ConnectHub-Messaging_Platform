import unicodedata
import uuid
from datetime import datetime
from typing import Self

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def normalize_identifier(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def normalize_display_text(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterRequest(StrictModel):
    username: str
    email: str
    password: str = Field(min_length=12, max_length=128)
    display_name: str

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str) -> str:
        normalized = normalize_identifier(value)
        if not 1 <= len(normalized) <= 50 or any(char.isspace() for char in normalized):
            raise ValueError("Username must be 1-50 characters without whitespace.")
        return normalized

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        try:
            result = validate_email(
                value,
                check_deliverability=False,
                test_environment=True,
            )
        except EmailNotValidError as error:
            raise ValueError("Enter a valid email address.") from error
        return result.normalized.casefold()

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = normalize_display_text(value)
        if not 1 <= len(normalized) <= 100:
            raise ValueError("Display name must be 1-100 characters.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Password contains an invalid character.")
        return value


class LoginRequest(StrictModel):
    identifier: str
    password: str = Field(min_length=1, max_length=128)

    @field_validator("identifier")
    @classmethod
    def validate_identifier(cls, value: str) -> str:
        normalized = normalize_identifier(value)
        if not 1 <= len(normalized) <= 320:
            raise ValueError("Identifier is invalid.")
        return normalized


class ProfileUpdateRequest(StrictModel):
    username: str | None = None
    display_name: str | None = None

    @field_validator("username")
    @classmethod
    def validate_username(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return RegisterRequest.validate_username(value)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return RegisterRequest.validate_display_name(value)

    @model_validator(mode="after")
    def require_change(self) -> Self:
        if self.username is None and self.display_name is None:
            raise ValueError("At least one profile field must be supplied.")
        return self


class PublicUser(StrictModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: uuid.UUID
    username: str
    display_name: str
    created_at: datetime


class OwnUser(PublicUser):
    email: str
    updated_at: datetime


class OwnUserEnvelope(StrictModel):
    user: OwnUser
