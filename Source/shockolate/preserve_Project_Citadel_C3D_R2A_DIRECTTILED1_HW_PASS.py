#!/usr/bin/env python3
"""
preserve_Project_Citadel_C3D_R2A_DIRECTTILED1_HW_PASS.py

Run from:
    C:/Projects/Citadel_Citro3D_DEV/Source/shockolate

Purpose:
    Preserve the hardware-proven CITADEL-C3D-R2A-DIRECTTILED1 milestone as a
    complete source checkpoint with exact binary/log evidence, hashes,
    restoration instructions, and a local unpublished GitHub release-draft
    entry.

This script DOES NOT:
  - modify Citadel source files;
  - build the project;
  - run git add/commit/push/tag;
  - modify the currently published release or its release notes.

Optional:
    python preserve_Project_Citadel_C3D_R2A_DIRECTTILED1_HW_PASS.py \
        --profile-log /x/3ds/SystemShock3D/C3D_R2_DIRECTTILEDPROFILE.log
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
from datetime import datetime
from pathlib import Path
from typing import Iterable, NoReturn


MILESTONE = "CITADEL_C3D_R2A_DIRECTTILED1_HW_PASS"
DISPLAY_MILESTONE = "CITADEL-C3D-R2A-DIRECTTILED1"
EXPECTED_SOURCE_FRAGMENT = "Citadel_Citro3D_DEV/Source/shockolate"

SOURCE_ROOT = Path.cwd().resolve()
GITHUB_ROOT = Path("/c/Projects/Citadel_3D_GITHUB")
CHECKPOINT_PARENT = Path("/c/Projects/Citadel_C3D_CHECKPOINTS")
BUILD_ROOT = SOURCE_ROOT / "build-c3d-r2a-directtiled1"
SHOCK_SOURCE = SOURCE_ROOT / "src/MacSrc/Shock.c"
CMAKE_FILE = SOURCE_ROOT / "CMakeLists.txt"

PROFILE_FILENAME = "C3D_R2_DIRECTTILEDPROFILE.log"
BINARY_OUTPUT_NAME = "3D_Citadel_3DS_R2A_DIRECTTILED1.3dsx"

SOURCE_MARKERS = (
    "PROJECT CITADEL C3D R2A DIRECTTILED1",
    "GPU C3D R2A DIRECTTILED VALIDATION PASS",
    "C3D_R2_DIRECTTILEDPROFILE.log",
)

BINARY_MARKERS = (
    b"PROJECT CITADEL C3D R2A DIRECTTILED1 ACTIVE",
    b"GPU C3D R2A DIRECTTILED VALIDATION PASS",
    b"C3D_R2_DIRECTTILEDPROFILE.log",
    b"MONO_SINGLE_EYE",
    b"STEREO_DUAL_EYE",
)

PROFILE_MARKERS = (
    "PROJECT CITADEL C3D R2A DIRECTTILED1 ACTIVE",
    "Direct-tiled enabled at shutdown: YES",
    "Direct-tiled validation: PASS mismatches=0",
    "fallback=0",
    "Upload failures: 0",
    "Draw failures: 0",
    "Clean Shutdown: YES",
)

# Hardware-proven R1 baseline from C3D_R1_TRANSPORTPROFILE.log.
R1_BASELINE = {
    "mono_cycle_ms": 45.631,
    "mono_upload_ms": 22.418,
    "stereo_cycle_ms": 94.288,
    "stereo_upload_ms": 45.008,
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


def fail(message: str) -> NoReturn:
    raise SystemExit(f"ERROR: {message}\nNo checkpoint or GitHub draft was finalized.")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_float(text: str, pattern: str, label: str) -> float:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise PreserveError(f"Could not parse {label} from profile log.")
    return float(match.group(1))


def safe_int(text: str, pattern: str, label: str) -> int:
    match = re.search(pattern, text, flags=re.MULTILINE)
    if not match:
        raise PreserveError(f"Could not parse {label} from profile log.")
    return int(match.group(1))


def pct_reduction(before: float, after: float) -> float:
    if before <= 0.0:
        return 0.0
    return ((before - after) / before) * 100.0


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


def locate_profile_log(explicit: Path | None) -> Path:
    candidates: list[Path] = []

    if explicit is not None:
        candidates.append(explicit.expanduser())

    candidates.extend(
        [
            SOURCE_ROOT / PROFILE_FILENAME,
            SOURCE_ROOT / "C3D_R2_DIRECTTILEDPROFILE_extracted.log",
            Path("/c/Users/benny/Downloads") / PROFILE_FILENAME,
            Path("/c/Users/benny/Desktop") / PROFILE_FILENAME,
        ]
    )

    # Search removable/mounted MSYS drive roots without assuming the SD letter.
    for letter in "defghijklmnopqrstuvwxyz":
        root = Path(f"/{letter}")
        candidates.append(root / "3ds/SystemShock3D" / PROFILE_FILENAME)

    # Downloads may have browser-added suffixes such as "(1)".
    downloads = Path("/c/Users/benny/Downloads")
    if downloads.is_dir():
        candidates.extend(sorted(downloads.glob("C3D_R2_DIRECTTILEDPROFILE*.log")))

    valid: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        if candidate.is_file():
            valid.append(candidate)

    if not valid:
        raise PreserveError(
            "Could not locate C3D_R2_DIRECTTILEDPROFILE.log. "
            "Copy it into this source folder or pass --profile-log PATH."
        )

    # Prefer a valid milestone log; among them, use the newest filesystem copy.
    proven: list[Path] = []
    for path in valid:
        text = path.read_text(encoding="utf-8", errors="replace")
        if all(marker in text for marker in PROFILE_MARKERS):
            proven.append(path)

    if not proven:
        listed = "\n  - ".join(str(path) for path in valid)
        raise PreserveError(
            "Profile candidates were found, but none prove the R2A hardware pass:\n"
            f"  - {listed}"
        )

    return max(proven, key=lambda path: path.stat().st_mtime_ns)


def locate_verified_binary() -> Path:
    if not BUILD_ROOT.is_dir():
        raise PreserveError(f"Missing R2A build folder: {BUILD_ROOT}")

    binaries = sorted(BUILD_ROOT.rglob("*.3dsx"))
    if not binaries:
        raise PreserveError(f"No .3dsx found beneath {BUILD_ROOT}")

    matches: list[Path] = []
    for binary in binaries:
        data = binary.read_bytes()
        if all(marker in data for marker in BINARY_MARKERS):
            matches.append(binary)

    if not matches:
        raise PreserveError(
            "No R2A build output contains all DIRECTTILED1 proof markers."
        )

    return max(matches, key=lambda path: path.stat().st_mtime_ns)


def parse_profile(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="replace")

    for marker in PROFILE_MARKERS:
        if marker not in text:
            raise PreserveError(f"Profile proof marker missing: {marker}")

    metrics: dict[str, object] = {
        "build": re.search(r"^Build:\s*(.+)$", text, flags=re.MULTILINE).group(1),
        "presented_frames": safe_int(
            text,
            r"^Presented frames observed by GPU logger:\s*(\d+)",
            "presented frames",
        ),
        "left_eye_passes": safe_int(
            text,
            r"^Direct-tiled eye passes:\s*left=(\d+)",
            "left-eye passes",
        ),
        "right_eye_passes": safe_int(
            text,
            r"^Direct-tiled eye passes:\s*left=\d+\s+right=(\d+)",
            "right-eye passes",
        ),
        "fallbacks": safe_int(
            text,
            r"^Direct-tiled eye passes:.*fallback=(\d+)",
            "fallback count",
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
        "mono_upload_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE avg_frame_begin_ms=[0-9.]+ avg_upload_total_ms=([0-9.]+)",
            "mono upload",
        ),
        "mono_directtiled_ms": safe_float(
            text,
            r"^PROFILE mode=MONO_SINGLE_EYE avg_palette_ms=[0-9.]+ avg_left_directtiled_ms=([0-9.]+)",
            "mono direct-tiled pass",
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
        "stereo_upload_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE avg_frame_begin_ms=[0-9.]+ avg_upload_total_ms=([0-9.]+)",
            "stereo upload",
        ),
        "stereo_left_directtiled_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE avg_palette_ms=[0-9.]+ avg_left_directtiled_ms=([0-9.]+)",
            "stereo left direct-tiled pass",
        ),
        "stereo_right_directtiled_ms": safe_float(
            text,
            r"^PROFILE mode=STEREO_DUAL_EYE.*avg_right_directtiled_ms=([0-9.]+)",
            "stereo right direct-tiled pass",
        ),
    }

    metrics.update(
        {
            "mono_fps": fps_from_ms(float(metrics["mono_cycle_ms"])),
            "stereo_fps": fps_from_ms(float(metrics["stereo_cycle_ms"])),
            "mono_upload_reduction_pct": pct_reduction(
                R1_BASELINE["mono_upload_ms"],
                float(metrics["mono_upload_ms"]),
            ),
            "stereo_upload_reduction_pct": pct_reduction(
                R1_BASELINE["stereo_upload_ms"],
                float(metrics["stereo_upload_ms"]),
            ),
            "mono_cycle_reduction_pct": pct_reduction(
                R1_BASELINE["mono_cycle_ms"],
                float(metrics["mono_cycle_ms"]),
            ),
            "stereo_cycle_reduction_pct": pct_reduction(
                R1_BASELINE["stereo_cycle_ms"],
                float(metrics["stereo_cycle_ms"]),
            ),
            "r1_mono_fps": fps_from_ms(R1_BASELINE["mono_cycle_ms"]),
            "r1_stereo_fps": fps_from_ms(R1_BASELINE["stereo_cycle_ms"]),
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


def metrics_markdown(metrics: dict[str, object]) -> str:
    return f"""# {DISPLAY_MILESTONE} — Hardware Results

