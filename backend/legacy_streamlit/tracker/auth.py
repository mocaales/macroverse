import hmac
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PBKDF2_ITERATIONS = 150_000
SESSION_TTL_SECONDS = 3 * 60 * 60


def normalize_email(email):
    if not email:
        return ""
    return email.strip().lower()


def _hash_password(password, salt=None, iterations=PBKDF2_ITERATIONS):
    if not password:
        return ""
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        iterations,
    )
    return f"pbkdf2_sha256${iterations}${salt}${dk.hex()}"


def _verify_password(password, stored):
    try:
        algo, iterations, salt, digest = stored.split("$", 3)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    candidate = _hash_password(password, salt=salt, iterations=int(iterations))
    return hmac.compare_digest(candidate, stored)


def get_user(db, email):
    email_norm = normalize_email(email)
    if not email_norm:
        return None
    return db.users.find_one({"email": email_norm}, {"_id": 0})


def register_user(db, email, password, confirm_password=None):
    email_norm = normalize_email(email)
    if not email_norm or not EMAIL_RE.match(email_norm):
        return False, "Enter a valid email address."
    if not password or len(password) < 8:
        return False, "Password must be at least 8 characters."
    if confirm_password is not None and password != confirm_password:
        return False, "Passwords do not match."
    if get_user(db, email_norm):
        return False, "An account with this email already exists."
    password_hash = _hash_password(password)
    db.users.insert_one(
        {
            "email": email_norm,
            "password": password_hash,
            "active": True,
        }
    )
    return True, "Account created."


def authenticate_user(db, email, password):
    email_norm = normalize_email(email)
    if not email_norm:
        return False, "Enter a valid email address."
    user = get_user(db, email_norm)
    if not user:
        return False, "Invalid email or password."
    if not _verify_password(password or "", user.get("password", "")):
        return False, "Invalid email or password."
    db.users.update_one(
        {"email": email_norm},
        {"$set": {"active": True}},
    )
    return True, email_norm


def logout_user(db, email):
    email_norm = normalize_email(email)
    if not email_norm:
        return
    db.users.update_one({"email": email_norm}, {"$set": {"active": False}})


def create_session(db, email):
    email_norm = normalize_email(email)
    if not email_norm:
        return ""
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=SESSION_TTL_SECONDS)
    db.user_sessions.insert_one(
        {
            "token": token,
            "email": email_norm,
            "active": True,
            "created_at": now,
            "expires_at": expires_at,
        }
    )
    return token


def get_session(db, token):
    if not token:
        return None
    session = db.user_sessions.find_one(
        {"token": token, "active": True},
        {"_id": 0},
    )
    if not session:
        return None

    now = datetime.now(timezone.utc)
    expires_at = session.get("expires_at")
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at and expires_at <= now:
        db.user_sessions.update_one(
            {"token": token},
            {"$set": {"active": False}},
        )
        return None

    # Backfill expiration for legacy sessions that predate TTL support.
    if not expires_at:
        db.user_sessions.update_one(
            {"token": token},
            {"$set": {"expires_at": now + timedelta(seconds=SESSION_TTL_SECONDS)}},
        )

    return session


def invalidate_session(db, token):
    if not token:
        return
    db.user_sessions.update_one({"token": token}, {"$set": {"active": False}})


def get_user_favourites(db, email):
    email_norm = normalize_email(email)
    if not email_norm:
        return set()
    doc = db.user_favourites.find_one(
        {"email": email_norm}, {"_id": 0, "favourites": 1}
    )
    if not doc:
        return set()
    return set(doc.get("favourites", []))


def toggle_user_favourite(db, email, chart_name):
    email_norm = normalize_email(email)
    if not email_norm or not chart_name:
        return False
    user = get_user(db, email_norm)
    if not user:
        return False
    doc = db.user_favourites.find_one(
        {"email": email_norm}, {"_id": 0, "favourites": 1}
    )
    favourites = set(doc.get("favourites", [])) if doc else set()
    if chart_name in favourites:
        db.user_favourites.update_one(
            {"email": email_norm},
            {"$pull": {"favourites": chart_name}},
            upsert=True,
        )
        return False
    db.user_favourites.update_one(
        {"email": email_norm},
        {"$addToSet": {"favourites": chart_name}},
        upsert=True,
    )
    return True
