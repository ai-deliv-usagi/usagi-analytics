from __future__ import annotations

import os
from dataclasses import dataclass


DEFAULT_VIDEO_FIELDS = [
    "id",
    "title",
    "create_time",
    "view_count",
    "like_count",
    "comment_count",
    "share_count",
    "video_description",
    "duration",
    "share_url",
]


@dataclass(frozen=True)
class Settings:
    tiktok_client_key: str
    tiktok_client_secret: str
    tiktok_redirect_uri: str
    tiktok_cloud_run_callback_url: str
    token_store_backend: str = "file"
    token_file_path: str = ".local/tiktok_token.json"
    gcp_project_id: str | None = None
    token_secret_id: str = "tiktok-display-api-token"
    storage_backend: str = "sqlite"
    sqlite_db_path: str = ".local/usagi_analytics.sqlite3"
    gcs_bucket_name: str | None = None
    run_fetch_token: str | None = None
    request_sleep_seconds: float = 0.5
    tiktok_auth_base_url: str = "https://www.tiktok.com/v2/auth/authorize/"
    tiktok_token_url: str = "https://open.tiktokapis.com/v2/oauth/token/"


def load_settings() -> Settings:
    return Settings(
        tiktok_client_key=os.getenv("TIKTOK_CLIENT_KEY", ""),
        tiktok_client_secret=os.getenv("TIKTOK_CLIENT_SECRET", ""),
        tiktok_redirect_uri=os.getenv("TIKTOK_REDIRECT_URI", ""),
        tiktok_cloud_run_callback_url=os.getenv("TIKTOK_CLOUD_RUN_CALLBACK_URL", ""),
        token_store_backend=os.getenv("TOKEN_STORE_BACKEND", "file"),
        token_file_path=os.getenv("TOKEN_FILE_PATH", ".local/tiktok_token.json"),
        gcp_project_id=os.getenv("GCP_PROJECT_ID"),
        token_secret_id=os.getenv("TOKEN_SECRET_ID", "tiktok-display-api-token"),
        storage_backend=os.getenv("STORAGE_BACKEND", "sqlite"),
        sqlite_db_path=os.getenv("SQLITE_DB_PATH", ".local/usagi_analytics.sqlite3"),
        gcs_bucket_name=os.getenv("GCS_BUCKET_NAME"),
        run_fetch_token=os.getenv("RUN_FETCH_TOKEN"),
        request_sleep_seconds=float(os.getenv("TIKTOK_REQUEST_SLEEP_SECONDS", "0.5")),
        tiktok_auth_base_url=os.getenv(
            "TIKTOK_AUTH_BASE_URL", "https://www.tiktok.com/v2/auth/authorize/"
        ),
        tiktok_token_url=os.getenv(
            "TIKTOK_TOKEN_URL", "https://open.tiktokapis.com/v2/oauth/token/"
        ),
    )


def require(value: str | None, name: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value