Status: **PASS**  
Publication status: **LOCAL DRAFT — DO NOT PUBLISH YET**

## Validation

- Direct-tiled enabled at shutdown: **YES**
- Byte-for-byte validation: **PASS, 0 mismatches**
- Direct-tiled fallbacks: **{metrics['fallbacks']}**
- Left-eye passes: **{metrics['left_eye_passes']}**
- Right-eye passes: **{metrics['right_eye_passes']}**
- Presented frames: **{metrics['presented_frames']}**
- Upload failures: **0**
- Draw failures: **0**
- Clean shutdown: **YES**

## R1 transport baseline versus R2A

| Measurement | R1 baseline | R2A DIRECTTILED1 | Change |
|---|---:|---:|---:|
| Mono texture transport | {R1_BASELINE['mono_upload_ms']:.3f} ms | {float(metrics['mono_upload_ms']):.3f} ms | **{float(metrics['mono_upload_reduction_pct']):.1f}% lower** |
| Stereo texture transport | {R1_BASELINE['stereo_upload_ms']:.3f} ms | {float(metrics['stereo_upload_ms']):.3f} ms | **{float(metrics['stereo_upload_reduction_pct']):.1f}% lower** |
| Mono full frame | {R1_BASELINE['mono_cycle_ms']:.3f} ms | {float(metrics['mono_cycle_ms']):.3f} ms | **{float(metrics['mono_cycle_reduction_pct']):.1f}% shorter** |
| Stereo full frame | {R1_BASELINE['stereo_cycle_ms']:.3f} ms | {float(metrics['stereo_cycle_ms']):.3f} ms | **{float(metrics['stereo_cycle_reduction_pct']):.1f}% shorter** |
| Approximate mono rate | {float(metrics['r1_mono_fps']):.1f} FPS | {float(metrics['mono_fps']):.1f} FPS | session comparison |
| Approximate stereo rate | {float(metrics['r1_stereo_fps']):.1f} FPS | {float(metrics['stereo_fps']):.1f} FPS | session comparison |

