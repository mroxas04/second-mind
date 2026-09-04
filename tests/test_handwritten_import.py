"""Tests for the private handwritten-import staging boundary."""

from pathlib import Path

import pytest

from second_mind import load_journals
from second_mind.index import HashingEmbedder, index_journals
from second_mind.handwritten_import import (
    HandwrittenImportWorkspace,
    ImportState,
    OcrError,
    OcrObservation,
    approve_draft,
    recognize_staged_scan,
    stage_scan,
    write_draft,
)


def test_stage_scan_copies_a_synthetic_source_outside_the_journal_library(
    tmp_path: Path,
) -> None:
    source = tmp_path / "phone-transfer.jpg"
    source.write_bytes(b"fictional scan")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    workspace = HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root)

    staged = stage_scan(source, workspace)

    assert staged.state is ImportState.STAGED
    assert staged.retained_scan.is_file()
    assert staged.retained_scan.read_bytes() == b"fictional scan"
    assert staged.retained_scan != source
    assert staged.draft.suffixes == [".md", ".draft"]
    assert staged.manifest.is_file()
    assert load_journals(workspace.root) == []


def test_stage_scan_uses_distinct_retained_copies_for_same_named_sources(
    tmp_path: Path,
) -> None:
    first_directory = tmp_path / "first"
    second_directory = tmp_path / "second"
    first_directory.mkdir()
    second_directory.mkdir()
    first = first_directory / "scan.jpg"
    second = second_directory / "scan.jpg"
    first.write_bytes(b"first fictional scan")
    second.write_bytes(b"second fictional scan")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    workspace = HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root)

    staged_first = stage_scan(first, workspace)
    staged_second = stage_scan(second, workspace)

    assert staged_first.retained_scan != staged_second.retained_scan
    assert first.read_bytes() == b"first fictional scan"
    assert second.read_bytes() == b"second fictional scan"


@pytest.mark.parametrize("source_kind", ["missing", "directory", "symlink"])
def test_stage_scan_rejects_unsafe_sources(tmp_path: Path, source_kind: str) -> None:
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    workspace = HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root)
    source = tmp_path / "scan.jpg"
    if source_kind == "directory":
        source.mkdir()
    elif source_kind == "symlink":
        target = tmp_path / "target.jpg"
        target.write_bytes(b"fictional scan")
        source.symlink_to(target)

    with pytest.raises(ValueError, match="regular"):
        stage_scan(source, workspace)


def test_workspace_rejects_a_journal_root_or_path_escape(tmp_path: Path) -> None:
    journal_root = tmp_path / "journals"
    journal_root.mkdir()

    with pytest.raises(ValueError, match="separate"):
        HandwrittenImportWorkspace(journal_root, journal_root)

    workspace = HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root)
    with pytest.raises(ValueError, match="workspace"):
        workspace.path_for("../escape")


def test_recognize_staged_scan_accepts_a_versioned_fictional_result(
    tmp_path: Path,
) -> None:
    source = tmp_path / "phone-transfer.jpg"
    source.write_bytes(b"fictional scan")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    staged = stage_scan(
        source,
        HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root),
    )

    observations = recognize_staged_scan(
        staged,
        runner=lambda _: {
            "version": 1,
            "observations": [
                {"text": "August 24, 2026", "confidence": 0.91, "x": 0.1, "y": 0.9},
                {"text": "Fictional title", "confidence": 0.88, "x": 0.1, "y": 0.8},
            ],
        },
    )

    assert [observation.text for observation in observations] == [
        "August 24, 2026",
        "Fictional title",
    ]


@pytest.mark.parametrize("result", [{}, {"version": 1, "observations": []}])
def test_recognize_staged_scan_marks_bad_results_failed(
    tmp_path: Path, result: dict[str, object]
) -> None:
    source = tmp_path / "phone-transfer.jpg"
    source.write_bytes(b"fictional scan")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    staged = stage_scan(
        source,
        HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root),
    )

    with pytest.raises(OcrError, match="local OCR failed"):
        recognize_staged_scan(staged, runner=lambda _: result)

    assert '"state": "failed"' in staged.manifest.read_text(encoding="utf-8")
    assert staged.retained_scan.is_file()
    assert source.is_file()


def test_only_explicit_approval_publishes_an_editable_draft(tmp_path: Path) -> None:
    source = tmp_path / "phone-transfer.jpg"
    source.write_bytes(b"fictional scan")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    staged = stage_scan(
        source,
        HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root),
    )
    observations = recognize_staged_scan(
        staged,
        runner=lambda _: {
            "version": 1,
            "observations": [
                {"text": "2026-08-24", "confidence": 0.9, "x": 0.1, "y": 0.9},
                {"text": "Fictional day", "confidence": 0.9, "x": 0.1, "y": 0.8},
                {"text": "Grateful for a fictional test.", "confidence": 0.9, "x": 0.1, "y": 0.7},
            ],
        },
    )

    draft = write_draft(staged, observations)
    draft.draft.write_text(
        "# Corrected fictional title\n\nCorrected fictional body.\n",
        encoding="utf-8",
    )

    assert list(journal_root.iterdir()) == []
    approved = approve_draft(draft)

    assert approved.name == "2026-08-24-fictional-day.md"
    assert "Corrected fictional body." in approved.read_text(encoding="utf-8")
    assert staged.retained_scan.is_file()
    assert load_journals(journal_root)[0].source_path == approved
    assert approve_draft(draft) == approved


def test_approval_never_overwrites_an_existing_entry(tmp_path: Path) -> None:
    source = tmp_path / "phone-transfer.jpg"
    source.write_bytes(b"fictional scan")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    existing = journal_root / "2026-08-24-fictional-day.md"
    existing.write_text("Existing fictional body.\n", encoding="utf-8")
    staged = stage_scan(
        source,
        HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root),
    )
    draft = write_draft(
        staged,
        (
            # OCR observations stay fictional in this test.
            OcrObservation("2026-08-24", 0.9, 0.1, 0.9),
            OcrObservation("Fictional day", 0.9, 0.1, 0.8),
            OcrObservation("Body", 0.9, 0.1, 0.7),
        ),
    )

    with pytest.raises(FileExistsError, match="already exists"):
        approve_draft(draft)

    assert existing.read_text(encoding="utf-8") == "Existing fictional body.\n"
    assert draft.draft.is_file()


def test_drafts_do_not_index_until_a_later_explicit_refresh(tmp_path: Path) -> None:
    source = tmp_path / "phone-transfer.jpg"
    source.write_bytes(b"fictional scan")
    journal_root = tmp_path / "journals"
    journal_root.mkdir()
    staged = stage_scan(
        source,
        HandwrittenImportWorkspace(tmp_path / "handwritten_import", journal_root),
    )
    draft = write_draft(
        staged,
        (
            OcrObservation("2026-08-24", 0.9, 0.1, 0.9),
            OcrObservation("Fictional indexing", 0.9, 0.1, 0.8),
            OcrObservation("Fictional body for indexing.", 0.9, 0.1, 0.7),
        ),
    )

    with pytest.raises(ValueError, match="no valid"):
        index_journals(journal_root, tmp_path / "index.sqlite3", embedder=HashingEmbedder())
    approve_draft(draft)
    summary = index_journals(journal_root, tmp_path / "index.sqlite3", embedder=HashingEmbedder())
    duplicate_safe = index_journals(journal_root, tmp_path / "index.sqlite3", embedder=HashingEmbedder())

    assert summary.indexed == 1
    assert duplicate_safe.indexed == 0
