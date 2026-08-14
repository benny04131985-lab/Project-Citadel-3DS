#!/usr/bin/env python3
"""
finalize_Project_Citadel_R2C_HOTFIX_and_FORK_NATIVE.py

Run from:
    C:/Projects/Citadel_Citro3D_DEV/Source/shockolate

Purpose:
  1. Verify the exact hardware-proven R2C source, binary, and FTP evidence.
  2. Preserve a complete timestamped R2C milestone checkpoint and tar.gz.
  3. Update the local Citadel_3D_GITHUB working tree as the publish-ready
     v1.0.2 Final Software Renderer Hotfix.
  4. Stage the exact tested release payload outside the repository.
  5. Create a separate Citadel_Citro3D_NATIVE_DEV source tree from the exact
     frozen R2C source, with R3A-WORLDPROOF1 handoff notes.

Safety:
  - No source behavior is changed.
  - The exact hardware-tested R2C .3dsx is staged unchanged.
  - No push or GitHub release is performed.
  - No remote branch is created.
  - By default no local git commit/tag is made. Pass --commit-local to create
    a local commit, annotated v1.0.2 tag, and native-citro3d-world branch.
  - Existing native trees, checkpoint names, and release staging folders are
    never overwritten.
  - The GitHub repo must be clean before this script changes it.

FTP evidence examples:
    python finalize_Project_Citadel_R2C_HOTFIX_and_FORK_NATIVE.py \
        --evidence-zip '/c/Users/benny/Downloads/Temp(4).zip'

    python finalize_Project_Citadel_R2C_HOTFIX_and_FORK_NATIVE.py \
        --profile-log /c/Users/benny/Downloads/C3D_R2C_PINGPONGTILEDPROFILE.log \
        --diag-log /c/Users/benny/Downloads/citadel_diag.log
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, NoReturn


RELEASE_VERSION = "1.0.2"
RELEASE_TAG = "v1.0.2"
RELEASE_TITLE = "Project Citadel 3D v1.0.2 — Final Software Renderer Hotfix"
MILESTONE = "CITADEL_C3D_R2C_PINGPONGTILED1_HW_PASS"
DISPLAY_MILESTONE = "CITADEL-C3D-R2C-PINGPONGTILED1"
EXPECTED_SOURCE_FRAGMENT = "Citadel_Citro3D_DEV/Source/shockolate"

SOURCE_ROOT = Path.cwd().resolve()
GITHUB_ROOT = Path("/c/Projects/Citadel_3D_GITHUB")
CHECKPOINT_PARENT = Path("/c/Projects/Citadel_C3D_CHECKPOINTS")
RELEASE_STAGE = Path("/c/Projects/Citadel_3D_v1.0.2_R2C_SOFTWARE_HOTFIX_RELEASE")
NATIVE_PROJECT_ROOT = Path("/c/Projects/Citadel_Citro3D_NATIVE_DEV")
NATIVE_SOURCE_ROOT = NATIVE_PROJECT_ROOT / "Source/shockolate"

BUILD_ROOT = SOURCE_ROOT / "build-c3d-r2c-pingpongtiled1"
STAGED_BINARY = Path("/c/Projects/CITADEL_C3D_R2C_PINGPONGTILED1.3dsx")
SHOCK_SOURCE = SOURCE_ROOT / "src/MacSrc/Shock.c"
CMAKE_FILE = SOURCE_ROOT / "CMakeLists.txt"
SHADER_FILE = SOURCE_ROOT / "src/MacSrc/citadel_directquad_vshader.v.pica"
EMBEDDER_FILE = SOURCE_ROOT / "tools/citadel_embed_binary.py"
PATCH_SCRIPT = SOURCE_ROOT / "apply_Project_Citadel_C3D_R2C_PINGPONGTILED1.py"
BUILD_LOG = SOURCE_ROOT / "C3D_R2C_PINGPONGTILED1_BUILD.log"

PROFILE_FILENAME = "C3D_R2C_PINGPONGTILEDPROFILE.log"
DIAG_FILENAME = "citadel_diag.log"
BINARY_RELEASE_NAME = "3D_Citadel_3DS.3dsx"

SOURCE_MARKERS = (
    "PROJECT CITADEL C3D R0 DIRECTQUAD1",
    "PROJECT CITADEL C3D R1 TRANSPORTPROFILE1",
    "PROJECT CITADEL C3D R2A DIRECTTILED1",
    "PROJECT CITADEL C3D R2B CROPPEDTILED1",
    "PROJECT CITADEL C3D R2C PINGPONGTILED1",
    "C3D_R2C_PINGPONGTILEDPROFILE.log",
    "CROPPED_TILED_PINGPONG_OVERLAP",
)

BINARY_MARKERS = (
    b"PROJECT CITADEL C3D R2C PINGPONGTILED1 ACTIVE",
    b"C3D_R2C_PINGPONGTILEDPROFILE.log",
    b"GPU C3D R2C PINGPONGTILED INIT SUCCESS",
    b"CROPPED_TILED_PINGPONG_OVERLAP",
    b"MONO_SINGLE_EYE",
    b"STEREO_DUAL_EYE",
)

PROFILE_MARKERS = (
    "PROJECT CITADEL C3D R2C PINGPONGTILED1 ACTIVE",
    "Transport active: CITADEL-C3D-R2C-PINGPONGTILED1",
    "Cropped-tiled enabled at shutdown: YES",
    "Ping-pong overlap enabled at shutdown: YES second_set=YES",
    "Direct-tiled validation: PASS mismatches=0",
    "Upload failures: 0",
    "Draw failures: 0",
    "Clean Shutdown: YES",
)

DIAG_MARKERS = (
    "Version: 1.0.1-DIAG2-FPS-SPLIT",
    "Hardware detected: New Nintendo 3DS",
    "Mono average FPS:",
    "Stereo average FPS:",
    "Combined average FPS:",
)

# Original stable diagnostic baseline measured before the C3D transport work.
BASELINE = {
    "mono_fps": 21.808,
    "mono_ms": 45.856,
    "stereo_fps": 11.608,
    "stereo_ms": 86.146,
    "combined_fps": 17.178,
}

EXCLUDED_DIR_NAMES = {
    ".git",
    ".vs",
    ".vscode",
    "__pycache__",
    "CITADEL_C3D_R0_AUDIT",
}
EXCLUDED_FILE_SUFFIXES = {".o", ".obj", ".a", ".elf", ".3dsx", ".cia", ".smdh"}

PUBLIC_SYNC_FILES = (
    Path("CMakeLists.txt"),
    Path("src/MacSrc/Shock.c"),
    Path("src/MacSrc/citadel_directquad_vshader.v.pica"),
    Path("tools/citadel_embed_binary.py"),
)


class FinalizeError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceFile:
    logical_name: str
    description: str
    data: bytes
    timestamp_ns: int

    @property
    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace")

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def fail(message: str) -> NoReturn:
    raise SystemExit(f"\nERROR: {message}\nNothing was pushed or published.\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def run(command: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and result.returncode != 0:
        joined = " ".join(command)
        detail = (result.stdout + result.stderr).strip()
        raise FinalizeError(f"Command failed ({joined}):\n{detail}")
    return result


def safe_match(text: str, pattern: str, label: str) -> re.Match[str]:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise FinalizeError(f"Could not parse {label}.")
    return match


def safe_float(text: str, pattern: str, label: str) -> float:
    return float(safe_match(text, pattern, label).group(1))


def safe_int(text: str, pattern: str, label: str) -> int:
    return int(safe_match(text, pattern, label).group(1))


def pct_gain(before: float, after: float) -> float:
    return ((after - before) / before) * 100.0 if before else 0.0


def pct_reduction(before: float, after: float) -> float:
    return ((before - after) / before) * 100.0 if before else 0.0


def evidence_from_path(path: Path, logical_name: str) -> EvidenceFile | None:
    if not path.is_file():
        return None
    return EvidenceFile(logical_name, str(path), path.read_bytes(), path.stat().st_mtime_ns)


def evidence_from_zip(path: Path) -> list[EvidenceFile]:
    results: list[EvidenceFile] = []
    if not path.is_file() or not zipfile.is_zipfile(path):
        return results
    stamp = path.stat().st_mtime_ns
    with zipfile.ZipFile(path, "r") as archive:
        for member in archive.infolist():
            base = Path(member.filename).name.lower()
            logical: str | None = None
            if "c3d_r2c_pingpongtiledprofile" in base and base.endswith(".log"):
                logical = PROFILE_FILENAME
            elif base == "citadel_diag.log":
                logical = DIAG_FILENAME
            if logical:
                results.append(
                    EvidenceFile(
                        logical,
                        f"{path} :: {member.filename}",
                        archive.read(member),
                        stamp,
                    )
                )
    return results


def locate_evidence(
    explicit_profile: Path | None,
    explicit_diag: Path | None,
    explicit_zip: Path | None,
) -> tuple[EvidenceFile, EvidenceFile, Path | None]:
    candidates: list[EvidenceFile] = []
    zip_used: Path | None = None

    if explicit_profile:
        item = evidence_from_path(explicit_profile.expanduser(), PROFILE_FILENAME)
        if item:
            candidates.append(item)
    if explicit_diag:
        item = evidence_from_path(explicit_diag.expanduser(), DIAG_FILENAME)
        if item:
            candidates.append(item)
    if explicit_zip:
        explicit_zip = explicit_zip.expanduser()
        candidates.extend(evidence_from_zip(explicit_zip))
        zip_used = explicit_zip

    search_dirs = [
        SOURCE_ROOT,
        Path("/c/Users/benny/Downloads"),
        Path("/c/Users/benny/Desktop"),
    ]
    for directory in search_dirs:
        if not directory.is_dir():
            continue
        for name, logical in ((PROFILE_FILENAME, PROFILE_FILENAME), (DIAG_FILENAME, DIAG_FILENAME)):
            item = evidence_from_path(directory / name, logical)
            if item:
                candidates.append(item)
        for zpath in sorted(directory.glob("Temp*.zip")):
            found = evidence_from_zip(zpath)
            if found:
                candidates.extend(found)
                if zip_used is None:
                    zip_used = zpath

    profiles = [item for item in candidates if item.logical_name == PROFILE_FILENAME]
    diags = [item for item in candidates if item.logical_name == DIAG_FILENAME]

    valid_profiles = [
        item for item in profiles
        if all(marker in item.text for marker in PROFILE_MARKERS)
    ]
    valid_diags = [
        item for item in diags
        if all(marker in item.text for marker in DIAG_MARKERS)
        and "Build: Aug  3 2026 16:52:56" in item.text
    ]

    if not valid_profiles:
        raise FinalizeError(
            "No hardware-proven R2C profile was found. Pass --evidence-zip Temp(4).zip "
            "or --profile-log PATH."
        )
    if not valid_diags:
        raise FinalizeError(
            "No matching R2C citadel_diag.log was found. Pass --evidence-zip Temp(4).zip "
            "or --diag-log PATH."
        )

    return (
        max(valid_profiles, key=lambda item: item.timestamp_ns),
        max(valid_diags, key=lambda item: item.timestamp_ns),
        zip_used,
    )


def parse_profile(profile: EvidenceFile) -> dict[str, object]:
    text = profile.text
    for marker in PROFILE_MARKERS:
        if marker not in text:
            raise FinalizeError(f"R2C profile marker missing: {marker}")

    validations = safe_match(
        text,
        r"^Cropped validations:\s+legacy_left=(\w+)\s+split_left=(\w+)\s+"
        r"legacy_right=(\w+)\s+split_right=(\w+)\s+mismatches=(\d+)",
        "cropped validation states",
    )
    states = {
        "legacy_left": validations.group(1),
        "split_left": validations.group(2),
        "legacy_right": validations.group(3),
        "split_right": validations.group(4),
    }
    mismatches = int(validations.group(5))
    if states["legacy_left"] != "PASS" or states["split_left"] != "PASS" or states["split_right"] != "PASS":
        raise FinalizeError(f"Required R2C validation path failed: {states}")
    if states["legacy_right"] not in {"PASS", "PENDING"}:
        raise FinalizeError(f"Unexpected legacy_right validation state: {states['legacy_right']}")
    if mismatches != 0:
        raise FinalizeError(f"R2C recorded {mismatches} visual mismatches.")

    cropped = safe_match(
        text,
        r"^Cropped frame passes:\s+top_left=(\d+)\s+top_right=(\d+)\s+"
        r"bottom=(\d+)\s+fallback=(\d+)\s+pixels=(\d+)",
        "cropped frame passes",
    )
    ping = safe_match(
        text,
        r"^Ping-pong passes:\s+preframe_uploads=(\d+)\s+inframe_uploads=(\d+)\s+"
        r"preframe_failures=(\d+)\s+switches=(\d+)\s+set0_draws=(\d+)\s+set1_draws=(\d+)",
        "ping-pong passes",
    )
    direct_fallback = safe_int(text, r"^Direct-tiled eye passes:.*fallback=(\d+)", "direct-tiled fallback")

    cropped_fallback = int(cropped.group(4))
    preframe_failures = int(ping.group(3))
    set0_draws = int(ping.group(5))
    set1_draws = int(ping.group(6))
    if cropped_fallback != 0 or direct_fallback != 0 or preframe_failures != 0:
        raise FinalizeError(
            f"Fallback/failure proof is not clean: cropped={cropped_fallback}, "
            f"direct={direct_fallback}, preframe_failures={preframe_failures}"
        )
    if set0_draws <= 0 or set1_draws <= 0:
        raise FinalizeError("Both ping-pong texture sets were not exercised.")

    return {
        "build": safe_match(text, r"^Build:\s*(.+)$", "profile build").group(1),
        "validation_states": states,
        "mismatches": mismatches,
        "top_left_passes": int(cropped.group(1)),
        "top_right_passes": int(cropped.group(2)),
        "bottom_passes": int(cropped.group(3)),
        "cropped_fallbacks": cropped_fallback,
        "pixels_processed": int(cropped.group(5)),
        "preframe_uploads": int(ping.group(1)),
        "inframe_uploads": int(ping.group(2)),
        "preframe_failures": preframe_failures,
        "switches": int(ping.group(4)),
        "set0_draws": set0_draws,
        "set1_draws": set1_draws,
        "direct_fallbacks": direct_fallback,
        "presented_frames": safe_int(text, r"^Presented frames observed by GPU logger:\s*(\d+)", "presented frames"),
        "mono_profile_frames": safe_int(text, r"^PROFILE mode=MONO_SINGLE_EYE frames=(\d+)", "mono profile frames"),
        "mono_profile_cycle_ms": safe_float(text, r"^PROFILE mode=MONO_SINGLE_EYE frames=\d+ avg_cycle_ms=([0-9.]+)", "mono profile cycle"),
        "mono_pre_present_ms": safe_float(text, r"^PROFILE mode=MONO_SINGLE_EYE frames=\d+.*avg_pre_present_ms=([0-9.]+)", "mono pre-present"),
        "mono_present_ms": safe_float(text, r"^PROFILE mode=MONO_SINGLE_EYE frames=\d+.*avg_present_ms=([0-9.]+)", "mono presentation"),
        "mono_frame_begin_ms": safe_float(text, r"^PROFILE mode=MONO_SINGLE_EYE avg_frame_begin_ms=([0-9.]+)", "mono frame begin"),
        "mono_upload_ms": safe_float(text, r"^PROFILE mode=MONO_SINGLE_EYE avg_frame_begin_ms=[0-9.]+ avg_upload_total_ms=([0-9.]+)", "mono upload"),
        "stereo_profile_frames": safe_int(text, r"^PROFILE mode=STEREO_DUAL_EYE frames=(\d+)", "stereo profile frames"),
        "stereo_profile_cycle_ms": safe_float(text, r"^PROFILE mode=STEREO_DUAL_EYE frames=\d+ avg_cycle_ms=([0-9.]+)", "stereo profile cycle"),
        "stereo_pre_present_ms": safe_float(text, r"^PROFILE mode=STEREO_DUAL_EYE frames=\d+.*avg_pre_present_ms=([0-9.]+)", "stereo pre-present"),
        "stereo_present_ms": safe_float(text, r"^PROFILE mode=STEREO_DUAL_EYE frames=\d+.*avg_present_ms=([0-9.]+)", "stereo presentation"),
        "stereo_frame_begin_ms": safe_float(text, r"^PROFILE mode=STEREO_DUAL_EYE avg_frame_begin_ms=([0-9.]+)", "stereo frame begin"),
        "stereo_upload_ms": safe_float(text, r"^PROFILE mode=STEREO_DUAL_EYE avg_frame_begin_ms=[0-9.]+ avg_upload_total_ms=([0-9.]+)", "stereo upload"),
    }


def parse_diag(diag: EvidenceFile) -> dict[str, object]:
    text = diag.text
    for marker in DIAG_MARKERS:
        if marker not in text:
            raise FinalizeError(f"Diagnostic marker missing: {marker}")
    metrics = {
        "diag_version": safe_match(text, r"^Version:\s*(.+)$", "diagnostic version").group(1),
        "build": safe_match(text, r"^Build:\s*(.+)$", "diagnostic build").group(1),
        "duration_seconds": safe_float(text, r"^Session duration:\s*([0-9.]+) seconds", "session duration"),
        "measured_frames": safe_int(text, r"^Measured frames:\s*(\d+)", "measured frames"),
        "mono_frames": safe_int(text, r"^Mono-slider frames:\s*(\d+)", "mono diagnostic frames"),
        "mono_fps": safe_float(text, r"^Mono average FPS:\s*([0-9.]+)", "mono FPS"),
        "mono_ms": safe_float(text, r"^Mono average frame time:\s*([0-9.]+) ms", "mono frame time"),
        "stereo_frames": safe_int(text, r"^Stereo-slider frames:\s*(\d+)", "stereo diagnostic frames"),
        "stereo_fps": safe_float(text, r"^Stereo average FPS:\s*([0-9.]+)", "stereo FPS"),
        "stereo_ms": safe_float(text, r"^Stereo average frame time:\s*([0-9.]+) ms", "stereo frame time"),
        "combined_fps": safe_float(text, r"^Combined average FPS:\s*([0-9.]+)", "combined FPS"),
        "combined_ms": safe_float(text, r"^Average frame time:\s*([0-9.]+) ms", "combined frame time"),
    }
    if float(metrics["mono_fps"]) < 30.0:
        raise FinalizeError(f"R2C mono proof did not cross 30 FPS: {metrics['mono_fps']}")
    return metrics


def locate_verified_binary() -> Path:
    candidates: list[Path] = []
    if BUILD_ROOT.is_dir():
        candidates.extend(sorted(BUILD_ROOT.rglob("*.3dsx")))
    if STAGED_BINARY.is_file():
        candidates.append(STAGED_BINARY)
    if not candidates:
        raise FinalizeError(
            f"No R2C .3dsx found under {BUILD_ROOT} or at {STAGED_BINARY}."
        )
    matches: list[Path] = []
    for path in candidates:
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if all(marker in data for marker in BINARY_MARKERS):
            matches.append(path)
    if not matches:
        raise FinalizeError("No candidate R2C binary contains every required proof marker.")
    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def verify_source_tree() -> None:
    normalized = SOURCE_ROOT.as_posix().lower()
    if EXPECTED_SOURCE_FRAGMENT.lower() not in normalized:
        raise FinalizeError(
            "Run this from C:/Projects/Citadel_Citro3D_DEV/Source/shockolate.\n"
            f"Current directory: {SOURCE_ROOT}"
        )
    for path in (SHOCK_SOURCE, CMAKE_FILE, SHADER_FILE, EMBEDDER_FILE):
        if not path.is_file():
            raise FinalizeError(f"Required R2C source component is missing: {path}")
    shock = read_text(SHOCK_SOURCE)
    missing = [marker for marker in SOURCE_MARKERS if marker not in shock]
    if missing:
        raise FinalizeError("Shock.c is not the full R2C source. Missing:\n  - " + "\n  - ".join(missing))
    cmake = read_text(CMAKE_FILE)
    if "CITADEL_C3D_DIRECTQUAD_SHADER_SOURCE" not in cmake:
        raise FinalizeError("CMakeLists.txt is missing the R0 Citro3D shader build block.")


def ignore_source_copy(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    current = Path(directory)
    for name in names:
        path = current / name
        if name in EXCLUDED_DIR_NAMES:
            ignored.add(name)
        elif path.is_dir() and (name.startswith("build-") or name.startswith("CITADEL_C3D_CHECKPOINT")):
            ignored.add(name)
        elif path.is_file() and path.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
            ignored.add(name)
    return ignored


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def write_sha256sums(root: Path, output: Path) -> None:
    lines: list[str] = []
    for path in iter_files(root):
        if path.resolve() == output.resolve():
            continue
        lines.append(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}")
    write_text(output, "\n".join(lines))


def release_notes(profile: dict[str, object], diag: dict[str, object]) -> str:
    mono_gain = pct_gain(BASELINE["mono_fps"], float(diag["mono_fps"]))
    stereo_gain = pct_gain(BASELINE["stereo_fps"], float(diag["stereo_fps"]))
    mono_ms_drop = pct_reduction(BASELINE["mono_ms"], float(diag["mono_ms"]))
    stereo_ms_drop = pct_reduction(BASELINE["stereo_ms"], float(diag["stereo_ms"]))
    legacy_right = profile["validation_states"]["legacy_right"]  # type: ignore[index]
    return f"""# {RELEASE_TITLE}

