#!/usr/bin/env python3

from pathlib import Path
import hashlib
import shutil
import sys


ROOT = Path.cwd().resolve()
EXPECTED_ROOT = Path("/c/Projects/Citadel_3D_DEV/Source/shockolate")

# MSYS Python may present C: paths differently, so verify by structure too.
if ROOT.name != "shockolate" or ROOT.parent.name != "Source":
    print(f"ERROR: Run this from the shockolate source root.\nCurrent: {ROOT}")
    sys.exit(1)

shock_file = ROOT / "src" / "MacSrc" / "Shock.c"
cmake_file = ROOT / "CMakeLists.txt"

for required in (shock_file, cmake_file):
    if not required.is_file():
        print(f"ERROR: Missing required file: {required}")
        sys.exit(1)

# This is outside Source/shockolate so ordinary source cleanup cannot erase it.
protected = ROOT.parent.parent / "_PROTECTED_BASELINES" / "S0A_PRE_3D_WALL"

if protected.exists():
    print(f"ERROR: Protected baseline already exists:\n{protected}")
    print("Nothing was changed.")
    sys.exit(1)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


shock_replacements = [
    (
        '"sdmc:/3ds/SystemShock/Hack-i-Ben_Splash.t3x"',
        '"sdmc:/3ds/SystemShock3D/Hack-i-Ben_Splash.t3x"',
        1,
    ),
    (
        '"sdmc:/3ds/systemshock/Hack-i-Ben_Splash.t3x"',
        '"sdmc:/3ds/SystemShock3D/Hack-i-Ben_Splash.t3x"',
        1,
    ),
    (
        '"sdmc:/3ds/systemshock/V15H_CONTROL.t3x"',
        '"sdmc:/3ds/SystemShock3D/V15H_CONTROL.t3x"',
        1,
    ),
    (
        '"sdmc:/3ds/SystemShock/V15H_CONTROL.t3x"',
        '"sdmc:/3ds/SystemShock3D/V15H_CONTROL.t3x"',
        1,
    ),
    (
        'chdir("sdmc:/3ds/SystemShock");',
        'chdir("sdmc:/3ds/SystemShock3D");',
        1,
    ),
]

cmake_replacements = [
    (
        "remain external in sdmc:/3ds/SystemShock/.",
        "remain external in sdmc:/3ds/SystemShock3D/.",
        1,
    ),
    (
        '"${CMAKE_BINARY_DIR}/Project_Citadel_3DS.smdh"',
        '"${CMAKE_BINARY_DIR}/3D_Citadel_3DS.smdh"',
        1,
    ),
    (
        '"${CMAKE_BINARY_DIR}/Project_Citadel_3DS.bnr"',
        '"${CMAKE_BINARY_DIR}/3D_Citadel_3DS.bnr"',
        1,
    ),
    (
        '"${CMAKE_BINARY_DIR}/Project_Citadel_3DS.3dsx"',
        '"${CMAKE_BINARY_DIR}/3D_Citadel_3DS.3dsx"',
        1,
    ),
    (
        '"${CMAKE_BINARY_DIR}/Project_Citadel_3DS.cia"',
        '"${CMAKE_BINARY_DIR}/3D_Citadel_3DS.cia"',
        1,
    ),
    (
        '-s "Project Citadel 3DS"',
        '-s "Citadel 3D Stereo"',
        1,
    ),
]


def prepare_change(path: Path, replacements):
    original = path.read_text(encoding="utf-8")
    changed = original

    for old, new, expected_count in replacements:
        actual_count = changed.count(old)

        if actual_count != expected_count:
            print(f"ERROR: Unexpected source state in {path}")
            print(f"Expected {expected_count} occurrence(s), found {actual_count}:")
            print(old)
            sys.exit(1)

        changed = changed.replace(old, new)

    if changed == original:
        print(f"ERROR: No changes prepared for {path}")
        sys.exit(1)

    return original, changed


print("===== S0A CITADEL 3D WALL =====")
print(f"Project root: {ROOT}")
print(f"Protected baseline: {protected}")

shock_original, shock_changed = prepare_change(
    shock_file, shock_replacements
)
cmake_original, cmake_changed = prepare_change(
    cmake_file, cmake_replacements
)

# All assertions succeeded. Only now create backups and write changes.
protected.mkdir(parents=True, exist_ok=False)

shutil.copy2(shock_file, protected / "Shock.c")
shutil.copy2(cmake_file, protected / "CMakeLists.txt")

manifest = protected / "SHA256_BEFORE.txt"
manifest.write_text(
    f"{sha256(protected / 'Shock.c')}  Shock.c\n"
    f"{sha256(protected / 'CMakeLists.txt')}  CMakeLists.txt\n",
    encoding="utf-8",
)

shock_file.write_text(shock_changed, encoding="utf-8", newline="")
cmake_file.write_text(cmake_changed, encoding="utf-8", newline="")

# Hard post-write verification of the active build inputs.
forbidden = (
    "sdmc:/3ds/SystemShock/",
    "sdmc:/3ds/systemshock/",
    'chdir("sdmc:/3ds/SystemShock")',
    'chdir("sdmc:/3ds/systemshock")',
)

active_text = (
    shock_file.read_text(encoding="utf-8")
    + "\n"
    + cmake_file.read_text(encoding="utf-8")
)

remaining = [value for value in forbidden if value in active_text]

if remaining:
    print("ERROR: Forbidden mono path survived in an active build file:")
    for item in remaining:
        print(f"  {item}")
    print("Restore from the protected baseline before proceeding.")
    sys.exit(1)

required_new = (
    "sdmc:/3ds/SystemShock3D/",
    'chdir("sdmc:/3ds/SystemShock3D")',
    "3D_Citadel_3DS.3dsx",
)

missing = [value for value in required_new if value not in active_text]

if missing:
    print("ERROR: Required stereo identity was not established:")
    for item in missing:
        print(f"  {item}")
    sys.exit(1)

print()
print("PASS: Protected baseline created.")
print("PASS: Active runtime paths now use only SystemShock3D.")
print("PASS: Generated 3DS output is now 3D_Citadel_3DS.3dsx.")
print()
print("Modified:")
print(f"  {shock_file}")
print(f"  {cmake_file}")
print()
print("S0A COMPLETE")