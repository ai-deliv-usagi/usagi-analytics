from src.main import create_app
from src.stream_health.analyzer import analyze_session


def test_dashboard_renders_rows_from_stream_health_repository(monkeypatch):
    monkeypatch.setenv("STREAM_HEALTH_BUCKET_NAME", "bucket")

    class FakeRepository:
        def __init__(self, *args, **kwargs):
            pass

        def read_index(self):
            return [analyze_session("stream.jsonl", [], set()).to_row()]

    monkeypatch.setattr("src.main.GCSStreamHealthRepository", FakeRepository)
    app = create_app()

    response = app.test_client().get("/dashboard")

    assert response.status_code == 200
    assert b"stream.jsonl" in response.data


def test_dashboard_uses_available_chartjs_and_handles_load_failure(monkeypatch):
    monkeypatch.setenv("STREAM_HEALTH_BUCKET_NAME", "bucket")

    class FakeRepository:
        def __init__(self, *args, **kwargs):
            pass

        def read_index(self):
            return [analyze_session("stream.jsonl", [], set()).to_row()]

    monkeypatch.setattr("src.main.GCSStreamHealthRepository", FakeRepository)
    response = create_app().test_client().get("/dashboard")
    html = response.get_data(as_text=True)

    assert "Chart.js/4.5.1/chart.umd.min.js" in html
    assert 'typeof Chart === "undefined"' in html
    assert "グラフを読み込めませんでした" in html
    assert "判断基準:" in html
    assert "危険ライン" in html
    assert "rows.map(dateLabel)" in html
    assert 'month: "numeric", day: "numeric"' in html
    assert 'hour: "2-digit"' not in html
    assert "gift_response_non_playing_seconds" in html


def test_run_stream_health_endpoint_reports_analyzed_and_written_counts(monkeypatch):
    monkeypatch.setenv("STREAM_HEALTH_BUCKET_NAME", "bucket")

    summary = analyze_session("stream.jsonl", [], set())

    class FakeSource:
        def __init__(self, *args, **kwargs):
            pass

        def analyze(self, *args, **kwargs):
            return [summary]

    class FakeRepository:
        def __init__(self, *args, **kwargs):
            pass

        def write_summaries(self, summaries):
            return len(summaries)

    monkeypatch.setattr("src.main.GCSStreamHealthSource", FakeSource)
    monkeypatch.setattr("src.main.GCSStreamHealthRepository", FakeRepository)
    app = create_app()

    response = app.test_client().post("/run-stream-health")

    assert response.status_code == 200
    assert response.get_json() == {
        "ok": True,
        "analyzed_streams": 1,
        "written_summaries": 1,
        "latest_stream": "stream.jsonl",
    }


def test_run_fetch_requires_header_when_token_is_configured(monkeypatch):
    monkeypatch.setenv("RUN_FETCH_TOKEN", "secret-token")
    app = create_app()

    response = app.test_client().post("/run-fetch")

    assert response.status_code == 401


def test_oauth_callback_returns_bad_request_for_exchange_error(monkeypatch):
    class FailingOAuthClient:
        def exchange_code(self, code):
            raise RuntimeError("TikTok OAuth error: invalid_grant")

    monkeypatch.setattr("src.main.build_oauth_client", lambda: FailingOAuthClient())
    app = create_app()

    response = app.test_client().get("/oauth/callback?code=test-code")

    assert response.status_code == 400
    assert response.get_json()["error"] == "TikTok OAuth error: invalid_grant"
