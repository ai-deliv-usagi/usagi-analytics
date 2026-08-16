from __future__ import annotations

import time
from typing import Any

import requests

from src.config import DEFAULT_VIDEO_FIELDS
from src.tiktok_client.models import Video


class TikTokVideoListClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        sleep_seconds: float = 0.5,
        max_retries: int = 3,
        endpoint: str = "https://open.tiktokapis.com/v2/video/list/",
    ) -> None:
        self.session = session or requests.Session()
        self.sleep_seconds = sleep_seconds
        self.max_retries = max_retries
        self.endpoint = endpoint

    def fetch_all_videos(
        self,
        access_token: str,
        fields: list[str] | None = None,
        max_count: int = 20,
    ) -> list[Video]:
        fields = fields or DEFAULT_VIDEO_FIELDS
        videos: list[Video] = []
        cursor: int | None = None

        while True:
            body: dict[str, Any] = {"max_count": max_count}
            if cursor is not None:
                body["cursor"] = cursor

            data = self._call_video_list_api(access_token, fields, body)
            page = data.get("data", {})
            videos.extend(Video.from_api(video) for video in page.get("videos", []))

            if not page.get("has_more", False):
                break
            cursor = page.get("cursor")
            if cursor is None:
                raise RuntimeError("TikTok response had has_more=true but no cursor.")
            time.sleep(self.sleep_seconds)

        return videos

    def _call_video_list_api(
        self, access_token: str, fields: list[str], body: dict[str, Any]
    ) -> dict[str, Any]:
        params = {"fields": ",".join(fields)}
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.post(
                    self.endpoint,
                    params=params,
                    json=body,
                    headers=headers,
                    timeout=30,
                )
                if response.status_code in (429, 500, 502, 503, 504):
                    raise RetryableTikTokError(
                        f"Retryable TikTok status {response.status_code}: {response.text}"
                    )
                response.raise_for_status()
                data = response.json()
                error = data.get("error", {})
                if error and error.get("code") not in ("ok", None, ""):
                    raise RuntimeError(f"TikTok video/list error: {error}")
                return data
            except (requests.RequestException, RetryableTikTokError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(min(2**attempt, 8))
        raise RuntimeError(f"TikTok video/list failed after retries: {last_error}") from last_error


class RetryableTikTokError(Exception):
    pass
