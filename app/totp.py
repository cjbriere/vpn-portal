# app/totp.py
# Minimal TOTP utilities (RFC 6238) with base32 secrets; no 3rd-party deps required.

import base64
import hashlib
import hmac
import os
import struct
import time
from typing import Optional

_DEFAULT_PERIOD = 30
_DEFAULT_DIGITS = 6
_DEFAULT_ALGO = hashlib.sha1  # widely supported by authenticator apps

def _int_to_bytes(counter: int) -> bytes:
    return struct.pack(">Q", counter)

def _dynamic_truncate(hmac_digest: bytes) -> int:
    offset = hmac_digest[-1] & 0x0F
    code = ((hmac_digest[offset] & 0x7f) << 24 |
            (hmac_digest[offset + 1] & 0xff) << 16 |
            (hmac_digest[offset + 2] & 0xff) << 8 |
            (hmac_digest[offset + 3] & 0xff))
    return code

def _b32_normalize(s: str) -> str:
    s = s.strip().replace(" ", "").upper()
    pad = (-len(s)) % 8
    return s + ("=" * pad)

def generate_base32_secret(length: int = 20) -> str:
    raw = os.urandom(length)
    return base64.b32encode(raw).decode("ascii").strip().replace("=", "")

def _hotp(secret_b32: str, counter: int, digits: int = _DEFAULT_DIGITS,
          algo=_DEFAULT_ALGO) -> int:
    key = base64.b32decode(_b32_normalize(secret_b32))
    h = hmac.new(key, _int_to_bytes(counter), algo).digest()
    code_int = _dynamic_truncate(h) % (10 ** digits)
    return code_int

def totp_now(secret_b32: str, timestamp: Optional[int] = None,
             period: int = _DEFAULT_PERIOD, digits: int = _DEFAULT_DIGITS,
             algo=_DEFAULT_ALGO) -> int:
    if timestamp is None:
        timestamp = int(time.time())
    counter = int(timestamp // period)
    return _hotp(secret_b32, counter, digits=digits, algo=algo)

def verify_totp(secret_b32: str, code: str, period: int = _DEFAULT_PERIOD,
                digits: int = _DEFAULT_DIGITS, window: int = 1,
                timestamp: Optional[int] = None, algo=_DEFAULT_ALGO) -> bool:
    try:
        code_int = int(code)
    except ValueError:
        return False
    if timestamp is None:
        timestamp = int(time.time())
    counter = int(timestamp // period)
    for off in range(-window, window + 1):
        if _hotp(secret_b32, counter + off, digits=digits, algo=algo) == code_int:
            return True
    return False

def build_otpauth_uri(secret_b32: str, account_label: str, issuer: str) -> str:
    from urllib.parse import quote
    label = quote(f"{issuer}:{account_label}")
    params = f"secret={secret_b32}&issuer={quote(issuer)}&algorithm=SHA1&digits={_DEFAULT_DIGITS}&period={_DEFAULT_PERIOD}"
    return f"otpauth://totp/{label}?{params}"