## Summary

This hotfix is the final optimized software-renderer release before native
Citro3D world rendering development begins. System Shock's original software
renderer still produces the game world, while the 3DS presentation path has
been replaced and optimized through direct Citro3D textured quads, fused
indexed-to-tiled conversion, output-sized cropped textures, and alternating
ping-pong texture sets.

The release uses the exact hardware-tested R2C binary. No behavior-changing
source edits were made after the successful hardware run.

## Hardware-measured result

Measured on New Nintendo 3DS hardware across **{diag['measured_frames']}** normal
frames during a **{float(diag['duration_seconds']):.1f}-second** session:

| Mode | v1.0.1 baseline | v1.0.2 R2C | Improvement |
|---|---:|---:|---:|
| Mono | {BASELINE['mono_fps']:.3f} FPS | **{float(diag['mono_fps']):.3f} FPS** | **+{mono_gain:.1f}%** |
| Stereo | {BASELINE['stereo_fps']:.3f} FPS | **{float(diag['stereo_fps']):.3f} FPS** | **+{stereo_gain:.1f}%** |
| Mono frame time | {BASELINE['mono_ms']:.3f} ms | **{float(diag['mono_ms']):.3f} ms** | **{mono_ms_drop:.1f}% shorter** |
| Stereo frame time | {BASELINE['stereo_ms']:.3f} ms | **{float(diag['stereo_ms']):.3f} ms** | **{stereo_ms_drop:.1f}% shorter** |

