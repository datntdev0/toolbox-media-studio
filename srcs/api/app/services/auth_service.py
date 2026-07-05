"""Authentication use-cases: validate credentials and issue tokens.

No database this iteration — the single valid account is ADMIN_EMAIL / ADMIN_PASSWORD
from settings.
"""

from app.core.config import Settings
from app.core.security import create_access_token, verify_password

ADMIN_ROLE = "admin"


class InvalidCredentialsError(Exception):
    """Raised when login credentials do not match the configured admin."""


def authenticate(email: str, password: str, settings: Settings) -> str:
    """Validate credentials against config and return a signed JWT.

    Raises InvalidCredentialsError if the email or password does not match.
    """
    email_ok = verify_password(email.lower(), settings.admin_email.lower())
    password_ok = verify_password(password, settings.admin_password)
    if not (email_ok and password_ok):
        raise InvalidCredentialsError

    return create_access_token(
        subject=settings.admin_email,
        settings=settings,
        role=ADMIN_ROLE,
    )
