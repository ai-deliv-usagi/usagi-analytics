import json

from src.stream_health.analyzer import (
    analyze_session,
    console_lines,
    finalize_summaries,
    parse_datetime_from_filename,
)


def analyze_dir(tmp_path, excluded_users=None, since=None, until=None, file_patterns=None):
    """Test-only helper: run the analyzer against a local directory of jsonl
    files, mirroring how gcs_source.GCSStreamHealthSource drives it against
    GCS blobs (single prefix used for both history and display)."""
    summaries = []
    names = set()
    for path in sorted(tmp_path.glob("*.jsonl")):
        text = path.read_text(encoding="utf-8-sig")
        summary = analyze_session(path.name, text.splitlines(), excluded_users or set())
        summaries.append(summary)
        names.add(path.name)
    return finalize_summaries(
        summaries, names, since=since, until=until, file_patterns=file_patterns
    )


def write_jsonl(path, records):
    path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False) for record in records),
        encoding="utf-8",
    )


def test_treats_missing_old_fields_as_na(tmp_path):
    log = tmp_path / "old.jsonl"
    write_jsonl(
        log,
        [
            {
                "wall_time": "2026-07-10T10:00:00+09:00",
                "unix_ts": 100.0,
                "type": "comment",
                "user": "operator",
                "text": "local note",
            },
            {
                "wall_time": "2026-07-10T10:00:01+09:00",
                "unix_ts": 101.0,
                "type": "comment",
                "user": "viewer",
                "text": "hello",
            },
            {
                "wall_time": "2026-07-10T10:00:02+09:00",
                "unix_ts": 102.0,
                "type": "playback",
                "text": "hello",
                "response_to_events": [
                    {"type": "comment", "user": "viewer", "ts": 101.0}
                ],
            },
            {
                "wall_time": "2026-07-10T10:00:03+09:00",
                "unix_ts": 103.0,
                "type": "gift",
                "user": "viewer",
                "diamond_count": 0,
            },
        ],
    )

    row = analyze_dir(tmp_path, excluded_users={"operator"})[0].to_row()

    assert row["operator_excluded_comment_count"] == 1
    assert row["unique_event_user_count"] == 1
    assert row["lang_detected_comment_count"] == 0
    assert row["non_ja_comment_ratio"] == ""
    assert row["reaction_speech_ratio"] == ""
    assert row["gift_concentration_top1_ratio"] == ""
    assert row["total_diamonds"] == ""
    assert row["comment_response_median_seconds"] == "1"


def test_excludes_operator_flagged_comments_without_config(tmp_path):
    write_jsonl(
        tmp_path / "operator_flag.jsonl",
        [
            {"type": "comment", "user": "operator", "text": "route check", "is_operator": True},
            {"type": "comment", "user": "viewer", "text": "hello", "lang": "en"},
        ],
    )

    row = analyze_dir(tmp_path)[0].to_row()

    assert row["comment_count"] == 2
    assert row["operator_excluded_comment_count"] == 1
    assert row["unique_event_user_count"] == 1
    assert row["lang_detected_comment_count"] == 1


def test_debug_counts_skipped_lines_and_at_prefixed_filename(tmp_path):
    assert (
        parse_datetime_from_filename("@ai_deliv_usagi_20260710_181601.jsonl")
        == "2026-07-10T18:16:01"
    )

    log = tmp_path / "@ai_deliv_usagi_20260710_181601.jsonl"
    log.write_text(
        "\n".join(
            [
                "",
                json.dumps({"unix_ts": 100.0, "type": "comment", "user": "alice"}, ensure_ascii=False),
                "{not-json",
                json.dumps(["not", "an", "object"], ensure_ascii=False),
                json.dumps({"unix_ts": 101.0, "type": "follow", "user": "alice"}, ensure_ascii=False),
            ]
        ),
        encoding="utf-8",
    )

    summaries = analyze_dir(tmp_path)

    assert summaries[0].started_at == "2026-07-10T18:16:01"
    assert summaries[0].parsed_line_count == 2
    assert summaries[0].skipped_line_count == 3
    assert summaries[0].type_counts == {"comment": 1, "follow": 1}


