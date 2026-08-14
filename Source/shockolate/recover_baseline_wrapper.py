#!/usr/bin/env python3

from pathlib import Path
import hashlib
import os
import shutil
import sys

roots = [
    Path("."),
    Path("/c/Projects"),
    Path("/c/Users/benny/Desktop"),
]

required = "PROJECT CITADEL SAVE KEYBOARD V2"

forbidden = (
    "NEWGAME_HOME_T5",
    "NEWGAME_HOME_T6",
    "NEWGAME_HOME_T7",
    "NEWGAME_HOME_T7P",
    "HOME NORMALIZER T6",
    "PROJECT CITADEL T7",
    "T7P",
    "V17-SHIP",
    "V18-SHIP",
    "V20-SHIP",
)

matches = []
seen = set()

for root in roots:
    if not root.exists():
        continue

    for directory, subdirs, filenames in os.walk(root):
        subdirs[:] = [
            name for name in subdirs
            if name.lower() not in {
                "build", ".git", "cmakefiles", "node_modules"
            }
        ]

        for filename in filenames:
            if not filename.lower().endswith(".c"):
                continue

            if "wrapper" not in filename.lower():
                continue

            path = Path(directory) / filename

            try:
                data = path.read_bytes()
                text = data.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                continue

            digest = hashlib.sha256(data).hexdigest()

            if digest in seen:
                continue

            if required not in text:
                continue

            if any(token in text for token in forbidden):
                continue

            seen.add(digest)
            matches.append((path, digest))

print("===== VALID SAVE KEYBOARD V2 WRAPPERS =====")

for path, digest in matches:
    print()
    print(f"SHA256: {digest}")
    print(f"PATH:   {path}")

if not matches:
    raise SystemExit(
        "\nERROR: No uncontaminated Save Keyboard V2 wrapper was found locally."
    )

unique_hashes = {digest for _, digest in matches}

if len(unique_hashes) != 1:
    raise SystemExit(
        "\nERROR: Multiple different valid-looking wrapper versions were found. "
        "Nothing was copied."
    )

source = matches[0][0]
destination = Path("wrapper_BASELINE_RECOVERED.c")

shutil.copy2(source, destination)

print()
print("============================================================")
print("BASELINE WRAPPER RECOVERED")
print(f"FROM:   {source}")
print(f"TO:     {destination}")
print(f"SHA256: {matches[0][1]}")
print("============================================================")
