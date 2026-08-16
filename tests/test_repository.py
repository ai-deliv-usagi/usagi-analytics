from datetime import datetime, timezone

from src.storage.repository import SQLiteVideoSnapshotRepository
from src.tiktok_client.models import Video


def test_save_snapshots_keeps_history(tmp_path):
    repo = SQLiteVideoSnapshotRepository(str(tmp_path / "snapshots.sqlite3"))
    video = Video(
        id="123",
        title="title",
        create_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        view_count=10,
        like_count=2,
        comment_count=1,
        share_count=0,
        video_description="description",
        duration=12,
        share_url="https://example.test/video/123",
    )

    repo.save_snapshots([video], fetched_at=datetime(2026, 1, 2, tzinfo=timezone.utc))
    repo.save_snapshots([video], fetched_at=datetime(2026, 1, 3, tzinfo=timezone.utc))

    stats = repo.stats()
    assert stats.snapshots == 2
    assert stats.distinct_videos == 1
