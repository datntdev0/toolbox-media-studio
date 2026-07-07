"""User repository contracts and in-memory implementation."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Protocol

from app.domain.users import User, UserPage, UserStatus


class UserRepository(Protocol):
    """Persistence contract for user records."""

    def create(self, user: User) -> User: ...

    def get_by_id(self, id: str) -> User | None: ...

    def get_by_email(self, email: str) -> User | None: ...

    def list(self, limit: int, continuation_token: str | None) -> UserPage: ...

    def update(self, user: User, etag: str | None) -> User: ...

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None: ...

    def seed_admin(self, user: User) -> User | None: ...


class UserAlreadyExistsError(Exception):
    """Raised when a unique user identity already exists."""


class UserNotFoundError(Exception):
    """Raised when a user cannot be found."""


class UserConflictError(Exception):
    """Raised when optimistic concurrency validation fails."""


class InMemoryUserRepository:
    """Simple repository used for tests."""

    def __init__(self) -> None:
        self._users: dict[str, User] = {}

    def create(self, user: User) -> User:
        if any(
            existing.normalized_email == user.normalized_email
            for existing in self._users.values()
        ):
            raise UserAlreadyExistsError

        stored = deepcopy(user)
        stored.etag = self._next_etag()
        self._users[stored.id] = stored
        return deepcopy(stored)

    def get_by_id(self, id: str) -> User | None:
        user = self._users.get(id)
        if user is None or user.status == UserStatus.DELETED:
            return None
        return deepcopy(user)

    def get_by_email(self, email: str) -> User | None:
        normalized_email = email.strip().lower()
        for user in self._users.values():
            if user.normalized_email == normalized_email and user.status != UserStatus.DELETED:
                return deepcopy(user)
        return None

    def list(self, limit: int, continuation_token: str | None) -> UserPage:
        del continuation_token
        users = [
            deepcopy(user)
            for user in self._users.values()
            if user.status != UserStatus.DELETED
        ]
        users.sort(key=lambda item: item.created_at)
        return UserPage(items=users[:limit], continuation_token=None)

    def update(self, user: User, etag: str | None) -> User:
        current = self._users.get(user.id)
        if current is None or current.status == UserStatus.DELETED:
            raise UserNotFoundError
        if etag is not None and current.etag != etag:
            raise UserConflictError
        if any(
            existing.id != user.id and existing.normalized_email == user.normalized_email
            for existing in self._users.values()
        ):
            raise UserAlreadyExistsError

        stored = deepcopy(user)
        stored.etag = self._next_etag()
        self._users[stored.id] = stored
        return deepcopy(stored)

    def delete(self, id: str, etag: str | None, deleted_by: str) -> None:
        current = self._users.get(id)
        if current is None or current.status == UserStatus.DELETED:
            raise UserNotFoundError
        if etag is not None and current.etag != etag:
            raise UserConflictError

        now = datetime.now(UTC)
        current.status = UserStatus.DELETED
        current.deleted_at = now
        current.deleted_by = deleted_by
        current.updated_at = now
        current.updated_by = deleted_by
        current.etag = self._next_etag()

    def seed_admin(self, user: User) -> User | None:
        if self.get_by_email(user.email) is not None:
            return None
        return self.create(user)

    @staticmethod
    def _next_etag() -> str:
        return datetime.now(UTC).isoformat()
