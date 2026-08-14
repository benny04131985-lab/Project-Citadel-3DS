#!/usr/bin/env python3
"""
Create a protected Project Citadel VX1-SHIP gold archive.

Run from:
    /c/Projects/Citadel-Ship-16-1/Source/shockolate

Command:
    python seal_citadel_vx1_ship_gold.py

Output:
    /c/Projects/GoldCitadel/
        Citadel_VX1-SHIP_GOLD_<timestamp>/

The output is a timestamped, no-overwrite archival package containing:
  * the exact five ship-critical source files;
  * the complete current build/ directory;
  * relevant VX1/T7/splash scripts, diffs, install records, and notes;
  * available repository/project documentation;
  * README_VX1-SHIP.md with the recent development history and test matrix;
  * BUILD_COMMAND.txt;
  * ARCHIVE_INVENTORY.txt;
  * SHA256SUMS.txt;
  * CURRENT_SOURCE_HASHES.txt;
  * a do-not-edit marker.

This does not modify, rename, clean, or delete anything in the active project.
It does not create a ZIP; the user plans to make the final copies and ZIP
manually after inspecting this archive.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import os
import shutil
import sys


GOLD_ROOT = Path("/c/Projects/GoldCitadel")

SHOCK = Path("src/MacSrc/Shock.c")
SETUP = Path("src/GameSrc/setup.c")
MAINLOOP = Path("src/GameSrc/mainloop.c")
WRAPPER = Path("src/GameSrc/wrapper.c")
GAMEWRAP = Path("src/GameSrc/gamewrap.c")

SHIP_FILES = [SHOCK, SETUP, MAINLOOP, WRAPPER, GAMEWRAP]

EXPECTED_MARKER = (
    "PROJECT CITADEL VX1.1-SPLASH-SYNTH-A: "
    "startup GPU ownership round trip is ACTIVE"
)

EXPECTED_UNCHANGED_GAMEWRAP_HASH = (
    "c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30"
)

BUILD_COMMAND = r"""rm -rf build

cmake -S . -B build \
  -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DENABLE_OPENGL=OFF \
  -DENABLE_SOUND=OFF \
  -DENABLE_FLUIDSYNTH=OFF \
  -DENABLE_SDL2=ON

cmake --build build \
  --target project_citadel_3dsx \
  -j"$(nproc)"
