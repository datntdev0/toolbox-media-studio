
import datetime
import hashlib
import secrets
from logging import Logger
from uuid import uuid4

from app.core.exceptions import InvalidCredentialsError
from app.core.logging import LogManager
from app.core.config.app_config import AppConfig
from app.core.security.jwt_helper import create_access_token
from app.repositories.user_repository import UserRepository
from app.domain.users import User, UserRole, UserStatus

def hash_password(plain: str) -> str:
    """Return the SHA-256 digest for the supplied password."""

    return hashlib.sha256(plain.encode("utf-8")).hexdigest()


def verify_password(plain: str, expected_hash: str) -> bool:
    """Constant-time comparison of a plaintext password against its expected SHA-256 digest."""

    return secrets.compare_digest(hash_password(plain), expected_hash)


def authenticate(email: str, password: str, user_repository: UserRepository) -> str:
    """Validate credentials against the user store and return a signed JWT."""

    user = user_repository.get_by_email(email)

    if user is None or user.status != UserStatus.ACTIVE:
        raise InvalidCredentialsError
    if not verify_password(password, user.password_hash):
        raise InvalidCredentialsError

    return create_access_token(
        subject=user.id,
        email=user.email,
        role=user.role.value,
    )

def seed_admin_user(logger: Logger, config: AppConfig, repository: UserRepository):
    """Seed an admin user into the user store if it doesn't already exist."""

    email = config.security.default_admin_email
    password = config.security.default_admin_password
    if email is None or password is None:
        logger.warn("Admin user seeding skipped: default admin email or password not set in configuration.")
        return
    
    existing_user = repository.get_by_email(email)
    if existing_user is not None:
        return  # Admin user already exists
    
    now = datetime.datetime.now(datetime.timezone.utc)
    normalized_email = email.lower()
    
    seed_user = User(
        id=str(uuid4()),
        email=normalized_email,
        normalized_email=normalized_email,
        password_hash=hash_password(password),
        display_name="Admin",
        role=UserRole.ADMIN,
        status=UserStatus.ACTIVE,
        created_by="SEED_ACTOR",
        created_at=now,
        updated_by="SEED_ACTOR",
        updated_at=now,
    )

    repository.create(seed_user)