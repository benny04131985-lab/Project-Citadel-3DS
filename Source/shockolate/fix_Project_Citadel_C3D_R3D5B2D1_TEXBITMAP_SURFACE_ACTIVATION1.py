#!/usr/bin/env python3
"""
Project Citadel R3D5B2D1 TEXBITMAP SURFACE ACTIVATION FIX1

Fixes one activation omission in the exact R3D5B2D source:

gameobj.c correctly calls:
    citadel_native_world_set_surface_kind(
        CITADEL_NATIVE_SURFACE_TEXBITMAP);

but Citro3DNative.c's setter accepted WALL/FLOOR/CEILING/DOOR/WORLD_BITMAP
and accidentally omitted TEXBITMAP, causing the default branch to convert
the requested kind back to NONE.

This patch adds only:
    case CITADEL_NATIVE_SURFACE_TEXBITMAP:

No capture logic, texture logic, masks, geometry, doors, terrain, sprites,
stereo behavior, shaders, logging format, or CMake files are changed.
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
BEFORE_SHA256 = "c6a77e83f7c8c9478d6f4ee53412caf77f1970cc8ce3ebbaecb3b2146a7ed7c2"
AFTER_SHA256 = "9d33a810cb72d2ba6d045a525e68d1619a2768d92da1d8682e6f7f11b938bb64"

OLD = """    case CITADEL_NATIVE_SURFACE_DOOR:
    case CITADEL_NATIVE_SURFACE_WORLD_BITMAP:
        citadel_native_surface_kind = kind;
        break;
"""
NEW = """    case CITADEL_NATIVE_SURFACE_DOOR:
    case CITADEL_NATIVE_SURFACE_WORLD_BITMAP:
    case CITADEL_NATIVE_SURFACE_TEXBITMAP:
        citadel_native_surface_kind = kind;
        break;
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
    print("PROJECT CITADEL R3D5B2D1 TEXBITMAP SURFACE ACTIVATION FIX1")
    print("=" * 78)
    print(f"Target: {target}")

    try:
        if not target.is_file():
            raise PatchError(f"Missing source file: {target}")

        current = sha256(target)

        if current == AFTER_SHA256:
            print("PASS: B2D1 activation fix is already installed exactly.")
            print("No files were changed.")
            return 0

        if current != BEFORE_SHA256:
            raise PatchError(
                "Unexpected Citro3DNative.c state; refusing to write.\n"
                f"Expected exact B2D: {BEFORE_SHA256}\n"
                f"Found:              {current}"
            )

        text = target.read_text(encoding="utf-8")

        if text.count(OLD) != 1:
            raise PatchError(
                "Expected exactly one surface-kind switch anchor; "
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
            print("PASS: exact B2D input and activation fix verified.")
            print("Check-only mode: no files were changed.")
            return 0

        backup = target.with_suffix(
            target.suffix + ".R3D5B2D1_TEXBITMAP_ACTIVATION_FIX1.bak"
        )
        shutil.copy2(target, backup)

        temporary = target.with_suffix(
            target.suffix + ".r3d5b2d1.tmp"
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
        print("PASS: R3D5B2D1 TEXBITMAP activation fix installed.")
        print(f"Backup: {backup}")
        print("TEXBITMAP surface-kind setter: ENABLED")
        print("Renderer architecture:          UNCHANGED")
        print("Modified files:                 Citro3DNative.c only")
        print(f"SHA-256: {AFTER_SHA256}")
        return 0

    except PatchError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
