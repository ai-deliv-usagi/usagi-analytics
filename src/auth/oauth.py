from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlencode

import requests

from src.auth.token_store import TokenSet, TokenStore


SCOPES = ["video.list"]


class TikTokOAuthClient:
    def __init__(
        self,
        client_key: str,
        client_secret: str,
        redirect_uri: str,
        token_store: TokenStore,
        auth_base_url: str = "https://www.tiktok.com/v2/auth/authorize/",
        token_url: str = "https://open.tiktokapis.com/v2/oauth/token/",
        session: requests.Session | None = None,
    ) -> None:
        self.client_key = client_key
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.token_store = token_store
        self.auth_base_url = auth_base_url
        self.token_url = token_url
        self.session = session or requests.Session()

    def build_authorization_url(self, state: str | None = None) -> tuple[str, str]:
        state = state or secrets.token_urlsafe(24)
        query = urlencode(
            {
                "client_key": self.client_key,
                "scope": ",".join(SCOPES),
                "response_type": "code",
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{self.auth_base_url}?{query}", state

    def exchange_code(self, code: str) -> TokenSet:
        payload = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.redirect_uri,
        }
        token_set = self._post_token(payload)
        self.token_store.save(token_set)
        return token_set

    def refresh(self, refresh_token: str) -> TokenSet:
        payload = {
            "client_key": self.client_key,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        }
        token_set = self._post_token(payload)
        self.token_store.save(token_set)
        return token_set

    def get_valid_access_token(self) -> str:
        token_set = self.token_store.load()
        if token_set is None:
            raise RuntimeError("No TikTok token is stored. Complete OAuth authorization first.")
        if token_set.is_expiring_soon():
            token_set = self.refresh(token_set.refresh_token)
        return token_set.access_token

    def _post_token(self, payload: dict[str, str]) -> TokenSet:
        response = self.session.post(
            self.token_url,
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        if "data" in data:
            data = data["data"]
        if data.get("error") or data.get("error_code", 0) not in (0, None):
            raise RuntimeError(f"TikTok OAuth error: {data}")
        return _token_set_from_response(data)


def _token_set_from_response(data: dict[str, Any]) -> TokenSet:
    now = datetime.now(timezone.utc)
    expires_in = int(data["expires_in"])
    refresh_expires_in = data.get("refresh_expires_in")
    return TokenSet(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_at=now + timedelta(seconds=expires_in),
        refresh_expires_at=(
            now + timedelta(seconds=int(refresh_expires_in)) if refresh_expires_in else None
        ),
        open_id=data.get("open_id"),
        scope=data.get("scope"),
        token_type=data.get("token_type", "Bearer"),
    )