The isolated transport measurements are the strongest apples-to-apples result.
Full-frame rates also depend on the gameplay activity represented in each run.

## Implementation

R2A fuses indexed-color palette conversion and Morton-tiled RGB565 output into
one pass per eye. It removes the separate linear RGB565 staging pass, separate
Morton swizzle pass, unnecessary full-texture padding clear, and repeated
per-pixel scaling divisions. The old transport remains available as a safety
fallback, but this hardware run used it **zero times**.

## Remaining bottlenecks

The fused direct-tiled pass still costs approximately
**{float(metrics['mono_directtiled_ms']):.3f} ms per mono eye** and
**{float(metrics['stereo_left_directtiled_ms']):.3f}/{float(metrics['stereo_right_directtiled_ms']):.3f} ms per stereo eye**.
The next practical target is reducing the number of pixels processed before a
larger native-world-renderer conversion.
"""


def release_draft_markdown(metrics: dict[str, object]) -> str:
    stereo_gain = (
        (float(metrics["stereo_fps"]) / float(metrics["r1_stereo_fps"]) - 1.0)
        * 100.0
    )
    mono_gain = (
        (float(metrics["mono_fps"]) / float(metrics["r1_mono_fps"]) - 1.0)
        * 100.0
    )

    return f"""# Draft Citadel 3DS Citro3D Progress Update

