"""Build the Gradescope zip (report + code + small data) and check it is portable.

Usage:
    python scripts/package_submission.py --check      # portability + size checks only
    python scripts/package_submission.py --dry-run    # check, then list what would be zipped
    python scripts/package_submission.py              # check, then write submission/<name>.zip

The course requires code and data that run on another computer with relative paths only.
`data/raw/` (large downloads, git-ignored) is excluded; `data/interim` and `data/processed`
are included.
"""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "submission"

INCLUDE = [
    "README.md",
    "LICENSE",
    "pyproject.toml",
    "uv.lock",
    "config",
    "src",
    "scripts",
    "tests",
    "notebooks",
    "docs",
    "report",
    "data",
]
EXCLUDE_DIRS = {"__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".ruff_cache", ".venv", "raw"}
EXCLUDE_SUFFIXES = {".pyc", ".lic"}
KEEP_UNDER_RAW = {".gitkeep"}

MAX_DATA_MB = 25.0
SCAN_SUFFIXES = {".py", ".yaml", ".yml", ".toml", ".ipynb"}
# Files that legitimately contain example absolute paths (this script, tests).
SCAN_SKIP = {Path("scripts/package_submission.py")}
SCAN_SKIP_DIRS = {"tests"}
ABS_PATH = re.compile(r"[A-Za-z]:[\\/]{1,2}(?:Users|Documents)|(?<![\w.])/(?:Users|home)/\w+")


def iter_files() -> list[Path]:
    files: list[Path] = []
    for name in INCLUDE:
        p = ROOT / name
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if not f.is_file():
                    continue
                rel_parts = f.relative_to(ROOT).parts
                if any(part in EXCLUDE_DIRS for part in rel_parts):
                    if not (rel_parts[:2] == ("data", "raw") and f.name in KEEP_UNDER_RAW):
                        continue
                if f.suffix in EXCLUDE_SUFFIXES:
                    continue
                files.append(f)
    return files


def check(files: list[Path]) -> list[str]:
    problems: list[str] = []
    for f in files:
        rel = f.relative_to(ROOT)
        if f.suffix not in SCAN_SUFFIXES or rel in SCAN_SKIP or rel.parts[0] in SCAN_SKIP_DIRS:
            continue
        text = f.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            if ABS_PATH.search(line):
                problems.append(f"absolute path in {rel.as_posix()}:{lineno}: {line.strip()[:80]}")
    data_bytes = sum(f.stat().st_size for f in files if f.relative_to(ROOT).parts[0] == "data")
    if data_bytes / 1e6 > MAX_DATA_MB:
        problems.append(f"data/ is {data_bytes / 1e6:.1f} MB (limit {MAX_DATA_MB} MB)")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="only run checks")
    parser.add_argument("--dry-run", action="store_true", help="list files, do not write a zip")
    parser.add_argument("--name", default="d2a-final-submission", help="zip base name")
    args = parser.parse_args(argv)

    files = iter_files()
    problems = check(files)
    for msg in problems:
        print(f"FAIL: {msg}", file=sys.stderr)
    if problems:
        return 1
    print(f"OK: {len(files)} files pass portability and size checks")
    if args.check:
        return 0

    if args.dry_run:
        for f in files:
            print(f.relative_to(ROOT).as_posix())
        return 0

    OUT_DIR.mkdir(exist_ok=True)
    target = OUT_DIR / f"{args.name}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.write(f, f.relative_to(ROOT).as_posix())
    print(f"wrote {target.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
