import json

from src.stream_health.gcs_source import GCSStreamHealthSource
from src.stream_health.repository import GCSStreamHealthRepository
from tests.fakes_gcs import FakeClient


def jsonl(records):
    return "\n".join(json.dumps(record, ensure_ascii=False) for record in records)


def test_gcs_source_analyzes_blobs_under_prefix():
    client = FakeClient()
    client.put_text(
        "bucket",
        "stream_health/raw/@ai_deliv_usagi_20260710_100000.jsonl",
        jsonl([{"type": "comment", "user": "alice"}]),
    )
    client.put_text(
        "bucket",
        "stream_health/raw/@ai_deliv_usagi_20260711_100000.jsonl",
        jsonl([{"type": "comment", "user": "alice"}, {"type": "follow", "user": "bob"}]),
    )
    client.put_text("bucket", "stream_health/other/ignored.jsonl", jsonl([{"type": "comment"}]))

    source = GCSStreamHealthSource("bucket", prefix="stream_health/raw", client=client)
    summaries = source.analyze()

    assert [summary.name for summary in summaries] == [
        "@ai_deliv_usagi_20260710_100000.jsonl",
        "@ai_deliv_usagi_20260711_100000.jsonl",
    ]
    assert summaries[-1].to_row()["repeater_rate"] == "0.5"


def test_gcs_repository_writes_per_stream_and_index_json():
    client = FakeClient()
    source = GCSStreamHealthSource("bucket", prefix="stream_health/raw", client=client)
    client.put_text(
        "bucket",
        "stream_health/raw/@ai_deliv_usagi_20260710_100000.jsonl",
        jsonl([{"type": "comment", "user": "alice"}]),
    )
    summaries = source.analyze()

    repository = GCSStreamHealthRepository("bucket", daily_prefix="stream_health/daily", client=client)
    written = repository.write_summaries(summaries)

    assert written == 1
    bucket = client.bucket("bucket")
    per_stream = json.loads(bucket.objects["stream_health/daily/@ai_deliv_usagi_20260710_100000.json"])
    assert per_stream["stream_file"] == "@ai_deliv_usagi_20260710_100000.jsonl"

    index = repository.read_index()
    assert index == [per_stream]


def test_gcs_repository_read_index_returns_empty_list_when_missing():
    client = FakeClient()
    repository = GCSStreamHealthRepository("bucket", client=client)

    assert repository.read_index() == []
