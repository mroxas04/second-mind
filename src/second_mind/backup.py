"""Create and verify local journal backup snapshots without cloud services."""

from argparse import ArgumentParser
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path, PurePosixPath
import json
import shutil
import sqlite3
from string import hexdigits
import sys
import tempfile

from second_mind.index import DEFAULT_INDEX_PATH


MANIFEST_FILENAME = "manifest.json"
MANIFEST_VERSION = 1


@dataclass(frozen=True, slots=True)
class BackupSummary:
    """Details of one completed and verified local backup snapshot."""

    snapshot_path: Path
    files: int
    bytes_copied: int


@dataclass(frozen=True, slots=True)
class BackupVerification:
    """Checksum verification results for a local backup snapshot."""

    snapshot_path: Path
    files: int
    bytes_checked: int
    errors: tuple[str, ...]

    @property
    def valid(self) -> bool:
        """Return whether every manifested file is present and unchanged."""

        return not self.errors


@dataclass(frozen=True, slots=True)
class RestoreSummary:
    """Details of one restored local snapshot."""

    restore_path: Path
    files: int
    bytes_restored: int


def create_backup(
    journal_directory: Path,
    destination: Path,
    index_path: Path = DEFAULT_INDEX_PATH,
    *,
    snapshot_name: str | None = None,
) -> BackupSummary:
    """Create and checksum-verify a timestamped local backup snapshot.

    The caller chooses the destination explicitly. Journal files, the current
    SQLite index, and a content-checksum manifest are copied locally. Existing
    snapshots are never overwritten.
    """

    journal_directory = _require_directory(journal_directory, "journal directory")
    index_path = _require_file(index_path, "index")
    destination = destination.expanduser().resolve()
    if _is_relative_to(destination, journal_directory):
        raise ValueError("backup destination must not be inside the journal directory")

    destination.mkdir(parents=True, exist_ok=True)
    name = snapshot_name or _default_snapshot_name()
    _validate_snapshot_name(name)
    snapshot_path = destination / name
    if snapshot_path.exists():
        raise FileExistsError(f"backup snapshot already exists: {snapshot_path}")

    staging = Path(tempfile.mkdtemp(prefix=".second-mind-backup-", dir=destination))
    try:
        records = _copy_journals(journal_directory, staging / "journals")
        index_destination = staging / "index" / index_path.name
        records.append(_copy_index(index_path, index_destination))
        manifest = {
            "version": MANIFEST_VERSION,
            "created_at": datetime.now(UTC).isoformat(),
            "files": records,
        }
        (staging / MANIFEST_FILENAME).write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        verification = verify_backup(staging)
        if not verification.valid:
            raise ValueError(
                "backup verification failed: " + "; ".join(verification.errors)
            )
        staging.rename(snapshot_path)
    finally:
        if staging.exists():
            shutil.rmtree(staging)

    return BackupSummary(
        snapshot_path=snapshot_path,
        files=len(records),
        bytes_copied=sum(int(record["size"]) for record in records),
    )


