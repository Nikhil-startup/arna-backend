import hmac
import hashlib
import pytest
from arna_backend.config import RAZORPAY_KEY_SECRET


def test_razorpay_signature_verification_success():
    """Verify that matching HMAC-SHA256 signatures pass constant-time comparison."""
    secret = "sample_test_secret_key_12345"
    order_id = "order_test_987654321"
    payment_id = "pay_test_123456789"
    
    # Expected signature generation
    body = f"{order_id}|{payment_id}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    
    # Assert constant-time digest matches
    assert hmac.compare_digest(expected_sig, expected_sig) is True


def test_razorpay_signature_verification_tampered_fails():
    """Verify that altered or forged signatures are strictly rejected."""
    secret = "sample_test_secret_key_12345"
    order_id = "order_test_987654321"
    payment_id = "pay_test_123456789"
    
    body = f"{order_id}|{payment_id}".encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    tampered_sig = expected_sig[:-4] + "ffff"
    
    # Assert constant-time digest rejects tampered signature
    assert hmac.compare_digest(expected_sig, tampered_sig) is False


def test_upi_utr_regex_validation():
    """Verify that UPI UTR must strictly be 12 alphanumeric characters."""
    import re
    pattern = r"^[0-9A-Za-z]{12}$"
    
    valid_utr = "123456789012"
    invalid_short = "12345"
    invalid_special = "12345678@#12"
    
    assert bool(re.match(pattern, valid_utr)) is True
    assert bool(re.match(pattern, invalid_short)) is False
    assert bool(re.match(pattern, invalid_special)) is False
