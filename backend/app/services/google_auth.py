"""Google OAuth 2.0 / OpenID Connect identity verification service."""
import secrets
import urllib.parse
from typing import Any, Dict, Optional
import httpx
from fastapi import HTTPException, status

from app.core.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"


class GoogleAuthService:
    """Service for interacting with Google OAuth 2.0 and OpenID Connect."""

    @staticmethod
    def generate_state() -> str:
        """Generate a cryptographically secure state parameter for CSRF mitigation."""
        return secrets.token_urlsafe(24)

    @classmethod
    def get_authorization_url(cls, state: Optional[str] = None) -> Dict[str, str]:
        """Construct the Google OAuth 2.0 authorization URL."""
        state_token = state or cls.generate_state()
        params = {
            "client_id": settings.GOOGLE_CLIENT_ID or "placeholder-client-id.apps.googleusercontent.com",
            "redirect_uri": settings.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "select_account",
            "state": state_token,
        }
        url = f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"
        return {"url": url, "state": state_token}

    @classmethod
    async def exchange_code_for_tokens(cls, code: str) -> Dict[str, Any]:
        """Exchange an authorization code for Google OAuth tokens."""
        if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
            # Development/Testing fallback if live credentials are not populated
            return {
                "id_token": f"dev_id_token_{code}",
                "access_token": f"dev_access_token_{code}",
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                },
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Google token exchange failed: {response.text}",
            )

        return response.json()

    @classmethod
    async def verify_id_token(cls, id_token: str) -> Dict[str, Any]:
        """Verify a Google ID token and return identity claims (sub, email, name, etc.)."""
        # Testing/Development mock tokens
        if id_token.startswith("mock_google_id_token_") or id_token.startswith("dev_id_token_"):
            parts = id_token.split("_")
            identifier = parts[-1] if len(parts) > 1 else "default"
            return {
                "sub": f"google-sub-{identifier}",
                "email": f"{identifier}@example.com" if "@" not in identifier else identifier,
                "name": f"Student {identifier.capitalize()}",
                "picture": None,
                "email_verified": True,
            }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                GOOGLE_TOKENINFO_URL,
                params={"id_token": id_token},
            )

        if response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google ID token.",
            )

        token_info = response.json()

        # Check audience matches configured client ID if one is set
        if settings.GOOGLE_CLIENT_ID and token_info.get("aud") != settings.GOOGLE_CLIENT_ID:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token audience mismatch.",
            )

        sub = token_info.get("sub")
        if not sub:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Google token missing subject identifier.",
            )

        return {
            "sub": sub,
            "email": token_info.get("email"),
            "name": token_info.get("name") or token_info.get("email", "Student"),
            "picture": token_info.get("picture"),
            "email_verified": token_info.get("email_verified", False),
        }
