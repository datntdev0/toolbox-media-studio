"""Inbound request bodies."""

from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, model_validator

from app.domain.novels import Novel, NovelStatus
from app.domain.translations import Translation, TranslationConfiguration, TranslationStatus
from app.domain.users import User, UserRole, UserStatus

NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class LoginRequest(BaseModel):
    """Credentials submitted to POST /auth/login."""

    email: EmailStr
    password: str


class UserCreateRequest(BaseModel):
    """Payload for creating a user."""

    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr
    password: str
    display_name: str | None = Field(default=None, alias="displayName")
    role: UserRole = UserRole.MEMBER
    status: UserStatus = UserStatus.ACTIVE


class UserUpdateRequest(BaseModel):
    """Payload for partially updating a user."""

    model_config = ConfigDict(populate_by_name=True)

    password: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")
    role: UserRole | None = None
    status: UserStatus | None = None
    etag: str | None = None


class NovelCreateRequest(BaseModel):
    """Payload for creating a novel."""

    model_config = ConfigDict(populate_by_name=True)

    title: str = Field(min_length=1)
    description: str | None = None
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    language: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    notes: str | None = None


class NovelUpdateRequest(BaseModel):
    """Payload for updating a novel while allowing nullable fields to be cleared."""

    model_config = ConfigDict(populate_by_name=True)

    title: str | None = Field(default=None, min_length=1)
    description: str | None = None
    cover_image_url: str | None = Field(default=None, alias="coverImageUrl")
    language: str | None = None
    author: str | None = None
    tags: list[str] | None = None
    notes: str | None = None
    status: NovelStatus | None = None
    etag: str | None = None

    @model_validator(mode="after")
    def validate_required_fields(self) -> "NovelUpdateRequest":
        """Reject null required fields when they are explicitly supplied."""

        invalid_fields = [
            field
            for field in ("title", "status")
            if field in self.model_fields_set and getattr(self, field) is None
        ]
        if invalid_fields:
            fields = ", ".join(invalid_fields)
            raise ValueError(f"Required field(s) cannot be null: {fields}")
        return self


class TranslationConfigurationRequest(BaseModel):
    """AI configuration saved with a translation."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    provider_id: NonBlankStr = Field(alias="providerId")
    model_id: NonBlankStr = Field(alias="modelId")
    global_prompt: NonBlankStr = Field(alias="globalPrompt")


class TranslationCreateRequest(BaseModel):
    """Payload for creating a translation."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: NonBlankStr
    novel_id: NonBlankStr = Field(alias="novelId")
    target_language: NonBlankStr = Field(alias="targetLanguage")


class TranslationUpdateRequest(BaseModel):
    """Editable translation values."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    name: NonBlankStr
    novel_id: NonBlankStr = Field(alias="novelId")
    target_language: NonBlankStr = Field(alias="targetLanguage")
    configuration: TranslationConfigurationRequest | None
    etag: str | None = None


def to_user_entity(body: UserCreateRequest) -> User:
    """Convert a UserCreateRequest to a User entity."""

    now = datetime.now(UTC)
    normalized_email = body.email.lower()
    return User(
        id=str(uuid4()),
        email=normalized_email,
        normalized_email=normalized_email,
        password_hash="",
        display_name=body.display_name,
        role=body.role,
        status=body.status,
        created_by="",
        created_at=now,
        updated_by="",
        updated_at=now,
    )


def to_novel_entity(body: NovelCreateRequest, created_by: str) -> Novel:
    """Convert a NovelCreateRequest to a Novel entity."""

    now = datetime.now(UTC)
    return Novel(
        id=str(uuid4()),
        title=body.title,
        description=body.description,
        cover_image_url=body.cover_image_url,
        language=body.language,
        author=body.author,
        tags=list(body.tags or []),
        notes=body.notes,
        status=NovelStatus.DRAFT,
        created_by=created_by,
        created_at=now,
        updated_by=created_by,
        updated_at=now,
    )


def to_translation_entity(
    body: TranslationCreateRequest,
    created_by: str,
) -> Translation:
    """Convert a TranslationCreateRequest to a Translation entity."""

    now = datetime.now(UTC)
    return Translation(
        id=str(uuid4()),
        name=body.name.strip(),
        novel_id=body.novel_id,
        target_language=body.target_language.strip(),
        configuration=None,
        status=TranslationStatus.NEEDS_SETUP,
        created_by=created_by,
        created_at=now,
        updated_by=created_by,
        updated_at=now,
    )


def to_translation_configuration(
    body: TranslationConfigurationRequest | None,
) -> TranslationConfiguration | None:
    """Convert an optional configuration request to its domain representation."""

    if body is None:
        return None
    return TranslationConfiguration(
        provider_id=body.provider_id.strip(),
        model_id=body.model_id.strip(),
        global_prompt=body.global_prompt.strip(),
    )
