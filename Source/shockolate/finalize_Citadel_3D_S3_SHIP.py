#!/usr/bin/env python3
"""
Finalize Project Citadel 3D S3 into C:/Projects/Citadel_3D_S3_SHIP.

Run from:
  C:/Projects/Citadel_3D_DEV/Source/shockolate

The script verifies S3/S2.1, clean-builds from an empty build directory,
enforces the SystemShock3D wall, archives the source, copies the final 3DSX,
writes ship notes, and creates SHA-256 manifests.

Licensed System Shock game data is never copied.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
import zipfile


ROOT = Path.cwd().resolve()
EXPECTED_SUFFIX = "citadel_3d_dev/source/shockolate"
DESTINATION = ROOT.parents[2] / "Citadel_3D_S3_SHIP"
BUILD = ROOT / "build"
FINAL_3DSX = BUILD / "3D_Citadel_3DS.3dsx"

MARKERS = {
    Path("CMakeLists.txt"): [
        "3D_Citadel_3DS.3dsx",
        "sdmc:/3ds/SystemShock3D/",
    ],
    Path("src/MacSrc/Shock.c"): [
        "PROJECT CITADEL 3D S3: ship polish and quiet diagnostics are ACTIVE",
        "PROJECT CITADEL 3D S2: true dual-camera world stereo is ACTIVE",
        'chdir("sdmc:/3ds/SystemShock3D")',
        "GPU 3D S3 mode=TRUE_WORLD_AUTO_FLAT_UI",
        "GPU 3D S3 FIRST TRUE FRAME",
    ],
    Path("src/GameSrc/render.c"): [
        "PROJECT CITADEL 3D S3: ship-safe exceptional-view flattening is ACTIVE",
        "global_fullmap->cyber ||",
        "view360_render_on ||",
        "hack_takeover",
    ],
    Path("src/GameSrc/frsetup.c"): [
        "PROJECT CITADEL 3D S2.1: centered depth curve and 5px ceiling are ACTIVE",
        "CITADEL_3DS_STEREO_MAX_CONVERGENCE_PIXELS 5",
        "citadel_3ds_stereo_centered_slider_curve",
    ],
    Path("src/Libraries/INPUT/Source/sdl_events.c"): [
        "PROJECT CITADEL 3D S2.1 INPUT: frame-time freelook normalization is ACTIVE",
        "citadel_3ds_stereo_freelook_frame_scale",
    ],
}

CORE_FILES = [
    Path("CMakeLists.txt"),
    Path("src/MacSrc/Shock.c"),
    Path("src/MacSrc/SDLSound.c"),
    Path("src/GameSrc/render.c"),
    Path("src/GameSrc/frsetup.c"),
    Path("src/GameSrc/frmain.c"),
    Path("src/GameSrc/mainloop.c"),
    Path("src/GameSrc/setup.c"),
    Path("src/GameSrc/wrapper.c"),
    Path("src/GameSrc/gamewrap.c"),
    Path("src/Libraries/INPUT/Source/sdl_events.c"),
]

FORBIDDEN = (
    "sdmc:/3ds/SystemShock/",
    "sdmc:/3ds/systemshock/",
)

EXCLUDED_DIRS = {
    ".git",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
}

EXCLUDED_SUFFIXES = {
    ".o",
    ".a",
    ".elf",
    ".3dsx",
    ".cia",
    ".smdh",
    ".bnr",
    ".log",
    ".dmp",
    ".pyc",
}


def die(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def readable_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB"):
        if value < 1024 or unit == "GiB":
            return f"{value:.2f} {unit}"
        value /= 1024
    return str(size)


def verify_source() -> None:
    print("===== VERIFY FINAL S3 SOURCE =====")

    if not ROOT.as_posix().lower().endswith(EXPECTED_SUFFIX):
        die(
            "Run this from:\n"
            "  C:/Projects/Citadel_3D_DEV/Source/shockolate\n"
            f"Current: {ROOT}"
        )

    loaded = {}
    for relative, required in MARKERS.items():
        path = ROOT / relative
        if not path.is_file():
            die(f"Missing active file: {relative}")

        text = path.read_text(encoding="utf-8", errors="replace")
        loaded[relative] = text
        missing = [item for item in required if item not in text]

        if missing:
            print(f"FAIL: {relative}")
            for item in missing:
                print(f"  missing: {item}")
            die("The working tree is not the completed S3/S2.1 ship state.")

        print(f"PASS: {relative}")

    active_paths = (
        loaded[Path("CMakeLists.txt")]
        + "\n"
        + loaded[Path("src/MacSrc/Shock.c")]
    )
    for token in FORBIDDEN:
        if token in active_paths:
            die(f"Mono SD path survived in active source: {token}")

    if "(citadel_gpu_presented_frames % 600) == 0" in loaded[
        Path("src/MacSrc/Shock.c")
    ]:
        die("The recurring S2 development frame log survived into S3.")

    print("PASS: active mono SD path is absent.")
    print("PASS: S2.1 depth and C-nub tuning are frozen.")
    print("PASS: S3 exceptional-view flattening is present.")


def run_and_log(command: list[str], log) -> None:
    shown = " ".join(command)
    print(f"\n$ {shown}")
    log.write(f"\n$ {shown}\n")
    log.flush()

    process = subprocess.Popen(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        bufsize=1,
        env=os.environ.copy(),
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="")
        log.write(line)

    code = process.wait()
    log.flush()
    if code:
        die(f"Build command failed with exit code {code}: {shown}")


def clean_build(stage: Path) -> Path:
    print("\n===== CLEAN FINAL BUILD =====")

    cmake = shutil.which("cmake")
    if not cmake:
        die("cmake is not available in PATH.")

    devkitpro = os.environ.get("DEVKITPRO")
    if not devkitpro:
        die("DEVKITPRO is not set.")

    toolchain = Path(devkitpro) / "cmake" / "3DS.cmake"
    if not toolchain.is_file():
        die(f"3DS toolchain file is missing: {toolchain}")

    if BUILD.exists():
        print(f"Removing generated build tree: {BUILD}")
        shutil.rmtree(BUILD)

    log_dir = stage / "BuildLogs"
    log_dir.mkdir(parents=True)
    log_path = log_dir / "S3_FINAL_CLEAN_BUILD.log"

    configure = [
        cmake,
        "-S", ".",
        "-B", "build",
        f"-DCMAKE_TOOLCHAIN_FILE={toolchain}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DCMAKE_POLICY_VERSION_MINIMUM=3.5",
        "-DENABLE_OPENGL=OFF",
        "-DENABLE_SOUND=OFF",
        "-DENABLE_FLUIDSYNTH=OFF",
        "-DENABLE_SDL2=ON",
    ]

    build = [
        cmake,
        "--build", "build",
        "--target", "project_citadel_3dsx",
        f"-j{max(1, os.cpu_count() or 1)}",
    ]

    with log_path.open("w", encoding="utf-8", newline="") as log:
        log.write(
            "PROJECT CITADEL 3D S3 — FINAL CLEAN BUILD\n"
            f"Started: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Root: {ROOT}\n"
        )
        run_and_log(configure, log)
        run_and_log(build, log)

    if not FINAL_3DSX.is_file() or FINAL_3DSX.stat().st_size == 0:
        die(f"Final output was not generated: {FINAL_3DSX}")

    print(f"\nPASS: {FINAL_3DSX}")
    print(f"Size: {readable_size(FINAL_3DSX.stat().st_size)}")
    return log_path


def verify_binary() -> None:
    print("\n===== VERIFY FINAL 3DSX =====")
    data = FINAL_3DSX.read_bytes()

    for token in FORBIDDEN:
        if token.encode("ascii") in data:
            die(f"Final binary contains the mono SD path: {token}")

    if b"sdmc:/3ds/SystemShock3D" not in data:
        die("Final binary does not contain the SystemShock3D runtime identity.")

    print("PASS: mono SD path absent from binary.")
    print("PASS: SystemShock3D identity present in binary.")
    print(f"SHA-256: {sha256(FINAL_3DSX)}")


def allowed_source(relative: Path) -> bool:
    if any(part in EXCLUDED_DIRS for part in relative.parts):
        return False
    if relative.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    return True


def archive_source(stage: Path) -> int:
    print("\n===== ARCHIVE FINAL SOURCE =====")
    source_dir = stage / "Source"
    source_dir.mkdir(parents=True)

    archive = source_dir / "Citadel_3D_S3_SHIP_SOURCE.zip"
    manifest = []
    count = 0

    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as output:
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue

            relative = path.relative_to(ROOT)
            if not allowed_source(relative):
                continue

            data = path.read_bytes()
            output.writestr(relative.as_posix(), data)
            manifest.append(
                f"{hashlib.sha256(data).hexdigest()}  {relative.as_posix()}"
            )
            count += 1

        output.writestr(
            "CITADEL_3D_S3_SOURCE_SHA256.txt",
            "\n".join(manifest) + "\n",
        )

    print(f"PASS: {archive}")
    print(f"Files: {count}")
    print(f"Size: {readable_size(archive.stat().st_size)}")
    return count


def copy_core_files(stage: Path) -> None:
    core = stage / "Source" / "ACTIVE_CORE_FILES"
    sums = []

    for relative in CORE_FILES:
        source = ROOT / relative
        if not source.is_file():
            print(f"NOTE: optional core file absent: {relative}")
            continue

        target = core / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        sums.append(f"{sha256(target)}  {relative.as_posix()}")

    (core / "SHA256SUMS.txt").write_text(
        "\n".join(sums) + "\n",
        encoding="utf-8",
    )


def copy_release(stage: Path) -> None:
    print("\n===== COPY RELEASE ARTIFACTS =====")
    release = stage / "Release"
    release.mkdir(parents=True)

    shutil.copy2(FINAL_3DSX, release / "3D_Citadel_3DS.3dsx")
    print("PASS: 3D_Citadel_3DS.3dsx")

    for name in (
        "3D_Citadel_3DS.smdh",
        "3D_Citadel_3DS.bnr",
        "3D_Citadel_3DS.cia",
    ):
        candidate = BUILD / name
        if candidate.is_file():
            shutil.copy2(candidate, release / name)
            print(f"PASS: {name}")


def write_docs(stage: Path, source_count: int) -> None:
    docs = stage / "Docs"
    docs.mkdir(parents=True)

    final_binary = stage / "Release" / "3D_Citadel_3DS.3dsx"

    readme = f"""PROJECT CITADEL 3D — S3 SHIP
