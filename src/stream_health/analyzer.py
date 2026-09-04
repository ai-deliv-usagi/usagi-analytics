from __future__ import annotations

import fnmatch
import re
import statistics
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Iterable

import json


CSV_FIELDS = [
    "stream_file",
    "started_at",
    "ended_at",
    "duration_seconds",
    "record_count",
    "comment_count",
    "operator_excluded_comment_count",
    "gift_count",
    "follow_count",
    "unique_event_user_count",
    "lang_detected_comment_count",
    "non_ja_comment_ratio",
    "repeater_rate",
    "repeater_count",
    "repeater_denominator",
    "repeater_display",
    "comment_response_median_seconds",
    "gift_response_seconds",
    "gift_response_non_playing_seconds",
    "gift_response_during_playback_seconds",
    "reaction_speech_ratio",
    "gift_concentration_top1_ratio",
    "total_diamonds",
    "follow_conversion_rate",
]

REACTION_SPEECH_CATEGORIES = {
    "join_reaction",
    "join_gift_reaction",
    "gift_reaction",
    "follow_reaction",
    "join_bulk_reaction",
}

METRIC_LABELS = {
    "non_ja_comment_ratio": "非日本語コメント比率",
    "repeater_rate": "リピーター率",
    "comment_response_median_seconds": "コメント応答中央値",
    "gift_response_seconds": "ギフト応答時間",
    "reaction_speech_ratio": "反応系発話比率",
    "gift_concentration_top1_ratio": "ギフト集中度",
    "follow_conversion_rate": "フォロー転換率",
}

CRITERIA = {
    "non_ja_comment_ratio": "傾向観察のみ。閾値なし",
    "repeater_rate": "上昇傾向=健全。3配信連続低下で黄信号",
    "comment_response_median_seconds": "15秒超が2配信続いたら劣化調査",
    "gift_response_seconds": "非再生中発生分が10秒超なら要調査",
    "reaction_speech_ratio": "30%超で発話予算の設定見直し",
    "gift_concentration_top1_ratio": "単日でなく4週移動平均で見る",
    "follow_conversion_rate": "傾向観察のみ",
}

COMMENT_RESPONSE_WARNING_SECONDS = 15.0

FILENAME_DATETIME_RE = re.compile(r"(?:^|_)(\d{8})_(\d{6})(?:\.|_|$)")


@dataclass
class SessionSummary:
    name: str
    started_at: str = ""
    ended_at: str = ""
    duration_seconds: float | None = None
    record_count: int = 0
    comment_count: int = 0
    operator_excluded_comment_count: int = 0
    gift_count: int = 0
    follow_count: int = 0
    unique_event_users: set[str] = field(default_factory=set)
    lang_detected_comment_count: int = 0
    non_ja_comment_ratio: float | None = None
    repeater_rate: float | None = None
    repeater_count: int | None = None
    repeater_denominator: int | None = None
    comment_response_median_seconds: float | None = None
    gift_response_seconds: list[float] = field(default_factory=list)
    gift_response_non_playing_seconds: list[float] = field(default_factory=list)
    gift_response_during_playback_seconds: list[float] = field(default_factory=list)
    reaction_speech_ratio: float | None = None
    gift_concentration_top1_ratio: float | None = None
    total_diamonds: int | None = None
    follow_conversion_rate: float | None = None
    parsed_line_count: int = 0
    skipped_line_count: int = 0
    type_counts: Counter = field(default_factory=Counter)
    filename_started_at: str = ""
    _filename_sort_ts: float | None = None
    _first_ts: float | None = None
    _last_ts: float | None = None

    def sort_key(self):
        if self._first_ts is not None:
            timestamp = self._first_ts
        elif self._filename_sort_ts is not None:
            timestamp = self._filename_sort_ts
        else:
            timestamp = float("inf")
        return (timestamp, self.name)

    def matches_pattern(self, pattern: str) -> bool:
        return fnmatch.fnmatch(self.name, pattern) or self.name == pattern

    def to_row(self):
        return {
            "stream_file": self.name,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": format_number(self.duration_seconds),
            "record_count": self.record_count,
            "comment_count": self.comment_count,
            "operator_excluded_comment_count": self.operator_excluded_comment_count,
            "gift_count": self.gift_count,
            "follow_count": self.follow_count,
            "unique_event_user_count": len(self.unique_event_users),
            "lang_detected_comment_count": self.lang_detected_comment_count,
            "non_ja_comment_ratio": format_ratio(self.non_ja_comment_ratio),
            "repeater_rate": format_ratio(self.repeater_rate),
            "repeater_count": "" if self.repeater_count is None else self.repeater_count,
            "repeater_denominator": (
                "" if self.repeater_denominator is None else self.repeater_denominator
            ),
            "repeater_display": format_repeater_display(
                self.repeater_rate, self.repeater_count, self.repeater_denominator
            ),
            "comment_response_median_seconds": format_number(
                self.comment_response_median_seconds
            ),
            "gift_response_seconds": ";".join(
                format_number(value) for value in self.gift_response_seconds
            ),
            "gift_response_non_playing_seconds": ";".join(
                format_number(value) for value in self.gift_response_non_playing_seconds
            ),
            "gift_response_during_playback_seconds": ";".join(
                format_number(value)
                for value in self.gift_response_during_playback_seconds
            ),
            "reaction_speech_ratio": format_ratio(self.reaction_speech_ratio),
            "gift_concentration_top1_ratio": format_ratio(
                self.gift_concentration_top1_ratio
            ),
            "total_diamonds": "" if self.total_diamonds is None else self.total_diamonds,
            "follow_conversion_rate": format_ratio(self.follow_conversion_rate),
        }


