"""Record and summarize privacy-safe local usage outcomes."""

from argparse import ArgumentParser
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
import json
import sys


DEFAULT_USAGE_LOG_PATH = Path("data/usage/outcomes.jsonl")
MINIMUM_USES = 10
SCHEMA_VERSION = 1


class UsageCategory(StrEnum):
    """Allowed non-sensitive outcomes for one real Second Mind use."""

    CORRECT_ANSWER = "correct-answer"
    CORRECT_REFUSAL = "correct-refusal"
    MISSED_RELEVANT_PASSAGE = "missed-relevant-passage"
    WRONG_PASSAGE = "wrong-passage"
    UNSUPPORTED_ANSWER = "unsupported-answer"
    INCORRECT_REFUSAL = "incorrect-refusal"
    CITATION_PROBLEM = "citation-problem"
    STALE_INDEX = "stale-index"
    COMMAND_ERROR = "command-error"
    OTHER_FAILURE = "other-failure"


SUCCESS_CATEGORIES = frozenset(
    {UsageCategory.CORRECT_ANSWER, UsageCategory.CORRECT_REFUSAL}
)

CATEGORY_DESCRIPTIONS = {
    UsageCategory.CORRECT_ANSWER: "answer was useful and supported by its citation",
    UsageCategory.CORRECT_REFUSAL: "refusal was appropriate because evidence was absent",
    UsageCategory.MISSED_RELEVANT_PASSAGE: "relevant evidence existed but was not retrieved",
    UsageCategory.WRONG_PASSAGE: "retrieval returned an irrelevant or less relevant passage",
    UsageCategory.UNSUPPORTED_ANSWER: "the system answered without sufficient evidence",
    UsageCategory.INCORRECT_REFUSAL: "the system refused despite relevant evidence",
    UsageCategory.CITATION_PROBLEM: "the answer citation was missing or incorrect",
    UsageCategory.STALE_INDEX: "new or changed journal data was not reflected",
    UsageCategory.COMMAND_ERROR: "the local command failed to complete",
    UsageCategory.OTHER_FAILURE: "another non-sensitive failure category applies",
}


@dataclass(frozen=True, slots=True)
class UsageRecord:
    """One timestamped category without question, answer, or source content."""

    recorded_at: datetime
    category: UsageCategory


@dataclass(frozen=True, slots=True)
class FailurePriority:
    """A ranked failure category and its observed count."""

    category: UsageCategory
    count: int


@dataclass(frozen=True, slots=True)
class UsageReport:
    """Readiness and ranked failure evidence from a local outcome log."""

    total_uses: int
    successful_uses: int
    failures: int
    priorities: tuple[FailurePriority, ...]

    @property
    def ready(self) -> bool:
        """Return whether the log contains the milestone's ten required uses."""

        return self.total_uses >= MINIMUM_USES

    @property
    def remaining(self) -> int:
        """Return the number of additional uses needed for M030."""

        return max(0, MINIMUM_USES - self.total_uses)


def record_usage(
    category: UsageCategory,
    log_path: Path = DEFAULT_USAGE_LOG_PATH,
    *,
    recorded_at: datetime | None = None,
) -> UsageReport:
    """Append one fixed outcome category and return the updated local report.

    The log intentionally has no field for the question, answer, journal text,
    source path, title, or free-form notes.
    """

    existing = load_usage_records(log_path)
    timestamp = recorded_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("recorded_at must include a timezone")

    log_path = log_path.expanduser()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": SCHEMA_VERSION,
        "recorded_at": timestamp.astimezone(UTC).isoformat(),
        "category": category.value,
    }
    with log_path.open("a", encoding="utf-8", newline="\n") as destination:
        destination.write(json.dumps(payload, separators=(",", ":")) + "\n")

    return build_usage_report((*existing, UsageRecord(timestamp, category)))


