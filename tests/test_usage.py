"""Tests for privacy-safe local usage evidence."""

from datetime import UTC, datetime
import json
from pathlib import Path

import pytest

from second_mind.usage import (
    UsageCategory,
    generate_usage_report,
    load_usage_records,
    record_usage,
)


def test_record_usage_stores_only_fixed_non_sensitive_fields(tmp_path: Path) -> None:
    log_path = tmp_path / "usage" / "outcomes.jsonl"
    recorded_at = datetime(2027, 1, 3, 14, 30, tzinfo=UTC)

    report = record_usage(
        UsageCategory.CORRECT_ANSWER,
        log_path,
        recorded_at=recorded_at,
    )
    payload = json.loads(log_path.read_text(encoding="utf-8"))

    assert payload == {
        "version": 1,
        "recorded_at": "2027-01-03T14:30:00+00:00",
        "category": "correct-answer",
    }
    assert report.total_uses == 1
    assert report.remaining == 9
    assert not report.ready


def test_report_ranks_top_three_failures_after_ten_uses(tmp_path: Path) -> None:
    log_path = tmp_path / "outcomes.jsonl"
    categories = [
        UsageCategory.WRONG_PASSAGE,
        UsageCategory.CORRECT_ANSWER,
        UsageCategory.WRONG_PASSAGE,
        UsageCategory.INCORRECT_REFUSAL,
        UsageCategory.CORRECT_REFUSAL,
        UsageCategory.CITATION_PROBLEM,
        UsageCategory.WRONG_PASSAGE,
        UsageCategory.INCORRECT_REFUSAL,
        UsageCategory.COMMAND_ERROR,
        UsageCategory.CORRECT_ANSWER,
    ]
    for minute, category in enumerate(categories):
        record_usage(
            category,
            log_path,
            recorded_at=datetime(2027, 1, 4, 12, minute, tzinfo=UTC),
        )

    report = generate_usage_report(log_path)

    assert report.ready
    assert report.remaining == 0
    assert report.total_uses == 10
    assert report.successful_uses == 3
    assert report.failures == 7
    assert [
        (priority.category, priority.count) for priority in report.priorities
    ] == [
        (UsageCategory.WRONG_PASSAGE, 3),
        (UsageCategory.INCORRECT_REFUSAL, 2),
        (UsageCategory.CITATION_PROBLEM, 1),
    ]


def test_report_breaks_failure_count_ties_by_category(tmp_path: Path) -> None:
    log_path = tmp_path / "outcomes.jsonl"
    record_usage(UsageCategory.STALE_INDEX, log_path)
    record_usage(UsageCategory.COMMAND_ERROR, log_path)

    report = generate_usage_report(log_path)

    assert [priority.category for priority in report.priorities] == [
        UsageCategory.COMMAND_ERROR,
        UsageCategory.STALE_INDEX,
    ]


def test_load_usage_records_rejects_free_form_or_sensitive_fields(
    tmp_path: Path,
) -> None:
    log_path = tmp_path / "outcomes.jsonl"
    log_path.write_text(
        '{"version":1,"recorded_at":"2027-01-03T14:30:00+00:00",'
        '"category":"correct-answer","question":"private text"}\n',
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unexpected fields"):
        load_usage_records(log_path)


def test_record_usage_refuses_to_append_to_corrupt_log(tmp_path: Path) -> None:
    log_path = tmp_path / "outcomes.jsonl"
    log_path.write_text("not-json\n", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON"):
        record_usage(UsageCategory.CORRECT_REFUSAL, log_path)

    assert log_path.read_text(encoding="utf-8") == "not-json\n"


def test_record_usage_requires_timezone_aware_timestamp(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="include a timezone"):
        record_usage(
            UsageCategory.CORRECT_ANSWER,
            tmp_path / "outcomes.jsonl",
            recorded_at=datetime(2027, 1, 3, 14, 30),
        )
