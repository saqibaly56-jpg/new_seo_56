import hashlib
import secrets
from typing import Optional, Dict

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import APIKeyCookie
from utils.db import get_db_connection, USE_POSTGRES

cookie_scheme = APIKeyCookie(name="session_token", auto_error=False)

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    salt_hex = salt.hex()
    dk = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return f"pbkdf2:sha256:100000${salt_hex}${dk.hex()}"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not hashed_password:
        return False
    if hashed_password.startswith("pbkdf2:sha256:"):
        try:
            parts = hashed_password.split("$")
            if len(parts) != 3:
                return False
            salt = bytes.fromhex(parts[1])
            expected_dk_hex = parts[2]
            dk = hashlib.pbkdf2_hmac('sha256', plain_password.encode('utf-8'), salt, 100000)
            return secrets.compare_digest(dk.hex(), expected_dk_hex)
        except Exception:
            return False
    # Fallback for legacy unsalted SHA-256 hashes
    legacy_hash = hashlib.sha256(plain_password.encode('utf-8')).hexdigest()
    return secrets.compare_digest(legacy_hash, hashed_password)

def generate_session_token() -> str:
    return secrets.token_urlsafe(32)

def get_current_user_id(session_token: str = Depends(cookie_scheme)) -> int:
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    
    try:
        with get_db_connection() as conn:
            expiry_clause = (
                "sessions.created_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'"
                if USE_POSTGRES else
                "sessions.created_at >= datetime('now', '-7 days')"
            )
            result = conn.execute(f"""
                SELECT sessions.user_id
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = ?
                  AND users.is_active = 1
                  AND {expiry_clause}
            """, (session_token,))
            row = result.fetchone()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication service is temporarily unavailable",
        )

    if not row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session"
        )

    return row['user_id']

def get_current_user(user_id: int = Depends(get_current_user_id)):
    from utils.db_models import SessionLocal, User
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found")
        return user

def require_admin(user = Depends(get_current_user)):
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required"
        )
    return user

def log_audit_event(user_id: Optional[int], action: str, resource_type: str = None, resource_id: str = None, ip_address: str = None, details: dict = None):
    try:
        from utils.db_models import SessionLocal, AuditLog
        import json
        with SessionLocal() as db:
            audit = AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=resource_id,
                ip_address=ip_address,
                details_json=json.dumps(details or {})
            )
            db.add(audit)
            db.commit()
    except Exception as e:
        pass

def get_user_settings(user_id: int) -> dict:
    from utils.crypto import decrypt_credential
    with get_db_connection() as conn:
        result = conn.execute("SELECT * FROM user_settings WHERE user_id = ?", (user_id,))
        row = result.fetchone()
        if not row:
            return {}
        data = dict(row)
        if data.get('wp_app_password'):
            data['wp_app_password'] = decrypt_credential(data['wp_app_password'])
        return data
