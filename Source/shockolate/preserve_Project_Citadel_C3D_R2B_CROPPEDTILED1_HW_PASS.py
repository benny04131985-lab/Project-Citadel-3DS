#!/usr/bin/env python3
"""
preserve_Project_Citadel_C3D_R2B_CROPPEDTILED1_HW_PASS.py

Run from:
    C:/Projects/Citadel_Citro3D_DEV/Source/shockolate

Purpose:
    Preserve the hardware-proven CITADEL-C3D-R2B-CROPPEDTILED1 milestone as a
    complete source checkpoint with the exact verified binary, hardware log,
    hashes, restoration instructions, benchmark comparison, and a local
    unpublished GitHub progress-entry folder.

This script DOES NOT:
  - modify Citadel source files;
  - build the project;
  - run git add/commit/push/tag;
  - publish or modify an existing GitHub release.

The hardware run proved legacy-left, split-left, and split-right with zero
mismatches and zero fallbacks. The script accepts legacy-right as PASS or
PENDING and records the exact observed state without claiming untested coverage.

Examples:
    python preserve_Project_Citadel_C3D_R2B_CROPPEDTILED1_HW_PASS.py \
        --profile-log /c/Users/benny/Downloads/C3D_R2B_CROPPEDTILEDPROFILE.log

    python preserve_Project_Citadel_C3D_R2B_CROPPEDTILED1_HW_PASS.py \
        --evidence-zip '/c/Users/benny/Downloads/Temp(3).zip'
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, NoReturn


MILESTONE = "CITADEL_C3D_R2B_CROPPEDTILED1_HW_PASS"
DISPLAY_MILESTONE = "CITADEL-C3D-R2B-CROPPEDTILED1"
EXPECTED_SOURCE_FRAGMENT = "Citadel_Citro3D_DEV/Source/shockolate"

SOURCE_ROOT = Path.cwd().resolve()
GITHUB_ROOT = Path("/c/Projects/Citadel_3D_GITHUB")
CHECKPOINT_PARENT = Path("/c/Projects/Citadel_C3D_CHECKPOINTS")
BUILD_ROOT = SOURCE_ROOT / "build-c3d-r2b-croppedtiled1"
STAGED_BINARY = Path("/c/Projects/CITADEL_C3D_R2B_CROPPEDTILED1.3dsx")
SHOCK_SOURCE = SOURCE_ROOT / "src/MacSrc/Shock.c"
CMAKE_FILE = SOURCE_ROOT / "CMakeLists.txt"

PROFILE_FILENAME = "C3D_R2B_CROPPEDTILEDPROFILE.log"
BINARY_OUTPUT_NAME = "3D_Citadel_3DS_R2B_CROPPEDTILED1.3dsx"
BUILD_LOG_NAME = "C3D_R2B_CROPPEDTILED1_BUILD.log"
PATCH_SCRIPT_NAME = "apply_Project_Citadel_C3D_R2B_CROPPEDTILED1.py"

SOURCE_MARKERS = (
    "PROJECT CITADEL C3D R2A DIRECTTILED1",
    "PROJECT CITADEL C3D R2B CROPPEDTILED1",
    "GPU C3D R2B CROPPEDTILED VALIDATION PASS",
    "C3D_R2B_CROPPEDTILEDPROFILE.log",
    "CROPPED_TILED_OUTPUT_SIZED",
)

BINARY_MARKERS = (
    b"PROJECT CITADEL C3D R2B CROPPEDTILED1 ACTIVE",
    b"GPU C3D R2B CROPPEDTILED VALIDATION PASS",
    b"C3D_R2B_CROPPEDTILEDPROFILE.log",
    b"R2A_FULL_TEXTURE_RESTORED",
    b"CROPPED_TILED_OUTPUT_SIZED",
    b"MONO_SINGLE_EYE",
    b"STEREO_DUAL_EYE",
)

PROFILE_MARKERS = (
    "PROJECT CITADEL C3D R2B CROPPEDTILED1 ACTIVE",
    "Transport active: CITADEL-C3D-R2B-CROPPEDTILED1",
    "Cropped-tiled enabled at shutdown: YES",
    "Cropped validations:",
    "Cropped frame passes:",
    "Direct-tiled enabled at shutdown: YES",
    "Direct-tiled validation: PASS mismatches=0",
    "Upload failures: 0",
    "Draw failures: 0",
    "Clean Shutdown: YES",
)

# Hardware profiles recorded immediately before R2B.
R1_BASELINE = {
    "mono_cycle_ms": 45.631,
    "mono_upload_ms": 22.418,
    "stereo_cycle_ms": 94.288,
    "stereo_upload_ms": 45.008,
}

R2A_BASELINE = {
    "mono_cycle_ms": 41.106,
    "mono_upload_ms": 14.252,
    "stereo_cycle_ms": 71.890,
    "stereo_upload_ms": 28.212,
}

# Full source checkpoint excludes generated/rebuildable output and VCS metadata.
EXCLUDED_DIR_NAMES = {
    ".git",
    ".vs",
    ".vscode",
    "__pycache__",
    "CITADEL_C3D_R0_AUDIT",
}
EXCLUDED_FILE_SUFFIXES = {".o", ".obj", ".a", ".elf", ".3dsx", ".cia", ".smdh"}


class PreserveError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProfileEvidence:
    description: str
    data: bytes
    timestamp_ns: int

    @property
    def text(self) -> str:
        return self.data.decode("utf-8", errors="replace")

    @property
    def digest(self) -> str:
        return hashlib.sha256(self.data).hexdigest()


def fail(message: str) -> NoReturn:
    raise SystemExit(f"ERROR: {message}\nNo checkpoint or GitHub draft was finalized.")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_match(text: str, pattern: str, label: str) -> re.Match[str]:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise PreserveError(f"Could not parse {label} from profile log.")
    return match


def safe_float(text: str, pattern: str, label: str) -> float:
    return float(safe_match(text, pattern, label).group(1))


def safe_int(text: str, pattern: str, label: str) -> int:
    return int(safe_match(text, pattern, label).group(1))


def pct_reduction(before: float, after: float) -> float:
    if before <= 0.0:
        return 0.0
    return ((before - after) / before) * 100.0


def pct_gain(before: float, after: float) -> float:
    if before <= 0.0:
        return 0.0
    return ((after - before) / before) * 100.0


def fps_from_ms(ms: float) -> float:
    return 1000.0 / ms if ms > 0.0 else 0.0


def run_git_status(repo: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "status", "--short", "--branch"],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return "git status unavailable"

    output = (result.stdout + result.stderr).strip()
    return output or "working tree clean"


def evidence_from_log(path: Path) -> ProfileEvidence | None:
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()
        timestamp_ns = path.stat().st_mtime_ns
    except OSError:
        return None
    return ProfileEvidence(str(path), data, timestamp_ns)


def evidence_from_zip(path: Path) -> list[ProfileEvidence]:
    if not path.is_file() or not zipfile.is_zipfile(path):
        return []

    results: list[ProfileEvidence] = []
    try:
        timestamp_ns = path.stat().st_mtime_ns
        with zipfile.ZipFile(path, "r") as archive:
            for member in archive.infolist():
                basename = Path(member.filename).name.lower()
                if not basename.endswith(".log"):
                    continue
                if "c3d_r2b_croppedtiledprofile" not in basename:
                    continue
                try:
                    data = archive.read(member)
                except (KeyError, OSError, RuntimeError, zipfile.BadZipFile):
                    continue
                results.append(
                    ProfileEvidence(
                        f"{path} :: {member.filename}",
                        data,
                        timestamp_ns,
                    )
                )
    except (OSError, RuntimeError, zipfile.BadZipFile):
        return []

    return results


def profile_has_core_proof(text: str) -> bool:
    return all(marker in text for marker in PROFILE_MARKERS)


def locate_profile_evidence(
    explicit_log: Path | None,
    explicit_zip: Path | None,
) -> ProfileEvidence:
    candidates: list[ProfileEvidence] = []

    if explicit_log is not None:
        explicit_log = explicit_log.expanduser()
        if explicit_log.suffix.lower() == ".zip":
            candidates.extend(evidence_from_zip(explicit_log))
        else:
            item = evidence_from_log(explicit_log)
            if item is not None:
                candidates.append(item)

    if explicit_zip is not None:
        candidates.extend(evidence_from_zip(explicit_zip.expanduser()))

    regular_paths = [
        SOURCE_ROOT / PROFILE_FILENAME,
        Path("/c/Users/benny/Downloads") / PROFILE_FILENAME,
        Path("/c/Users/benny/Desktop") / PROFILE_FILENAME,
    ]

    downloads = Path("/c/Users/benny/Downloads")
    desktop = Path("/c/Users/benny/Desktop")
    for directory in (SOURCE_ROOT, downloads, desktop):
        if not directory.is_dir():
            continue
        regular_paths.extend(sorted(directory.glob("C3D_R2B_CROPPEDTILEDPROFILE*.log")))

    seen_logs: set[str] = set()
    for path in regular_paths:
        key = str(path).lower()
        if key in seen_logs:
            continue
        seen_logs.add(key)
        item = evidence_from_log(path)
        if item is not None:
            candidates.append(item)

    # The FTP workflow often produces a small evidence ZIP such as Temp(3).zip.
    zip_paths: list[Path] = []
    for directory in (SOURCE_ROOT, downloads, desktop):
        if not directory.is_dir():
            continue
        zip_paths.extend(directory.glob("Temp*.zip"))
        zip_paths.extend(directory.glob("*C3D*.zip"))
        zip_paths.extend(directory.glob("*Citadel*.zip"))

    seen_zips: set[str] = set()
    for path in sorted(zip_paths):
        key = str(path).lower()
        if key in seen_zips:
            continue
        seen_zips.add(key)
        candidates.extend(evidence_from_zip(path))

    valid = [item for item in candidates if profile_has_core_proof(item.text)]
    if not valid:
        discovered = "\n  - ".join(item.description for item in candidates)
        detail = f"\nCandidates inspected:\n  - {discovered}" if discovered else ""
        raise PreserveError(
            "Could not locate a hardware-proven R2B profile. Copy the log into "
            "this source folder, pass --profile-log PATH, or pass --evidence-zip PATH."
            + detail
        )

    # Prefer the newest filesystem copy/ZIP. Validation is repeated in parse_profile.
    return max(valid, key=lambda item: item.timestamp_ns)


def locate_verified_binary() -> Path:
    candidates: list[Path] = []
    if BUILD_ROOT.is_dir():
        candidates.extend(sorted(BUILD_ROOT.rglob("*.3dsx")))
    if STAGED_BINARY.is_file():
        candidates.append(STAGED_BINARY)

    if not candidates:
        raise PreserveError(
            f"No R2B .3dsx found beneath {BUILD_ROOT} and staged binary is missing: "
            f"{STAGED_BINARY}"
        )

    matches: list[Path] = []
    for binary in candidates:
        try:
            data = binary.read_bytes()
        except OSError:
            continue
        if all(marker in data for marker in BINARY_MARKERS):
            matches.append(binary)

    if not matches:
        raise PreserveError(
            "No R2B build output contains all CROPPEDTILED1 proof markers."
        )

    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def parse_profile(evidence: ProfileEvidence) -> dict[str, object]:
    text = evidence.text

    for marker in PROFILE_MARKERS:
        if marker not in text:
            raise PreserveError(f"Profile proof marker missing: {marker}")

    validations = safe_match(
        text,
        r"^Cropped validations:\s+legacy_left=(\w+)\s+split_left=(\w+)\s+"
        r"legacy_right=(\w+)\s+split_right=(\w+)\s+mismatches=(\d+)",
        "cropped validation states",
    )
    validation_states = {
        "legacy_left": validations.group(1),
        "split_left": validations.group(2),
        "legacy_right": validations.group(3),
        "split_right": validations.group(4),
    }
    mismatches = int(validations.group(5))

    required_passes = ("legacy_left", "split_left", "split_right")
    failed_required = [
        name for name in required_passes if validation_states[name] != "PASS"
    ]
    if failed_required:
        raise PreserveError(
            "Required cropped validation did not pass: " + ", ".join(failed_required)
        )
    if validation_states["legacy_right"] not in {"PASS", "PENDING"}:
        raise PreserveError(
            "legacy_right must be PASS or PENDING; observed "
            + validation_states["legacy_right"]
        )
    if mismatches != 0:
        raise PreserveError(f"R2B recorded {mismatches} cropped validation mismatches.")

    frame_passes = safe_match(
        text,
        r"^Cropped frame passes:\s+top_left=(\d+)\s+top_right=(\d+)\s+"
        r"bottom=(\d+)\s+fallback=(\d+)\s+pixels=(\d+)",
        "cropped frame passes",
    )

    cropped_fallbacks = int(frame_passes.group(4))
    if cropped_fallbacks != 0:
        raise PreserveError(f"R2B recorded {cropped_fallbacks} cropped fallbacks.")

    direct_fallbacks = safe_int(
        text,
        r"^Direct-tiled eye passes:.*fallback=(\d+)",
        "R2A safety fallback count",
    )
    if direct_fallbacks != 0:
        raise PreserveError(f"R2A safety transport recorded {direct_fallbacks} fallbacks.")

    mono_left_fallback = safe_float(
        text,
        r"^PROFILE mode=MONO_SINGLE_EYE avg_palette_ms=[0-9.]+ "
        r"avg_left_croppedtiled_ms=[0-9.]+ avg_left_fallback_swizzle_ms=([0-9.]+)",
        "mono fallback-swizzle time",
    )
    stereo_left_fallback = safe_float(
        text,
        r"^PROFILE mode=STEREO_DUAL_EYE avg_palette_ms=[0-9.]+ "
        r"avg_left_croppedtiled_ms=[0-9.]+ avg_left_fallback_swizzle_ms=([0-9.]+)",
        "stereo left fallback-swizzle time",
    )
    stereo_right_fallback = safe_float(
        text,
        r"^PROFILE mode=STEREO_DUAL_EYE.*avg_right_fallback_swizzle_ms=([0-9.]+)",
        "stereo right fallback-swizzle time",
    )
    if any(value != 0.0 for value in (
        mono_left_fallback,
        stereo_left_fallback,
        stereo_right_fallback,
    )):
        raise PreserveError("One or more measured fallback-swizzle averages are nonzero.")

    build_match = safe_match(text, r"^Build:\s*(.+)$", "build timestamp")

    metrics: dict[str, object] = {
        "build": build_match.group(1),
        "validation_states": validation_states,
        "validation_mismatches": mismatches,
        "top_left_passes": int(frame_passes.group(1)),
        "top_right_passes": int(frame_passes.group(2)),
        "bottom_passes": int(frame_passes.group(3)),
        "cropped_fallbacks": cropped_fallbacks,
        "pixels_processed": int(frame_passes.group(5)),
        "direct_fallbacks": direct_fallbacks,
        "presented_frames": safe_int(
            text,
            r"^Presented frames observed by GPU logger:\s*(\d+)",
            "presented frames",
        ),
        "mono_frames": safe_int(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE frames=(\d+)",
            "mono frames",
        ),
        "mono_cycle_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE frames=\d+ avg_cycle_ms=([0-9.]+)",
            "mono cycle",
        ),
        "mono_pre_present_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE frames=\d+.*avg_pre_present_ms=([0-9.]+)",
            "mono pre-present",
        ),
        "mono_present_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE frames=\d+.*avg_present_ms=([0-9.]+)",
            "mono present",
        ),
        "mono_frame_begin_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE avg_frame_begin_ms=([0-9.]+)",
            "mono frame begin",
        ),
        "mono_upload_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE avg_frame_begin_ms=[0-9.]+ "
            r"avg_upload_total_ms=([0-9.]+)",
            "mono upload",
        ),
        "mono_draw_submit_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE.*avg_draw_submit_ms=([0-9.]+)",
            "mono draw submit",
        ),
        "mono_left_cropped_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE avg_palette_ms=[0-9.]+ "
            r"avg_left_croppedtiled_ms=([0-9.]+)",
            "mono left cropped-tiled pass",
        ),
        "stereo_frames": safe_int(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE frames=(\d+)",
            "stereo frames",
        ),
        "stereo_cycle_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE frames=\d+ avg_cycle_ms=([0-9.]+)",
            "stereo cycle",
        ),
        "stereo_pre_present_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE frames=\d+.*avg_pre_present_ms=([0-9.]+)",
            "stereo pre-present",
        ),
        "stereo_present_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE frames=\d+.*avg_present_ms=([0-9.]+)",
            "stereo present",
        ),
        "stereo_frame_begin_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE avg_frame_begin_ms=([0-9.]+)",
            "stereo frame begin",
        ),
        "stereo_upload_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE avg_frame_begin_ms=[0-9.]+ "
            r"avg_upload_total_ms=([0-9.]+)",
            "stereo upload",
        ),
        "stereo_draw_submit_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE.*avg_draw_submit_ms=([0-9.]+)",
            "stereo draw submit",
        ),
        "stereo_left_cropped_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE avg_palette_ms=[0-9.]+ "
            r"avg_left_croppedtiled_ms=([0-9.]+)",
            "stereo left cropped-tiled pass",
        ),
        "stereo_right_cropped_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE.*avg_right_croppedtiled_ms=([0-9.]+)",
            "stereo right cropped-tiled pass",
        ),
        "fallback_swizzle_averages_ms": {
            "mono_left": mono_left_fallback,
            "stereo_left": stereo_left_fallback,
            "stereo_right": stereo_right_fallback,
        },
    }

    mono_fps = fps_from_ms(float(metrics["mono_cycle_ms"]))
    stereo_fps = fps_from_ms(float(metrics["stereo_cycle_ms"]))
    r1_mono_fps = fps_from_ms(R1_BASELINE["mono_cycle_ms"])
    r1_stereo_fps = fps_from_ms(R1_BASELINE["stereo_cycle_ms"])
    r2a_mono_fps = fps_from_ms(R2A_BASELINE["mono_cycle_ms"])
    r2a_stereo_fps = fps_from_ms(R2A_BASELINE["stereo_cycle_ms"])

    metrics.update(
        {
            "mono_fps": mono_fps,
            "stereo_fps": stereo_fps,
            "r1_mono_fps": r1_mono_fps,
            "r1_stereo_fps": r1_stereo_fps,
            "r2a_mono_fps": r2a_mono_fps,
            "r2a_stereo_fps": r2a_stereo_fps,
            "r2a_to_r2b_mono_upload_reduction_pct": pct_reduction(
                R2A_BASELINE["mono_upload_ms"], float(metrics["mono_upload_ms"])
            ),
            "r2a_to_r2b_stereo_upload_reduction_pct": pct_reduction(
                R2A_BASELINE["stereo_upload_ms"], float(metrics["stereo_upload_ms"])
            ),
            "r2a_to_r2b_mono_cycle_reduction_pct": pct_reduction(
                R2A_BASELINE["mono_cycle_ms"], float(metrics["mono_cycle_ms"])
            ),
            "r2a_to_r2b_stereo_cycle_reduction_pct": pct_reduction(
                R2A_BASELINE["stereo_cycle_ms"], float(metrics["stereo_cycle_ms"])
            ),
            "r1_to_r2b_mono_fps_gain_pct": pct_gain(r1_mono_fps, mono_fps),
            "r1_to_r2b_stereo_fps_gain_pct": pct_gain(r1_stereo_fps, stereo_fps),
            "r2a_to_r2b_mono_fps_gain_pct": pct_gain(r2a_mono_fps, mono_fps),
            "r2a_to_r2b_stereo_fps_gain_pct": pct_gain(r2a_stereo_fps, stereo_fps),
        }
    )

    return metrics


def ignore_source_copy(directory: str, names: list[str]) -> set[str]:
    ignored: set[str] = set()
    current = Path(directory)

    for name in names:
        path = current / name

        if name in EXCLUDED_DIR_NAMES:
            ignored.add(name)
            continue

        if path.is_dir() and (
            name.startswith("build-")
            or name.startswith("CITADEL_C3D_CHECKPOINT")
        ):
            ignored.add(name)
            continue

        if path.is_file() and path.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
            ignored.add(name)
            continue

    return ignored


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def iter_files(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path


def write_sha256sums(root: Path, output: Path) -> None:
    lines: list[str] = []
    for path in iter_files(root):
        if path.resolve() == output.resolve():
            continue
        relative = path.relative_to(root).as_posix()
        lines.append(f"{sha256(path)}  {relative}")
    write_text(output, "\n".join(lines) + "\n")


def validation_markdown(metrics: dict[str, object]) -> str:
    states = metrics["validation_states"]
    assert isinstance(states, dict)
    legacy_right_note = (
        "**PASS**"
        if states["legacy_right"] == "PASS"
        else "**PENDING — this exact stereo/legacy combination was not exercised**"
    )
    return f"""## Validation coverage

