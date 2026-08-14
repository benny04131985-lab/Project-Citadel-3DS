#!/usr/bin/env python3
"""
Exact compile/runtime fix for:
PRESERVE_AND_COLLECT_Project_Citadel_C3D_R3D4D_HW_PASS_FOR_R3D5.py

Adds the missing standard-library import:
    import tempfile

No checkpoint, source, archive, audit-selection, or validation behavior changes.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

DEFAULT_TARGET = Path(
    "/c/Projects/Citadel_Citro3D_NATIVE_DEV/Source/shockolate/"
    "PRESERVE_AND_COLLECT_Project_Citadel_C3D_R3D4D_HW_PASS_FOR_R3D5.py"
)

EXPECTED_BEFORE = "3440393af98e3f2d1136d8d86622f25ea3ca46f498707b64f2ef8d45227c091b"
EXPECTED_AFTER = "c5087ade255dc7522fcf8237f5eab1d59d3b06e86e07601c2ccaf25aff53d246"

OLD = """import sys
import tarfile
import zipfile
"""

NEW = """import sys
import tarfile
import tempfile
import zipfile
"""


class PatchError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET)
    args = parser.parse_args()

    target = args.target.resolve()

    print("=" * 76)
    print("FIX R3D4D PRESERVATION AUDIT TEMPFILE IMPORT")
    print("=" * 76)
    print(f"Target: {target}")

    try:
        if not target.is_file():
            raise PatchError(f"Missing target script: {target}")

        current = sha256(target)

        if current == EXPECTED_AFTER:
            print("PASS: tempfile import fix is already installed exactly.")
            print("No files were changed.")
            return 0

        if current != EXPECTED_BEFORE:
            raise PatchError(
                "Unknown target script state; refusing to write.\n"
                f"Expected original: {EXPECTED_BEFORE}\n"
                f"Found:             {current}"
            )

        text = target.read_text(encoding="utf-8")

        count = text.count(OLD)
        if count != 1:
            raise PatchError(
                f"Expected one import anchor, found {count}."
            )

        output = text.replace(OLD, NEW, 1)
        produced = hashlib.sha256(output.encode("utf-8")).hexdigest()

        if produced != EXPECTED_AFTER:
            raise PatchError(
                "Internal output hash mismatch.\n"
                f"Expected: {EXPECTED_AFTER}\n"
                f"Produced: {produced}"
            )

        backup = target.with_suffix(target.suffix + ".before_tempfile_fix.bak")
        shutil.copy2(target, backup)

        temporary = target.with_suffix(target.suffix + ".tempfile_fix.tmp")
        temporary.write_text(output, encoding="utf-8", newline="\n")
        temporary.replace(target)

        if sha256(target) != EXPECTED_AFTER:
            shutil.copy2(backup, target)
            raise PatchError(
                "Post-write verification failed; original restored."
            )

        print("")
        print("PASS: missing tempfile import installed.")
        print(f"Backup: {backup}")
        print(f"New SHA-256: {EXPECTED_AFTER}")
        print("Behavioral changes: NONE")
        print("Required action: rerun the original preservation command")
        return 0

    except PatchError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
