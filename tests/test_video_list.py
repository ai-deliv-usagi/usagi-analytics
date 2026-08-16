from src.tiktok_client.video_list import TikTokVideoListClient


class FakeResponse:
    status_code = 200
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.calls = []

    def post(self, endpoint, params, json, headers, timeout):
        self.calls.append({"endpoint": endpoint, "params": params, "json": json, "headers": headers})
        if len(self.calls) == 1:
            return FakeResponse(
                {
                    "data": {
                        "videos": [{"id": "1", "title": "first"}],
                        "cursor": 12345,
                        "has_more": True,
                    },
                    "error": {"code": "ok"},
                }
            )
        return FakeResponse(
            {
                "data": {
                    "videos": [{"id": "2", "title": "second"}],
                    "has_more": False,
                },
                "error": {"code": "ok"},
            }
        )


def test_fetch_all_videos_uses_cursor_until_has_more_false():
    session = FakeSession()
    client = TikTokVideoListClient(session=session, sleep_seconds=0)

    videos = client.fetch_all_videos("access-token", fields=["id", "title"])

    assert [video.id for video in videos] == ["1", "2"]
    assert session.calls[0]["json"] == {"max_count": 20}
    assert session.calls[1]["json"] == {"max_count": 20, "cursor": 12345}
    assert session.calls[0]["params"] == {"fields": "id,title"}
