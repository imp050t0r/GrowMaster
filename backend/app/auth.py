from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
from threading import Lock
import time

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.models import AdminCredential, AuthSession


SESSION_COOKIE = "growmaster_session"
PASSWORD_ALGORITHM = "scrypt-v1"
SESSION_LIFETIME = timedelta(days=30)
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_LENGTH = 32
LOGIN_WINDOW_SECONDS = 5 * 60
LOGIN_FAILURE_LIMIT = 5
_login_failures: dict[str, list[float]] = {}
_login_lock = Lock()


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def cookie_secure() -> bool:
    return os.getenv("COOKIE_SECURE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def password_is_strong(password: str) -> bool:
    return (
        len(password) >= 12
        and any(character.isalpha() for character in password)
        and any(character.isdigit() for character in password)
    )


def login_rate_limited(client_key: str) -> bool:
    cutoff = time.monotonic() - LOGIN_WINDOW_SECONDS
    with _login_lock:
        recent = [value for value in _login_failures.get(client_key, []) if value > cutoff]
        _login_failures[client_key] = recent
        return len(recent) >= LOGIN_FAILURE_LIMIT


def record_login_failure(client_key: str) -> None:
    with _login_lock:
        _login_failures.setdefault(client_key, []).append(time.monotonic())


def clear_login_failures(client_key: str) -> None:
    with _login_lock:
        _login_failures.pop(client_key, None)


def hash_password(password: str, salt: bytes) -> bytes:
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=SCRYPT_LENGTH,
    )


def verify_password(credential: AdminCredential, password: str) -> bool:
    if credential.password_algorithm != PASSWORD_ALGORITHM:
        return False
    candidate = hash_password(password, credential.password_salt)
    return hmac.compare_digest(credential.password_hash, candidate)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def get_credential(db: Session) -> AdminCredential | None:
    return db.scalar(select(AdminCredential).order_by(AdminCredential.id).limit(1))


def create_credential(db: Session, display_name: str, password: str) -> AdminCredential:
    salt = secrets.token_bytes(16)
    credential = AdminCredential(
        id=1,
        display_name=display_name.strip(),
        password_hash=hash_password(password, salt),
        password_salt=salt,
        password_algorithm=PASSWORD_ALGORITHM,
    )
    db.add(credential)
    db.flush()
    return credential


def create_session(db: Session, credential: AdminCredential) -> tuple[str, AuthSession]:
    now = utc_now()
    db.execute(delete(AuthSession).where(AuthSession.expires_at <= now))
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        credential_id=credential.id,
        token_hash=token_digest(token),
        expires_at=now + SESSION_LIFETIME,
    )
    db.add(session)
    db.flush()

    session_ids = list(
        db.scalars(
            select(AuthSession.id)
            .where(AuthSession.credential_id == credential.id)
            .order_by(AuthSession.created_at.desc(), AuthSession.id.desc())
        )
    )
    if len(session_ids) > 10:
        db.execute(delete(AuthSession).where(AuthSession.id.in_(session_ids[10:])))
    return token, session


def active_session_count(db: Session, credential: AdminCredential) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(AuthSession)
            .where(
                AuthSession.credential_id == credential.id,
                AuthSession.expires_at > utc_now(),
            )
        )
        or 0
    )


def replace_password(
    db: Session, credential: AdminCredential, new_password: str
) -> tuple[str, AuthSession]:
    salt = secrets.token_bytes(16)
    credential.password_hash = hash_password(new_password, salt)
    credential.password_salt = salt
    credential.password_algorithm = PASSWORD_ALGORITHM
    credential.updated_at = utc_now()
    db.execute(
        delete(AuthSession).where(AuthSession.credential_id == credential.id)
    )
    return create_session(db, credential)


def authenticated_credential(db: Session, token: str | None) -> AdminCredential | None:
    if not token:
        return None
    session = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == token_digest(token))
    )
    if session is None:
        return None
    if session.expires_at <= utc_now():
        db.delete(session)
        db.commit()
        return None
    return db.get(AdminCredential, session.credential_id)


def revoke_session(db: Session, token: str | None) -> None:
    if token:
        db.execute(delete(AuthSession).where(AuthSession.token_hash == token_digest(token)))
        db.commit()
