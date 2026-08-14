#!/usr/bin/env python3

from datetime import datetime
from pathlib import Path
import shutil

build = Path("build")

if not build.is_dir():
    raise SystemExit("ERROR: build directory not found.")

generated_names = {
    "compiler_depend.make",
    "compiler_depend.ts",
    "compiler_depend.internal",
    "depend.make",
}

files = [
    path for path in build.rglob("*")
    if path.is_file() and path.name in generated_names
]

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = Path(f"BACKUP_CMAKE_DEPENDENCIES_{stamp}")

if not files:
    print("No generated dependency files were found.")
    raise SystemExit(0)

for source in files:
    relative = source.relative_to(build)
    destination = backup / relative

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source.unlink()

    print(f"Removed generated file: {source}")

print()
print(f"Backups saved in: {backup}")
print(f"Removed {len(files)} generated dependency files.")
print("Source files and compiled object files were not touched.")
