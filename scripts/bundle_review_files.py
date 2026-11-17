"""Build the owner-requested, source-only ConnectHub review archive."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "ConnectHub_Review_Files.zip"
TEMP_OUTPUT = OUTPUT.with_suffix(".zip.tmp")

EXPLICIT_FILES = (
    "README.md",
    "scripts/bundle_review_files.py",
    "backend/app/ai/__init__.py",
    "backend/app/ai/provider.py",
    "backend/app/ai/router.py",
    "backend/app/ai/schemas.py",
    "backend/app/ai/service.py",
    "backend/app/ai/worker.py",
    "backend/app/core/config.py",
    "backend/app/messaging/service.py",
    "backend/app/models/__init__.py",
    "backend/app/models/ai_summary.py",
    "backend/app/models/embedding_job.py",
    "backend/app/models/message.py",
    "backend/app/models/message_embedding.py",
    "backend/migrations/versions/20261116_0002_complete_backend.py",
    "backend/migrations/versions/20261117_0003_ai_profile_safety.py",
    "backend/evals/__init__.py",
    "backend/evals/dataset.py",
    "backend/evals/metrics.py",
    "backend/evals/run_retrieval.py",
    "backend/evals/run_live_gemini.py",
    "backend/evals/summary_dataset.py",
    "backend/evals/exact_baseline_full.json",
    "backend/evals/exact_baseline_candidate50.json",
    "backend/tests/integration/test_ai_features.py",
    "backend/tests/integration/test_messaging_api.py",
    "backend/tests/unit/test_ai_provider.py",
    "backend/tests/unit/test_evaluation_metrics.py",
    "frontend/src/features/frontend-flows.test.tsx",
)

FORBIDDEN_PARTS = {
    ".env",
    ".git",
    ".runtime",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "playwright-report",
    "test-results",
}
FORBIDDEN_SUFFIXES = {
    ".db",
    ".dump",
    ".key",
    ".pem",
    ".sqlite",
    ".sqlite3",
    ".zip",
}


def relative_file(path: Path) -> Path:
    resolved = path.resolve(strict=True)
    try:
        relative = resolved.relative_to(PROJECT_ROOT)
    except ValueError as error:
        raise RuntimeError(
            f"Refusing a file outside the project: {resolved}"
        ) from error
    lowered_parts = {part.casefold() for part in relative.parts}
    if lowered_parts & FORBIDDEN_PARTS:
        raise RuntimeError(f"Refusing forbidden path: {relative.as_posix()}")
    if relative.suffix.casefold() in FORBIDDEN_SUFFIXES:
        raise RuntimeError(f"Refusing forbidden file type: {relative.as_posix()}")
    if not resolved.is_file():
        raise RuntimeError(f"Expected a regular file: {relative.as_posix()}")
    return relative


def collect_files() -> list[Path]:
    docs_root = PROJECT_ROOT / "docs"
    if not docs_root.is_dir():
        raise RuntimeError("The required docs/ directory does not exist")

    candidates = [path for path in docs_root.rglob("*") if path.is_file()]
    candidates.extend(PROJECT_ROOT / item for item in EXPLICIT_FILES)
    relative_paths = {relative_file(path) for path in candidates}

    missing = [item for item in EXPLICIT_FILES if Path(item) not in relative_paths]
    if missing:
        raise RuntimeError(f"Required review files are missing: {', '.join(missing)}")
    if not any(path.parts[0] == "docs" for path in relative_paths):
        raise RuntimeError("No documentation files were collected")
    return sorted(relative_paths, key=lambda path: path.as_posix().casefold())


def digest(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_archive() -> tuple[int, int]:
    files = collect_files()
    manifest_lines = [
        "ConnectHub review archive",
        "Source-only allowlist; secrets, environments, dependencies, dumps, and runtime files excluded.",
        "",
    ]
    for relative in files:
        source = PROJECT_ROOT / relative
        manifest_lines.append(
            f"{digest(source)}  {source.stat().st_size:>8}  {relative.as_posix()}"
        )

    TEMP_OUTPUT.unlink(missing_ok=True)
    with ZipFile(
        TEMP_OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9
    ) as archive:
        for relative in files:
            archive.write(PROJECT_ROOT / relative, relative.as_posix())
        archive.writestr("REVIEW_MANIFEST.txt", "\n".join(manifest_lines) + "\n")

    with ZipFile(TEMP_OUTPUT, "r") as archive:
        names = archive.namelist()
        if archive.testzip() is not None:
            raise RuntimeError("ZIP integrity verification failed")
        if len(names) != len(set(names)):
            raise RuntimeError("ZIP contains duplicate paths")
        for name in names:
            normalized = Path(name)
            lowered_parts = {part.casefold() for part in normalized.parts}
            if lowered_parts & FORBIDDEN_PARTS:
                raise RuntimeError(f"Forbidden path entered ZIP: {name}")
            if normalized.suffix.casefold() in FORBIDDEN_SUFFIXES:
                raise RuntimeError(f"Forbidden file type entered ZIP: {name}")

    os.replace(TEMP_OUTPUT, OUTPUT)
    return len(files) + 1, OUTPUT.stat().st_size


if __name__ == "__main__":
    count, size = build_archive()
    print(f"Created {OUTPUT}")
    print(f"Verified {count} archive entries; {size} bytes")
