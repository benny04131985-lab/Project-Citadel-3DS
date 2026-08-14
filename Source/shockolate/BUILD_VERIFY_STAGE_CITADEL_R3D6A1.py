#!/usr/bin/env python3
"""
BUILD + VERIFY + STAGE Project Citadel C3D R3D6A1 NATIVE STEREO TAKEOVER1

Run from MSYS2 with:
    python BUILD_VERIFY_STAGE_CITADEL_R3D6A1.py

This script:
  1. Verifies the active source is the exact installed R3D6A1 source.
  2. Deletes ONLY the canonical generated build/ directory.
  3. Reconfigures using the proven Citadel 3DS CMake recipe.
  4. Builds target project_citadel_3dsx.
  5. Finds the produced .3dsx and verifies R3D6A1 identity strings INSIDE it.
  6. Copies only the verified binary to:
       /c/Projects/CITADEL_C3D_R3D6A1_NATIVE_STEREO_TAKEOVER1.3dsx
  7. Writes a stage report with SHA-256 and the exact SD deployment filename.

It deliberately refuses to stage a B2D2/stale binary.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path("/c/Projects/Citadel_Citro3D_NATIVE_DEV/Source/shockolate")
BUILD = ROOT / "build"
STAGED = Path("/c/Projects/CITADEL_C3D_R3D6A1_NATIVE_STEREO_TAKEOVER1.3dsx")
REPORT = Path("/c/Projects/CITADEL_C3D_R3D6A1_NATIVE_STEREO_TAKEOVER1_STAGE_REPORT.txt")

SOURCE_HASHES = {
    "src/MacSrc/Shock.c":
        "235e70269ca7318568fb1d00beb92c4a7a1788ff9db9c450b1d3ad5fae22b6e7",
    "src/MacSrc/Citro3DNative.c":
        "43444641a52eedb2e439a345e11ca18113a9433996e9624b6792c2dfa3bb76f5",
}

# These strings must be embedded in the newly-linked .3dsx.
REQUIRED_BINARY_MARKERS = (
    b"CITADEL-C3D-R3D6A1-NATIVE-STEREO-TAKEOVER1",
    b"PROJECT CITADEL C3D R3D6A1 NATIVE STEREO TAKEOVER1 ACTIVE",
    b"_STEREO_PROOF.log",
    b"ACTIVE_DUAL_EYE_NATIVE_TAKEOVER",
    b"DUAL_EYE_RGBA5551_KEYED",
    b"Native stereo takeover proven",
)

# A stale B2D2 executable is allowed to contain old historical strings in source
# ancestry, so we do NOT reject merely because "R3D5B2D2" appears somewhere.
# We require all of the NEW R3D6A1 runtime/logger strings above instead.

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def fail(message: str) -> None:
    print()
    print("ERROR:", message, file=sys.stderr)
    raise SystemExit(1)

def run(cmd: list[str], env: dict[str, str]) -> None:
    print()
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, env=env, check=True)

def main() -> int:
    print("=" * 78)
    print("PROJECT CITADEL C3D R3D6A1 — CLEAN BUILD / VERIFY / STAGE")
    print("=" * 78)
    print(f"Source root: {ROOT}")

    if not ROOT.is_dir():
        fail(f"Missing source root: {ROOT}")

    print()
    print("Verifying exact R3D6A1 source hashes...")
    for relative, expected in SOURCE_HASHES.items():
        path = ROOT / relative
        if not path.is_file():
            fail(f"Missing source file: {path}")
        actual = sha256(path)
        print(f"  {relative}")
        print(f"    {actual}")
        if actual != expected:
            fail(
                f"Source is not exact R3D6A1 for {relative}\n"
                f"Expected: {expected}\n"
                f"Found:    {actual}"
            )

    print("PASS: exact R3D6A1 source verified.")

    env = os.environ.copy()
    env["DEVKITPRO"] = "/opt/devkitpro"
    env["DEVKITARM"] = "/opt/devkitpro/devkitARM"

    cmake = shutil.which("cmake", path=env.get("PATH"))
    if not cmake:
        fail("cmake was not found in PATH.")

    if BUILD.exists():
        print()
        print(f"Removing generated build tree only: {BUILD}")
        shutil.rmtree(BUILD)

    configure = [
        cmake,
        "-S", ".",
        "-B", "build",
        "-DCMAKE_TOOLCHAIN_FILE=/opt/devkitpro/cmake/3DS.cmake",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        "-DENABLE_OPENGL=OFF",
        "-DENABLE_SOUND=OFF",
        "-DENABLE_FLUIDSYNTH=OFF",
        "-DENABLE_SDL2=ON",
    ]
    run(configure, env)

    jobs = str(os.cpu_count() or 4)
    build_cmd = [
        cmake,
        "--build", "build",
        "--target", "project_citadel_3dsx",
        "-j" + jobs,
    ]
    run(build_cmd, env)

    candidates = sorted(BUILD.rglob("*.3dsx"))
    if not candidates:
        fail("Build completed but no .3dsx was found under build/.")

    print()
    print("Checking built .3dsx files for exact R3D6A1 runtime identity...")

    valid: list[Path] = []
    for candidate in candidates:
        data = candidate.read_bytes()
        missing = [
            marker.decode("ascii", errors="replace")
            for marker in REQUIRED_BINARY_MARKERS
            if marker not in data
        ]

        print(f"  {candidate.relative_to(ROOT)}")
        if missing:
            print("    REJECT: missing R3D6A1 marker(s):")
            for marker in missing:
                print(f"      - {marker}")
        else:
            print("    PASS: all R3D6A1 markers embedded")
            valid.append(candidate)

    if len(valid) != 1:
        fail(
            f"Expected exactly one verified R3D6A1 .3dsx, found {len(valid)}.\n"
            "Nothing was staged."
        )

    binary = valid[0]
    binary_hash = sha256(binary)

    print()
    print("VERIFIED BUILD:")
    print(f"  {binary}")
    print(f"  SHA-256: {binary_hash}")

    STAGED.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(binary, STAGED)

    staged_hash = sha256(STAGED)
    if staged_hash != binary_hash:
        fail("Staged binary hash differs from verified build output.")

    report = f"""PROJECT CITADEL C3D R3D6A1 STAGING REPORT