"""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def verify_repo_root(repo_root: Path) -> None:
    if not (repo_root / "src/MacSrc").is_dir():
        raise RuntimeError(
            "Run this script from the Shockolate repository root. "
            "Expected src/MacSrc was not found."
        )

    if not (repo_root / "src/GameSrc").is_dir():
        raise RuntimeError(
            "Run this script from the Shockolate repository root. "
            "Expected src/GameSrc was not found."
        )

    for relative in SHIP_FILES:
        path = repo_root / relative

        if not path.is_file():
            raise RuntimeError(
                f"Missing required ship source file: {relative}"
            )

    build_dir = repo_root / "build"

    if not build_dir.is_dir():
        raise RuntimeError(
            "Current build/ directory is missing. Build the ship candidate "
            "before sealing it."
        )


def copy_file_verified(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

    source_hash = sha256_file(source)
    destination_hash = sha256_file(destination)

    if source_hash != destination_hash:
        raise RuntimeError(
            f"Copy verification failed:\n"
            f"  source:      {source}\n"
            f"  destination: {destination}"
        )


def copy_tree_verified(source: Path, destination: Path) -> None:
    if destination.exists():
        raise RuntimeError(
            f"Refusing to overwrite existing directory: {destination}"
        )

    shutil.copytree(
        source,
        destination,
        copy_function=shutil.copy2,
        symlinks=True,
    )

    source_files = sorted(
        path
        for path in source.rglob("*")
        if path.is_file() and not path.is_symlink()
    )

    for source_file in source_files:
        relative = source_file.relative_to(source)
        destination_file = destination / relative

        if not destination_file.is_file():
            raise RuntimeError(
                f"Copied tree is missing: {destination_file}"
            )

        if sha256_file(source_file) != sha256_file(destination_file):
            raise RuntimeError(
                f"Tree copy hash mismatch: {relative}"
            )


def find_build_products(build_dir: Path) -> list[Path]:
    extensions = {
        ".3dsx",
        ".elf",
        ".smdh",
        ".cia",
        ".map",
    }

    return sorted(
        path
        for path in build_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in extensions
    )


def collect_root_records(repo_root: Path) -> list[Path]:
    exact_names = {
        "VX1_1_SPLASH_SYNTH_A.diff",
        "VX1_1_SPLASH_SYNTH_A_INSTALLED.txt",
        "VX1_NATURAL_NO_T7_INSTALLED.txt",
        "VX1_NATURAL_NEWGAME.diff",
        "VX1_NATURAL_INSTALLED.txt",
    }

    patterns = [
        "VX1*.diff",
        "VX1*.txt",
        "*splash*synth*.py",
        "*SPLASH*SYNTH*.py",
        "*t7*.py",
        "*T7*.py",
        "*seal*baseline*.py",
        "*seal*ship*.py",
        "remove_all_t7_and_seal*.py",
        "apply_vx1_1_splash_synth_a.py",
    ]

    found: set[Path] = set()

    for name in exact_names:
        path = repo_root / name

        if path.is_file():
            found.add(path)

    for pattern in patterns:
        for path in repo_root.glob(pattern):
            if path.is_file():
                found.add(path)

    script_path = Path(sys.argv[0]).resolve()

    if script_path.is_file():
        found.add(script_path)

    return sorted(found)


def collect_documentation_sources(
    repo_root: Path,
    project_root: Path,
) -> list[tuple[Path, Path]]:
    sources: list[tuple[Path, Path]] = []

    for name in ("README.md", "README.txt", "README", "LICENSE", "COPYING"):
        path = repo_root / name

        if path.is_file():
            sources.append(
                (path, Path("Documentation/Repository") / path.name)
            )

    for name in ("docs", "Docs", "doc", "Doc"):
        path = repo_root / name

        if path.is_dir():
            sources.append(
                (path, Path("Documentation/Repository") / path.name)
            )

    project_docs = project_root / "Docs"

    if project_docs.is_dir():
        sources.append(
            (
                project_docs,
                Path("Documentation/Project/Citadel-Ship-16-1-Docs"),
            )
        )

    return sources


def relative_archive_files(archive_root: Path) -> list[Path]:
    return sorted(
        path.relative_to(archive_root)
        for path in archive_root.rglob("*")
        if path.is_file()
    )


def write_hash_manifest(archive_root: Path) -> None:
    manifest_path = archive_root / "SHA256SUMS.txt"

    files = [
        relative
        for relative in relative_archive_files(archive_root)
        if relative != Path("SHA256SUMS.txt")
    ]

    lines = [
        f"{sha256_file(archive_root / relative)}  {relative.as_posix()}"
        for relative in files
    ]

    manifest_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def create_readme(
    repo_root: Path,
    project_root: Path,
    archive_name: str,
    source_hashes: dict[Path, str],
    build_products: list[Path],
) -> str:
    products_text = "\n".join(
        f"- `{path.relative_to(repo_root / 'build').as_posix()}`"
        for path in build_products
    )

    if not products_text:
        products_text = (
            "- No `.3dsx`, `.elf`, `.smdh`, `.cia`, or `.map` product was "
            "detected. The complete build tree is still archived."
        )

    hashes_text = "\n".join(
        f"- `{relative.as_posix()}` — `{source_hashes[relative]}`"
        for relative in SHIP_FILES
    )

    return f"""# Project Citadel VX1-SHIP Gold Archive

**Archive:** `{archive_name}`  
**Sealed:** {datetime.now().isoformat(timespec="seconds")}  
**Active repository at seal time:** `{repo_root}`  
**Project root:** `{project_root}`