================================

STATUS
------
Final stereoscopic ship build.

Finalized: {datetime.now().isoformat(timespec='seconds')}
Final binary SHA-256: {sha256(final_binary)}
Archived source files: {source_count}

INSTALLATION
------------
Copy:

  Release/3D_Citadel_3DS.3dsx

to:

  sdmc:/3ds/SystemShock3D/3D_Citadel_3DS.3dsx

This stereo build is intentionally isolated from:

  sdmc:/3ds/SystemShock/

LICENSED GAME DATA
------------------
Licensed System Shock game data is not included.

The tested user-supplied runtime layout is:

  sdmc:/3ds/SystemShock3D/
    DATA/
    RES/
    SOUND/
    Hack-i-Ben_Splash.t3x
    V15H_CONTROL.t3x
    3D_Citadel_3DS.3dsx

STEREOSCOPIC BEHAVIOR
---------------------
* Ordinary station gameplay uses true dual-camera world stereo.
* HUD, weapon, cursor, text, borders, and interface stay at zero parallax.
* Cyberspace remains flat.
* The 360-degree view remains flat.
* Full security-camera takeover remains flat.
* Returning to station gameplay restores true stereo automatically.
* No extra stereo control buttons are needed.

3D SLIDER
---------
The middle adjustment range is the recommended comfort sweet spot.

