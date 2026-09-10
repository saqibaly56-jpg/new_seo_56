import os
import pytest
from unittest import mock
from dashboard.auth import hash_password, verify_password
from utils.crypto import encrypt_credential, decrypt_credential
from utils.db import get_db_connection
from adapters.wp_base import BaseWordPressAdapter

def test_pbkdf2_password_hashing():
    raw_pw = "SuperSecret123!"
    hashed = hash_password(raw_pw)
    assert hashed.startswith("pbkdf2:sha256:100000$")
    assert verify_password(raw_pw, hashed) is True
    assert verify_password("WrongPassword", hashed) is False

def test_legacy_sha256_hash_compatibility():
    raw_pw = "LegacyPassword123"
    import hashlib
    legacy_hash = hashlib.sha256(raw_pw.encode('utf-8')).hexdigest()
    assert verify_password(raw_pw, legacy_hash) is True
    assert verify_password("WrongPassword", legacy_hash) is False

def test_credential_encryption():
    secret = "wp_app_password_987654321"
    encrypted = encrypt_credential(secret)
    assert encrypted.startswith("enc:")
    assert encrypted != secret
    decrypted = decrypt_credential(encrypted)
    assert decrypted == secret

    tampered = encrypted[:-2] + ("aa" if encrypted[-2:] != "aa" else "bb")
    assert decrypt_credential(tampered) == ""

def test_legacy_unencrypted_credential_fallback():
    raw_secret = "legacy_plain_password"
    assert decrypt_credential(raw_secret) == raw_secret

def test_sqlite_wal_mode():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"

def test_wp_base_non_json_handling():
    adapter = BaseWordPressAdapter({
        'site_url': 'https://example.com',
        'username': 'admin',
        'app_password': 'pass'
    })
    
    mock_response = mock.Mock()
    mock_response.status_code = 502
    mock_response.headers = {'content-type': 'text/html'}
    mock_response.text = "<html>502 Bad Gateway</html>"
    
    with mock.patch('adapters.wp_base.request_with_retry', return_value=mock_response):
        result = adapter._push_post({'title': 'test'})
        assert result is None
