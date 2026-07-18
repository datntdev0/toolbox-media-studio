from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

class UserRole(StrEnum):
    """Supported authorization roles."""

    ADMIN = "admin"
    MEMBER = "member"


class UserStatus(StrEnum):
    """Supported user lifecycle states."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


@dataclass(slots=True)
class User:
    """Persisted user record."""

    id: str
    email: str
    normalized_email: str
    password_hash: str
    display_name: str | None
    role: UserRole
    status: UserStatus
    created_by: str
    created_at: datetime
    updated_by: str
    updated_at: datetime
    deleted_at: datetime | None = None
    deleted_by: str | None = None
    etag: str | None = None


@dataclass(slots=True)
class UserPage:
    """Paged user list result."""

    items: list[User]
    continuation_token: str | None
