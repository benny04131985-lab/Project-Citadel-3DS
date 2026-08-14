#!/usr/bin/env python3
"""Resume only the Project Citadel V16.1 asset installation.

Run this from the Shockolate project root after extracting the complete
V16.1 package somewhere accessible.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

EXPECTED = [
    "Hack-i-Ben_Splash.png",
    "Project_Citadel_Icon.png",
    "Project_Citadel_Banner.png",
    "Project_Citadel_Banner.wav",
    "Project_Citadel_3DS.rsf",
]


def valid_asset_dir(path: Path) -> bool:
    return path.is_dir() and all((path / name).is_file() for name in EXPECTED)


def find_asset_dir(explicit: str | None) -> Path | None:
    candidates: list[Path] = []

    if explicit:
        candidates.append(Path(explicit).expanduser())

    here = Path(__file__).resolve().parent
    cwd = Path.cwd()

    candidates.extend([
        here / "assets" / "v16_1",
        here / "Project_Citadel_3DS_V16_1_Launch_Polish" / "assets" / "v16_1",
        cwd / "Project_Citadel_3DS_V16_1_Launch_Polish" / "assets" / "v16_1",
    ])

    for base in (here, cwd):
        try:
            for candidate in base.glob("**/assets/v16_1"):
                candidates.append(candidate)
        except OSError:
            pass

    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue

        if resolved in seen:
            continue
        seen.add(resolved)

        if valid_asset_dir(resolved):
            return resolved

    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        help="Path to the extracted package's assets/v16_1 folder",
    )
    args = parser.parse_args()

    project_root = Path.cwd()
    cmake = project_root / "CMakeLists.txt"
    if not cmake.is_file():
        print(
            "ERROR: Run this from the Shockolate project root "
            "(the folder containing CMakeLists.txt).",
            file=sys.stderr,
        )
        return 1

    source = find_asset_dir(args.source)
    if source is None:
        print("ERROR: Could not locate the extracted V16.1 assets.", file=sys.stderr)
        print("Extract the complete V16.1 ZIP, then run:", file=sys.stderr)
        print(
            '  python repair_Project_Citadel_V16_1_assets.py '
            '--source "/path/to/extracted/assets/v16_1"',
            file=sys.stderr,
        )
        return 1

    destination = project_root / "assets" / "v16_1"
    destination.parent.mkdir(parents=True, exist_ok=True)

    if destination.exists():
        shutil.rmtree(destination)

    shutil.copytree(source, destination)

    missing = [name for name in EXPECTED if not (destination / name).is_file()]
    if missing:
        print("ERROR: Asset copy was incomplete:", file=sys.stderr)
        for name in missing:
            print(f"  {name}", file=sys.stderr)
        return 1

    print(f"Source:      {source}")
    print(f"Installed:   {destination}")
    print("V16.1 asset repair completed.")
    print()
    print("Continue with:")
    print("  cmake --build build-3ds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