- Legacy left: **{states['legacy_left']}**
- Split left: **{states['split_left']}**
- Legacy right: {legacy_right_note}
- Split right: **{states['split_right']}**
- Pixel mismatches: **{metrics['validation_mismatches']}**
- Cropped-path fallbacks: **{metrics['cropped_fallbacks']}**
- R2A safety-path fallbacks: **{metrics['direct_fallbacks']}**
- Upload failures: **0**
- Draw failures: **0**
- Clean shutdown: **YES**
"""


def metrics_markdown(metrics: dict[str, object]) -> str:
    return f"""# {DISPLAY_MILESTONE} — Hardware Results

Status: **HARDWARE PASS**  
Publication status: **LOCAL DRAFT — DO NOT PUBLISH YET**

{validation_markdown(metrics)}

The milestone is valid for every path exercised during the run. `legacy_right`
remains recorded as **{metrics['validation_states']['legacy_right']}** rather
than being silently promoted to PASS.

## Preserved hardware workload

- Presented frames: **{metrics['presented_frames']}**
- Mono frames: **{metrics['mono_frames']}**
- Stereo frames: **{metrics['stereo_frames']}**
- Top-left cropped passes: **{metrics['top_left_passes']}**
- Top-right cropped passes: **{metrics['top_right_passes']}**
- Bottom-atlas passes: **{metrics['bottom_passes']}**
- Cropped pixels processed: **{metrics['pixels_processed']:,}**

