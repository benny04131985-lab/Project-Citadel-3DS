#!/usr/bin/env python3
"""
Seal the current Project Citadel VX1-NATURAL five-file baseline.

Run from the Shockolate repository root:

    python seal_vx1_natural_baseline.py

The script does not modify the active source tree.

It verifies:
  * Shock.c, mainloop.c, wrapper.c, and gamewrap.c still match exact VX0.
  * setup.c contains the VX1-NATURAL marker.
  * setup.c no longer contains the active T7 arming call.

It then copies the five files into:
  C:/Projects/Citadel-Baselines/VX1-NATURAL-BASELINE_<timestamp>/

and creates:
  VX1-NATURAL-BASELINE_<timestamp>.zip
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import hashlib
import shutil
import sys
import zipfile


SAFE_ROOT = Path("/c/Projects/Citadel-Baselines")

FILES = [
    Path("src/MacSrc/Shock.c"),
    Path("src/GameSrc/setup.c"),
    Path("src/GameSrc/mainloop.c"),
    Path("src/GameSrc/wrapper.c"),
    Path("src/GameSrc/gamewrap.c"),
]

EXACT_UNCHANGED_HASHES = {
    Path("src/MacSrc/Shock.c"):
        "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724",
    Path("src/GameSrc/mainloop.c"):
        "8fb3331b9e3e0fe1532417237d5adb8a8820508dc5f7e4f9d389870d31e9a369",
    Path("src/GameSrc/wrapper.c"):
        "d027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2",
    Path("src/GameSrc/gamewrap.c"):
        "c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30",
}

SETUP = Path("src/GameSrc/setup.c")
NATURAL_MARKER = (
    "PROJECT CITADEL VX1-NATURAL: use the original New Game path."
)
ACTIVE_T7_CALL = "citadel_3ds_arm_newgame_home_t7();"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def main() -> int:
    if not Path("src/MacSrc").is_dir() or not Path("src/GameSrc").is_dir():
        print("ERROR: Run this from the Shockolate repository root.")
        return 1

    print("============================================================")
    print("PROJECT CITADEL VX1-NATURAL BASELINE SEAL")
    print("============================================================")
    print()
    print("Verifying active source state...")

    for path in FILES:
        if not path.is_file():
            print(f"ERROR: Missing required source file: {path}")
            print("Nothing was copied.")
            return 1

    for path, expected in EXACT_UNCHANGED_HASHES.items():
        actual = sha256(path)
        status = "OK" if actual == expected else "WRONG"
        print(f"{status:5} {actual}  {path}")

        if actual != expected:
            print()
            print(
                "ERROR: One of the four unchanged VX0 files does not match."
            )
            print("Nothing was copied.")
            return 1

    setup_text = SETUP.read_text(encoding="utf-8")
    setup_hash = sha256(SETUP)

    print(f"CHECK {setup_hash}  {SETUP}")

    if NATURAL_MARKER not in setup_text:
        print()
        print("ERROR: VX1-NATURAL marker is missing from setup.c.")
        print("Nothing was copied.")
        return 1

    active_call_lines = [
        line_number
        for line_number, line in enumerate(
            setup_text.splitlines(),
            start=1,
        )
        if ACTIVE_T7_CALL in line
        and not line.lstrip().startswith(("//", "/*", "*"))
    ]

    if active_call_lines:
        print()
        print(
            "ERROR: Active T7 Save/Load arming call still exists at "
            f"line(s): {active_call_lines}"
        )
        print("Nothing was copied.")
        return 1

    print("OK    setup.c contains VX1-NATURAL marker")
    print("OK    active T7 Save/Load arming call is absent")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    baseline_name = f"VX1-NATURAL-BASELINE_{timestamp}"
    destination_root = SAFE_ROOT / baseline_name
    archive_path = SAFE_ROOT / f"{baseline_name}.zip"

    if destination_root.exists() or archive_path.exists():
        print()
        print("ERROR: Timestamped destination already exists.")
        print("Nothing was copied.")
        return 1

    destination_root.mkdir(parents=True, exist_ok=False)

    source_hashes: dict[Path, str] = {}

    print()
    print(f"Copying baseline to: {destination_root}")

    for source in FILES:
        source_hash = sha256(source)
        source_hashes[source] = source_hash

        destination = destination_root / source
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

        copied_hash = sha256(destination)

        if copied_hash != source_hash:
            print()
            print(f"ERROR: Copy verification failed for {source}")
            print(f"Partial destination remains at: {destination_root}")
            return 1

        print(f"SEALED {source_hash}  {source}")

    manifest_lines = [
        f"{source_hashes[source]}  {source.as_posix()}"
        for source in FILES
    ]

    (destination_root / "SHA256SUMS.txt").write_text(
        "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
    )

    (destination_root / "BASELINE_INFO.txt").write_text(
        "PROJECT CITADEL VX1-NATURAL BASELINE\n"
        "====================================\n\n"
        "Purpose:\n"
        "  Immutable baseline for all future HOME-suspend experiments.\n\n"
        "Behavior:\n"
        "  Natural original New Game path.\n"
        "  Automatic T7 Save/Load normalizer is not armed.\n"
        "  Shock.c, mainloop.c, wrapper.c, and gamewrap.c remain exact VX0.\n\n"
        f"Sealed: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Source repository: {Path.cwd()}\n"
        f"setup.c SHA256: {setup_hash}\n\n"
        "Iteration rule:\n"
        "  Never modify this folder.\n"
        "  Every failed experiment must begin again from these five files.\n",
        encoding="utf-8",
    )

    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(destination_root.rglob("*")):
            if path.is_file():
                archive.write(
                    path,
                    Path(baseline_name) / path.relative_to(destination_root),
                )

    print()
    print("Verifying sealed folder...")

    for source in FILES:
        sealed = destination_root / source
        actual = sha256(sealed)
        expected = source_hashes[source]
        status = "OK" if actual == expected else "WRONG"
        print(f"{status:5} {actual}  {sealed}")

        if actual != expected:
            print()
            print("ERROR: Final sealed-folder verification failed.")
            return 1

    archive_hash = sha256(archive_path)

    (SAFE_ROOT / f"{baseline_name}.zip.sha256.txt").write_text(
        f"{archive_hash}  {archive_path.name}\n",
        encoding="utf-8",
    )

    print()
    print("============================================================")
    print("VX1-NATURAL BASELINE SEALED SUCCESSFULLY")
    print(f"FOLDER: {destination_root}")
    print(f"ZIP:    {archive_path}")
    print(f"ZIP SHA256: {archive_hash}")
    print("ACTIVE SOURCE TREE WAS NOT MODIFIED")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
