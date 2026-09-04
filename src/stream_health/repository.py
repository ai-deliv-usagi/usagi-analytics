from __future__ import annotations

import json
from pathlib import Path

from .analyzer import SessionSummary


class GCSStreamHealthRepository:
    def __init__(
        self,
        bucket_name: str,
        daily_prefix: str = "stream_health/daily",
        client=None,
    ) -> None:
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self.client = client
        self.bucket = self.client.bucket(bucket_name)
        self.daily_prefix = daily_prefix.strip("/")

    def write_summaries(self, summaries: list[SessionSummary]) -> int:
        index_rows = []
        for summary in summaries:
            row = summary.to_row()
            stem = Path(summary.name).stem
            self.bucket.blob(f"{self.daily_prefix}/{stem}.json").upload_from_string(
                json.dumps(row, ensure_ascii=False, indent=2),
                content_type="application/json",
            )
            index_rows.append(row)

        self.bucket.blob(f"{self.daily_prefix}/index.json").upload_from_string(
            json.dumps(index_rows, ensure_ascii=False, indent=2),
            content_type="application/json",
        )
        return len(index_rows)

    def read_index(self) -> list[dict]:
        blob = self.bucket.blob(f"{self.daily_prefix}/index.json")
        if not blob.exists():
            return []
        return json.loads(blob.download_as_text(encoding="utf-8"))