def format_number(value):
    if value is None:
        return ""
    return f"{value:.3f}".rstrip("0").rstrip(".")


def format_ratio(value):
    if value is None:
        return ""
    return f"{value:.6f}".rstrip("0").rstrip(".")


def format_repeater_display(rate, count, denominator):
    if rate is None or count is None or denominator is None:
        return ""
    return f"{format_percent(rate)} ({count}/{denominator}人)"


def parse_datetime_from_filename(name: str) -> str:
    value = parse_filename_datetime_value(name)
    if value is None:
        return ""
    return value.isoformat()


def parse_filename_datetime_value(name: str):
    match = FILENAME_DATETIME_RE.search(name)
    if not match:
        return None
    value = "".join(match.groups())
    try:
        return datetime.strptime(value, "%Y%m%d%H%M%S")
    except ValueError:
        return None


def iter_records(name: str, lines: Iterable[str], summary: SessionSummary):
    for line in lines:
        line = line.strip()
        if not line:
            summary.skipped_line_count += 1
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            summary.skipped_line_count += 1
            continue
        if not isinstance(record, dict):
            summary.skipped_line_count += 1
            continue
        summary.parsed_line_count += 1
        yield record


def analyze_session(name: str, lines: Iterable[str], excluded_users) -> SessionSummary:
    summary = SessionSummary(name=name)
    summary.filename_started_at = parse_datetime_from_filename(name)
    filename_datetime = parse_filename_datetime_value(name)
    if filename_datetime is not None:
        summary._filename_sort_ts = filename_datetime.timestamp()
    summary.started_at = summary.filename_started_at
    records = list(iter_records(name, lines, summary))
    playback_intervals = build_playback_intervals(records)
    non_ja_comments = 0
    comment_response_times = []
    gifter_diamonds = {}
    playback_count = 0
    categorized_playback_count = 0
    reaction_playback_count = 0

    for record in records:
        summary.record_count += 1
        ts = numeric(record.get("unix_ts"))
        if ts is not None:
            summary._first_ts = ts if summary._first_ts is None else min(summary._first_ts, ts)
            summary._last_ts = ts if summary._last_ts is None else max(summary._last_ts, ts)
        if (
            record.get("wall_time")
            and (not summary.started_at or summary.started_at == summary.filename_started_at)
        ):
            summary.started_at = record["wall_time"]
        if record.get("wall_time"):
            summary.ended_at = record["wall_time"]

        event_type = record.get("type")
        summary.type_counts[str(event_type or "(missing)")] += 1
        user = clean_user(record.get("user"))
        is_excluded_comment = event_type == "comment" and (
            bool(record.get("is_operator")) or user in excluded_users
        )

        if event_type == "comment":
            summary.comment_count += 1
            if is_excluded_comment:
                summary.operator_excluded_comment_count += 1
            else:
                if user:
                    summary.unique_event_users.add(user)
                lang = record.get("lang")
                if lang:
                    summary.lang_detected_comment_count += 1
                    if lang != "ja":
                        non_ja_comments += 1
        elif event_type == "gift":
            summary.gift_count += 1
            if user:
                summary.unique_event_users.add(user)
                diamonds = gift_diamonds(record)
                if diamonds is not None:
                    gifter_diamonds[user] = gifter_diamonds.get(user, 0) + diamonds
        elif event_type == "follow":
            summary.follow_count += 1
            if user:
                summary.unique_event_users.add(user)

        if event_type == "playback":
            playback_count += 1
            category = speech_category(record)
            if category:
                categorized_playback_count += 1
                if category in REACTION_SPEECH_CATEGORIES:
                    reaction_playback_count += 1
            if ts is not None:
                for event in record.get("response_to_events") or []:
                    event_ts = numeric(event.get("ts"))
                    if event_ts is None:
                        continue
                    delay = round(ts - event_ts, 3)
                    if event.get("type") == "comment":
                        comment_response_times.append(delay)
                    elif event.get("type") == "gift":
                        summary.gift_response_seconds.append(delay)
                        if event_was_during_playback(event_ts, playback_intervals):
                            summary.gift_response_during_playback_seconds.append(delay)
                        else:
                            summary.gift_response_non_playing_seconds.append(delay)

    if summary._first_ts is not None and summary._last_ts is not None:
        summary.duration_seconds = round(summary._last_ts - summary._first_ts, 3)
    if summary.lang_detected_comment_count:
        summary.non_ja_comment_ratio = non_ja_comments / summary.lang_detected_comment_count
    if comment_response_times:
        summary.comment_response_median_seconds = round(
            statistics.median(comment_response_times), 3
        )
    if playback_count and categorized_playback_count:
        summary.reaction_speech_ratio = reaction_playback_count / playback_count
    if gifter_diamonds:
        total = sum(gifter_diamonds.values())
        if total > 0:
            summary.total_diamonds = total
            summary.gift_concentration_top1_ratio = max(gifter_diamonds.values()) / total
    if summary.unique_event_users:
        summary.follow_conversion_rate = summary.follow_count / len(summary.unique_event_users)
    return summary


