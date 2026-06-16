"""
Security utilities: password hashing, JWT token management, and
Shopify webhook HMAC-SHA256 validation.
"""

import hashlib
import hmac
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
import bcrypt
from app.core.config import settings

def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(plain_password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


# ---------------------------------------------------------------------------
# JWT Token Management
# ---------------------------------------------------------------------------


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode (must include "sub" key).
        expires_delta: Optional custom expiration. Defaults to config value.

    Returns:
        Encoded JWT string.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def verify_access_token(token: str) -> dict | None:
    """
    Decode and verify a JWT access token.

    Args:
        token: The JWT token string.

    Returns:
        Decoded payload dict, or None if verification fails.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        return payload
    except JWTError:
        return None


# ---------------------------------------------------------------------------
# Shopify Webhook HMAC-SHA256 Validation
# ---------------------------------------------------------------------------


def verify_shopify_hmac(
    payload_body: bytes,
    hmac_header: str,
    secret: str | None = None,
) -> bool:
    """
    Verify a Shopify webhook payload using HMAC-SHA256.

    Args:
        payload_body: Raw request body bytes.
        hmac_header: The X-Shopify-Hmac-Sha256 header value.
        secret: Webhook secret (defaults to config value).

    Returns:
        True if the HMAC is valid.
    """
    if not secret:
        secret = getattr(settings, "SHOPIFY_WEBHOOK_SECRET", None)
    if not secret:
        return False

    computed = hmac.new(
        secret.encode("utf-8"),
        payload_body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed, hmac_header)

# ---------------------------------------------------------------------------
# Symmetric Encryption (Fernet) for API Tokens
# ---------------------------------------------------------------------------
from cryptography.fernet import Fernet, InvalidToken
import structlog

logger = structlog.get_logger(__name__)

_fernet: Fernet | None = None
if settings.ENCRYPTION_KEY:
    try:
        _fernet = Fernet(settings.ENCRYPTION_KEY.encode())
    except Exception as e:
        logger.warning("failed_to_initialize_fernet", error=str(e))

def encrypt_data(plain_text: str | None) -> str | None:
    """Encrypt plain text using Fernet. Returns plain text if no key is configured."""
    if not plain_text or not _fernet:
        return plain_text
    return _fernet.encrypt(plain_text.encode("utf-8")).decode("utf-8")

def decrypt_data(encrypted_text: str | None) -> str | None:
    """Decrypt text using Fernet. Fallbacks to original text if not encrypted."""
    if not encrypted_text or not _fernet:
        return encrypted_text
    try:
        return _fernet.decrypt(encrypted_text.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        # Fallback for plain text rows existing before encryption
        return encrypted_text
    except Exception as e:
        logger.warning("decryption_error", error=str(e))
        return encrypted_text

"""
Cara setup

Skenario 1: Instalasi Baru (Fresh Database)
Jika Anda menjalankan proyek ini dari nol (tabel database kosong):

Anda cukup menjalankan skrip pendek ini di terminal untuk membuat kunci baru:
bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
Taruh hasilnya di file .env (ENCRYPTION_KEY=hasil_tadi...)
Jalankan aplikasi, lalu buka UI Test Bench. Anda tinggal memasukkan ulang Token Shopify dan Telegram Anda di sana lalu klik "Save". Sistem akan otomatis mengenkripsi token Anda menggunakan kunci yang baru.
Skenario 2: Migrasi Server (Membawa Database Lama)
Jika Anda memindahkan proyek beserta seluruh isi database PostgreSQL Anda saat ini ke server lain:

Anda wajib mem-backup dan menyalin ENCRYPTION_KEY yang ada di .env saat ini ke server baru.
Apa yang terjadi jika Anda kehilangan kuncinya? Anda tetap tidak akan kehilangan proyek Anda! Anda hanya akan kehilangan kemampuan untuk membaca sandi (decrypt) token di database. Solusinya sangat mudah: Anda cukup buka halaman UI Test Bench, masukkan ulang Token Shopify dan Telegram, lalu klik Save. Sistem akan menimpanya dengan enkripsi kunci yang baru!
"""