The mono result averages above the 30 FPS milestone. Performance remains
scene-dependent and stereo continues to render two complete software views.

## Renderer changes

- Replaced Citro2D screen-quad submission with direct Citro3D textured draws.
- Fused palette conversion and Morton-tiled texture writes into one pass.
- Removed the intermediate full-frame RGB565 staging/swizzle path during normal use.
- Generated only the top-screen and lower-screen regions actually displayed.
- Added two complete cropped texture sets for safe ping-pong submission.
- Kept the full R2A and R2B paths as automatic safety fallbacks.
- Preserved legacy and split-screen layouts, lower-screen controls, and true stereo.

## Hardware validation

- Legacy-left: **{profile['validation_states']['legacy_left']}**
- Split-left: **{profile['validation_states']['split_left']}**
- Split-right: **{profile['validation_states']['split_right']}**
- Legacy-right: **{legacy_right}** (not failed; this exact combination was not exercised)
- Pixel mismatches: **{profile['mismatches']}**
- Cropped fallbacks: **{profile['cropped_fallbacks']}**
- Direct-tiled safety fallbacks: **{profile['direct_fallbacks']}**
- Ping-pong pre-frame failures: **{profile['preframe_failures']}**
- Texture-set draws: **set 0 = {profile['set0_draws']}, set 1 = {profile['set1_draws']}**
- Upload failures: **0**
- Draw failures: **0**
- GPU profile clean shutdown: **YES**