## Status

This archive preserves the exact source/build state accepted as:

> **Project Citadel VX1-SHIP**

VX1-SHIP is the mono, dual-screen Citadel/System Shock 3DS release candidate
immediately before stereoscopic development begins. It has clean user-facing
visual behavior and generally functional HOME Menu suspend/resume behavior,
with acknowledged occasional inconsistencies.

This package is archival. Do not develop inside it. Create a separate complete
project copy for `Citadel_3D_DEV`.

## What is included

- `Source_Five_File_Ship_Set/`
  - The five ship-critical source files, preserving their repository paths.
- `build/`
  - A complete copy of the current CMake build directory.
- `Documentation/`
  - Available repository and project documentation.
- `Development_Records/`
  - Available VX1/T7/splash scripts, diffs, install records, and notes.
- `README_VX1-SHIP.md`
  - This release history and recovery guide.
- `BUILD_COMMAND.txt`
  - The exact clean-build command used.
- `CURRENT_SOURCE_HASHES.txt`
  - SHA-256 values for the five ship files.
- `ARCHIVE_INVENTORY.txt`
  - File inventory with byte sizes.
- `SHA256SUMS.txt`
  - SHA-256 manifest for the complete package.
- `.GOLD_ARCHIVE_DO_NOT_EDIT`
  - Archive identity marker.

This is **not a complete source repository**. The active/full project should be
copied separately for the backup, ZIP, and `Citadel_3D_DEV` work trees.

## Recent source progression

### VX0 — automatic T7 Save/Load normalization

The earlier five-file baseline contained an automatic T7 Save/Load sequence
after New Game. Save/Load could often prepare HOME suspension, but natural New
Game remained unreliable and the automatic operation was visible and lengthy.

### VX1-NATURAL — T7 arming disabled

The automatic New Game Save/Load arming call was disabled while the dormant T7
code remained compiled. Natural New Game unexpectedly passed HOME suspension
three consecutive times, while some previously safe Save/Load paths became
inconsistent.

### VX1-NATURAL-NO-T7 — T7 removed completely

All T7 declarations, frame hooks, state, and Load-result instrumentation were
removed from:

- `src/GameSrc/setup.c`
- `src/GameSrc/mainloop.c`
- `src/GameSrc/wrapper.c`

`Shock.c` and `gamewrap.c` remained unchanged during that removal.

Observed no-T7 matrix:

- Continue → HOME: **failed**
- New Game → manual Load → HOME: **passed**
- Menu HOME/resume → New Game → HOME: **passed**
- HOME after saving: **failed**
- Natural New Game → HOME: **failed**
- Direct lid sleep: black-screen/failure behavior

This produced a clean, understandable baseline but did not provide broadly
reliable suspension.

### VX1.1-SPLASH-SYNTH-A — accepted ship candidate

Only `src/MacSrc/Shock.c` was modified from the protected no-T7 baseline.

The existing Hack-i-Ben launch image already renders as a real full-screen
400×240 Citro2D texture inside synchronized Citro3D frames. After the eighth
completed splash frame, VX1.1 performs one startup GPU/VRAM ownership round
trip:

1. `C3D_FrameSync()`
2. `gspWaitForVBlank()`
3. `GSPGPU_SaveVramSysArea()`
4. `GSPGPU_ImportDisplayCaptureInfo()`
5. `GSPGPU_ReleaseRight()`
6. `GSPGPU_AcquireRight(0)`
7. `GSPGPU_RestoreVramSysArea()`
8. `gspWaitForVBlank()`
9. A later ordinary splash frame
10. `C3D_FrameSync()` and VBlank verification

The dedicated runtime log is:

`VX1_1_SPLASH_SYNTH_A.log`

No automatic Save/Load workaround, New Game hook, mainloop alteration,
post-Save patch, post-Load patch, or visible masking was added.

