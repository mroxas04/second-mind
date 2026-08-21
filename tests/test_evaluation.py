"""Tests for the offline five-question retrieval evaluation."""

from pathlib import Path
import json

import pytest

from second_mind.evaluation import (
    REQUIRED_CASE_COUNT,
    evaluate_retrieval,
    load_evaluation_cases,
)


SAMPLE_DIRECTORY = Path(__file__).parents[1] / "data" / "sample_journals"
SAMPLE_CASES = SAMPLE_DIRECTORY / "retrieval_evaluation.json"


def test_sample_evaluation_defines_exactly_five_questions() -> None:
    cases = load_evaluation_cases(SAMPLE_CASES)

    assert len(cases) == REQUIRED_CASE_COUNT
    assert len({case.identifier for case in cases}) == REQUIRED_CASE_COUNT
    assert sum(case.expects_refusal for case in cases) == 1


def test_sample_evaluation_passes_all_quality_gates() -> None:
    summary = evaluate_retrieval(SAMPLE_DIRECTORY, SAMPLE_CASES)

    assert summary.passed
    assert summary.passed_cases == 5
    assert summary.retrieval_score == (4, 4)
    assert summary.citation_score == (4, 4)
    assert summary.refusal_score == (1, 1)


def test_evaluation_fails_incorrect_expected_citation(tmp_path: Path) -> None:
    raw = json.loads(SAMPLE_CASES.read_text(encoding="utf-8"))
    raw["cases"][0]["expected_date"] = "2026-07-04"
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(raw), encoding="utf-8")

    summary = evaluate_retrieval(SAMPLE_DIRECTORY, cases_path)

    assert not summary.passed
    assert summary.passed_cases == 4
    assert summary.retrieval_score == (4, 4)
    assert summary.citation_score == (3, 4)


def test_evaluation_requires_exactly_five_cases(tmp_path: Path) -> None:
    cases_path = tmp_path / "cases.json"
    cases_path.write_text('{"cases": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="exactly 5 cases"):
        load_evaluation_cases(cases_path)


def test_evaluation_requires_a_refusal_case(tmp_path: Path) -> None:
    raw = json.loads(SAMPLE_CASES.read_text(encoding="utf-8"))
    raw["cases"][4] = dict(raw["cases"][0], id="Q5")
    cases_path = tmp_path / "cases.json"
    cases_path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(ValueError, match="at least one refusal case"):
        load_evaluation_cases(cases_path)