## Diagnostic version label

The included hardware-tested binary still reports
`1.0.1-DIAG2-FPS-SPLIT` inside `citadel_diag.log`. That string identifies the
silent diagnostic schema inherited from v1.0.1; R2C's independent renderer and
profile markers identify the v1.0.2 hotfix implementation. The binary is left
unchanged to preserve exact hardware-test identity.

## Scope

This is the final software-world-renderer optimization milestone. The next
development branch replaces world rasterization itself with native Citro3D
geometry while keeping this R2C release as the stable fallback and comparison
baseline.

No copyrighted System Shock game data is included. A legally obtained original
copy of System Shock is required.
"""


def performance_report(profile: dict[str, object], diag: dict[str, object]) -> str:
    return f"""# {DISPLAY_MILESTONE} — Final Software Renderer Benchmark

Status: **HARDWARE PASS**  
Release role: **v{RELEASE_VERSION} final software renderer hotfix baseline**

## User-facing diagnostic average

- Session duration: **{float(diag['duration_seconds']):.3f} seconds**
- Measured frames: **{diag['measured_frames']}**
- Mono frames: **{diag['mono_frames']}**
- Mono average: **{float(diag['mono_fps']):.3f} FPS / {float(diag['mono_ms']):.3f} ms**
- Stereo frames: **{diag['stereo_frames']}**
- Stereo average: **{float(diag['stereo_fps']):.3f} FPS / {float(diag['stereo_ms']):.3f} ms**
- Combined average: **{float(diag['combined_fps']):.3f} FPS / {float(diag['combined_ms']):.3f} ms**

