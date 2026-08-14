#!/usr/bin/env python3
"""
Project Citadel VX1-NATURAL

Run from the Shockolate repository root:

    python make_vx1_natural_newgame.py

This script requires the exact installed VX0 five-file set. It changes only
src/GameSrc/setup.c, removing the single active call that arms the automatic
T7 Save/Load normalizer. T7 remains compiled but permanently IDLE.

No renderer, input, layout, Continue, Load, wrapper, mainloop, audio, or
gamewrap behavior is changed.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime
import difflib
import hashlib
import os
import shutil
import sys

VX0 = {
    Path("src/MacSrc/Shock.c"):
        "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724",
    Path("src/GameSrc/setup.c"):
        "236b2517ad37b87e88e4232bca712aaf8910f51205e130f13d0069cfe2f4ba82",
    Path("src/GameSrc/mainloop.c"):
        "8fb3331b9e3e0fe1532417237d5adb8a8820508dc5f7e4f9d389870d31e9a369",
    Path("src/GameSrc/wrapper.c"):
        "d027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2",
    Path("src/GameSrc/gamewrap.c"):
        "c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30",
}

SETUP = Path("src/GameSrc/setup.c")
ACTIVE_CALL = "    citadel_3ds_arm_newgame_home_t7();\n"
REPLACEMENT = (
    "    /* PROJECT CITADEL VX1-NATURAL: use the original New Game path. */\n"
)
MARKER = "PROJECT CITADEL VX1-NATURAL: use the original New Game path."


def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def main() -> int:
    if not Path("src/GameSrc").is_dir() or not Path("src/MacSrc").is_dir():
        print("ERROR: Run this from the Shockolate repository root.")
        return 1

    print("============================================================")
    print("PROJECT CITADEL VX1-NATURAL")
    print("============================================================")
    print()
    print("Verifying exact VX0 base...")

    for path, expected in VX0.items():
        if not path.is_file():
            print(f"ERROR: Missing {path}. Nothing changed.")
            return 1

        actual = sha256(path)
        status = "OK" if actual == expected else "WRONG"
        print(f"{status:5} {actual}  {path}")

        if actual != expected:
            print()
            print("ERROR: Active tree is not exact VX0. Nothing changed.")
            return 1

    original = SETUP.read_text(encoding="utf-8")

    count = original.count(ACTIVE_CALL)
    if count != 1:
        print()
        print(
            "ERROR: Expected exactly one active T7 arming call in setup.c; "
            f"found {count}. Nothing changed."
        )
        return 1

    if MARKER in original:
        print("ERROR: VX1-NATURAL is already installed. Nothing changed.")
        return 1

    patched = original.replace(ACTIVE_CALL, REPLACEMENT, 1)

    if ACTIVE_CALL in patched:
        print("ERROR: Active T7 arming call remains. Nothing changed.")
        return 1

    if patched.count(MARKER) != 1:
        print("ERROR: VX1 marker verification failed. Nothing changed.")
        return 1

    backup_root = Path("BEFORE_VX1_NATURAL")
    backup = backup_root / SETUP
    backup.parent.mkdir(parents=True, exist_ok=True)

    if backup.exists():
        if sha256(backup) != VX0[SETUP]:
            print(
                f"ERROR: Existing backup is not exact VX0: {backup}\n"
                "Nothing changed."
            )
            return 1
    else:
        shutil.copy2(SETUP, backup)

    diff = "".join(
        difflib.unified_diff(
            original.splitlines(keepends=True),
            patched.splitlines(keepends=True),
            fromfile="src/GameSrc/setup.c (VX0)",
            tofile="src/GameSrc/setup.c (VX1-NATURAL)",
        )
    )

    temporary = SETUP.with_name(SETUP.name + ".VX1_NATURAL_TEMP")
    temporary.write_text(patched, encoding="utf-8")

    if ACTIVE_CALL in temporary.read_text(encoding="utf-8"):
        temporary.unlink(missing_ok=True)
        print("ERROR: Temporary verification failed. Nothing changed.")
        return 1

    os.replace(temporary, SETUP)

    new_hash = sha256(SETUP)

    Path("VX1_NATURAL_NEWGAME.diff").write_text(diff, encoding="utf-8")
    Path("VX1_NATURAL_INSTALLED.txt").write_text(
        "PROJECT CITADEL VX1-NATURAL\n"
        "Only the active T7 arming call was removed from setup.c.\n"
        "New Game now follows the original path.\n"
        f"Installed: {datetime.now().isoformat(timespec='seconds')}\n"
        f"VX0 setup SHA256: {VX0[SETUP]}\n"
        f"VX1 setup SHA256: {new_hash}\n",
        encoding="utf-8",
    )

    print()
    print("===== FINAL VERIFICATION =====")

    failed = False
    for path, expected in VX0.items():
        actual = sha256(path)

        if path == SETUP:
            status = "CHANGED" if actual == new_hash else "WRONG"
        else:
            status = "OK" if actual == expected else "WRONG"

        print(f"{status:7} {actual}  {path}")

        if path != SETUP and actual != expected:
            failed = True

    if failed:
        print()
        print("ERROR: A file other than setup.c changed.")
        return 1

    print()
    print("============================================================")
    print("VX1-NATURAL INSTALLED")
    print("ONLY ACTIVE CHANGE:")
    print("  automatic T7 Save/Load arming removed from setup.c")
    print(f"VX0 BACKUP: {backup}")
    print("DIFF: VX1_NATURAL_NEWGAME.diff")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