> **DO NOT PUBLISH YET.** This local entry preserves the August 3, 2026 R2A
> milestone while additional performance work continues.

## Direct-tiled framebuffer transport is hardware verified

The experimental Citro3D branch has reached its first substantial measured
performance gain. `CITADEL-C3D-R2A-DIRECTTILED1` replaces the previous
linear-RGB565-plus-Morton-swizzle pipeline with a fused pass that converts the
8-bit software framebuffer directly into the final tiled Citro3D texture.

Hardware validation completed with:

- **0 visual-data mismatches** during byte-for-byte validation
- **0 fallback transport passes**
- **0 upload failures**
- **0 draw failures**
- **clean shutdown**

Measured texture-transport cost changed from:

- Mono: **{R1_BASELINE['mono_upload_ms']:.3f} ms → {float(metrics['mono_upload_ms']):.3f} ms** ({float(metrics['mono_upload_reduction_pct']):.1f}% lower)
- Stereo: **{R1_BASELINE['stereo_upload_ms']:.3f} ms → {float(metrics['stereo_upload_ms']):.3f} ms** ({float(metrics['stereo_upload_reduction_pct']):.1f}% lower)

During these hardware sessions, approximate complete-frame rates changed from:

- Mono: **{float(metrics['r1_mono_fps']):.1f} FPS → {float(metrics['mono_fps']):.1f} FPS** ({mono_gain:.1f}% higher)
- Stereo: **{float(metrics['r1_stereo_fps']):.1f} FPS → {float(metrics['stereo_fps']):.1f} FPS** ({stereo_gain:.1f}% higher)

The isolated transport figures are directly comparable. Complete-frame rates
vary somewhat with gameplay activity, but the stereo improvement was also
clearly noticeable during hardware testing.

This is not yet a fully native world renderer: System Shock still rasterizes
its world in software. The current branch now has a verified native Citro3D
presenter and a substantially faster framebuffer transport layer, giving us a
stronger base for the next optimization pass.
"""


def restore_markdown(checkpoint_name: str) -> str:
    return f"""# Restore {DISPLAY_MILESTONE}

This checkpoint preserves the source tree and exact hardware-proven artifacts.
Generated build directories were intentionally excluded; rebuild them from the
preserved source.

## Restore source safely

From MSYS2:

```bash
cd /c/Projects
mv Citadel_Citro3D_DEV Citadel_Citro3D_DEV_BEFORE_R2A_RESTORE
mkdir -p Citadel_Citro3D_DEV/Source
cp -a \
  /c/Projects/Citadel_C3D_CHECKPOINTS/{checkpoint_name}/source/shockolate \
  /c/Projects/Citadel_Citro3D_DEV/Source/
```

## Hardware-proven binary

The exact verified `.3dsx` is stored under:

```text
artifacts/{BINARY_OUTPUT_NAME}
```

## Evidence

The hardware profile is stored under:

```text
evidence/{PROFILE_FILENAME}
```