## R1 transport profiler

- Presented frames: **{profile['presented_frames']}**
- Mono profiler frames: **{profile['mono_profile_frames']}**
- Mono profiler cycle: **{float(profile['mono_profile_cycle_ms']):.3f} ms**
- Mono pre-present: **{float(profile['mono_pre_present_ms']):.3f} ms**
- Mono presentation: **{float(profile['mono_present_ms']):.3f} ms**
- Mono FrameBegin: **{float(profile['mono_frame_begin_ms']):.3f} ms**
- Mono cropped upload: **{float(profile['mono_upload_ms']):.3f} ms**
- Stereo profiler frames: **{profile['stereo_profile_frames']}**
- Stereo profiler cycle: **{float(profile['stereo_profile_cycle_ms']):.3f} ms**
- Stereo pre-present: **{float(profile['stereo_pre_present_ms']):.3f} ms**
- Stereo presentation: **{float(profile['stereo_present_ms']):.3f} ms**
- Stereo FrameBegin: **{float(profile['stereo_frame_begin_ms']):.3f} ms**
- Stereo cropped upload: **{float(profile['stereo_upload_ms']):.3f} ms**

The diagnostic average excludes gaps longer than one second and is the preferred
normal-gameplay FPS measurement. The transport profiler retains long-cycle
information useful for renderer analysis.

## Ping-pong proof

- Pre-frame uploads: **{profile['preframe_uploads']}**
- In-frame uploads: **{profile['inframe_uploads']}**
- Pre-frame failures: **{profile['preframe_failures']}**
- Texture switches: **{profile['switches']}**
- Set 0 draws: **{profile['set0_draws']}**
- Set 1 draws: **{profile['set1_draws']}**

## Safety proof

- Cropped mismatches: **{profile['mismatches']}**
- Cropped fallbacks: **{profile['cropped_fallbacks']}**
- Direct-tiled fallbacks: **{profile['direct_fallbacks']}**
- Upload failures: **0**
- Draw failures: **0**
- GPU profile clean shutdown: **YES**
"""


def native_handoff(profile: dict[str, object], diag: dict[str, object], binary_hash: str) -> str:
    return f"""# Citadel Citro3D Native Branch Handoff

Branch base: **{DISPLAY_MILESTONE}**  
Frozen software baseline: **v{RELEASE_VERSION} Final Software Renderer Hotfix**  
Hardware-tested binary SHA-256: `{binary_hash}`

## Proven baseline

- Mono: **{float(diag['mono_fps']):.3f} FPS**
- Stereo: **{float(diag['stereo_fps']):.3f} FPS**
- Pixel mismatches: **0**
- Transport fallbacks: **0**
- GPU upload/draw failures: **0**

Do not weaken or delete the R2C path while native coverage is incomplete. It is
the fallback, comparison renderer, menu/UI presenter, and rollback point.

## First native milestone

`CITADEL-C3D-R3A-WORLDPROOF1`

Goal: render one genuine live System Shock room through native Citro3D geometry
while simulation, visibility, camera state, unsupported objects, menus, HUD, and
fallback presentation remain owned by the established engine paths.

### Recommended sequence

1. Instrument the software world renderer immediately before span/pixel rasterization.
2. Identify live opaque world polygons and their camera-space vertices.
3. Capture walls first; add floor and ceiling once the coordinate transform is proven.
4. Submit flat diagnostic colors through a dedicated native vertex buffer.
5. Use a real depth buffer and perspective projection.
6. Suppress only geometry positively confirmed as natively replayed.
7. Preserve the R2C software image for unsupported geometry and emergency fallback.
8. Prove walking, turning, looking, doors, and room transitions on hardware.
9. Only after geometry is stable, add texture/material translation and native stereo.

## Success condition