def test_latest_sort_uses_filename_datetime_when_unix_ts_is_missing(tmp_path):
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260713_073927.jsonl",
        [{"type": "comment", "user": "old"}],
    )
    write_jsonl(
        tmp_path / "ai_deliv_usagi_20260716_210000.jsonl",
        [{"type": "comment", "user": "new"}],
    )

    summaries = analyze_dir(tmp_path)

    assert [summary.name for summary in summaries] == [
        "@ai_deliv_usagi_20260713_073927.jsonl",
        "ai_deliv_usagi_20260716_210000.jsonl",
    ]
    assert "Latest stream: ai_deliv_usagi_20260716_210000.jsonl" in console_lines(summaries)[0]


def test_repeater_rate_uses_full_history_when_display_period_changes(tmp_path):
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260710_100000.jsonl",
        [{"type": "comment", "user": "alice"}],
    )
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260711_100000.jsonl",
        [{"type": "comment", "user": "bob"}],
    )
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260712_100000.jsonl",
        [
            {"type": "comment", "user": "alice"},
            {"type": "follow", "user": "charlie"},
        ],
    )

    latest_one_day = analyze_dir(tmp_path, since="2026-07-12")[-1].to_row()
    latest_two_days = analyze_dir(tmp_path, since="2026-07-11")[-1].to_row()

    assert latest_one_day["stream_file"] == "@ai_deliv_usagi_20260712_100000.jsonl"
    assert latest_one_day["repeater_rate"] == "0.5"
    assert latest_one_day["repeater_display"] == "50.0% (1/2人)"
    assert latest_two_days["repeater_rate"] == latest_one_day["repeater_rate"]


def test_gift_response_split_ignores_during_playback_for_warning(tmp_path):
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260712_100000.jsonl",
        [
            {"type": "playback", "unix_ts": 100.0, "duration": 30.0},
            {"type": "gift", "user": "alice", "unix_ts": 110.0},
            {
                "type": "playback",
                "unix_ts": 140.0,
                "duration": 1.0,
                "response_to_events": [{"type": "gift", "user": "alice", "ts": 110.0}],
            },
        ],
    )

    summary = analyze_dir(tmp_path)[0]

    assert summary.to_row()["gift_response_seconds"] == "30"
    assert summary.to_row()["gift_response_non_playing_seconds"] == ""
    assert summary.to_row()["gift_response_during_playback_seconds"] == "30"
    assert "⚠" not in "\n".join(console_lines([summary]))


def test_gift_response_warns_only_for_slow_non_playing_gift(tmp_path):
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260712_100000.jsonl",
        [
            {"type": "gift", "user": "alice", "unix_ts": 110.0},
            {
                "type": "playback",
                "unix_ts": 121.0,
                "duration": 1.0,
                "response_to_events": [{"type": "gift", "user": "alice", "ts": 110.0}],
            },
        ],
    )

    summary = analyze_dir(tmp_path)[0]

    assert summary.to_row()["gift_response_non_playing_seconds"] == "11"
    assert "⚠" in "\n".join(console_lines([summary]))


def test_console_shows_comment_response_warning_streak(tmp_path):
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260710_100000.jsonl",
        [
            {"type": "comment", "user": "alice", "unix_ts": 100.0},
            {
                "type": "playback",
                "unix_ts": 120.0,
                "response_to_events": [{"type": "comment", "user": "alice", "ts": 100.0}],
            },
        ],
    )
    write_jsonl(
        tmp_path / "@ai_deliv_usagi_20260711_100000.jsonl",
        [
            {"type": "comment", "user": "bob", "unix_ts": 200.0},
            {
                "type": "playback",
                "unix_ts": 218.0,
                "response_to_events": [{"type": "comment", "user": "bob", "ts": 200.0}],
            },
        ],
    )

    lines = console_lines(analyze_dir(tmp_path))

    assert "consecutive >15s: 2 streams" in "\n".join(lines)
