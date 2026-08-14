#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import hashlib
import os
import shutil
import sys

EXPECTED = {
    "Shock": {
        "hash": "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724",
        "patterns": ("Shock*.c",),
        "target": Path("src/MacSrc/Shock.c"),
    },
    "setup": {
        "hash": "236b2517ad37b87e88e4232bca712aaf8910f51205e130f13d0069cfe2f4ba82",
        "patterns": ("setup*.c",),
        "target": Path("src/GameSrc/setup.c"),
    },
    "wrapper": {
        "hash": "d027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2",
        "patterns": ("wrapper*.c",),
        "target": Path("src/GameSrc/wrapper.c"),
    },
    "gamewrap": {
        "hash": "c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30",
        "patterns": ("gamewrap*.c",),
        "target": Path("src/GameSrc/gamewrap.c"),
    },
}

MAINLOOP_TARGET = Path("src/GameSrc/mainloop.c")
MAINLOOP_HASH = (
    "ec06102cfb003e3ccd49f53012af199086bc865c39f47e69fbea69a4c556ff1f"
)

ROOTS = [
    Path("."),
    Path("/c/Projects/Citadel-Recovery-PROBFUCKED"),
    Path("/c/Users/benny/Desktop"),
    Path("/c/Users/benny/Downloads"),
]

SKIP_PARTS = {
    "build",
    ".git",
    "__pycache__",
}

def sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            block = handle.read(1024 * 1024)
            if not block:
                break
            digest.update(block)

    return digest.hexdigest()


def should_skip(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    return bool(lowered & SKIP_PARTS)


def preference(path: Path) -> tuple:
    text = str(path).replace("\\", "/").lower()

    # Prefer clearly preserved local recovery copies.
    if "before_exact_v17_recovery" in text:
        rank = 0
    elif "from_zip_archives" in text:
        rank = 1
    elif "citadel-recovery-probfucked" in text:
        rank = 2
    elif "/c/projects/citadel-ship-16-1/" in text:
        rank = 3
    elif "/desktop/" in text:
        rank = 4
    elif "/downloads/" in text:
        rank = 5
    else:
        rank = 6

    return rank, len(text), text


def find_matches(patterns: tuple[str, ...], expected_hash: str) -> list[Path]:
    matches = []
    seen = set()

    for root in ROOTS:
        if not root.exists():
            continue

        for pattern in patterns:
            try:
                candidates = root.rglob(pattern)
            except OSError:
                continue

            for path in candidates:
                try:
                    if not path.is_file() or should_skip(path):
                        continue

                    resolved = path.resolve()

                    if resolved in seen:
                        continue

                    seen.add(resolved)

                    if sha256(path) == expected_hash:
                        matches.append(path)

                except (OSError, PermissionError):
                    continue

    return sorted(matches, key=preference)


print("============================================================")
print("PROJECT CITADEL — MATCHED V21E SET INSTALLER")
print("============================================================")

if not MAINLOOP_TARGET.is_file():
    sys.exit(f"ERROR: Missing active mainloop: {MAINLOOP_TARGET}")

active_mainloop_hash = sha256(MAINLOOP_TARGET)

print()
print("V21E MAINLOOP")
print(f"PATH:   {MAINLOOP_TARGET}")
print(f"SHA256: {active_mainloop_hash}")

if active_mainloop_hash != MAINLOOP_HASH:
    sys.exit(
        "\nERROR: Active mainloop is not the recovered V21E source. "
        "Nothing was changed."
    )

selected = {}

for label, info in EXPECTED.items():
    print()
    print(f"Searching for exact {label}...")

    matches = find_matches(info["patterns"], info["hash"])

    if not matches:
        sys.exit(
            f"\nERROR: No exact {label} match found for:\n"
            f"{info['hash']}\n"
            "Nothing was changed."
        )

    selected[label] = matches[0]

    print(f"MATCHES FOUND: {len(matches)}")
    print(f"SELECTED:      {matches[0]}")

print()
print("All four exact companion files were located.")
print("No files have been changed yet.")

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = Path(f"BEFORE_MATCHED_V21E_INSTALL_{timestamp}")
backup.mkdir(parents=True, exist_ok=False)

active_files = {
    "Shock": Path("src/MacSrc/Shock.c"),
    "setup": Path("src/GameSrc/setup.c"),
    "mainloop": MAINLOOP_TARGET,
    "wrapper": Path("src/GameSrc/wrapper.c"),
    "gamewrap": Path("src/GameSrc/gamewrap.c"),
}

print()
print(f"Backing up active state to: {backup}")

for label, source in active_files.items():
    if not source.is_file():
        sys.exit(
            f"\nERROR: Active file disappeared before backup: {source}"
        )

    destination = backup / source
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

manifest = backup / "ACTIVE_SHA256SUMS.txt"

with manifest.open("w", encoding="utf-8") as handle:
    for label, path in active_files.items():
        handle.write(f"{sha256(path)}  {path}\n")

print()
print("Installing exact companion files...")

for label, source in selected.items():
    target = EXPECTED[label]["target"]
    temporary = target.with_name(target.name + ".V21E_INSTALL_TEMP")

    shutil.copy2(source, temporary)

    copied_hash = sha256(temporary)

    if copied_hash != EXPECTED[label]["hash"]:
        temporary.unlink(missing_ok=True)
        sys.exit(
            f"\nERROR: Temporary copy verification failed for {label}. "
            "Active target was not replaced."
        )

    os.replace(temporary, target)
    print(f"{label:8} <- {source}")

print()
print("============================================================")
print("FINAL VERIFICATION")
print("============================================================")

final_expected = {
    Path("src/MacSrc/Shock.c"): EXPECTED["Shock"]["hash"],
    Path("src/GameSrc/setup.c"): EXPECTED["setup"]["hash"],
    MAINLOOP_TARGET: MAINLOOP_HASH,
    Path("src/GameSrc/wrapper.c"): EXPECTED["wrapper"]["hash"],
    Path("src/GameSrc/gamewrap.c"): EXPECTED["gamewrap"]["hash"],
}

failed = False

for path, expected_hash in final_expected.items():
    actual_hash = sha256(path)
    status = "OK" if actual_hash == expected_hash else "WRONG"

    print(f"{status:5} {actual_hash}  {path}")

    if actual_hash != expected_hash:
        failed = True

if failed:
    sys.exit(
        "\nERROR: Final verification failed. "
        f"The previous state is preserved in {backup}"
    )

install_manifest = Path("MATCHED_V21E_INSTALLED_SHA256SUMS.txt")

with install_manifest.open("w", encoding="utf-8") as handle:
    for path in final_expected:
        handle.write(f"{sha256(path)}  {path}\n")

print()
print("============================================================")
print("MATCHED V21E FIVE-FILE SET INSTALLED")
print(f"BACKUP:   {backup}")
print(f"MANIFEST: {install_manifest}")
print("============================================================")