def verify_backup(snapshot_path: Path) -> BackupVerification:
    """Verify all files in a backup snapshot against its local manifest."""

    snapshot_path = _require_directory(snapshot_path, "backup snapshot")
    manifest_path = snapshot_path / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise ValueError(f"backup manifest does not exist: {manifest_path}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise ValueError(f"backup manifest is invalid: {error}") from error
    records = _validate_manifest(manifest)

    errors: list[str] = []
    bytes_checked = 0
    for record in records:
        relative_path = PurePosixPath(record["path"])
        stored_path = snapshot_path.joinpath(*relative_path.parts)
        if (
            not _is_relative_to(stored_path.resolve(), snapshot_path)
            or not stored_path.is_file()
            or stored_path.is_symlink()
        ):
            errors.append(f"missing file: {relative_path}")
            continue
        size = stored_path.stat().st_size
        bytes_checked += size
        if size != record["size"]:
            errors.append(f"size mismatch: {relative_path}")
            continue
        if _sha256(stored_path) != record["sha256"]:
            errors.append(f"checksum mismatch: {relative_path}")

    return BackupVerification(
        snapshot_path=snapshot_path,
        files=len(records),
        bytes_checked=bytes_checked,
        errors=tuple(errors),
    )


def restore_backup(snapshot_path: Path, destination: Path) -> RestoreSummary:
    """Restore a verified snapshot into a new, isolated directory."""
    snapshot_path = _require_directory(snapshot_path, "backup snapshot")
    verification = verify_backup(snapshot_path)
    if not verification.valid:
        raise ValueError("backup verification failed: " + "; ".join(verification.errors))
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise FileExistsError(f"restore destination already exists: {destination}")
    destination.mkdir(parents=True)
    manifest = json.loads((snapshot_path / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    records = _validate_manifest(manifest)
    try:
        for record in records:
            relative = PurePosixPath(record["path"])
            source = snapshot_path.joinpath(*relative.parts)
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        shutil.copy2(snapshot_path / MANIFEST_FILENAME, destination / MANIFEST_FILENAME)
    except Exception:
        shutil.rmtree(destination)
        raise
    restored = verify_backup(destination)
    if not restored.valid:
        shutil.rmtree(destination)
        raise ValueError("restored backup verification failed: " + "; ".join(restored.errors))
    return RestoreSummary(destination, restored.files, restored.bytes_checked)


def main(argv: Sequence[str] | None = None) -> int:
    """Create or verify a local backup snapshot from the command line."""

    parser = ArgumentParser(
        prog="second-mind-backup",
        description="Create and verify local journal backup snapshots.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create a local snapshot")
    create_parser.add_argument("journal_directory", type=Path)
    create_parser.add_argument("destination", type=Path)
    create_parser.add_argument("--index", type=Path, default=DEFAULT_INDEX_PATH)
    create_parser.add_argument(
        "--name",
        dest="snapshot_name",
        help="optional unique snapshot directory name",
    )

    verify_parser = subparsers.add_parser("verify", help="verify a local snapshot")
    verify_parser.add_argument("snapshot", type=Path)

    restore_parser = subparsers.add_parser("restore", help="restore into a new directory")
    restore_parser.add_argument("snapshot", type=Path)
    restore_parser.add_argument("destination", type=Path)

    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "create":
            summary = create_backup(
                arguments.journal_directory,
                arguments.destination,
                arguments.index,
                snapshot_name=arguments.snapshot_name,
            )
            print(
                f"snapshot={summary.snapshot_path} | files={summary.files} | "
                f"bytes={summary.bytes_copied} | verified=yes"
            )
            return 0

        if arguments.command == "restore":
            summary = restore_backup(arguments.snapshot, arguments.destination)
            print(f"restore={summary.restore_path} | files={summary.files} | bytes={summary.bytes_restored} | verified=yes")
            return 0
        verification = verify_backup(arguments.snapshot)
    except (OSError, sqlite3.Error, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    if verification.valid:
        print(
            f"snapshot={verification.snapshot_path} | files={verification.files} | "
            f"bytes={verification.bytes_checked} | verified=yes"
        )
        return 0
    print(
        "error: backup verification failed: " + "; ".join(verification.errors),
        file=sys.stderr,
    )
    return 1


def _copy_journals(source: Path, destination: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for source_path in sorted(source.rglob("*")):
        if source_path.is_symlink():
            raise ValueError(f"journal directory contains a symbolic link: {source_path}")
        if source_path.is_dir():
            continue
        if not source_path.is_file():
            raise ValueError(f"journal directory contains an unsupported item: {source_path}")
        relative_path = source_path.relative_to(source)
        target = destination / relative_path
        records.append(
            _copy_file(
                source_path,
                target,
                "journal",
                PurePosixPath("journals", relative_path.as_posix()),
            )
        )
    if not records:
        raise ValueError("journal directory contains no files to back up")
    return records


def _copy_index(source: Path, destination: Path) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with (
        sqlite3.connect(f"{source.as_uri()}?mode=ro", uri=True) as source_database,
        sqlite3.connect(destination) as destination_database,
    ):
        source_database.backup(destination_database)
    return _file_record(destination, "index", PurePosixPath("index", source.name))


def _copy_file(
    source: Path,
    destination: Path,
    role: str,
    manifest_path: PurePosixPath,
) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return _file_record(destination, role, manifest_path)


def _file_record(
    stored_path: Path,
    role: str,
    manifest_path: PurePosixPath,
) -> dict[str, object]:
    return {
        "path": manifest_path.as_posix(),
        "role": role,
        "sha256": _sha256(stored_path),
        "size": stored_path.stat().st_size,
    }


def _validate_manifest(manifest: object) -> list[dict[str, object]]:
    if not isinstance(manifest, dict) or manifest.get("version") != MANIFEST_VERSION:
        raise ValueError("backup manifest has an unsupported version")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("backup manifest contains no files")

    validated: list[dict[str, object]] = []
    seen: set[str] = set()
    for record in files:
        if not isinstance(record, dict):
            raise ValueError("backup manifest contains an invalid file record")
        path = record.get("path")
        role = record.get("role")
        checksum = record.get("sha256")
        size = record.get("size")
        if (
            not isinstance(path, str)
            or not _is_safe_relative_path(path)
            or path in seen
            or role not in {"journal", "index"}
            or not isinstance(checksum, str)
            or len(checksum) != 64
            or any(character not in hexdigits for character in checksum)
            or not isinstance(size, int)
            or isinstance(size, bool)
            or size < 0
        ):
            raise ValueError("backup manifest contains an invalid file record")
        seen.add(path)
        validated.append(record)
    return validated


def _is_safe_relative_path(value: str) -> bool:
    path = PurePosixPath(value)
    return bool(path.parts) and not path.is_absolute() and ".." not in path.parts


def _require_directory(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"{label} does not exist or is not a directory: {path}")
    return resolved


def _require_file(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file() or resolved.is_symlink():
        raise ValueError(f"{label} does not exist or is not a regular file: {path}")
    return resolved


def _is_relative_to(path: Path, parent: Path) -> bool:
    return path == parent or path.is_relative_to(parent)


def _default_snapshot_name() -> str:
    return f"second-mind-{datetime.now(UTC):%Y%m%dT%H%M%SZ}"


def _validate_snapshot_name(value: str) -> None:
    if value in {"", ".", ".."} or Path(value).name != value:
        raise ValueError("snapshot name must be one safe path segment")


def _sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