A genuine current Citadel room—rather than a test triangle or reconstructed
mock-up—tracks the player's live camera and renders walls, floor, and ceiling on
PICA200 without corrupting the existing lower-screen interface.
"""


def append_section(path: Path, heading: str, section: str) -> str:
    if path.exists():
        text = read_text(path)
        if heading in text:
            return "already present"
        write_text(path, text.rstrip() + "\n\n" + section)
        return "added"
    write_text(path, section)
    return "created"


def git_clean(repo: Path) -> bool:
    result = run(["git", "-C", str(repo), "status", "--porcelain"], check=False)
    return result.returncode == 0 and not result.stdout.strip()


def create_repo_backup(timestamp: str) -> Path:
    backup = Path("/c/Projects") / f"Citadel_3D_GITHUB_PRE_v1.0.2_R2C_{timestamp}.tar.gz"
    if backup.exists():
        raise FinalizeError(f"GitHub backup already exists: {backup}")
    with tarfile.open(backup, "w:gz") as archive:
        for path in GITHUB_ROOT.rglob("*"):
            if ".git" in path.parts or not path.is_file():
                continue
            archive.add(path, arcname=(Path("Citadel_3D_GITHUB") / path.relative_to(GITHUB_ROOT)).as_posix())
    return backup


def create_checkpoint(
    timestamp: str,
    binary: Path,
    profile: EvidenceFile,
    diag: EvidenceFile,
    evidence_zip: Path | None,
    profile_metrics: dict[str, object],
    diag_metrics: dict[str, object],
) -> tuple[Path, Path]:
    CHECKPOINT_PARENT.mkdir(parents=True, exist_ok=True)
    final = CHECKPOINT_PARENT / f"{MILESTONE}_{timestamp}"
    archive_path = CHECKPOINT_PARENT / f"{MILESTONE}_{timestamp}.tar.gz"
    temp = CHECKPOINT_PARENT / f".{MILESTONE}_{timestamp}.INCOMPLETE"
    if final.exists() or archive_path.exists() or temp.exists():
        raise FinalizeError("Checkpoint destination already exists; refusing to overwrite.")

    temp.mkdir(parents=True)
    try:
        shutil.copytree(
            SOURCE_ROOT,
            temp / "source/shockolate",
            ignore=ignore_source_copy,
            dirs_exist_ok=False,
        )
        artifacts = temp / "artifacts"
        evidence_dir = temp / "evidence"
        metadata = temp / "metadata"
        artifacts.mkdir(parents=True)
        evidence_dir.mkdir(parents=True)
        metadata.mkdir(parents=True)

        shutil.copy2(binary, artifacts / BINARY_RELEASE_NAME)
        write_bytes(evidence_dir / PROFILE_FILENAME, profile.data)
        write_bytes(evidence_dir / DIAG_FILENAME, diag.data)
        if evidence_zip and evidence_zip.is_file():
            shutil.copy2(evidence_zip, evidence_dir / evidence_zip.name)
        if BUILD_LOG.is_file():
            shutil.copy2(BUILD_LOG, evidence_dir / BUILD_LOG.name)
        if PATCH_SCRIPT.is_file():
            shutil.copy2(PATCH_SCRIPT, metadata / PATCH_SCRIPT.name)

        binary_hash = sha256_file(artifacts / BINARY_RELEASE_NAME)
        manifest = {
            "milestone": MILESTONE,
            "display_milestone": DISPLAY_MILESTONE,
            "release_version": RELEASE_VERSION,
            "created_local": datetime.now().astimezone().isoformat(),
            "source_root": str(SOURCE_ROOT),
            "verified_binary_source": str(binary),
            "verified_binary_sha256": binary_hash,
            "profile_source": profile.description,
            "profile_sha256": profile.sha256,
            "diagnostic_source": diag.description,
            "diagnostic_sha256": diag.sha256,
            "profile_metrics": profile_metrics,
            "diagnostic_metrics": diag_metrics,
            "publication_role": "final software renderer hotfix baseline",
            "native_successor": "CITADEL-C3D-R3A-WORLDPROOF1",
        }
        write_text(metadata / "MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True))
        write_text(metadata / "RELEASE_NOTES_v1.0.2.md", release_notes(profile_metrics, diag_metrics))
        write_text(metadata / "PERFORMANCE_RESULTS.md", performance_report(profile_metrics, diag_metrics))
        write_text(metadata / "NATIVE_BRANCH_HANDOFF.md", native_handoff(profile_metrics, diag_metrics, binary_hash))
        write_text(
            metadata / "RESTORE_INSTRUCTIONS.md",
            f"""# Restore {DISPLAY_MILESTONE}

1. Rename the current development tree out of the way.
2. Copy `source/shockolate` back to:
   `C:/Projects/Citadel_Citro3D_DEV/Source/shockolate`
3. Use `artifacts/{BINARY_RELEASE_NAME}` as the exact hardware-tested fallback.
4. Verify the binary SHA-256 against `metadata/MANIFEST.json`.
5. Rebuild only when source changes are intentionally required.

This checkpoint excludes generated build directories and `.git` metadata but
contains the complete restorable source tree and exact tested binary.
""",
        )
        write_sha256sums(temp, temp / "SHA256SUMS.txt")
        temp.rename(final)
        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(final, arcname=final.name)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return final, archive_path


def update_github(
    timestamp: str,
    binary: Path,
    profile: EvidenceFile,
    diag: EvidenceFile,
    profile_metrics: dict[str, object],
    diag_metrics: dict[str, object],
) -> tuple[Path, list[str]]:
    candidate = GITHUB_ROOT / "Release_Candidates/v1.0.2_R2C_SOFTWARE_RENDERER_HOTFIX"
    if candidate.exists():
        raise FinalizeError(f"GitHub release candidate already exists: {candidate}")
    if not (GITHUB_ROOT / ".git").is_dir():
        raise FinalizeError(f"GitHub repository not found: {GITHUB_ROOT}")
    if not git_clean(GITHUB_ROOT):
        status = run(["git", "-C", str(GITHUB_ROOT), "status", "--short", "--branch"], check=False)
        raise FinalizeError(
            "Citadel_3D_GITHUB has uncommitted changes. Commit or preserve them before running this script.\n"
            + status.stdout.strip()
        )

    backup = create_repo_backup(timestamp)
    changed: list[str] = []
    for rel in PUBLIC_SYNC_FILES:
        src = SOURCE_ROOT / rel
        dst = GITHUB_ROOT / rel
        if not src.is_file():
            raise FinalizeError(f"Public sync source is missing: {src}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        changed.append(rel.as_posix())

    notes = release_notes(profile_metrics, diag_metrics)
    perf = performance_report(profile_metrics, diag_metrics)
    notes_path = GITHUB_ROOT / "RELEASE_NOTES_v1.0.2.md"
    perf_path = GITHUB_ROOT / "docs/performance/C3D_R2C_FINAL_SOFTWARE_RENDERER.md"
    profile_path = GITHUB_ROOT / f"docs/performance/evidence/{PROFILE_FILENAME}"
    diag_path = GITHUB_ROOT / "docs/performance/evidence/citadel_diag_R2C.log"
    write_text(notes_path, notes)
    write_text(perf_path, perf)
    write_bytes(profile_path, profile.data)
    write_bytes(diag_path, diag.data)
    changed.extend([
        notes_path.relative_to(GITHUB_ROOT).as_posix(),
        perf_path.relative_to(GITHUB_ROOT).as_posix(),
        profile_path.relative_to(GITHUB_ROOT).as_posix(),
        diag_path.relative_to(GITHUB_ROOT).as_posix(),
    ])

    readme_section = f"""## v{RELEASE_VERSION} — Final Software Renderer Hotfix

