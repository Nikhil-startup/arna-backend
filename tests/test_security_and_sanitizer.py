import pytest
from arna_backend.routers.auth import hash_password, verify_password
from arna_backend.services.sanitizer import (
    mask_card_number,
    sanitize_string,
    sanitize_dict
)


def test_hash_password_format_and_determinism():
    """Ensure passwords are saved with #hash_ prefix and deterministic salted SHA-256."""
    plain = "SuperSecret123!"
    hashed = hash_password(plain)
    
    assert hashed.startswith("#hash_")
    assert len(hashed) > 15
    assert hash_password(plain) == hashed
    assert hash_password("DifferentPassword") != hashed


def test_verify_password_correct_and_incorrect():
    """Verify constant-time password matching against hashes."""
    pwd = "MyLuxuryPassword2026"
    stored_hash = hash_password(pwd)
    
    assert verify_password(pwd, stored_hash) is True
    assert verify_password("WrongPassword", stored_hash) is False
    assert verify_password("", stored_hash) is False
    assert verify_password(pwd, None) is False


def test_verify_password_legacy_plaintext_compatibility():
    """Verify legacy plaintext accounts can still authenticate."""
    legacy_pwd = "PlainOldPassword"
    assert verify_password(legacy_pwd, legacy_pwd) is True
    assert verify_password("Incorrect", legacy_pwd) is False


def test_mask_card_number():
    """Ensure credit card numbers have only last 4 digits visible."""
    card = "4111 2222 3333 4444"
    masked = mask_card_number(card)
    assert masked == "****-****-****-4444"

    short_card = "1234"
    assert mask_card_number(short_card) == "****"


def test_sanitize_string_redacts_passwords_and_cards():
    """Ensure log sanitizer redacts passwords, tokens, CVVs and card numbers in text."""
    sample_log = 'User {"password": "SecretPass!", "cvv": "123"} paid with 4111-2222-3333-4444 using Bearer abcd1234efgh'
    sanitized = sanitize_string(sample_log)
    
    assert "SecretPass!" not in sanitized
    assert '"[REDACTED]"' in sanitized
    assert "[REDACTED_CVV]" in sanitized
    assert "Bearer [REDACTED_TOKEN]" in sanitized
    assert "****-****-****-4444" in sanitized


def test_sanitize_dict_recursive():
    """Ensure dictionary sanitizer recursively scrubs sensitive fields."""
    payload = {
        "user": {
            "name": "Nikhil",
            "password": "Password123",
            "auth_token": "secret_token_value_xyz"
        },
        "payment": {
            "card_number": "5555444433332222",
            "cvv": "999"
        },
        "normal_field": "ARNA Fashion"
    }
    cleaned = sanitize_dict(payload)
    
    assert cleaned["user"]["password"] == "[REDACTED]"
    assert cleaned["payment"]["cvv"] == "[REDACTED]"
    assert cleaned["payment"]["card_number"] == "****-****-****-2222"
    assert cleaned["normal_field"] == "ARNA Fashion"