## Performance progression

| Measurement | R1 full transport | R2A direct-tiled | R2B cropped-tiled |
|---|---:|---:|---:|
| Mono texture transport | {R1_BASELINE['mono_upload_ms']:.3f} ms | {R2A_BASELINE['mono_upload_ms']:.3f} ms | **{float(metrics['mono_upload_ms']):.3f} ms** |
| Stereo texture transport | {R1_BASELINE['stereo_upload_ms']:.3f} ms | {R2A_BASELINE['stereo_upload_ms']:.3f} ms | **{float(metrics['stereo_upload_ms']):.3f} ms** |
| Mono complete frame | {R1_BASELINE['mono_cycle_ms']:.3f} ms | {R2A_BASELINE['mono_cycle_ms']:.3f} ms | **{float(metrics['mono_cycle_ms']):.3f} ms** |
| Stereo complete frame | {R1_BASELINE['stereo_cycle_ms']:.3f} ms | {R2A_BASELINE['stereo_cycle_ms']:.3f} ms | **{float(metrics['stereo_cycle_ms']):.3f} ms** |
| Approximate mono rate | {float(metrics['r1_mono_fps']):.1f} FPS | {float(metrics['r2a_mono_fps']):.1f} FPS | **{float(metrics['mono_fps']):.1f} FPS** |
| Approximate stereo rate | {float(metrics['r1_stereo_fps']):.1f} FPS | {float(metrics['r2a_stereo_fps']):.1f} FPS | **{float(metrics['stereo_fps']):.1f} FPS** |