The R2C Citro3D transport path is the final optimized software-renderer
baseline. Hardware measurements on New Nintendo 3DS averaged
**{float(diag_metrics['mono_fps']):.3f} FPS in mono** and
**{float(diag_metrics['stereo_fps']):.3f} FPS in true stereo**, with zero
transport mismatches, zero fallbacks, and zero GPU upload/draw failures.

The game world remains software rendered in this stable hotfix. Native Citro3D
world geometry is being developed separately and is not part of v{RELEASE_VERSION}.
"""
    result = append_section(GITHUB_ROOT / "README.md", f"## v{RELEASE_VERSION} — Final Software Renderer Hotfix", readme_section)
    if result != "already present":
        changed.append("README.md")

    known_section = """## Native Citro3D renderer status

The stable release still uses System Shock's software world renderer. Citro3D
handles the optimized final presentation path. A separate experimental native
world-renderer branch is under development; it is not included in this release.
"""
    result = append_section(GITHUB_ROOT / "KNOWN_ISSUES.md", "## Native Citro3D renderer status", known_section)
    if result != "already present":
        changed.append("KNOWN_ISSUES.md")

    candidate.mkdir(parents=True)
    shutil.copy2(binary, candidate / BINARY_RELEASE_NAME)
    write_text(candidate / "RELEASE_NOTES.md", notes)
    write_text(candidate / "PERFORMANCE_RESULTS.md", perf)
    write_bytes(candidate / PROFILE_FILENAME, profile.data)
    write_bytes(candidate / "citadel_diag_R2C.log", diag.data)
    write_text(
        candidate / "READY_TO_PUBLISH.txt",
        """This folder contains the exact hardware-tested R2C release candidate.

Review the repository diff, commit it, push it, and create the GitHub release
only after confirming the staged binary SHA-256. No game data is included.
""",
    )
    write_sha256sums(candidate, candidate / "SHA256SUMS.txt")
    changed.extend(path.relative_to(GITHUB_ROOT).as_posix() for path in iter_files(candidate))
    return backup, sorted(set(changed))


def stage_release(
    binary: Path,
    profile: EvidenceFile,
    diag: EvidenceFile,
    profile_metrics: dict[str, object],
    diag_metrics: dict[str, object],
) -> Path:
    if RELEASE_STAGE.exists():
        raise FinalizeError(f"Release staging folder already exists: {RELEASE_STAGE}")
    RELEASE_STAGE.mkdir(parents=True)
    shutil.copy2(binary, RELEASE_STAGE / BINARY_RELEASE_NAME)
    write_text(RELEASE_STAGE / "RELEASE_NOTES_v1.0.2.md", release_notes(profile_metrics, diag_metrics))
    write_text(RELEASE_STAGE / "PERFORMANCE_RESULTS.md", performance_report(profile_metrics, diag_metrics))
    write_bytes(RELEASE_STAGE / PROFILE_FILENAME, profile.data)
    write_bytes(RELEASE_STAGE / "citadel_diag_R2C.log", diag.data)
    write_sha256sums(RELEASE_STAGE, RELEASE_STAGE / "SHA256SUMS.txt")
    return RELEASE_STAGE


def create_native_tree(
    binary: Path,
    profile_metrics: dict[str, object],
    diag_metrics: dict[str, object],
) -> Path:
    if NATIVE_PROJECT_ROOT.exists():
        raise FinalizeError(f"Native project destination already exists: {NATIVE_PROJECT_ROOT}")
    temp_root = Path(str(NATIVE_PROJECT_ROOT) + ".INCOMPLETE")
    if temp_root.exists():
        raise FinalizeError(f"Incomplete native destination already exists: {temp_root}")
    temp_source = temp_root / "Source/shockolate"
    temp_source.parent.mkdir(parents=True)
    try:
        shutil.copytree(SOURCE_ROOT, temp_source, ignore=ignore_source_copy)
        baseline = temp_root / "Baselines/R2C_FINAL_SOFTWARE_RENDERER"
        baseline.mkdir(parents=True)
        shutil.copy2(binary, baseline / BINARY_RELEASE_NAME)
        binary_hash = sha256_file(baseline / BINARY_RELEASE_NAME)
        write_text(temp_root / "README_NATIVE_BRANCH.md", native_handoff(profile_metrics, diag_metrics, binary_hash))
        write_text(
            temp_source / "NATIVE_BRANCH_ORIGIN.md",
            native_handoff(profile_metrics, diag_metrics, binary_hash),
        )
        write_text(
            temp_source / "CITADEL_C3D_R3A_WORLDPROOF1.marker",
            f"""PROJECT CITADEL C3D NATIVE DEVELOPMENT BRANCH
