#!/usr/bin/env python3
"""
Fix Project Citadel R3D5B2A triangle metadata initialization.

B2A changed CitadelNativeWorldTriangle metadata from:

    uint8_t reserved[2];

to:

    uint8_t bitmap_category;
    uint8_t reserved;

The standard world-triangle append path still indexed the obsolete array.
This exact patch initializes non-bitmap triangles as category NONE and clears
the remaining scalar reserved byte.

No renderer routing, geometry, texture, logging, shader, or CMake behavior
is changed.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

DEFAULT_ROOT = Path(
    "/c/Projects/Citadel_Citro3D_NATIVE_DEV/Source/shockolate"
)
RELATIVE = Path("src/MacSrc/Citro3DNative.c")
BEFORE_SHA256 = "7e9d5afcc3cd96bf8425b9eb167efa8a96e778abad0b2c45838a5832bf62d670"
AFTER_SHA256 = "4094614334e471f646c4c20582d1f9f6ea397cd921c3df87fd152cb1e2f021b7"

OLD = """    triangle->kind = kind;
    triangle->light_flag = light_flag ? 1u : 0u;
    triangle->reserved[0] = 0;
    triangle->reserved[1] = 0;
"""
NEW = """    triangle->kind = kind;
    triangle->light_flag = light_flag ? 1u : 0u;
    triangle->bitmap_category =
        CITADEL_NATIVE_BITMAP_CATEGORY_NONE;
    triangle->reserved = 0;
"""


class PatchError(RuntimeError):
    pass


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    root = args.root.resolve()
    target = root / RELATIVE

    print("=" * 78)
    print("PROJECT CITADEL R3D5B2A TRIANGLE METADATA FIX1")
    print("=" * 78)
    print(f"Target: {target}")

    try:
        if not target.is_file():
            raise PatchError(f"Missing source file: {target}")

        current = sha256(target)

        if current == AFTER_SHA256:
            print("PASS: triangle metadata fix is already installed.")
            print("No files were changed.")
            return 0

        if current != BEFORE_SHA256:
            raise PatchError(
                "Unexpected Citro3DNative.c state; refusing to write.\n"
                f"Expected B2A: {BEFORE_SHA256}\n"
                f"Found:       {current}"
            )

        text = target.read_text(encoding="utf-8")

        if text.count(OLD) != 1:
            raise PatchError(
                "Expected exactly one obsolete reserved-array initializer; "
                f"found {text.count(OLD)}."
            )

        output = text.replace(OLD, NEW, 1).encode("utf-8")
        output_hash = hashlib.sha256(output).hexdigest()

        if output_hash != AFTER_SHA256:
            raise PatchError(
                "Generated output hash mismatch.\n"
                f"Expected: {AFTER_SHA256}\n"
                f"Found:    {output_hash}"
            )

        if args.check_only:
            print("PASS: exact B2A input and metadata fix verified.")
            print("Check-only mode: no files were changed.")
            return 0

        backup = target.with_suffix(
            target.suffix + ".R3D5B2A_TRIANGLE_METADATA_FIX1.bak"
        )
        shutil.copy2(target, backup)

        temporary = target.with_suffix(
            target.suffix + ".r3d5b2a_metadata.tmp"
        )
        temporary.write_bytes(output)
        temporary.replace(target)

        final_hash = sha256(target)

        if final_hash != AFTER_SHA256:
            shutil.copy2(backup, target)
            raise PatchError(
                "Post-write verification failed; original restored.\n"
                f"Expected: {AFTER_SHA256}\n"
                f"Found:    {final_hash}"
            )

        print("")
        print("PASS: R3D5B2A triangle metadata fix installed.")
        print(f"Backup: {backup}")
        print("Ordinary terrain/door category: NONE")
        print("Reserved metadata byte:         ZERO")
        print("Renderer behavior:              UNCHANGED")
        print("Modified files:                 Citro3DNative.c only")
        print(f"SHA-256: {AFTER_SHA256}")
        return 0

    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
