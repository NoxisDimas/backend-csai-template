from datetime import timedelta
import pytest
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_access_token,
    encrypt_data,
    decrypt_data,
)

def test_password_hashing():
    """Test bcrypt password hashing and verification."""
    password = "my_secure_password"
    hashed = hash_password(password)
    
    assert hashed != password
    assert verify_password(password, hashed) is True
    assert verify_password("wrong_password", hashed) is False

def test_jwt_token_creation_and_verification():
    """Test JWT creation and payload decoding."""
    data = {"sub": "user_123", "role": "admin"}
    token = create_access_token(data=data, expires_delta=timedelta(minutes=5))
    
    payload = verify_access_token(token)
    assert payload is not None
    assert payload["sub"] == "user_123"
    assert payload["role"] == "admin"
    assert "exp" in payload

def test_jwt_verification_failure():
    """Test JWT decoding with invalid token."""
    invalid_token = "invalid.token.string"
    payload = verify_access_token(invalid_token)
    assert payload is None

def test_encryption_decryption():
    """Test Fernet symmetric encryption."""
    plain_text = "sensitive_api_key"
    encrypted = encrypt_data(plain_text)
    
    # If ENCRYPTION_KEY is not set in environment during test, 
    # it might just return plain_text. Let's handle both.
    from app.core.security import _fernet
    if _fernet:
        assert encrypted != plain_text
        decrypted = decrypt_data(encrypted)
        assert decrypted == plain_text
    else:
        # Fallback behavior when key is absent
        assert encrypted == plain_text
        assert decrypt_data(encrypted) == plain_text
