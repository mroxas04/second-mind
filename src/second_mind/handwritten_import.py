"""Private staging primitives for locally transferred handwritten journal scans."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from uuid import uuid4

from second_mind.journal import load_journal


MAX_SCAN_BYTES = 25 * 1024 * 1024
OCR_RESULT_VERSION = 1
MAX_OCR_OUTPUT_BYTES = 1024 * 1024
OCR_TIMEOUT_SECONDS = 30


class ImportState(StrEnum):
    """The allowed lifecycle states for a handwritten import."""

    STAGED = "staged"
    DRAFT = "draft"
    APPROVED = "approved"
    FAILED = "failed"


class OcrError(ValueError):
    """Report a non-content-bearing local OCR failure."""


@dataclass(frozen=True, slots=True)
class OcrObservation:
    """One ordered local text-recognition observation."""

    text: str
    confidence: float
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class HandwrittenImportWorkspace:
    """Locations reserved for private scans, drafts, and import state."""

    root: Path
    journal_root: Path

    def __post_init__(self) -> None:
        root = self.root.expanduser().resolve()
        journal_root = self.journal_root.expanduser().resolve()
        if _is_relative_to(root, journal_root) or _is_relative_to(journal_root, root):
            raise ValueError("handwritten workspace must be separate from the journal root")
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "journal_root", journal_root)

    @property
    def scans_directory(self) -> Path:
        """Return the retained-scan directory."""

        return self.root / "scans"

    @property
    def drafts_directory(self) -> Path:
        """Return the unapproved-draft directory."""

        return self.root / "drafts"

    @property
    def state_directory(self) -> Path:
        """Return the private state-manifest directory."""

        return self.root / "state"

    def path_for(self, relative_path: str) -> Path:
        """Resolve a workspace-relative path without allowing escape."""

        candidate = (self.root / relative_path).resolve()
        if not _is_relative_to(candidate, self.root):
            raise ValueError("path must remain inside the handwritten workspace")
        return candidate

    def create_directories(self) -> None:
        """Create the private workspace directories on demand."""

        for directory in (self.scans_directory, self.drafts_directory, self.state_directory):
            directory.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True, slots=True)
class StagedImport:
    """Private paths and identity recorded when a scan is staged."""

    import_id: str
    state: ImportState
    retained_scan: Path
    draft: Path
    manifest: Path
    fingerprint: str


@dataclass(frozen=True, slots=True)
class DraftImport:
    """An editable, unapproved draft and its intended approved filename."""

    staged: StagedImport
    draft: Path
    intended_filename: str


def stage_scan(source: Path, workspace: HandwrittenImportWorkspace) -> StagedImport:
    """Copy one local scan into private staging without touching journal entries."""

    source = source.expanduser()
    _validate_source(source, workspace)
    workspace.create_directories()

    import_id = uuid4().hex
    suffix = source.suffix.lower() or ".bin"
    retained_scan = workspace.path_for(f"scans/{import_id}{suffix}")
    draft = workspace.path_for(f"drafts/{import_id}.md.draft")
    manifest = workspace.path_for(f"state/{import_id}.json")
    shutil.copyfile(source, retained_scan)
    fingerprint = _sha256(retained_scan)
    draft.write_text("", encoding="utf-8")
    manifest.write_text(
        json.dumps(
            {
                "version": 1,
                "import_id": import_id,
                "state": ImportState.STAGED,
                "retained_scan": retained_scan.name,
                "draft": draft.name,
                "fingerprint": fingerprint,
                "journal_root": str(workspace.journal_root),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return StagedImport(
        import_id=import_id,
        state=ImportState.STAGED,
        retained_scan=retained_scan,
        draft=draft,
        manifest=manifest,
        fingerprint=fingerprint,
    )


def recognize_staged_scan(
    staged: StagedImport,
    *,
    runner: Callable[[Path], dict[str, object]] | None = None,
) -> tuple[OcrObservation, ...]:
    """Recognize a retained scan through a local-only injectable OCR boundary."""

    try:
        result = (runner or _run_vision_ocr)(staged.retained_scan)
        observations = _parse_ocr_result(result)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as error:
        _write_state(staged, ImportState.FAILED)
        raise OcrError("local OCR failed") from error
    return observations


def write_draft(
    staged: StagedImport, observations: tuple[OcrObservation, ...]
) -> DraftImport:
    """Write a Markdown-formatted proposal which remains outside the journal root."""

    if not observations:
        raise ValueError("cannot write a draft without OCR observations")
    lines = [observation.text.strip() for observation in observations]
    proposed_date = _first_date(lines)
    title = lines[1] if proposed_date is not None and len(lines) > 1 else lines[0]
    body_start = 2 if proposed_date is not None and len(lines) > 1 else 1
    body = "\n".join(lines[body_start:]).strip()
    if not body:
        body = "[Review and complete this transcription before approval.]"
    staged.draft.write_text(f"# {title}\n\n{body}\n", encoding="utf-8")
    filename = _intended_filename(proposed_date, title)
    _write_state(staged, ImportState.DRAFT, intended_filename=filename)
    return DraftImport(staged=staged, draft=staged.draft, intended_filename=filename)


def approve_draft(draft_import: DraftImport) -> Path:
    """Publish a reviewed draft as a no-overwrite Markdown journal entry."""

    staged = draft_import.staged
    _require_regular_workspace_file(staged.retained_scan, staged.manifest.parent.parent)
    _require_regular_workspace_file(draft_import.draft, staged.manifest.parent.parent)
    manifest = _read_manifest(staged.manifest)
    journal_root = Path(manifest["journal_root"]).expanduser().resolve()
    if not journal_root.is_dir() or journal_root.is_symlink():
        raise ValueError("approved journal root is unavailable")
    if manifest.get("state") == ImportState.APPROVED:
        target = journal_root / str(manifest["intended_filename"])
        if target.is_file() and not target.is_symlink():
            return target
        raise ValueError("approved import is incomplete")
    target = journal_root / draft_import.intended_filename
    if target.parent != journal_root or target.suffix != ".md":
        raise ValueError("approved entry must remain inside the journal root")
    if target.exists():
        raise FileExistsError("approved journal entry already exists")
    text = draft_import.draft.read_text(encoding="utf-8")
    _validate_as_journal(text, target.name, staged.manifest.parent)
    temporary = journal_root / f".{target.name}.{uuid4().hex}.pending"
    try:
        with temporary.open("x", encoding="utf-8", newline="") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
        _fsync_directory(journal_root)
    except FileExistsError:
        raise FileExistsError("approved journal entry already exists") from None
    finally:
        if temporary.exists():
            temporary.unlink()
    _write_state(staged, ImportState.APPROVED, intended_filename=target.name)
    _fsync_directory(staged.manifest.parent)
    return target


def _validate_source(source: Path, workspace: HandwrittenImportWorkspace) -> None:
    if source.is_symlink() or not source.is_file():
        raise ValueError("scan source must be a regular non-symlink file")
    source_resolved = source.resolve()
    if _is_relative_to(source_resolved, workspace.root):
        raise ValueError("scan source must be outside the handwritten workspace")
    if _is_relative_to(source_resolved, workspace.journal_root):
        raise ValueError("scan source must be outside the approved journal root")
    if source.stat().st_size > MAX_SCAN_BYTES:
        raise ValueError("scan source exceeds the local size limit")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, directory: Path) -> bool:
    try:
        path.relative_to(directory)
    except ValueError:
        return False
    return True


def _run_vision_ocr(scan: Path) -> dict[str, object]:
    """Invoke the checked-in macOS Vision helper without a shell or network."""

    helper = Path(__file__).resolve().parents[2] / "tools" / "second_mind_vision_ocr.swift"
    swift = shutil.which("swift")
    if (
        sys.platform != "darwin"
        or swift is None
        or not helper.is_file()
        or helper.is_symlink()
        or not Path("/System/Library/Frameworks/Vision.framework").is_dir()
        or not Path("/System/Library/Frameworks/PDFKit.framework").is_dir()
    ):
        raise OcrError("local OCR capability is unavailable")
    environment = {"PATH": str(Path(swift).parent), "HOME": os.environ.get("HOME", "")}
    completed = subprocess.run(
        [swift, str(helper), str(scan)],
        check=False,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env=environment,
        timeout=OCR_TIMEOUT_SECONDS,
    )
    if completed.returncode != 0 or len(completed.stdout) > MAX_OCR_OUTPUT_BYTES:
        raise OcrError("local OCR helper did not return a usable result")
    try:
        parsed = json.loads(completed.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OcrError("local OCR helper returned invalid data") from error
    if not isinstance(parsed, dict):
        raise OcrError("local OCR helper returned invalid data")
    return parsed


def _parse_ocr_result(result: object) -> tuple[OcrObservation, ...]:
    if not isinstance(result, dict) or result.get("version") != OCR_RESULT_VERSION:
        raise ValueError("invalid OCR result version")
    raw_observations = result.get("observations")
    if not isinstance(raw_observations, list) or not raw_observations:
        raise ValueError("OCR result has no observations")
    observations: list[OcrObservation] = []
    for item in raw_observations:
        if not isinstance(item, dict):
            raise ValueError("OCR observation is invalid")
        text = item.get("text")
        confidence = item.get("confidence")
        x = item.get("x")
        y = item.get("y")
        if (
            not isinstance(text, str)
            or not text.strip()
            or not all(isinstance(value, (float, int)) for value in (confidence, x, y))
        ):
            raise ValueError("OCR observation is invalid")
        observations.append(OcrObservation(text, float(confidence), float(x), float(y)))
    return tuple(observations)


def _write_state(
    staged: StagedImport, state: ImportState, *, intended_filename: str | None = None
) -> None:
    try:
        manifest = json.loads(staged.manifest.read_text(encoding="utf-8"))
        manifest["state"] = state
        if intended_filename is not None:
            manifest["intended_filename"] = intended_filename
        staged.manifest.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass


def _first_date(lines: list[str]) -> date | None:
    for line in lines:
        try:
            return date.fromisoformat(line)
        except ValueError:
            continue
    return None


def _intended_filename(proposed_date: date | None, title: str) -> str:
    if proposed_date is None:
        return "unconfirmed.md"
    slug = "-".join(part for part in re.findall(r"[a-z0-9]+", title.lower()))
    return f"{proposed_date.isoformat()}{('-' + slug) if slug else ''}.md"


def _read_manifest(path: Path) -> dict[str, object]:
    _require_regular_workspace_file(path, path.parent.parent)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("private import state is invalid") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("journal_root"), str):
        raise ValueError("private import state is invalid")
    return manifest


def _require_regular_workspace_file(path: Path, workspace_root: Path) -> None:
    if path.is_symlink() or not path.is_file() or not _is_relative_to(path.resolve(), workspace_root.resolve()):
        raise ValueError("private import file is invalid")


def _validate_as_journal(text: str, filename: str, state_directory: Path) -> None:
    validation = state_directory / filename
    try:
        validation.write_text(text, encoding="utf-8", newline="")
        load_journal(validation)
    finally:
        if validation.exists():
            validation.unlink()


def _fsync_directory(directory: Path) -> None:
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
