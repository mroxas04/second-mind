"""Offline five-question retrieval evaluation with citation scoring."""

from argparse import ArgumentParser
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import sys

from second_mind.embeddings import Embedder, HashingEmbedder
from second_mind.index import index_journals
from second_mind.retrieval import RetrievedPassage, retrieve_passages


REQUIRED_CASE_COUNT = 5


@dataclass(frozen=True, slots=True)
class RetrievalEvaluationCase:
    """One question and its expected source metadata or refusal outcome."""

    identifier: str
    question: str
    expected_source: str | None
    expected_date: date | None
    expected_title: str | None
    expected_chunk: int | None

    @property
    def expects_refusal(self) -> bool:
        """Return whether this case expects no evidence-positive passage."""

        return self.expected_source is None


@dataclass(frozen=True, slots=True)
class EvaluationCaseResult:
    """Scored retrieval, citation, and refusal outcomes for one case."""

    case: RetrievalEvaluationCase
    passage: RetrievedPassage | None
    retrieval_passed: bool | None
    citation_passed: bool | None
    refusal_passed: bool | None

    @property
    def passed(self) -> bool:
        """Return whether every applicable criterion passed."""

        applicable = tuple(
            result
            for result in (
                self.retrieval_passed,
                self.citation_passed,
                self.refusal_passed,
            )
            if result is not None
        )
        return bool(applicable) and all(applicable)


@dataclass(frozen=True, slots=True)
class EvaluationSummary:
    """Aggregate scores for a five-question retrieval evaluation."""

    results: tuple[EvaluationCaseResult, ...]

    @property
    def passed_cases(self) -> int:
        """Return the number of cases whose applicable criteria passed."""

        return sum(result.passed for result in self.results)

    @property
    def retrieval_score(self) -> tuple[int, int]:
        """Return passed and applicable top-passage retrieval counts."""

        return _criterion_score(self.results, "retrieval_passed")

    @property
    def citation_score(self) -> tuple[int, int]:
        """Return passed and applicable citation-accuracy counts."""

        return _criterion_score(self.results, "citation_passed")

    @property
    def refusal_score(self) -> tuple[int, int]:
        """Return passed and applicable insufficient-evidence refusal counts."""

        return _criterion_score(self.results, "refusal_passed")

    @property
    def passed(self) -> bool:
        """Return whether all five cases and every criterion passed."""

        return (
            len(self.results) == REQUIRED_CASE_COUNT
            and self.passed_cases == REQUIRED_CASE_COUNT
        )


def load_evaluation_cases(path: Path) -> list[RetrievalEvaluationCase]:
    """Load and validate exactly five retrieval cases from a JSON file."""

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"evaluation file is not valid JSON: {error}") from error

    if not isinstance(raw, Mapping) or not isinstance(raw.get("cases"), list):
        raise ValueError("evaluation file must contain a 'cases' list")

    cases = [
        _case_from_mapping(item, position)
        for position, item in enumerate(raw["cases"], start=1)
    ]
    if len(cases) != REQUIRED_CASE_COUNT:
        raise ValueError(
            f"evaluation file must contain exactly {REQUIRED_CASE_COUNT} cases"
        )
    identifiers = [case.identifier for case in cases]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("evaluation case identifiers must be unique")
    if not any(case.expects_refusal for case in cases):
        raise ValueError("evaluation file must contain at least one refusal case")
    if all(case.expects_refusal for case in cases):
        raise ValueError(
            "evaluation file must contain at least one evidence-positive case"
        )
    return cases


def evaluate_retrieval(
    journal_directory: Path,
    cases_path: Path,
    *,
    embedder: Embedder | None = None,
) -> EvaluationSummary:
    """Index journals temporarily and score exactly five retrieval questions."""

    cases = load_evaluation_cases(cases_path)
    active_embedder = embedder or HashingEmbedder()
    with TemporaryDirectory(prefix="second-mind-evaluation-") as temporary:
        index_path = Path(temporary) / "journals.sqlite3"
        index_journals(
            journal_directory,
            index_path,
            embedder=active_embedder,
        )
        results = tuple(
            _evaluate_case(case, index_path, active_embedder) for case in cases
        )
    return EvaluationSummary(results=results)


def main(argv: Sequence[str] | None = None) -> int:
    """Run and print an offline five-question retrieval scorecard."""

    parser = ArgumentParser(
        prog="python -m second_mind.evaluation",
        description=(
            "Score five local journal retrieval questions, citations, and "
            "insufficient-evidence refusals."
        ),
    )
    parser.add_argument("journal_directory", type=Path)
    parser.add_argument("cases", type=Path)
    arguments = parser.parse_args(argv)

    try:
        summary = evaluate_retrieval(
            arguments.journal_directory,
            arguments.cases,
        )
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    _print_summary(summary)
    return 0 if summary.passed else 1


