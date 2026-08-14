#!/usr/bin/env python3
"""
verify_and_stage_citadel_c3d_r1_profile_binary.py

Run from:
    C:/Projects/Citadel_Citro3D_DEV/Source/shockolate

This script does not modify source or build files.

It:
  1. Verifies Shock.c contains TRANSPORTPROFILE1.
  2. Searches the R1 build tree for a .3dsx containing the profile markers.
  3. Copies the exact verified binary to:
       C:/Projects/CITADEL_C3D_R1_TRANSPORTPROFILE1_VERIFIED.3dsx
  4. Prints SHA-256 and embedded proof strings.
"""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path


ROOT = Path.cwd()
SOURCE = ROOT / "src/MacSrc/Shock.c"
BUILD = ROOT / "build-c3d-r1-profile1"
DESTINATION = Path("/c/Projects/CITADEL_C3D_R1_TRANSPORTPROFILE1_VERIFIED.3dsx")

SOURCE_MARKERS = (
    "PROJECT CITADEL C3D R1 TRANSPORTPROFILE1",
    "GPU C3D R1 TRANSPORTPROFILE1 SUMMARY",
    "MONO_SINGLE_EYE",
    "STEREO_DUAL_EYE",
)

BINARY_MARKERS = tuple(marker.encode("ascii") for marker in SOURCE_MARKERS[1:])


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    print("============================================================")
    print("CITADEL C3D R1 PROFILE BINARY VERIFIER")
    print("============================================================")

    if ROOT.name != "shockolate" or "Citadel_Citro3D_DEV" not in str(ROOT):
        fail(
            "Run this from "
            "C:/Projects/Citadel_Citro3D_DEV/Source/shockolate"
        )

    if not SOURCE.is_file():
        fail(f"Missing source: {SOURCE}")

    source_text = SOURCE.read_text(encoding="utf-8-sig", errors="replace")
    missing_source = [
        marker for marker in SOURCE_MARKERS if marker not in source_text
    ]
    if missing_source:
        fail(
            "The active Shock.c is not the R1 profile source.\n"
            "Missing:\n  - " + "\n  - ".join(missing_source)
        )

    print("SOURCE: TRANSPORTPROFILE1 markers verified.")

    if not BUILD.is_dir():
        fail(
            f"Build folder not found: {BUILD}\n"
            "Configure and build build-c3d-r1-profile1 first."
        )

    all_binaries = sorted(BUILD.rglob("*.3dsx"))
    if not all_binaries:
        fail(f"No .3dsx files were found under {BUILD}")

    matches: list[Path] = []

    for binary in all_binaries:
        data = binary.read_bytes()
        if all(marker in data for marker in BINARY_MARKERS):
            matches.append(binary)

    if not matches:
        print()
        print("Checked binaries:")
        for binary in all_binaries:
            print(f"  {binary}")
        fail(
            "No built .3dsx contains the TRANSPORTPROFILE1 markers.\n"
            "The build did not compile the active profiled Shock.c."
        )

    if len(matches) > 1:
        print("Multiple marked binaries found; selecting newest:")
        for binary in matches:
            print(f"  {binary}")

    selected = max(matches, key=lambda path: path.stat().st_mtime_ns)

    shutil.copy2(selected, DESTINATION)

    copied = DESTINATION.read_bytes()
    if not all(marker in copied for marker in BINARY_MARKERS):
        DESTINATION.unlink(missing_ok=True)
        fail("Destination verification failed after copying.")

    print()
    print("VERIFIED PROFILE BINARY FOUND")
    print(f"Source binary: {selected}")
    print(f"Staged binary: {DESTINATION}")
    print(f"SHA-256: {sha256(DESTINATION)}")
    print()
    print("Embedded proof:")
    for marker in SOURCE_MARKERS[1:]:
        print(f"  {marker}")
    print()
    print("Install only the staged binary shown above.")
    print("============================================================")


if __name__ == "__main__":
    main()
