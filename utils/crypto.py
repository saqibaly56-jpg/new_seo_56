import os
import base64
import hashlib
import hmac


def _is_production() -> bool:
    return os.getenv("APP_ENV", "development").strip().lower() in {"production", "prod"}


def _get_derived_key() -> bytes:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        if _is_production():
            raise RuntimeError("SECRET_KEY must be set in production. Refusing to start without a secret key.")
        secret = "seo_automation_local_dev_secret_key"
    return hashlib.sha256(secret.encode('utf-8')).digest()

def _keystream(key: bytes, nonce: bytes, length: int) -> bytes:
    stream = bytearray()
    counter = 0
    while len(stream) < length:
        stream.extend(hashlib.sha256(key + nonce + counter.to_bytes(8, "big")).digest())
        counter += 1
    return bytes(stream[:length])

def encrypt_credential(plain_text: str) -> str:
    """Encrypt credentials with an authenticated HMAC-SHA256 stream format."""
    if not plain_text:
        return ""
    key = _get_derived_key()
    nonce = os.urandom(16)
    plain_bytes = plain_text.encode('utf-8')
    cipher_bytes = bytes(a ^ b for a, b in zip(plain_bytes, _keystream(key, nonce, len(plain_bytes))))
    tag = hmac.new(key, nonce + cipher_bytes, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(nonce + tag + cipher_bytes).decode('ascii')
    return "enc:v2:" + token

def decrypt_credential(cipher_text: str) -> str:
    if not cipher_text:
        return ""
    if not cipher_text.startswith("enc:"):
        # Unencrypted plain text legacy credential
        return cipher_text
    try:
        if cipher_text.startswith("enc:v2:"):
            raw = base64.urlsafe_b64decode(cipher_text[7:].encode('ascii'))
            if len(raw) < 48:
                return ""
            nonce, tag, cipher_bytes = raw[:16], raw[16:48], raw[48:]
            expected_tag = hmac.new(_get_derived_key(), nonce + cipher_bytes, hashlib.sha256).digest()
            if not hmac.compare_digest(tag, expected_tag):
                return ""
            plain_bytes = bytes(a ^ b for a, b in zip(cipher_bytes, _keystream(_get_derived_key(), nonce, len(cipher_bytes))))
            return plain_bytes.decode('utf-8')

        # Legacy values are readable for migration; all new writes use v2.
        raw = base64.urlsafe_b64decode(cipher_text[4:].encode('ascii'))
        if len(raw) <= 16:
            return ""
        nonce = raw[:16]
        cipher_bytes = raw[16:]
        key = _get_derived_key()
        keystream = hashlib.sha256(key + nonce).digest()
        plain_bytes = bytearray()
        for i, b in enumerate(cipher_bytes):
            plain_bytes.append(b ^ keystream[i % len(keystream)])
        return plain_bytes.decode('utf-8')
    except (ValueError, UnicodeDecodeError, TypeError):
        return ""