def _case_from_mapping(
    raw: object,
    position: int,
) -> RetrievalEvaluationCase:
    if not isinstance(raw, Mapping):
        raise ValueError(f"evaluation case {position} must be an object")

    identifier = _required_text(raw, "id", position)
    question = _required_text(raw, "question", position)
    expected_source = _optional_text(raw, "expected_source", position)
    expected_date_text = _optional_text(raw, "expected_date", position)
    expected_title = _optional_text(raw, "expected_title", position)
    expected_chunk = raw.get("expected_chunk")

    if expected_source is None:
        if any(
            value is not None
            for value in (expected_date_text, expected_title, expected_chunk)
        ):
            raise ValueError(
                f"evaluation case {position} refusal metadata must be null"
            )
        return RetrievalEvaluationCase(
            identifier=identifier,
            question=question,
            expected_source=None,
            expected_date=None,
            expected_title=None,
            expected_chunk=None,
        )

    if Path(expected_source).name != expected_source:
        raise ValueError(
            f"evaluation case {position} expected_source must be a filename"
        )
    if expected_date_text is None:
        raise ValueError(
            f"evaluation case {position} expected_date must be a date string"
        )
    try:
        expected_date = date.fromisoformat(expected_date_text)
    except ValueError as error:
        raise ValueError(
            f"evaluation case {position} expected_date is invalid"
        ) from error
    if (
        not isinstance(expected_chunk, int)
        or isinstance(expected_chunk, bool)
        or expected_chunk < 0
    ):
        raise ValueError(
            f"evaluation case {position} expected_chunk must be non-negative"
        )

    return RetrievalEvaluationCase(
        identifier=identifier,
        question=question,
        expected_source=expected_source,
        expected_date=expected_date,
        expected_title=expected_title,
        expected_chunk=expected_chunk,
    )


def _required_text(
    raw: Mapping[object, object],
    field: str,
    position: int,
) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"evaluation case {position} {field} must be non-empty text"
        )
    return value.strip()


def _optional_text(
    raw: Mapping[object, object],
    field: str,
    position: int,
) -> str | None:
    value = raw.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"evaluation case {position} {field} must be text or null"
        )
    return value.strip()


def _evaluate_case(
    case: RetrievalEvaluationCase,
    index_path: Path,
    embedder: Embedder,
) -> EvaluationCaseResult:
    passages = retrieve_passages(
        case.question,
        index_path,
        limit=1,
        embedder=embedder,
    )
    passage = passages[0] if passages else None

    if case.expects_refusal:
        return EvaluationCaseResult(
            case=case,
            passage=passage,
            retrieval_passed=None,
            citation_passed=None,
            refusal_passed=passage is None,
        )

    retrieval_passed = (
        passage is not None
        and passage.chunk.source_path.name == case.expected_source
    )
    citation_passed = (
        retrieval_passed
        and passage is not None
        and passage.chunk.entry_date == case.expected_date
        and passage.chunk.title == case.expected_title
        and passage.chunk.chunk_index == case.expected_chunk
    )
    return EvaluationCaseResult(
        case=case,
        passage=passage,
        retrieval_passed=retrieval_passed,
        citation_passed=citation_passed,
        refusal_passed=None,
    )


def _criterion_score(
    results: Sequence[EvaluationCaseResult],
    field: str,
) -> tuple[int, int]:
    values = [
        value
        for result in results
        if (value := getattr(result, field)) is not None
    ]
    return sum(values), len(values)


def _print_summary(summary: EvaluationSummary) -> None:
    for result in summary.results:
        source = (
            result.passage.chunk.source_path.name
            if result.passage is not None
            else "<none>"
        )
        print(
            f"case={result.case.identifier} | "
            f"status={_status(result.passed)} | "
            f"retrieval={_status(result.retrieval_passed)} | "
            f"citation={_status(result.citation_passed)} | "
            f"refusal={_status(result.refusal_passed)} | "
            f"source={source}"
        )

    retrieval = summary.retrieval_score
    citations = summary.citation_score
    refusals = summary.refusal_score
    print(
        f"summary={_status(summary.passed)} | "
        f"cases={summary.passed_cases}/{len(summary.results)} | "
        f"retrieval={retrieval[0]}/{retrieval[1]} | "
        f"citations={citations[0]}/{citations[1]} | "
        f"refusals={refusals[0]}/{refusals[1]}"
    )


def _status(value: bool | None) -> str:
    if value is None:
        return "n/a"
    return "pass" if value else "fail"


if __name__ == "__main__":
    raise SystemExit(main())
