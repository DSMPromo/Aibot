"""
Security utilities for the AI Marketing Platform.

Implements:
- Password hashing with Argon2id (SEC-016)
- Token encryption with Fernet (SEC-003)
- JWT token generation and validation (SEC-020)
- TOTP/MFA utilities

SECURITY CRITICAL: This module handles sensitive operations.
Any changes require security review.
"""

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

import pyotp
import qrcode
import qrcode.image.svg
from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken
from jose import JWTError, jwt
from pydantic import BaseModel

from app.config import settings


# =============================================================================
# Password Hashing (Argon2id - SEC-016)
# =============================================================================

# Configure Argon2id with secure parameters
# - Type.ID provides best protection against GPU/ASIC attacks
# - Memory cost: 64MB (65536 KiB)
# - Time cost: 3 iterations
# - Parallelism: 4 threads
password_hasher = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
    type=Type.ID,  # Argon2id - hybrid of Argon2i and Argon2d
)


def hash_password(password: str) -> str:
    """
    Hash a password using Argon2id.

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        password: Plain text password to verify
        password_hash: Stored password hash

    Returns:
        True if password matches, False otherwise
    """
    try:
        password_hasher.verify(password_hash, password)
        return True
    except (VerifyMismatchError, InvalidHashError):
        return False


def check_needs_rehash(password_hash: str) -> bool:
    """
    Check if a password hash needs to be rehashed.

    This should be called after successful verification to upgrade
    old hashes to current parameters.

    Args:
        password_hash: Stored password hash

    Returns:
        True if hash should be regenerated
    """
    return password_hasher.check_needs_rehash(password_hash)


# =============================================================================
# Token Encryption (Fernet - SEC-003)
# =============================================================================

def get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    # In production, ENCRYPTION_KEY should be a valid Fernet key
    # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    key = settings.encryption_key
    if key == "change-me-in-production-use-fernet-key":
        # Generate a temporary key for development
        # WARNING: This will change on restart, invalidating encrypted data
        key = Fernet.generate_key().decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(token: str) -> bytes:
    """
    Encrypt a token (OAuth access/refresh tokens) for storage.

    Args:
        token: Plain text token

    Returns:
        Encrypted token bytes
    """
    fernet = get_fernet()
    return fernet.encrypt(token.encode())


def decrypt_token(encrypted_token: bytes) -> Optional[str]:
    """
    Decrypt an encrypted token.

    Args:
        encrypted_token: Encrypted token bytes

    Returns:
        Decrypted token string, or None if decryption fails
    """
    try:
        fernet = get_fernet()
        return fernet.decrypt(encrypted_token).decode()
    except InvalidToken:
        return None


# =============================================================================
# JWT Token Management (SEC-020)
# =============================================================================

class TokenData(BaseModel):
    """Data extracted from a valid JWT token."""
    user_id: str
    org_id: Optional[str] = None
    role: Optional[str] = None
    token_type: str = "access"
    exp: datetime


def create_access_token(
    user_id: str,
    org_id: Optional[str] = None,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        user_id: User identifier
        org_id: Organization identifier
        role: User role
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.jwt_access_token_expire_minutes)

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user_id,
        "org_id": org_id,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(
    user_id: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Create a JWT refresh token.

    Args:
        user_id: User identifier
        expires_delta: Custom expiration time

    Returns:
        Encoded JWT token
    """
    if expires_delta is None:
        expires_delta = timedelta(days=settings.jwt_refresh_token_expire_days)

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user_id,
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": secrets.token_urlsafe(16),  # Unique token ID for revocation
    }

    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def verify_token(token: str, token_type: str = "access") -> Optional[TokenData]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Expected token type ("access" or "refresh")

    Returns:
        TokenData if valid, None otherwise
    """
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )

        # Verify token type
        if payload.get("type") != token_type:
            return None

        return TokenData(
            user_id=payload["sub"],
            org_id=payload.get("org_id"),
            role=payload.get("role"),
            token_type=payload["type"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )

    except JWTError:
        return None


def create_token_pair(
    user_id: str,
    org_id: Optional[str] = None,
    role: Optional[str] = None,
) -> Tuple[str, str]:
    """
    Create both access and refresh tokens.

    Args:
        user_id: User identifier
        org_id: Organization identifier
        role: User role

    Returns:
        Tuple of (access_token, refresh_token)
    """
    access_token = create_access_token(user_id, org_id, role)
    refresh_token = create_refresh_token(user_id)
    return access_token, refresh_token


# =============================================================================
# MFA / TOTP Utilities
# =============================================================================

def generate_totp_secret() -> str:
    """
    Generate a new TOTP secret for MFA setup.

    Returns:
        Base32 encoded secret
    """
    return pyotp.random_base32()


def get_totp_uri(secret: str, email: str, issuer: str = "AI Marketing") -> str:
    """
    Generate the TOTP URI for QR code generation.

    Args:
        secret: TOTP secret
        email: User email
        issuer: Application name

    Returns:
        otpauth:// URI
    """
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=issuer)


def generate_totp_qr_code(secret: str, email: str) -> str:
    """
    Generate a QR code SVG for TOTP setup.

    Args:
        secret: TOTP secret
        email: User email

    Returns:
        SVG string of QR code
    """
    uri = get_totp_uri(secret, email)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(uri)
    qr.make(fit=True)

    img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
    return img.to_string().decode()


def verify_totp(secret: str, code: str) -> bool:
    """
    Verify a TOTP code.

    Args:
        secret: TOTP secret
        code: 6-digit code from authenticator app

    Returns:
        True if valid, False otherwise
    """
    totp = pyotp.TOTP(secret)
    # Allow 1 period tolerance for clock drift
    return totp.verify(code, valid_window=1)


def generate_recovery_codes(count: int = 10) -> list[str]:
    """
    Generate recovery codes for MFA backup.

    Args:
        count: Number of codes to generate

    Returns:
        List of recovery codes (format: XXXX-XXXX-XXXX)
    """
    codes = []
    for _ in range(count):
        # Generate 12 character code in groups of 4
        code = secrets.token_hex(6).upper()
        formatted = f"{code[:4]}-{code[4:8]}-{code[8:]}"
        codes.append(formatted)
    return codes


def hash_recovery_code(code: str) -> str:
    """
    Hash a recovery code for storage.

    Args:
        code: Recovery code

    Returns:
        Hashed code
    """
    # Remove dashes and hash
    clean_code = code.replace("-", "").upper()
    return hash_password(clean_code)


def verify_recovery_code(code: str, code_hash: str) -> bool:
    """
    Verify a recovery code against its hash.

    Args:
        code: Recovery code to verify
        code_hash: Stored hash

    Returns:
        True if valid, False otherwise
    """
    clean_code = code.replace("-", "").upper()
    return verify_password(clean_code, code_hash)


# =============================================================================
# Utility Functions
# =============================================================================

def generate_secure_token(length: int = 32) -> str:
    """
    Generate a cryptographically secure random token.

    Args:
        length: Number of bytes (output will be 2x this in hex)

    Returns:
        Hex-encoded random token
    """
    return secrets.token_hex(length)


def generate_api_key() -> str:
    """
    Generate an API key with prefix.

    Returns:
        API key in format: aim_xxxxx (AI Marketing)
    """
    return f"aim_{secrets.token_urlsafe(32)}"
