from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Video:
    id: str
    title: str | None
    create_time: datetime | None
    view_count: int | None
    like_count: int | None
    comment_count: int | None
    share_count: int | None
    video_description: str | None
    duration: int | None
    share_url: str | None

    @classmethod
    def from_api(cls, payload: dict[str, Any]) -> "Video":
        return cls(
            id=str(payload["id"]),
            title=payload.get("title"),
            create_time=_parse_unix_seconds(payload.get("create_time")),
            view_count=_optional_int(payload.get("view_count")),
            like_count=_optional_int(payload.get("like_count")),
            comment_count=_optional_int(payload.get("comment_count")),
            share_count=_optional_int(payload.get("share_count")),
            video_description=payload.get("video_description"),
            duration=_optional_int(payload.get("duration")),
            share_url=payload.get("share_url"),
        )


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _parse_unix_seconds(value: Any) -> datetime | None:
    if value is None:
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc)