def build_playback_intervals(records):
    intervals = []
    for record in records:
        if record.get("type") != "playback":
            continue
        start = numeric(record.get("unix_ts"))
        duration = numeric(record.get("duration"))
        if start is None or duration is None or duration <= 0:
            continue
        intervals.append((start, start + duration))
    return intervals


def event_was_during_playback(event_ts, playback_intervals):
    return any(start <= event_ts < end for start, end in playback_intervals)


def clean_user(value):
    if value is None:
        return ""
    return str(value).strip()


def numeric(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def gift_diamonds(record):
    total = numeric(record.get("total_diamonds"))
    if total is not None:
        return int(total)
    diamond_count = numeric(record.get("diamond_count"))
    repeat_count = numeric(record.get("repeat_count")) or 1
    if diamond_count is None:
        return None
    return int(diamond_count * repeat_count)


def speech_category(record):
    category = record.get("speech_category")
    if category:
        return str(category)
    metadata = record.get("metadata")
    if isinstance(metadata, dict) and metadata.get("speech_category"):
        return str(metadata["speech_category"])
    return ""


def finalize_summaries(
    all_summaries: list[SessionSummary],
    display_names: set[str],
    since=None,
    until=None,
    file_patterns=None,
) -> list[SessionSummary]:
    """Sort by time, compute repeater rate against the full history, then
    filter down to the display subset and the since/until/file window."""
    all_summaries = sorted(all_summaries, key=lambda item: item.sort_key())
    seen_users: set[str] = set()
    for summary in all_summaries:
        if summary.unique_event_users:
            repeaters = summary.unique_event_users & seen_users
            summary.repeater_count = len(repeaters)
            summary.repeater_denominator = len(summary.unique_event_users)
            summary.repeater_rate = len(repeaters) / len(summary.unique_event_users)
        seen_users.update(summary.unique_event_users)
    return [
        summary
        for summary in all_summaries
        if summary.name in display_names
        and summary_matches_filters(summary, since, until, file_patterns)
    ]


def summary_matches_filters(summary, since, until, file_patterns):
    timestamp = summary_sort_timestamp(summary)
    since_ts = parse_filter_timestamp(since, is_until=False)
    until_ts = parse_filter_timestamp(until, is_until=True)
    if since_ts is not None and (timestamp is None or timestamp < since_ts):
        return False
    if until_ts is not None and (timestamp is None or timestamp > until_ts):
        return False
    if file_patterns:
        return any(summary.matches_pattern(pattern) for pattern in file_patterns)
    return True


def summary_sort_timestamp(summary):
    if summary._first_ts is not None:
        return summary._first_ts
    return summary._filename_sort_ts


def parse_filter_timestamp(value, is_until):
    if not value:
        return None
    text = str(value)
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
            suffix = "T23:59:59.999999" if is_until else "T00:00:00"
            return datetime.fromisoformat(text + suffix).timestamp()
        return datetime.fromisoformat(text).timestamp()
    except ValueError as exc:
        raise ValueError(f"Invalid date/time filter: {value}") from exc


def write_csv(summaries, output_path):
    import csv

    with Path(output_path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for summary in summaries:
            writer.writerow(summary.to_row())


def metric_value(summary, key):
    if key == "gift_response_seconds":
        values = summary.gift_response_non_playing_seconds
        return max(values) if values else None
    return getattr(summary, key)


def moving_average_delta(summaries, key):
    if len(summaries) < 2:
        return None
    latest = metric_value(summaries[-1], key)
    previous = [
        metric_value(summary, key)
        for summary in summaries[-6:-1]
        if metric_value(summary, key) is not None
    ]
    if latest is None or not previous:
        return None
    average = sum(previous) / len(previous)
    if average == 0:
        return None
    return (latest - average) / average


def warning_for(summaries, key):
    latest = summaries[-1]
    if key == "repeater_rate" and len(summaries) >= 3:
        values = [summary.repeater_rate for summary in summaries[-3:]]
        if all(value is not None for value in values) and values[0] > values[1] > values[2]:
            return True
    if key == "comment_response_median_seconds" and len(summaries) >= 2:
        values = [summary.comment_response_median_seconds for summary in summaries[-2:]]
        if all(
            value is not None and value > COMMENT_RESPONSE_WARNING_SECONDS
            for value in values
        ):
            return True
    if key == "gift_response_seconds":
        return any(value > 10 for value in latest.gift_response_non_playing_seconds)
    if key == "reaction_speech_ratio":
        return (
            latest.reaction_speech_ratio is not None
            and latest.reaction_speech_ratio > 0.30
        )
    return False


def comment_response_warning_streak(summaries):
    streak = 0
    for summary in reversed(summaries):
        value = summary.comment_response_median_seconds
        if value is None or value <= COMMENT_RESPONSE_WARNING_SECONDS:
            break
        streak += 1
    return streak


def console_lines(summaries):
    if not summaries:
        return ["No JSONL files found."]
    latest = summaries[-1]
    lines = [
        f"Latest stream: {latest.name} started_at={latest.started_at or 'N/A'}"
    ]
    for key, label in METRIC_LABELS.items():
        value = metric_value(latest, key)
        if key == "gift_response_seconds":
            value_text = format_gift_response_display(latest)
        elif key == "repeater_rate":
            value_text = format_repeater_display(
                latest.repeater_rate,
                latest.repeater_count,
                latest.repeater_denominator,
            ) or "N/A"
        elif "ratio" in key or key.endswith("_rate"):
            value_text = format_percent(value)
        else:
            value_text = format_number(value) if value is not None else "N/A"
        delta = moving_average_delta(summaries, key)
        delta_text = "N/A" if delta is None else f"{delta:+.1%}"
        if len(summaries) < 10 and delta is not None:
            delta_text += " (参考値)"
        prefix = "⚠ " if warning_for(summaries, key) else ""
        streak_text = ""
        if key == "comment_response_median_seconds":
            streak = comment_response_warning_streak(summaries)
            streak_text = (
                f" / consecutive >{format_number(COMMENT_RESPONSE_WARNING_SECONDS)}s: "
                f"{streak} streams"
            )
        if streak_text:
            value_text += streak_text
        lines.append(
            f"{prefix}{label}: {value_text} / 直近5配信平均との差分 {delta_text} / 判断基準: {CRITERIA[key]}"
        )
    return lines


def format_gift_response_display(summary):
    non_playing = (
        ", ".join(format_number(value) + "s" for value in summary.gift_response_non_playing_seconds)
        if summary.gift_response_non_playing_seconds
        else "N/A"
    )
    during_playback = (
        ", ".join(
            format_number(value) + "s"
            for value in summary.gift_response_during_playback_seconds
        )
        if summary.gift_response_during_playback_seconds
        else "N/A"
    )
    return f"非再生中: {non_playing} / 再生中着弾: {during_playback}"


def format_percent(value):
    if value is None:
        return "N/A"
    return f"{value:.1%}"
