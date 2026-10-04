import re
import logging
from typing import Any, Dict

# Regex patterns for sensitive data
CARD_PATTERN = re.compile(r'\b(?:\d[ -]*?){13,19}\b')
CVV_PATTERN = re.compile(r'["\']?(?:cvv|cvc|security_code)["\']?\s*[:=]\s*["\']?(\d{3,4})["\']?', re.IGNORECASE)
PASSWORD_PATTERN = re.compile(r'("(?:password|password_hash|new_password|passcode|token|access_token|secret)"\s*:\s*)"([^"]+)"', re.IGNORECASE)
BEARER_PATTERN = re.compile(r'Bearer\s+[a-zA-Z0-9_\-\.]+', re.IGNORECASE)

def mask_card_number(card: str) -> str:
    """Masks credit card numbers leaving only the last 4 digits visible."""
    digits = re.sub(r'\D', '', card)
    if len(digits) >= 12:
        return f"****-****-****-{digits[-4:]}"
    return "****"

def sanitize_string(text: str) -> str:
    """Redacts sensitive passwords, tokens, CVVs, and credit card numbers from string logs."""
    if not text:
        return text
    
    # 1. Mask passwords and tokens in JSON / key-value representations
    text = PASSWORD_PATTERN.sub(r'\1"[REDACTED]"', text)
    
    # 2. Redact Bearer tokens
    text = BEARER_PATTERN.sub('Bearer [REDACTED_TOKEN]', text)
    
    # 3. Mask card numbers
    def _card_replacer(match):
        raw = match.group(0)
        digits = re.sub(r'\D', '', raw)
        if 13 <= len(digits) <= 19:
            return mask_card_number(raw)
        return raw

    text = CARD_PATTERN.sub(_card_replacer, text)
    
    # 4. Redact CVV
    text = CVV_PATTERN.sub(r'cvv: "[REDACTED_CVV]"', text)
    
    return text

def sanitize_dict(data: Any) -> Any:
    """Recursively redacts sensitive keys from dictionaries and lists."""
    if isinstance(data, dict):
        sanitized = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(secret in k_lower for secret in ['password', 'passcode', 'cvv', 'cvc', 'secret_key', 'auth_token']):
                sanitized[k] = "[REDACTED]"
            elif 'card' in k_lower and isinstance(v, str):
                sanitized[k] = mask_card_number(v)
            elif 'token' in k_lower and isinstance(v, str) and len(v) > 10:
                sanitized[k] = f"{v[:4]}...[REDACTED]"
            else:
                sanitized[k] = sanitize_dict(v)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_dict(item) for item in data]
    elif isinstance(data, str):
        return sanitize_string(data)
    return data

class SanitizedLogFilter(logging.Filter):
    """Logging filter that ensures no secret passwords, tokens, or card numbers are logged."""
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = sanitize_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = sanitize_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(sanitize_string(str(arg)) if isinstance(arg, str) else arg for arg in record.args)
        return True
