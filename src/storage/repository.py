from __future__ import annotations

import sqlite3
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from src.tiktok_client.models import Video


@dataclass(frozen=True)
class SnapshotStats:
    snapshots: int
    distinct_videos: int
    latest_fetched_at: str | None


class VideoSnapshotRepository(Protocol):
    def save_snapshots(
        self, videos: list[Video], fetched_at: datetime | None = None
    ) -> int:
        raise NotImplementedError

    def stats(self) -> SnapshotStats:
        raise NotImplementedError


class SQLiteVideoSnapshotRepository:
    def __init__(self, db_path: str) -> None:
        self.db_path = Path(db_path)

    def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS video_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    video_id TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    title TEXT,
                    create_time TEXT,
                    view_count INTEGER,
                    like_count INTEGER,
                    comment_count INTEGER,
                    share_count INTEGER,
                    video_description TEXT,
                    duration INTEGER,
                    share_url TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_video_snapshots_video_time
                ON video_snapshots(video_id, fetched_at)
                """
            )

    def save_snapshots(
        self, videos: list[Video], fetched_at: datetime | None = None
    ) -> int:
        self.initialize()
        fetched_at = fetched_at or datetime.now(timezone.utc)
        rows = [
            (
                video.id,
                fetched_at.isoformat(),
                video.title,
                video.create_time.isoformat() if video.create_time else None,
                video.view_count,
                video.like_count,
                video.comment_count,
                video.share_count,
                video.video_description,
                video.duration,
                video.share_url,
            )
            for video in videos
        ]
        with self._connect() as conn:
            conn.executemany(
                """
                INSERT INTO video_snapshots (
                    video_id,
                    fetched_at,
                    title,
                    create_time,
                    view_count,
                    like_count,
                    comment_count,
                    share_count,
                    video_description,
                    duration,
                    share_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                rows,
            )
        return len(rows)

    def stats(self) -> SnapshotStats:
        self.initialize()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT
                    COUNT(*) AS snapshots,
                    COUNT(DISTINCT video_id) AS distinct_videos,
                    MAX(fetched_at) AS latest_fetched_at
                FROM video_snapshots
                """
            ).fetchone()
        return SnapshotStats(
            snapshots=int(row["snapshots"]),
            distinct_videos=int(row["distinct_videos"]),
            latest_fetched_at=row["latest_fetched_at"],
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


class GCSJsonlVideoSnapshotRepository:
    def __init__(self, bucket_name: str, prefix: str = "video_snapshots") -> None:
        from google.cloud import storage

        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix.strip("/")

    def save_snapshots(
        self, videos: list[Video], fetched_at: datetime | None = None
    ) -> int:
        fetched_at = fetched_at or datetime.now(timezone.utc)
        object_name = (
            f"{self.prefix}/"
            f"{fetched_at:%Y/%m/%d}/"
            f"{fetched_at.strftime('%Y%m%dT%H%M%S%fZ')}.jsonl"
        )
        payload = "\n".join(
            json.dumps(_snapshot_payload(video, fetched_at), ensure_ascii=False)
            for video in videos
        )
        if payload:
            payload += "\n"
        self.bucket.blob(object_name).upload_from_string(
            payload, content_type="application/x-ndjson"
        )
        return len(videos)

    def stats(self) -> SnapshotStats:
        snapshots = 0
        distinct_videos: set[str] = set()
        latest_fetched_at: str | None = None

        for blob in self.client.list_blobs(self.bucket, prefix=f"{self.prefix}/"):
            raw = blob.download_as_text(encoding="utf-8")
            for line in raw.splitlines():
                if not line.strip():
                    continue
                payload = json.loads(line)
                snapshots += 1
                distinct_videos.add(payload["video_id"])
                fetched_at = payload["fetched_at"]
                if latest_fetched_at is None or fetched_at > latest_fetched_at:
                    latest_fetched_at = fetched_at

        return SnapshotStats(
            snapshots=snapshots,
            distinct_videos=len(distinct_videos),
            latest_fetched_at=latest_fetched_at,
        )


def build_video_snapshot_repository(
    backend: str,
    sqlite_db_path: str,
    gcs_bucket_name: str | None,
) -> VideoSnapshotRepository:
    if backend == "sqlite":
        return SQLiteVideoSnapshotRepository(sqlite_db_path)
    if backend == "gcs_jsonl":
        if not gcs_bucket_name:
            raise RuntimeError("GCS_BUCKET_NAME is required when STORAGE_BACKEND=gcs_jsonl")
        return GCSJsonlVideoSnapshotRepository(gcs_bucket_name)
    raise RuntimeError(f"Unsupported STORAGE_BACKEND: {backend}")


def _snapshot_payload(video: Video, fetched_at: datetime) -> dict[str, object]:
    return {
        "video_id": video.id,
        "fetched_at": fetched_at.isoformat(),
        "title": video.title,
        "create_time": video.create_time.isoformat() if video.create_time else None,
        "view_count": video.view_count,
        "like_count": video.like_count,
        "comment_count": video.comment_count,
        "share_count": video.share_count,
        "video_description": video.video_description,
        "duration": video.duration,
        "share_url": video.share_url,
    }