Base milestone: {DISPLAY_MILESTONE}
Release baseline: v{RELEASE_VERSION}
First target: CITADEL-C3D-R3A-WORLDPROOF1
Created: {datetime.now().astimezone().isoformat()}
""",
        )
        write_text(
            baseline / "BASELINE_SHA256.txt",
            f"{binary_hash}  {BINARY_RELEASE_NAME}\n",
        )
        temp_root.rename(NATIVE_PROJECT_ROOT)
    except Exception:
        shutil.rmtree(temp_root, ignore_errors=True)
        raise
    return NATIVE_SOURCE_ROOT


def maybe_commit_local(changed: list[str]) -> dict[str, str]:
    result = {"commit": "not requested", "tag": "not requested", "branch": "not requested"}
    name = run(["git", "-C", str(GITHUB_ROOT), "config", "user.name"], check=False).stdout.strip()
    email = run(["git", "-C", str(GITHUB_ROOT), "config", "user.email"], check=False).stdout.strip()
    if not name or not email:
        raise FinalizeError(
            "--commit-local was requested, but git user.name or user.email is not configured."
        )
    run(["git", "-C", str(GITHUB_ROOT), "add", "--", *changed])
    commit = run(
        ["git", "-C", str(GITHUB_ROOT), "commit", "-m", "Release v1.0.2: R2C final software renderer hotfix"]
    )
    commit_hash = run(["git", "-C", str(GITHUB_ROOT), "rev-parse", "HEAD"]).stdout.strip()
    result["commit"] = commit_hash

    existing_tag = run(["git", "-C", str(GITHUB_ROOT), "rev-parse", "-q", "--verify", f"refs/tags/{RELEASE_TAG}"], check=False)
    if existing_tag.returncode == 0:
        if existing_tag.stdout.strip() != commit_hash:
            raise FinalizeError(f"Tag {RELEASE_TAG} already exists at a different commit.")
        result["tag"] = f"already at {commit_hash}"
    else:
        run(["git", "-C", str(GITHUB_ROOT), "tag", "-a", RELEASE_TAG, "-m", RELEASE_TITLE])
        result["tag"] = RELEASE_TAG

    branch = "native-citro3d-world"
    existing_branch = run(["git", "-C", str(GITHUB_ROOT), "rev-parse", "-q", "--verify", f"refs/heads/{branch}"], check=False)
    if existing_branch.returncode == 0:
        if existing_branch.stdout.strip() != commit_hash:
            raise FinalizeError(f"Branch {branch} already exists at a different commit.")
        result["branch"] = f"already at {commit_hash}"
    else:
        run(["git", "-C", str(GITHUB_ROOT), "branch", branch, commit_hash])
        result["branch"] = branch
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Finalize R2C hotfix and fork native Citro3D development.")
    parser.add_argument("--evidence-zip", type=Path, help="FTP evidence ZIP such as Temp(4).zip")
    parser.add_argument("--profile-log", type=Path, help="Extracted C3D_R2C profile log")
    parser.add_argument("--diag-log", type=Path, help="Matching extracted citadel_diag.log")
    parser.add_argument(
        "--commit-local",
        action="store_true",
        help="Create a local git commit, annotated v1.0.2 tag, and native-citro3d-world branch. Never pushes.",
    )
    args = parser.parse_args()

    print("============================================================")
    print("PROJECT CITADEL R2C FINAL HOTFIX + NATIVE BRANCH HANDOFF")
    print("============================================================")

    try:
        verify_source_tree()
        profile_evidence, diag_evidence, evidence_zip = locate_evidence(
            args.profile_log, args.diag_log, args.evidence_zip
        )
        profile_metrics = parse_profile(profile_evidence)
        diag_metrics = parse_diag(diag_evidence)
        if profile_metrics["build"] != diag_metrics["build"]:
            raise FinalizeError(
                f"Profile and diagnostic build stamps differ: {profile_metrics['build']} vs {diag_metrics['build']}"
            )
        binary = locate_verified_binary()
        binary_hash = sha256_file(binary)

        if RELEASE_STAGE.exists():
            raise FinalizeError(f"Release staging destination already exists: {RELEASE_STAGE}")
        if NATIVE_PROJECT_ROOT.exists():
            raise FinalizeError(f"Native development destination already exists: {NATIVE_PROJECT_ROOT}")
        if not (GITHUB_ROOT / ".git").is_dir():
            raise FinalizeError(f"GitHub repository not found: {GITHUB_ROOT}")
        if not git_clean(GITHUB_ROOT):
            status = run(["git", "-C", str(GITHUB_ROOT), "status", "--short", "--branch"], check=False)
            raise FinalizeError("GitHub repository is not clean:\n" + status.stdout.strip())

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        checkpoint, checkpoint_archive = create_checkpoint(
            timestamp,
            binary,
            profile_evidence,
            diag_evidence,
            evidence_zip,
            profile_metrics,
            diag_metrics,
        )
        release_stage = stage_release(
            binary, profile_evidence, diag_evidence, profile_metrics, diag_metrics
        )
        native_source = create_native_tree(binary, profile_metrics, diag_metrics)
        github_backup, changed = update_github(
            timestamp,
            binary,
            profile_evidence,
            diag_evidence,
            profile_metrics,
            diag_metrics,
        )

        git_result = {"commit": "not requested", "tag": "not requested", "branch": "not requested"}
        if args.commit_local:
            git_result = maybe_commit_local(changed)

    except FinalizeError as exc:
        fail(str(exc))
    except (OSError, shutil.Error, zipfile.BadZipFile, tarfile.TarError) as exc:
        fail(f"Filesystem/archive operation failed: {exc}")

    print()
    print("SUCCESS: R2C is frozen as the final software-renderer hotfix baseline.")
    print()
    print(f"Verified binary: {binary}")
    print(f"Binary SHA-256: {binary_hash}")
    print(f"Hardware profile: {profile_evidence.description}")
    print(f"Diagnostic log: {diag_evidence.description}")
    print()
    print(f"Checkpoint: {checkpoint}")
    print(f"Checkpoint archive: {checkpoint_archive}")
    print(f"Release staging: {release_stage}")
    print(f"GitHub rollback backup: {github_backup}")
    print(f"GitHub files prepared: {len(changed)}")
    print(f"Native source tree: {native_source}")
    print()
    print("Measured release result:")
    print(f"  Mono:   {float(diag_metrics['mono_fps']):.3f} FPS / {float(diag_metrics['mono_ms']):.3f} ms")
    print(f"  Stereo: {float(diag_metrics['stereo_fps']):.3f} FPS / {float(diag_metrics['stereo_ms']):.3f} ms")
    print("  Mismatches: 0 | fallbacks: 0 | GPU failures: 0")
    print()
    if args.commit_local:
        print(f"Local commit: {git_result['commit']}")
        print(f"Local tag: {git_result['tag']}")
        print(f"Local native branch: {git_result['branch']}")
    else:
        print("No git commit, tag, push, or GitHub release was performed.")
        print("Review the Citadel_3D_GITHUB changes in GitHub Desktop, then commit/push/release.")
        print("The separate native source tree is already ready for R3A-WORLDPROOF1.")
    print("============================================================")


if __name__ == "__main__":
    main()