Maximum depth remains intentionally available and usable, but comfort at the
highest setting depends on the player and session length. Use personal
judgment.

CONFIRMED HARDWARE RESULTS
--------------------------
PASS: hallway and doorway depth
PASS: clean geometry edges
PASS: no visible eye splitting in ordinary play
PASS: calibrated C-nub freelook with stereo active
PASS: save and load
PASS: in-game quit
PASS: enter and exit cyberspace
PASS: restore station stereo after cyberspace

DEFERRED HOTFIX
---------------
HOME/suspend remains somewhat inconsistent.

Treat that as a separate future lifecycle hotfix. Do not alter the frozen S3
renderer, S2.1 depth curve, C-nub tuning, or exceptional-view behavior while
investigating suspend behavior.

BUILD RULE
----------
Under this Windows/MSYS/CMake setup, delete build/ and reconfigure after every
source-state change. Incremental dependency files have proven unreliable.

FINAL DECISION
--------------
S2.1 depth and C-nub tuning are frozen.
S3 presentation behavior is frozen.
Project Citadel 3D S3 is shippable.
"""

    (docs / "README_CITADEL_3D_S3_SHIP.txt").write_text(
        readme,
        encoding="utf-8",
        newline="",
    )

    restore = """RESTORE / FUTURE HOTFIX NOTES
