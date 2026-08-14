#!/usr/bin/env python3

from pathlib import Path
import hashlib
import os

targets = {
    "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724":
        "Shock V17",
    "236b2517ad37b87e88e4232bca712aaf8910f51205e130f13d0069cfe2f4ba82":
        "setup T7",
    "8fb3331b9e3e0fe1532417237d5adb8a8820508dc5f7e4f9d389870d31e9a369":
        "mainloop T7",
    "d027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2":
        "wrapper T7",
}

roots = [
    Path("/c/Projects"),
    Path("/c/Users/benny/Desktop"),
]

matches = {digest: [] for digest in targets}

for root in roots:
    if not root.exists():
        continue

    for directory, subdirs, filenames in os.walk(root):
        subdirs[:] = [
            name for name in subdirs
            if name.lower() not in {
                "build", ".git", "cmakefiles",
                "ftp_deploy", "node_modules"
            }
        ]

        for filename in filenames:
            if not filename.lower().endswith(".c"):
                continue

            path = Path(directory) / filename

            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except (OSError, PermissionError):
                continue

            if digest in targets:
                matches[digest].append(path)

print()
print("===== EXACT T7/V17 FILE SEARCH =====")

for digest, label in targets.items():
    print()
    print(f"{label}")
    print(f"SHA256: {digest}")

    if matches[digest]:
        for path in matches[digest]:
            print(f"  MATCH: {path}")
    else:
        print("  NOT FOUND LOCALLY")
