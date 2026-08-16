from __future__ import annotations

import argparse
import json
import os
from typing import Any

from flask import Flask, jsonify, request

from src.auth.oauth import TikTokOAuthClient
from src.auth.token_store import build_token_store
from src.config import load_settings, require
from src.storage.repository import build_video_snapshot_repository
from src.tiktok_client.video_list import TikTokVideoListClient


def build_oauth_client() -> TikTokOAuthClient:
    settings = load_settings()
    token_store = build_token_store(
        settings.token_store_backend,
        settings.token_file_path,
        settings.gcp_project_id,
        settings.token_secret_id,
    )
    return TikTokOAuthClient(
        client_key=require(settings.tiktok_client_key, "TIKTOK_CLIENT_KEY"),
        client_secret=require(settings.tiktok_client_secret, "TIKTOK_CLIENT_SECRET"),
        redirect_uri=require(settings.tiktok_redirect_uri, "TIKTOK_REDIRECT_URI"),
        token_store=token_store,
        auth_base_url=settings.tiktok_auth_base_url,
        token_url=settings.tiktok_token_url,
    )


def run_fetch() -> dict[str, Any]:
    settings = load_settings()
    oauth_client = build_oauth_client()
    access_token = oauth_client.get_valid_access_token()
    video_client = TikTokVideoListClient(sleep_seconds=settings.request_sleep_seconds)
    videos = video_client.fetch_all_videos(access_token)
    repository = build_video_snapshot_repository(
        settings.storage_backend,
        settings.sqlite_db_path,
        settings.gcs_bucket_name,
    )
    saved = repository.save_snapshots(videos)
    stats = repository.stats()
    return {
        "fetched_videos": len(videos),
        "saved_snapshots": saved,
        "total_snapshots": stats.snapshots,
        "distinct_videos": stats.distinct_videos,
        "latest_fetched_at": stats.latest_fetched_at,
    }


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def index() -> Any:
        return jsonify({"service": "usagi-analytics", "ok": True})

    @app.get("/oauth/callback")
    def oauth_callback() -> Any:
        code = request.args.get("code")
        error = request.args.get("error")
        if error:
            return jsonify({"ok": False, "error": error}), 400
        if not code:
            return jsonify({"ok": False, "error": "missing code"}), 400
        try:
            token_set = build_oauth_client().exchange_code(code)
        except RuntimeError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        return jsonify(
            {
                "ok": True,
                "open_id": token_set.open_id,
                "scope": token_set.scope,
                "expires_at": token_set.expires_at.isoformat(),
                "refresh_expires_at": (
                    token_set.refresh_expires_at.isoformat()
                    if token_set.refresh_expires_at
                    else None
                ),
            }
        )

    @app.post("/run-fetch")
    def run_fetch_endpoint() -> Any:
        settings = load_settings()
        if settings.run_fetch_token:
            supplied_token = request.headers.get("X-Usagi-Run-Token")
            if supplied_token != settings.run_fetch_token:
                return jsonify({"ok": False, "error": "unauthorized"}), 401
        result = run_fetch()
        return jsonify({"ok": True, **result})

    return app


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="usagi-analytics batch runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("auth-url", help="Print TikTok OAuth authorization URL")

    exchange_parser = subparsers.add_parser("exchange", help="Exchange authorization code")
    exchange_parser.add_argument("--code", required=True)

    subparsers.add_parser("fetch", help="Fetch all TikTok videos and save snapshots")
    subparsers.add_parser("stats", help="Print snapshot stats")
    serve_parser = subparsers.add_parser("serve", help="Run HTTP server")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "8080")))

    args = parser.parse_args(argv)

    if args.command == "auth-url":
        url, state = build_oauth_client().build_authorization_url()
        print(json.dumps({"authorization_url": url, "state": state}, ensure_ascii=False, indent=2))
    elif args.command == "exchange":
        token_set = build_oauth_client().exchange_code(args.code)
        print(
            json.dumps(
                {
                    "open_id": token_set.open_id,
                    "scope": token_set.scope,
                    "expires_at": token_set.expires_at.isoformat(),
                    "refresh_expires_at": (
                        token_set.refresh_expires_at.isoformat()
                        if token_set.refresh_expires_at
                        else None
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    elif args.command == "fetch":
        print(json.dumps(run_fetch(), ensure_ascii=False, indent=2))
    elif args.command == "stats":
        settings = load_settings()
        stats = build_video_snapshot_repository(
            settings.storage_backend,
            settings.sqlite_db_path,
            settings.gcs_bucket_name,
        ).stats()
        print(json.dumps(stats.__dict__, ensure_ascii=False, indent=2))
    elif args.command == "serve":
        create_app().run(host=args.host, port=args.port)


if __name__ == "__main__":
    cli()
