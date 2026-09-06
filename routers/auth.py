import os
import re
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import get_db
from models import User

router = APIRouter(prefix="/api/auth", tags=["Auth"])

# Google Web OAuth client IDs always end with this Google-owned suffix.
# Keeping placeholder values disabled prevents the browser from opening Google's
# "OAuth client was not found / invalid_client" page when setup is incomplete.
GOOGLE_CLIENT_ID_RE = re.compile(r"^\d+-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$")


def get_google_client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def google_client_is_configured(client_id: str) -> bool:
    placeholders = {
        "", "your-client-id.apps.googleusercontent.com", "your_google_client_id",
        "your-client-id", "replace-me"
    }
    return client_id not in placeholders and bool(GOOGLE_CLIENT_ID_RE.fullmatch(client_id))


def public_user(user):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "avatar_url": user.avatar_url,
    }


@router.get("/google/config")
def google_config():
    client_id = get_google_client_id()
    enabled = google_client_is_configured(client_id)
    return {
        "enabled": enabled,
        "client_id": client_id if enabled else "",
        "message": "Google Sign-In is ready" if enabled else (
            "Google Sign-In is not configured. Create a Google OAuth Web application client, "
            "add its real Client ID to .env, then restart the server."
        ),
    }


@router.post("/register")
def register(name: str, email: str, password: str, db: Session = Depends(get_db)):
    email = email.strip().lower()
    if not name.strip() or not email or not password:
        raise HTTPException(status_code=400, detail="Name, email and password are required")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(name=name.strip(), email=email, password=password)
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "Registered successfully", "user": public_user(user)}


@router.post("/login")
def login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email.strip().lower()).first()
    if not user or not user.password or user.password != password:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"message": "Login successful", "user": public_user(user)}


class GoogleCredentialIn(BaseModel):
    credential: str


@router.post("/google")
def google_login(payload: GoogleCredentialIn, db: Session = Depends(get_db)):
    credential = (payload.credential or "").strip()
    if not credential:
        raise HTTPException(status_code=400, detail="Google credential is missing")

    client_id = get_google_client_id()
    if not google_client_is_configured(client_id):
        raise HTTPException(
            status_code=503,
            detail="Google login is not configured with a valid Web Client ID. See GOOGLE_AUTH_SETUP.md.",
        )

    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as google_requests
<<<<<<< HEAD
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="Google Sign-In support is optional and is not installed. Install google-auth only if you configure Google login.",
        )
    try:
=======
>>>>>>> acb05f8ecc9b70bcc7a7da286e973fe6dd75117c
        info = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Google credential could not be verified. Check the Client ID and authorized JavaScript origins.",
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Google sign-in could not be verified")

    # Basic account identity checks before creating/updating a local user.
    if info.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=401, detail="Invalid Google token issuer")

    email = (info.get("email") or "").strip().lower()
    sub = info.get("sub")
    if not email or not sub:
        raise HTTPException(status_code=401, detail="Google account did not provide identity information")
    if info.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Google email address is not verified")

    user = db.query(User).filter((User.google_sub == sub) | (User.email == email)).first()
    if not user:
        user = User(
            name=info.get("name") or email.split("@")[0],
            email=email,
            password="",
            google_sub=sub,
            avatar_url=info.get("picture"),
        )
        db.add(user)
    else:
        user.google_sub = sub
        user.avatar_url = info.get("picture") or user.avatar_url
        user.name = info.get("name") or user.name

    db.commit()
    db.refresh(user)
    return {"message": "Google login successful", "user": public_user(user)}


@router.get("/me")
def me(x_user_id: int = Header(...), db: Session = Depends(get_db)):
    user = db.get(User, x_user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid user")
    return public_user(user)
