from __future__ import annotations

from .analyzer import SessionSummary, analyze_session, finalize_summaries


class GCSStreamHealthSource:
    def __init__(self, bucket_name: str, prefix: str = "stream_health/raw", client=None) -> None:
        if client is None:
            from google.cloud import storage

            client = storage.Client()
        self.client = client
        self.bucket = self.client.bucket(bucket_name)
        self.prefix = prefix.strip("/")

    def analyze(
        self,
        excluded_users=None,
        since: str | None = None,
        until: str | None = None,
        file_patterns=None,
    ) -> list[SessionSummary]:
        excluded_users = excluded_users or set()
        all_summaries: list[SessionSummary] = []
        display_names: set[str] = set()

        for blob in self.client.list_blobs(self.bucket, prefix=f"{self.prefix}/"):
            name = blob.name.rsplit("/", 1)[-1]
            if not name.endswith(".jsonl"):
                continue
            text = blob.download_as_text(encoding="utf-8-sig")
            summary = analyze_session(name, text.splitlines(), excluded_users)
            all_summaries.append(summary)
            display_names.add(name)

        return finalize_summaries(
            all_summaries,
            display_names,
            since=since,
            until=until,
            file_patterns=file_patterns,
        )
