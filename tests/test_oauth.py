from datetime import datetime, timezone

from src.auth.oauth import TikTokOAuthClient
from src.auth.token_store import TokenSet


class MemoryStore:
    def __init__(self, token_set=None):
        self.token_set = token_set

    def load(self):
        return self.token_set

    def save(self, token_set):
        self.token_set = token_set


class FakeResponse:
    status_code = 200

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def post(self, url, data, headers, timeout):
        self.calls.append({"url": url, "data": data, "headers": headers, "timeout": timeout})
        return FakeResponse(self.payload)


def test_build_authorization_url_uses_video_list_scope():
    client = TikTokOAuthClient("key", "secret", "https://example.test/callback", MemoryStore())

    url, state = client.build_authorization_url("fixed-state")

    assert state == "fixed-state"
    assert "client_key=key" in url
    assert "scope=video.list" in url
    assert "response_type=code" in url


def test_exchange_code_saves_token_set():
    session = FakeSession(
        {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 86400,
            "refresh_expires_in": 31536000,
            "open_id": "open-id",
            "scope": "video.list",
            "token_type": "Bearer",
        }
    )
    store = MemoryStore()
    client = TikTokOAuthClient("key", "secret", "redirect", store, session=session)

    token_set = client.exchange_code("code")

    assert token_set.access_token == "access"
    assert store.token_set == token_set
    assert session.calls[0]["data"]["grant_type"] == "authorization_code"


def test_token_set_round_trip_json():
    token_set = TokenSet(
        access_token="access",
        refresh_token="refresh",
        expires_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        refresh_expires_at=None,
    )

    assert TokenSet.from_json(token_set.to_json()) == token_set
