from src.main import create_app


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