================================

The source ZIP contains the exact non-generated source state archived at ship.

To continue later:

1. Extract Citadel_3D_S3_SHIP_SOURCE.zip into a new working folder.
2. Keep the completed ship tree untouched.
3. Delete any build/ directory.
4. Reconfigure with the flags in the ship README.
5. Build target project_citadel_3dsx.

Future HOME/suspend experiments should begin from a copy of this ship source.
The runtime folder must remain sdmc:/3ds/SystemShock3D/.
"""

    (docs / "RESTORE_AND_FUTURE_HOTFIX.txt").write_text(
        restore,
        encoding="utf-8",
        newline="",
    )

    done = """PROJECT CITADEL 3D S3 — FINALIZED
===================================

Source verification: PASS
Clean build: PASS
SD wall: PASS
Binary verification: PASS
Source archive: PASS
Release package: PASS
Checksums: PASS

STATUS: DONE :D
"""
    (stage / "CITADEL_3D_S3_FINALIZED.txt").write_text(
        done,
        encoding="utf-8",
        newline="",
    )


def write_checksums(stage: Path) -> None:
    checksums = stage / "Checksums"
    checksums.mkdir(parents=True)

    entries = []
    for path in sorted(stage.rglob("*")):
        if not path.is_file() or checksums in path.parents:
            continue
        entries.append(
            f"{sha256(path)}  {path.relative_to(stage).as_posix()}"
        )

    (checksums / "CITADEL_3D_S3_SHIP_SHA256.txt").write_text(
        "\n".join(entries) + "\n",
        encoding="utf-8",
    )

    binary = stage / "Release" / "3D_Citadel_3DS.3dsx"
    (checksums / "FINAL_3DSX_SHA256.txt").write_text(
        f"{sha256(binary)}  Release/3D_Citadel_3DS.3dsx\n",
        encoding="utf-8",
    )


def main() -> int:
    verify_source()

    if DESTINATION.exists():
        die(
            f"Final destination already exists:\n  {DESTINATION}\n"
            "Rename or remove it before running the finalizer again."
        )

    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(
        tempfile.mkdtemp(
            prefix=".Citadel_3D_S3_SHIP_STAGING_",
            dir=DESTINATION.parent,
        )
    )

    print(f"\nFinal destination: {DESTINATION}")
    print(f"Staging directory: {stage}")

    try:
        clean_build(stage)
        verify_binary()
        source_count = archive_source(stage)
        copy_core_files(stage)
        copy_release(stage)
        write_docs(stage, source_count)
        write_checksums(stage)
        os.replace(stage, DESTINATION)
    except BaseException:
        if stage.exists():
            print(f"\nStaging retained for inspection:\n  {stage}")
        raise

    print("\n============================================================")
    print("PROJECT CITADEL 3D S3 — FINAL SHIP COMPLETE")
    print("============================================================")
    print(f"Final folder: {DESTINATION}")
    print(
        "Final binary: "
        f"{DESTINATION / 'Release' / '3D_Citadel_3DS.3dsx'}"
    )
    print(
        "Source archive: "
        f"{DESTINATION / 'Source' / 'Citadel_3D_S3_SHIP_SOURCE.zip'}"
    )
    print("DONE :D")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