## R2A to R2B change

- Mono transport: **{float(metrics['r2a_to_r2b_mono_upload_reduction_pct']):.1f}% lower**
- Stereo transport: **{float(metrics['r2a_to_r2b_stereo_upload_reduction_pct']):.1f}% lower**
- Mono complete-frame time: **{float(metrics['r2a_to_r2b_mono_cycle_reduction_pct']):.1f}% shorter**
- Stereo complete-frame time: **{float(metrics['r2a_to_r2b_stereo_cycle_reduction_pct']):.1f}% shorter**
- Mono measured rate: **{float(metrics['r2a_to_r2b_mono_fps_gain_pct']):.1f}% higher**
- Stereo measured rate: **{float(metrics['r2a_to_r2b_stereo_fps_gain_pct']):.1f}% higher**

## R1 to R2B measured result

- Mono: **{float(metrics['r1_mono_fps']):.1f} → {float(metrics['mono_fps']):.1f} FPS** ({float(metrics['r1_to_r2b_mono_fps_gain_pct']):.1f}% higher)
- Stereo: **{float(metrics['r1_stereo_fps']):.1f} → {float(metrics['stereo_fps']):.1f} FPS** ({float(metrics['r1_to_r2b_stereo_fps_gain_pct']):.1f}% higher)

