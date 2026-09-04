"""Minimal in-memory fakes for google.cloud.storage, used by tests only."""
from __future__ import annotations


class FakeBlob:
    def __init__(self, bucket: "FakeBucket", name: str) -> None:
        self._bucket = bucket
        self.name = name

    def upload_from_string(self, data, content_type: str | None = None) -> None:
        self._bucket.objects[self.name] = data

    def download_as_text(self, encoding: str = "utf-8") -> str:
        data = self._bucket.objects[self.name]
        return data.decode(encoding) if isinstance(data, bytes) else data

    def exists(self) -> bool:
        return self.name in self._bucket.objects


class FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.objects: dict[str, str] = {}

    def blob(self, name: str) -> FakeBlob:
        return FakeBlob(self, name)


class FakeClient:
    def __init__(self) -> None:
        self._buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self._buckets.setdefault(name, FakeBucket(name))

    def list_blobs(self, bucket: FakeBucket, prefix: str = ""):
        for name in sorted(bucket.objects):
            if name.startswith(prefix):
                yield bucket.blob(name)

    def put_text(self, bucket_name: str, object_name: str, text: str) -> None:
        self.bucket(bucket_name).objects[object_name] = text
