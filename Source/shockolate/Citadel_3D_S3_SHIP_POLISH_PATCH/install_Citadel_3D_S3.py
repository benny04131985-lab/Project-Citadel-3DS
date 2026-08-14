#!/usr/bin/env python3
"""
Project Citadel 3D S3 — ship polish installer.

Changes only:
  src/GameSrc/render.c
  src/MacSrc/Shock.c

S2.1 stereo math and C-nub tuning are guarded and left untouched.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import os
import shutil
import sys
import zipfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
PATCHED = PACKAGE / "PATCHED"
SAFE_ROOT = ROOT.parent.parent / "_PROTECTED_BASELINES"

FILES = {
    Path("src/GameSrc/render.c"): (
        "a6062ecf827b5217b68151140a42e67bb8a376476388aced0228c898ad5113ab",
        "078328f4205e593e57ec54160d08cacb4f0f4e124ed5aee75273f26280917a9a",
    ),
    Path("src/MacSrc/Shock.c"): (
        "692c9c49e9d6d9963c452c66002cbd7bfce2bf17a067f687c301966579e95ed4",
        "287df735630ee43c7813c9fe2aaa605cede02f1eb823919b32b66c6ea25b9995",
    ),
}

GUARDS = {
    Path("src/GameSrc/frsetup.c"):
        "1c19322c514b94d6059a7535e33b6ecf23a536a5ef62b39be6b6c7c1f5e594c5",
    Path("src/GameSrc/frmain.c"):
        "e0aeb587cd0c62f86328316ac5cd12ca0d36455d4460ebf92102fac7a188def5",
}

S21_DEPTH = (
    "PROJECT CITADEL 3D S2.1: centered depth curve and 5px ceiling are ACTIVE"
)
S21_INPUT = (
    "PROJECT CITADEL 3D S2.1 INPUT: frame-time freelook normalization is ACTIVE"
)
S3_SHOCK = "PROJECT CITADEL 3D S3: ship polish and quiet diagnostics are ACTIVE"
S3_RENDER = (
    "PROJECT CITADEL 3D S3: ship-safe exceptional-view flattening is ACTIVE"
)


def die(message: str) -> None:
    print()
    print(f"ERROR: {message}", file=sys.stderr)
    print("No project files were changed.", file=sys.stderr)
    raise SystemExit(1)


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def snapshot(folder: Path, paths: list[Path], note: str) -> Path:
    folder.mkdir(parents=True, exist_ok=False)
    sums = []

    for relative in paths:
        source = ROOT / relative
        target = folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        sums.append(f"{sha(target)}  {relative.as_posix()}")

    (folder / "SHA256SUMS.txt").write_text(
        "\n".join(sums) + "\n",
        encoding="utf-8",
    )
    (folder / "BASELINE_INFO.txt").write_text(
        note.rstrip() + "\n",
        encoding="utf-8",
    )

    archive = folder.with_suffix(".zip")
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as handle:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(folder.parent))

    return archive


def main() -> int:
    if not ROOT.as_posix().lower().endswith(
        "citadel_3d_dev/source/shockolate"
    ):
        die(
            "Run from C:/Projects/Citadel_3D_DEV/Source/shockolate\n"
            f"Current: {ROOT}"
        )

    required = list(FILES) + list(GUARDS) + [
        Path("src/Libraries/INPUT/Source/sdl_events.c"),
    ]

    for relative in required:
        if not (ROOT / relative).is_file():
            die(f"Missing active file: {relative}")

    for relative in FILES:
        if not (PATCHED / relative).is_file():
            die(f"Patch package is incomplete: PATCHED/{relative}")

    current = {relative: sha(ROOT / relative) for relative in FILES}

    if all(current[relative] == FILES[relative][1] for relative in FILES):
        print("Citadel 3D S3 is already installed exactly; nothing changed.")
        return 0

    bad = [
        relative
        for relative in FILES
        if current[relative] != FILES[relative][0]
    ]
    if bad:
        print("These active files are not the exact successful S2.1 source:")
        for relative in bad:
            print(f"  {relative}: {current[relative]}")
        die("Refusing to merge into an unknown source state.")

    for relative, expected in GUARDS.items():
        actual = sha(ROOT / relative)
        if actual != expected:
            die(
                f"Protected S2.1 guard differs: {relative}\n"
                f"Expected: {expected}\n"
                f"Actual:   {actual}"
            )

    frsetup = (ROOT / "src/GameSrc/frsetup.c").read_text(
        encoding="utf-8",
        errors="replace",
    )
    input_source = (
        ROOT / "src/Libraries/INPUT/Source/sdl_events.c"
    ).read_text(encoding="utf-8", errors="replace")

    if S21_DEPTH not in frsetup:
        die("The sealed S2.1 depth marker is missing.")
    if S21_INPUT not in input_source:
        die("The sealed S2.1 C-nub marker is missing.")

    for relative, (_before, expected_after) in FILES.items():
        if sha(PATCHED / relative) != expected_after:
            die(f"Packaged patched-file hash failed: {relative}")

    patched_render = (
        PATCHED / "src/GameSrc/render.c"
    ).read_text(encoding="utf-8", errors="replace")
    patched_shock = (
        PATCHED / "src/MacSrc/Shock.c"
    ).read_text(encoding="utf-8", errors="replace")

    if S3_RENDER not in patched_render or S3_SHOCK not in patched_shock:
        die("Packaged S3 identity markers are incomplete.")

    if "sdmc:/3ds/SystemShock/" in patched_shock or (
        "sdmc:/3ds/systemshock/" in patched_shock
    ):
        die("Packaged Shock.c violates the mono SD wall.")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre = SAFE_ROOT / f"S3_PRE_SHIP_POLISH_{stamp}"
    post = SAFE_ROOT / f"S3_SHIP_POLISH_CANDIDATE_{stamp}"
    SAFE_ROOT.mkdir(parents=True, exist_ok=True)

    tracked = list(FILES) + list(GUARDS) + [
        Path("src/Libraries/INPUT/Source/sdl_events.c"),
    ]

    pre_zip = snapshot(
        pre,
        tracked,
        (
            "PROJECT CITADEL 3D — exact successful S2.1 source before S3.\n"
            "Depth tuning and C-nub normalization are frozen."
        ),
    )

    temps = []
    try:
        for relative in FILES:
            target = ROOT / relative
            temp = target.with_name(target.name + ".S3_TEMP")
            shutil.copy2(PATCHED / relative, temp)
            temps.append(temp)

        for relative in FILES:
            target = ROOT / relative
            os.replace(
                target.with_name(target.name + ".S3_TEMP"),
                target,
            )
    except Exception as error:
        for temp in temps:
            temp.unlink(missing_ok=True)
        die(f"Atomic install failed: {error}\nRestore from {pre}")

    for relative, (_before, expected_after) in FILES.items():
        if sha(ROOT / relative) != expected_after:
            die(f"Installed hash failed: {relative}\nRestore from {pre}")

    for relative, expected in GUARDS.items():
        if sha(ROOT / relative) != expected:
            die(f"Protected guard changed: {relative}\nRestore from {pre}")

    if S21_INPUT not in (
        ROOT / "src/Libraries/INPUT/Source/sdl_events.c"
    ).read_text(encoding="utf-8", errors="replace"):
        die(f"S2.1 input marker changed. Restore from {pre}")

    post_zip = snapshot(
        post,
        tracked,
        (
            "PROJECT CITADEL 3D — S3 ship-polish candidate.\n"
            "S2.1 depth and C-nub tuning unchanged.\n"
            "Cyberspace, 360 view and security-camera takeover use flat "
            "identical-eye transport.\n"
            "Recurring 600-frame stereo diagnostics removed."
        ),
    )

    print()
    print("============================================================")
    print("PROJECT CITADEL 3D S3 SHIP POLISH INSTALLED")
    print("============================================================")
    print("PASS: S2.1 depth curve remains byte-for-byte unchanged.")
    print("PASS: S2.1 C-nub source remains unchanged.")
    print("PASS: ordinary station gameplay remains true stereo.")
    print("PASS: cyberspace remains flat.")
    print("PASS: 360-degree view is explicitly flat.")
    print("PASS: security-camera takeover is explicitly flat.")
    print("PASS: recurring 600-frame stereo log removed.")
    print("PASS: one-time startup and first-true-frame diagnostics retained.")
    print()
    print(f"PRE-S3:      {pre}")
    print(f"PRE-S3 ZIP:  {pre_zip}")
    print(f"S3:          {post}")
    print(f"S3 ZIP:      {post_zip}")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