## Accepted VX1-SHIP suspend observations

Observed test results included:

- Cold boot → Continue → HOME: **pass**
- Cold boot → New Game → manual Load → HOME: **one observed failure**
- Cold boot → Natural New Game → HOME: **pass**
- Cold boot → menu HOME/resume → New Game → HOME: **pass**
- Menu-prepared game → Load → HOME: **pass**
- New Game → HOME → manual Load → HOME: **pass**
- Continue → Load Game → HOME: **pass**
- HOME → lid sleep → reopen: **pass**
- Direct cold-boot lid sleep → reopen: **failure observed**

The splash primer materially improved practical suspend behavior without
introducing visual jank. It does not guarantee perfect APT suspension under
every startup, Save, Load, or lid-sleep ordering.

## Release note / known issue

> **Suspend/Resume:** HOME Menu suspension and lid sleep are generally
> functional across Continue, New Game, and Load workflows. Rare resume
> failures or black screens may still occur, particularly during direct lid
> sleep soon after a cold launch or during certain Save/Load sequences. Save
> progress before suspending.

Avoid publishing a precise reliability percentage from the limited test sample.

## Preserved five-file ship set

{hashes_text}

## Detected build products

{products_text}

The entire `build/` directory is preserved even when an individual product is
not listed above.

## Clean build command

```bash
{BUILD_COMMAND.rstrip()}
```

## Recovery

To reconstruct the five-file source state, copy the contents of:

`Source_Five_File_Ship_Set/`

back into the same relative paths beneath the Shockolate repository root.

After restoration, delete `build/` and perform the clean build command above.

## Branching into stereoscopic development

Recommended manual sequence:

1. Keep one complete project copy named `Citadel_VX1-SHIP` as the untouched
   local backup.
2. ZIP a second complete `Citadel_VX1-SHIP` copy for offline preservation.
3. Rename a third complete project copy to `Citadel_3D_DEV`.
4. Begin stereo changes only in `Citadel_3D_DEV`.
5. Do not purge other material until all three copies open correctly and the
   gold archive's `SHA256SUMS.txt` verifies.

## Purge caution

Before emptying the recycle bin or deleting old folders, verify:

