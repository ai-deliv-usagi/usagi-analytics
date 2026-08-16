from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class TokenSet:
    access_token: str
    refresh_token: str
    expires_at: datetime
    refresh_expires_at: datetime | None
    open_id: str | None = None
    scope: str | None = None
    token_type: str = "Bearer"

    def is_expiring_soon(self, buffer_seconds: int = 300) -> bool:
        now = datetime.now(timezone.utc)
        return (self.expires_at - now).total_seconds() <= buffer_seconds

    def to_json(self) -> str:
        payload = asdict(self)
        payload["expires_at"] = self.expires_at.isoformat()
        payload["refresh_expires_at"] = (
            self.refresh_expires_at.isoformat() if self.refresh_expires_at else None
        )
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> "TokenSet":
        payload = json.loads(raw)
        payload["expires_at"] = _parse_datetime(payload["expires_at"])
        if payload.get("refresh_expires_at"):
            payload["refresh_expires_at"] = _parse_datetime(payload["refresh_expires_at"])
        return cls(**payload)


class TokenStore(Protocol):
    def load(self) -> TokenSet | None:
        raise NotImplementedError

    def save(self, token_set: TokenSet) -> None:
        raise NotImplementedError


class FileTokenStore:
    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def load(self) -> TokenSet | None:
        if not self.path.exists():
            return None
        return TokenSet.from_json(self.path.read_text(encoding="utf-8"))

    def save(self, token_set: TokenSet) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(token_set.to_json(), encoding="utf-8")


class SecretManagerTokenStore:
    def __init__(self, project_id: str, secret_id: str) -> None:
        from google.cloud import secretmanager

        self.client = secretmanager.SecretManagerServiceClient()
        self.secret_name = f"projects/{project_id}/secrets/{secret_id}"

    def load(self) -> TokenSet | None:
        try:
            response = self.client.access_secret_version(
                request={"name": f"{self.secret_name}/versions/latest"}
            )
        except Exception:
            return None
        raw = response.payload.data.decode("utf-8")
        return TokenSet.from_json(raw)

    def save(self, token_set: TokenSet) -> None:
        self.client.add_secret_version(
            request={
                "parent": self.secret_name,
                "payload": {"data": token_set.to_json().encode("utf-8")},
            }
        )


def build_token_store(
    backend: str,
    token_file_path: str,
    gcp_project_id: str | None,
    token_secret_id: str,
) -> TokenStore:
    if backend == "file":
        return FileTokenStore(token_file_path)
    if backend == "secret_manager":
        if not gcp_project_id:
            raise RuntimeError("GCP_PROJECT_ID is required when TOKEN_STORE_BACKEND=secret_manager")
        return SecretManagerTokenStore(gcp_project_id, token_secret_id)
    raise RuntimeError(f"Unsupported TOKEN_STORE_BACKEND: {backend}")


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
