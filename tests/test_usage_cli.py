"""End-to-end tests for the local usage-evidence command."""

from pathlib import Path
import subprocess
import sys


def run_usage(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the usage module in the active test environment."""

    return subprocess.run(
        [sys.executable, "-m", "second_mind.usage", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_cli_records_and_reports_without_content(tmp_path: Path) -> None:
    log_path = tmp_path / "outcomes.jsonl"

    recorded = run_usage(
        "--log",
        str(log_path),
        "record",
        "wrong-passage",
    )
    reported = run_usage("--log", str(log_path), "report")

    assert recorded.returncode == 0
    assert recorded.stderr == ""
    assert recorded.stdout == (
        "recorded=1 | category=wrong-passage | uses=1 | remaining=9\n"
    )
    assert reported.returncode == 0
    assert reported.stderr == ""
    assert reported.stdout == (
        "ready=no | uses=1 | remaining=9 | successful=0 | failures=1\n"
        "priority=1 | category=wrong-passage | count=1\n"
    )
    assert "question" not in log_path.read_text(encoding="utf-8")
    assert "answer" not in log_path.read_text(encoding="utf-8")


def test_cli_lists_fixed_categories() -> None:
    result = run_usage("categories")

    assert result.returncode == 0
    assert result.stderr == ""
    assert "correct-answer: answer was useful" in result.stdout
    assert "other-failure: another non-sensitive failure category applies" in (
        result.stdout
    )


def test_cli_reports_corrupt_log(tmp_path: Path) -> None:
    log_path = tmp_path / "outcomes.jsonl"
    log_path.write_text("not-json\n", encoding="utf-8")

    result = run_usage("--log", str(log_path), "report")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "usage log line 1 is invalid JSON" in result.stderr