def load_usage_records(log_path: Path = DEFAULT_USAGE_LOG_PATH) -> tuple[UsageRecord, ...]:
    """Load and strictly validate a local non-sensitive outcome log."""

    log_path = log_path.expanduser()
    if not log_path.exists():
        return ()
    if not log_path.is_file() or log_path.is_symlink():
        raise ValueError(f"usage log is not a regular file: {log_path}")

    records: list[UsageRecord] = []
    for line_number, raw_line in enumerate(
        log_path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        if not raw_line:
            raise ValueError(f"usage log line {line_number} is blank")
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError as error:
            raise ValueError(f"usage log line {line_number} is invalid JSON") from error
        records.append(_record_from_payload(payload, line_number))
    return tuple(records)


def build_usage_report(records: Sequence[UsageRecord]) -> UsageReport:
    """Build milestone readiness and top-three failure priorities."""

    failure_counts = Counter(
        record.category
        for record in records
        if record.category not in SUCCESS_CATEGORIES
    )
    ranked = sorted(
        failure_counts.items(),
        key=lambda item: (-item[1], item[0].value),
    )[:3]
    successes = sum(record.category in SUCCESS_CATEGORIES for record in records)
    return UsageReport(
        total_uses=len(records),
        successful_uses=successes,
        failures=len(records) - successes,
        priorities=tuple(
            FailurePriority(category=category, count=count)
            for category, count in ranked
        ),
    )


def generate_usage_report(log_path: Path = DEFAULT_USAGE_LOG_PATH) -> UsageReport:
    """Load the local outcome log and return its milestone report."""

    return build_usage_report(load_usage_records(log_path))


def main(argv: Sequence[str] | None = None) -> int:
    """Record a fixed outcome category or print the local usage report."""

    parser = ArgumentParser(
        prog="second-mind-usage",
        description=(
            "Record only non-sensitive outcome categories; never questions, "
            "answers, journal text, sources, or free-form notes."
        ),
    )
    parser.add_argument("--log", type=Path, default=DEFAULT_USAGE_LOG_PATH)
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="record one use outcome")
    record_parser.add_argument(
        "category",
        choices=[category.value for category in UsageCategory],
    )
    subparsers.add_parser("report", help="rank failures after ten uses")
    subparsers.add_parser("categories", help="describe the allowed categories")

    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "record":
            report = record_usage(UsageCategory(arguments.category), arguments.log)
            print(
                f"recorded=1 | category={arguments.category} | "
                f"uses={report.total_uses} | remaining={report.remaining}"
            )
            return 0
        if arguments.command == "categories":
            _print_categories()
            return 0
        report = generate_usage_report(arguments.log)
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    _print_report(report)
    return 0


def _record_from_payload(payload: object, line_number: int) -> UsageRecord:
    if not isinstance(payload, dict) or set(payload) != {
        "version",
        "recorded_at",
        "category",
    }:
        raise ValueError(f"usage log line {line_number} has unexpected fields")
    if payload["version"] != SCHEMA_VERSION:
        raise ValueError(f"usage log line {line_number} has an unsupported version")
    try:
        category = UsageCategory(payload["category"])
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"usage log line {line_number} has an invalid category"
        ) from error
    try:
        recorded_at = datetime.fromisoformat(payload["recorded_at"])
    except (TypeError, ValueError) as error:
        raise ValueError(
            f"usage log line {line_number} has an invalid timestamp"
        ) from error
    if recorded_at.tzinfo is None or recorded_at.utcoffset() is None:
        raise ValueError(f"usage log line {line_number} has a naive timestamp")
    return UsageRecord(recorded_at=recorded_at, category=category)


def _print_categories() -> None:
    for category in UsageCategory:
        print(f"{category.value}: {CATEGORY_DESCRIPTIONS[category]}")


def _print_report(report: UsageReport) -> None:
    ready = "yes" if report.ready else "no"
    print(
        f"ready={ready} | uses={report.total_uses} | "
        f"remaining={report.remaining} | successful={report.successful_uses} | "
        f"failures={report.failures}"
    )
    for position, priority in enumerate(report.priorities, start=1):
        print(
            f"priority={position} | category={priority.category.value} | "
            f"count={priority.count}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