Always verify `SHA256SUMS.txt` before restoring or distributing artifacts.
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
        help="Explicit path to C3D_R2_DIRECTTILEDPROFILE.log",
    )
    args = parser.parse_args()

    print("============================================================")
    print("PROJECT CITADEL R2A MILESTONE PRESERVATION")
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
        fail("Active source is not R2A DIRECTTILED1. Missing: " + ", ".join(missing_source))

    if not GITHUB_ROOT.is_dir():
        fail(f"GitHub working folder is missing: {GITHUB_ROOT}")

    try:
        profile_log = locate_profile_log(args.profile_log)
        binary = locate_verified_binary()
        metrics = parse_profile(profile_log)
    except PreserveError as exc:
        fail(str(exc))

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    checkpoint_name = f"{MILESTONE}_{timestamp}"
    checkpoint_dir = CHECKPOINT_PARENT / checkpoint_name
    checkpoint_temp = CHECKPOINT_PARENT / f".{checkpoint_name}.INCOMPLETE"
    checkpoint_archive = CHECKPOINT_PARENT / f"{checkpoint_name}.tar.gz"

    github_entry = GITHUB_ROOT / "Release_Drafts" / MILESTONE
    github_temp = GITHUB_ROOT / "Release_Drafts" / f".{MILESTONE}.INCOMPLETE"

    for path in (checkpoint_dir, checkpoint_temp, checkpoint_archive, github_entry, github_temp):
        if path.exists():
            fail(f"Refusing to overwrite existing milestone output: {path}")

    CHECKPOINT_PARENT.mkdir(parents=True, exist_ok=True)
    github_entry.parent.mkdir(parents=True, exist_ok=True)

    print(f"Verified source: {SHOCK_SOURCE}")
    print(f"Verified binary: {binary}")
    print(f"Verified profile: {profile_log}")
    print(f"Binary SHA-256: {sha256(binary)}")
    print(f"Profile SHA-256: {sha256(profile_log)}")

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
        evidence = checkpoint_temp / "evidence"
        metadata = checkpoint_temp / "metadata"
        artifacts.mkdir(parents=True)
        evidence.mkdir(parents=True)
        metadata.mkdir(parents=True)

        shutil.copy2(binary, artifacts / BINARY_OUTPUT_NAME)
        shutil.copy2(profile_log, evidence / PROFILE_FILENAME)

        build_log = SOURCE_ROOT / "C3D_R2A_DIRECTTILED1_BUILD.log"
        if build_log.is_file():
            shutil.copy2(build_log, evidence / build_log.name)

        patch_script = SOURCE_ROOT / "apply_Project_Citadel_C3D_R2A_DIRECTTILED1.py"
        if patch_script.is_file():
            shutil.copy2(patch_script, metadata / patch_script.name)

        write_text(metadata / "PROFILE_RESULTS.md", metrics_markdown(metrics))
        write_text(metadata / "RESTORE_INSTRUCTIONS.md", restore_markdown(checkpoint_name))

        manifest = {
            "milestone": DISPLAY_MILESTONE,
            "status": "HARDWARE_PASS",
            "created_local": datetime.now().astimezone().isoformat(),
            "source_root": str(SOURCE_ROOT),
            "source_shock_sha256": sha256(SHOCK_SOURCE),
            "cmake_sha256": sha256(CMAKE_FILE),
            "binary_source": str(binary),
            "binary_sha256": sha256(binary),
            "profile_source": str(profile_log),
            "profile_sha256": sha256(profile_log),
            "metrics": metrics,
            "r1_baseline": R1_BASELINE,
            "source_copy_exclusions": {
                "directories": sorted(EXCLUDED_DIR_NAMES),
                "patterns": ["build-*", "CITADEL_C3D_CHECKPOINT*"],
                "generated_binary_suffixes": sorted(EXCLUDED_FILE_SUFFIXES),
            },
            "github_status_before_draft": run_git_status(GITHUB_ROOT),
            "publication_status": "LOCAL_DRAFT_DO_NOT_PUBLISH_YET",
        }
        write_text(metadata / "MANIFEST.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

        write_sha256sums(checkpoint_temp, checkpoint_temp / "SHA256SUMS.txt")
        checkpoint_temp.rename(checkpoint_dir)
        create_tar_gz(checkpoint_dir, checkpoint_archive)

        # Create the unpublished GitHub release-draft entry atomically.
        github_temp.mkdir(parents=True)
        write_text(github_temp / "DO_NOT_PUBLISH_YET.txt", (
            "LOCAL DRAFT ONLY\n"
            "Created to preserve the R2A hardware-pass update while further "
            "Citro3D work continues.\n"
            "Do not commit, push, tag, or publish this entry yet.\n"
        ))
        write_text(github_temp / "README.md", release_draft_markdown(metrics))
        write_text(github_temp / "PROFILE_RESULTS.md", metrics_markdown(metrics))
        shutil.copy2(profile_log, github_temp / PROFILE_FILENAME)
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
    print("SUCCESS: R2A hardware milestone preserved.")
    print()
    print(f"Checkpoint folder: {checkpoint_dir}")
    print(f"Checkpoint archive: {checkpoint_archive}")
    print(f"GitHub local draft entry: {github_entry}")
    print()
    print("Preserved proof:")
    print("  Validation PASS, mismatches=0")
    print(f"  Fallbacks={metrics['fallbacks']}")
    print(f"  Mono transport={float(metrics['mono_upload_ms']):.3f} ms")
    print(f"  Stereo transport={float(metrics['stereo_upload_ms']):.3f} ms")
    print(f"  Mono measured rate={float(metrics['mono_fps']):.1f} FPS")
    print(f"  Stereo measured rate={float(metrics['stereo_fps']):.1f} FPS")
    print()
    print("No git commit, push, tag, or release action was performed.")
    print("============================================================")


if __name__ == "__main__":
    main()