The isolated transport measurements are the strongest apples-to-apples result.
Complete-frame rates also depend on the gameplay activity represented by each
hardware session.

## R2B timing detail

- Mono cropped transport: **{float(metrics['mono_left_cropped_ms']):.3f} ms**
- Stereo left cropped transport: **{float(metrics['stereo_left_cropped_ms']):.3f} ms**
- Stereo right cropped transport: **{float(metrics['stereo_right_cropped_ms']):.3f} ms**
- Mono pre-present engine work: **{float(metrics['mono_pre_present_ms']):.3f} ms**
- Stereo pre-present engine work: **{float(metrics['stereo_pre_present_ms']):.3f} ms**
- Mono presentation: **{float(metrics['mono_present_ms']):.3f} ms**
- Stereo presentation: **{float(metrics['stereo_present_ms']):.3f} ms**

## Implementation

R2B keeps the R2A direct indexed-to-Morton conversion but generates only the
output-sized regions consumed by the top and bottom 3DS displays. It uses
separate cropped top-left, cropped top-right, and bottom-atlas textures while
retaining the complete R2A transport as a frame-safe fallback.

This hardware run recorded zero cropped-path fallbacks and zero fallback-swizzle
time. The remaining major stereo cost is software rendering before presentation,
not texture submission.
"""


def release_draft_markdown(metrics: dict[str, object]) -> str:
    states = metrics["validation_states"]
    assert isinstance(states, dict)
    legacy_right_line = (
        "- Legacy-right validation: **PASS**"
        if states["legacy_right"] == "PASS"
        else "- Legacy-right validation: **pending; not exercised in this session**"
    )

    return f"""# Draft Citadel 3DS Citro3D Progress Update

