"""End-to-end tests for the five-question evaluation CLI."""

from pathlib import Path
import subprocess
import sys


SAMPLE_DIRECTORY = Path(__file__).parents[1] / "data" / "sample_journals"
SAMPLE_CASES = SAMPLE_DIRECTORY / "retrieval_evaluation.json"


def run_evaluation(*arguments: str) -> subprocess.CompletedProcess[str]:
    """Run the evaluation module in the active test environment."""

    return subprocess.run(
        [sys.executable, "-m", "second_mind.evaluation", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )


def test_evaluation_cli_prints_passing_scorecard() -> None:
    result = run_evaluation(str(SAMPLE_DIRECTORY), str(SAMPLE_CASES))

    assert result.returncode == 0
    assert result.stderr == ""
    assert result.stdout.count("case=Q") == 5
    assert "case=Q5 | status=pass" in result.stdout
    assert "refusal=pass | source=<none>" in result.stdout
    assert (
        "summary=pass | cases=5/5 | retrieval=4/4 | "
        "citations=4/4 | refusals=1/1"
    ) in result.stdout


def test_evaluation_cli_rejects_wrong_case_count(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text('{"cases": []}', encoding="utf-8")

    result = run_evaluation(str(SAMPLE_DIRECTORY), str(cases_path))

    assert result.returncode == 1
    assert result.stdout == ""
    assert "evaluation file must contain exactly 5 cases" in result.stderr