============================================================

Milestone:
  CITADEL-C3D-R3D6A1-NATIVE-STEREO-TAKEOVER1

Verified build:
  {binary}

Staged binary:
  {STAGED}

SHA-256:
  {staged_hash}

R3D6A1 binary identity:
  PASS — all required R3D6A1 runtime/logger markers embedded

Expected NEW hardware evidence filenames:
  C3D_RUN_R3D6A1_<token>_STARTED.txt
  C3D_RUN_R3D6A1_<token>_STEREO_PROOF.log
  C3D_RUN_R3D6A1_<token>_DIAG.log

Deploy this staged file to the stereo-development install as:
  SD:/3ds/SystemShock3D/3D_Citadel_3DS.3dsx

Do NOT hardware-test any binary that still produces:
  C3D_RUN_R3D5B2D2_*
"""
    REPORT.write_text(report, encoding="utf-8")

    print()
    print("=" * 78)
    print("PASS: R3D6A1 BUILD VERIFIED AND STAGED")
    print("=" * 78)
    print(f"Staged:  {STAGED}")
    print(f"SHA-256: {staged_hash}")
    print(f"Report:  {REPORT}")
    print()
    print("NEXT HARDWARE DEPLOYMENT TARGET:")
    print("  SD:/3ds/SystemShock3D/3D_Citadel_3DS.3dsx")
    print()
    print("EXPECTED NEW LOG NAMES:")
    print("  C3D_RUN_R3D6A1_<token>_STARTED.txt")
    print("  C3D_RUN_R3D6A1_<token>_STEREO_PROOF.log")
    print("  C3D_RUN_R3D6A1_<token>_DIAG.log")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
