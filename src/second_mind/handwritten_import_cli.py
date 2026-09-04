"""Deliberate local commands for handwritten journal imports."""

from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path
import sys

from second_mind.handwritten_import import (
    DraftImport,
    HandwrittenImportWorkspace,
    OcrError,
    StagedImport,
    _read_manifest,
    approve_draft,
    recognize_staged_scan,
    stage_scan,
    write_draft,
)


def main(argv: Sequence[str] | None = None) -> int:
    """Create a review draft or explicitly approve an existing local draft."""

    parser = ArgumentParser(prog="python -m second_mind.handwritten_import_cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="create a local OCR review draft")
    create.add_argument("source", type=Path)
    create.add_argument("workspace", type=Path)
    create.add_argument("journal_root", type=Path)
    approve = commands.add_parser("approve", help="approve one reviewed local draft")
    approve.add_argument("import_id")
    approve.add_argument("workspace", type=Path)
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "create":
            workspace = HandwrittenImportWorkspace(arguments.workspace, arguments.journal_root)
            staged = stage_scan(arguments.source, workspace)
            observations = recognize_staged_scan(staged)
            write_draft(staged, observations)
            print(f"draft created for import {staged.import_id}")
            return 0
        staged = _load_staged_import(arguments.workspace, arguments.import_id)
        manifest = _read_manifest(staged.manifest)
        draft = DraftImport(
            staged=staged,
            draft=staged.draft,
            intended_filename=str(manifest.get("intended_filename", "unconfirmed.md")),
        )
        approve_draft(draft)
        print(f"import {staged.import_id} approved")
        return 0
    except (OSError, ValueError, OcrError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def _load_staged_import(workspace: Path, import_id: str) -> StagedImport:
    """Reconstruct an import from its private manifest without OCR-derived names."""

    if len(import_id) != 32 or any(character not in "0123456789abcdef" for character in import_id):
        raise ValueError("invalid import identifier")
    root = workspace.expanduser().resolve()
    manifest_path = root / "state" / f"{import_id}.json"
    manifest = _read_manifest(manifest_path)
    retained_scan_name = manifest.get("retained_scan")
    draft_name = manifest.get("draft")
    fingerprint = manifest.get("fingerprint")
    if not all(isinstance(value, str) for value in (retained_scan_name, draft_name, fingerprint)):
        raise ValueError("private import state is invalid")
    return StagedImport(
        import_id=import_id,
        state=manifest.get("state", "staged"),
        retained_scan=root / "scans" / retained_scan_name,
        draft=root / "drafts" / draft_name,
        manifest=manifest_path,
        fingerprint=fingerprint,
    )


if __name__ == "__main__":
    raise SystemExit(main())