> **DO NOT PUBLISH YET.** This local entry preserves the August 3, 2026 R2B
> milestone while additional Citro3D performance work continues.

## Cropped direct-tiled transport is hardware verified

`CITADEL-C3D-R2B-CROPPEDTILED1` stops generating the unused portions of the
software framebuffer texture. The 3DS now prepares only the top-screen image
regions and the composed lower-screen atlas required for the active layout.

Hardware validation recorded:

- Legacy-left validation: **PASS**
- Split-left validation: **PASS**
- Split-right validation: **PASS**
{legacy_right_line}
- Pixel mismatches: **0**
- Cropped transport fallbacks: **0**
- Upload failures: **0**
- Draw failures: **0**
- Clean shutdown: **YES**

Compared with R2A, texture preparation changed from:

- Mono: **{R2A_BASELINE['mono_upload_ms']:.3f} ms → {float(metrics['mono_upload_ms']):.3f} ms** ({float(metrics['r2a_to_r2b_mono_upload_reduction_pct']):.1f}% lower)
- Stereo: **{R2A_BASELINE['stereo_upload_ms']:.3f} ms → {float(metrics['stereo_upload_ms']):.3f} ms** ({float(metrics['r2a_to_r2b_stereo_upload_reduction_pct']):.1f}% lower)

Across the full R1-to-R2B progression, measured complete-frame rates changed
from approximately:

- Mono: **{float(metrics['r1_mono_fps']):.1f} FPS → {float(metrics['mono_fps']):.1f} FPS**
- Stereo: **{float(metrics['r1_stereo_fps']):.1f} FPS → {float(metrics['stereo_fps']):.1f} FPS**

That places mono gameplay just below 30 FPS in this hardware session and makes
stereo roughly {float(metrics['r1_to_r2b_stereo_fps_gain_pct']):.1f}% faster than
the original profiled transport build. Complete-frame results vary with scene
activity, while the isolated transport reductions are directly measured.