- This gold archive exists and contains the five source files and `build/`.
- The complete `Citadel_VX1-SHIP` backup exists.
- The ZIP opens and lists files successfully.
- `Citadel_3D_DEV` contains the complete source tree.
- The ship `.3dsx` has been copied to at least two independent locations.
- `SHA256SUMS.txt` has been retained with the archive.
"""


def main() -> int:
    repo_root = Path.cwd()
    verify_repo_root(repo_root)

    project_root = repo_root.parent.parent
    build_dir = repo_root / "build"

    shock_text = (repo_root / SHOCK).read_text(
        encoding="utf-8",
        errors="replace",
    )

    if EXPECTED_MARKER not in shock_text:
        print(
            "ERROR: VX1.1-SPLASH-SYNTH-A marker is missing from Shock.c."
        )
        print("Nothing was copied.")
        return 1

    gamewrap_hash = sha256_file(repo_root / GAMEWRAP)

    if gamewrap_hash != EXPECTED_UNCHANGED_GAMEWRAP_HASH:
        print(
            "ERROR: gamewrap.c does not match the expected VX1 ship base."
        )
        print(f"Actual: {gamewrap_hash}")
        print("Nothing was copied.")
        return 1

    source_hashes = {
        relative: sha256_file(repo_root / relative)
        for relative in SHIP_FILES
    }

    build_products = find_build_products(build_dir)

    if not build_products:
        print(
            "WARNING: No .3dsx/.elf/.smdh/.cia/.map product was detected "
            "inside build/."
        )
        print("The complete build directory will still be archived.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archive_name = f"Citadel_VX1-SHIP_GOLD_{timestamp}"
    final_root = GOLD_ROOT / archive_name
    staging_root = GOLD_ROOT / f".{archive_name}.STAGING"

    GOLD_ROOT.mkdir(parents=True, exist_ok=True)

    if final_root.exists() or staging_root.exists():
        print(
            "ERROR: Refusing to overwrite an existing gold archive:"
        )
        print(f"  {final_root}")
        print("Nothing was copied.")
        return 1

    staging_root.mkdir(parents=True, exist_ok=False)

    try:
        print("============================================================")
        print("PROJECT CITADEL VX1-SHIP GOLD SEAL")
        print("============================================================")
        print(f"Repository:  {repo_root}")
        print(f"Destination: {final_root}")
        print()

        print("Copying five-file ship source set...")
        source_set_root = staging_root / "Source_Five_File_Ship_Set"

        for relative in SHIP_FILES:
            copy_file_verified(
                repo_root / relative,
                source_set_root / relative,
            )

        print("Copying complete build/ directory...")
        copy_tree_verified(
            build_dir,
            staging_root / "build",
        )

        print("Collecting development records...")
        records_root = staging_root / "Development_Records"
        records_root.mkdir(parents=True, exist_ok=True)

        record_sources = collect_root_records(repo_root)

        for source in record_sources:
            destination = records_root / source.name
            copy_file_verified(source, destination)

        print("Collecting available documentation...")
        for source, relative_destination in collect_documentation_sources(
            repo_root,
            project_root,
        ):
            destination = staging_root / relative_destination

            if source.is_dir():
                copy_tree_verified(source, destination)
            else:
                copy_file_verified(source, destination)

        readme = create_readme(
            repo_root,
            project_root,
            archive_name,
            source_hashes,
            build_products,
        )

        (staging_root / "README_VX1-SHIP.md").write_text(
            readme,
            encoding="utf-8",
        )

        (staging_root / "BUILD_COMMAND.txt").write_text(
            BUILD_COMMAND,
            encoding="utf-8",
        )

        current_hash_lines = [
            f"{source_hashes[relative]}  {relative.as_posix()}"
            for relative in SHIP_FILES
        ]

        (staging_root / "CURRENT_SOURCE_HASHES.txt").write_text(
            "\n".join(current_hash_lines) + "\n",
            encoding="utf-8",
        )

        (staging_root / ".GOLD_ARCHIVE_DO_NOT_EDIT").write_text(
            "PROJECT CITADEL VX1-SHIP GOLD ARCHIVE\n"
            f"Created: {datetime.now().isoformat(timespec='seconds')}\n"
            "Do not develop inside this folder.\n",
            encoding="utf-8",
        )

        inventory_lines: list[str] = []

        for relative in relative_archive_files(staging_root):
            path = staging_root / relative
            inventory_lines.append(
                f"{path.stat().st_size:12d}  {relative.as_posix()}"
            )

        (staging_root / "ARCHIVE_INVENTORY.txt").write_text(
            "\n".join(inventory_lines) + "\n",
            encoding="utf-8",
        )

        print("Hashing complete archive...")
        write_hash_manifest(staging_root)

        os.replace(staging_root, final_root)

    except Exception as error:
        print()
        print(f"ERROR: Gold sealing failed: {error}")

        if staging_root.exists():
            print(f"Incomplete staging folder retained at: {staging_root}")

        print("The active project was not modified.")
        return 1

    final_files = relative_archive_files(final_root)
    final_size = sum(
        (final_root / relative).stat().st_size
        for relative in final_files
    )

    print()
    print("============================================================")
    print("CITADEL VX1-SHIP GOLD ARCHIVE COMPLETE")
    print(f"FOLDER:       {final_root}")
    print(f"FILES:        {len(final_files)}")
    print(f"TOTAL BYTES:  {final_size}")
    print(f"BUILD ITEMS:  {len(build_products)}")
    print("ACTIVE TREE:  UNCHANGED")
    print("============================================================")
    print()
    print("Inspect README_VX1-SHIP.md and SHA256SUMS.txt before purge.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
