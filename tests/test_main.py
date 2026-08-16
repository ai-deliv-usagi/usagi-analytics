from src.main import create_app


def test_run_fetch_requires_header_when_token_is_configured(monkeypatch):
    monkeypatch.setenv("RUN_FETCH_TOKEN", "secret-token")
    app = create_app()

    response = app.test_client().post("/run-fetch")

    assert response.status_code == 401