This remains an experimental Citro3D branch rather than a native world renderer.
The remaining stereo ceiling is now dominated by the CPU software-rendering
work performed before presentation.
"""


def restore_markdown(checkpoint_name: str) -> str:
    return f"""# Restore {DISPLAY_MILESTONE}

This checkpoint preserves the complete working source tree and exact
hardware-proven artifacts. Generated build directories were intentionally
excluded; rebuild them from the preserved source when needed.

## Restore source safely

From MSYS2:

```bash
cd /c/Projects
mv Citadel_Citro3D_DEV Citadel_Citro3D_DEV_BEFORE_R2B_RESTORE
mkdir -p Citadel_Citro3D_DEV/Source
cp -a \\
  /c/Projects/Citadel_C3D_CHECKPOINTS/{checkpoint_name}/source/shockolate \\
  /c/Projects/Citadel_Citro3D_DEV/Source/
```

## Hardware-proven binary

```text
artifacts/{BINARY_OUTPUT_NAME}
```

## Hardware evidence

```text
evidence/{PROFILE_FILENAME}
```

The manifest records the exact validation state, including whether
`legacy_right` was PASS or PENDING. Verify `SHA256SUMS.txt` before restoring or
distributing any artifact.
"""


def create_tar_gz(source_dir: Path, archive_path: Path) -> None:
    with tarfile.open(archive_path, "w:gz") as archive:
        archive.add(source_dir, arcname=source_dir.name)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile-log",
        type=Path,
        default=None,
        help="Explicit path to C3D_R2B_CROPPEDTILEDPROFILE.log (or a ZIP containing it)",
    )
    parser.add_argument(
        "--evidence-zip",
        type=Path,
        default=None,
        help="Explicit evidence ZIP containing C3D_R2B_CROPPEDTILEDPROFILE.log",
    )
    args = parser.parse_args()

    print("============================================================")
    print("PROJECT CITADEL R2B MILESTONE PRESERVATION")
    print("============================================================")

    normalized = SOURCE_ROOT.as_posix()
    if EXPECTED_SOURCE_FRAGMENT not in normalized:
        fail(
            "Run this from "
            "C:/Projects/Citadel_Citro3D_DEV/Source/shockolate"
        )

    if not SHOCK_SOURCE.is_file() or not CMAKE_FILE.is_file():
        fail("Shock.c or CMakeLists.txt is missing.")

    source_text = SHOCK_SOURCE.read_text(encoding="utf-8-sig", errors="replace")
    missing_source = [marker for marker in SOURCE_MARKERS if marker not in source_text]
    if missing_source:
        fail(
            "Active source is not R2B CROPPEDTILED1. Missing: "
            + ", ".join(missing_source)
        )

    if not GITHUB_ROOT.is_dir():
        fail(f"GitHub working folder is missing: {GITHUB_ROOT}")

    try:
        evidence = locate_profile_evidence(args.profile_log, args.evidence_zip)
        binary = locate_verified_binary()
        metrics = parse_profile(evidence)
    except PreserveError as exc:
        fail(str(exc))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    checkpoint_name = f"{MILESTONE}_{timestamp}"
    checkpoint_dir = CHECKPOINT_PARENT / checkpoint_name
    checkpoint_temp = CHECKPOINT_PARENT / f".{checkpoint_name}.INCOMPLETE"
    checkpoint_archive = CHECKPOINT_PARENT / f"{checkpoint_name}.tar.gz"

    github_entry = GITHUB_ROOT / "Release_Drafts" / MILESTONE
    github_temp = GITHUB_ROOT / "Release_Drafts" / f".{MILESTONE}.INCOMPLETE"

    for path in (
        checkpoint_dir,
        checkpoint_temp,
        checkpoint_archive,
        github_entry,
        github_temp,
    ):
        if path.exists():
            fail(f"Refusing to overwrite existing milestone output: {path}")

    CHECKPOINT_PARENT.mkdir(parents=True, exist_ok=True)
    github_entry.parent.mkdir(parents=True, exist_ok=True)

    print(f"Verified source: {SHOCK_SOURCE}")
    print(f"Verified binary: {binary}")
    print(f"Verified profile evidence: {evidence.description}")
    print(f"Binary SHA-256: {sha256(binary)}")
    print(f"Profile SHA-256: {evidence.digest}")
    print(
        "Validation states: "
        + ", ".join(
            f"{name}={state}"
            for name, state in metrics["validation_states"].items()
        )
    )

    try:
        # Build checkpoint atomically in a hidden incomplete directory.
        source_destination = checkpoint_temp / "source/shockolate"
        shutil.copytree(
            SOURCE_ROOT,
            source_destination,
            ignore=ignore_source_copy,
            copy_function=shutil.copy2,
        )

        artifacts = checkpoint_temp / "artifacts"
        evidence_dir = checkpoint_temp / "evidence"
        metadata = checkpoint_temp / "metadata"
        artifacts.mkdir(parents=True)
        evidence_dir.mkdir(parents=True)
        metadata.mkdir(parents=True)

        shutil.copy2(binary, artifacts / BINARY_OUTPUT_NAME)
        write_bytes(evidence_dir / PROFILE_FILENAME, evidence.data)

        build_log = SOURCE_ROOT / BUILD_LOG_NAME
        if build_log.is_file():
            shutil.copy2(build_log, evidence_dir / build_log.name)

        patch_script = SOURCE_ROOT / PATCH_SCRIPT_NAME
        if patch_script.is_file():
            shutil.copy2(patch_script, metadata / patch_script.name)

        preservation_script = SOURCE_ROOT / Path(__file__).name
        if preservation_script.is_file():
            shutil.copy2(preservation_script, metadata / preservation_script.name)

        write_text(metadata / "PROFILE_RESULTS.md", metrics_markdown(metrics))
        write_text(
            metadata / "RESTORE_INSTRUCTIONS.md",
            restore_markdown(checkpoint_name),
        )

        manifest = {
            "milestone": DISPLAY_MILESTONE,
            "status": "HARDWARE_PASS",
            "coverage_note": (
                "legacy_right was not exercised in this run"
                if metrics["validation_states"]["legacy_right"] == "PENDING"
                else "all four validation paths passed"
            ),
            "created_local": datetime.now().astimezone().isoformat(),
            "source_root": str(SOURCE_ROOT),
            "source_shock_sha256": sha256(SHOCK_SOURCE),
            "cmake_sha256": sha256(CMAKE_FILE),
            "binary_source": str(binary),
            "binary_sha256": sha256(binary),
            "profile_source": evidence.description,
            "profile_sha256": evidence.digest,
            "metrics": metrics,
            "r1_baseline": R1_BASELINE,
            "r2a_baseline": R2A_BASELINE,
            "source_copy_exclusions": {
                "directories": sorted(EXCLUDED_DIR_NAMES),
                "patterns": ["build-*", "CITADEL_C3D_CHECKPOINT*"],
                "generated_binary_suffixes": sorted(EXCLUDED_FILE_SUFFIXES),
            },
            "github_status_before_draft": run_git_status(GITHUB_ROOT),
            "publication_status": "LOCAL_DRAFT_DO_NOT_PUBLISH_YET",
        }
        write_text(
            metadata / "MANIFEST.json",
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        )

        write_sha256sums(checkpoint_temp, checkpoint_temp / "SHA256SUMS.txt")
        checkpoint_temp.rename(checkpoint_dir)
        create_tar_gz(checkpoint_dir, checkpoint_archive)

        # Create the unpublished GitHub progress entry atomically.
        github_temp.mkdir(parents=True)
        write_text(
            github_temp / "DO_NOT_PUBLISH_YET.txt",
            "LOCAL DRAFT ONLY\n"
            "Created to preserve the R2B hardware-pass update while further "
            "Citro3D work continues.\n"
            "Do not commit, push, tag, or publish this entry yet.\n",
        )
        write_text(github_temp / "README.md", release_draft_markdown(metrics))
        write_text(github_temp / "PROFILE_RESULTS.md", metrics_markdown(metrics))
        write_bytes(github_temp / PROFILE_FILENAME, evidence.data)
        shutil.copy2(binary, github_temp / BINARY_OUTPUT_NAME)
        write_sha256sums(github_temp, github_temp / "SHA256SUMS.txt")
        github_temp.rename(github_entry)

    except Exception as exc:
        shutil.rmtree(checkpoint_temp, ignore_errors=True)
        shutil.rmtree(github_temp, ignore_errors=True)
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir, ignore_errors=True)
        checkpoint_archive.unlink(missing_ok=True)
        if github_entry.exists():
            shutil.rmtree(github_entry, ignore_errors=True)
        fail(f"Preservation failed and partial outputs were removed: {exc}")

    print()
    print("SUCCESS: R2B hardware milestone preserved.")
    print()
    print(f"Checkpoint folder: {checkpoint_dir}")
    print(f"Checkpoint archive: {checkpoint_archive}")
    print(f"GitHub local draft entry: {github_entry}")
    print()
    print("Preserved proof:")
    for name, state in metrics["validation_states"].items():
        print(f"  {name}={state}")
    print(f"  mismatches={metrics['validation_mismatches']}")
    print(f"  cropped fallbacks={metrics['cropped_fallbacks']}")
    print(f"  Mono transport={float(metrics['mono_upload_ms']):.3f} ms")
    print(f"  Stereo transport={float(metrics['stereo_upload_ms']):.3f} ms")
    print(f"  Mono measured rate={float(metrics['mono_fps']):.1f} FPS")
    print(f"  Stereo measured rate={float(metrics['stereo_fps']):.1f} FPS")
    print()
    print("No git commit, push, tag, or release action was performed.")
    print("============================================================")


if __name__ == "__main__":
    main()
