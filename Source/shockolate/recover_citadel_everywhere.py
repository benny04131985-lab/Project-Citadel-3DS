#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import hashlib
import os
import shutil
import zipfile

DEST = Path("/c/Projects/Citadel-Recovery-PROBFUCKED")

ROOTS = [
    Path("/c/Projects"),
    Path("/c/Users/benny/Desktop"),
    Path("/c/Users/benny/Documents"),
    Path("/c/Users/benny/Downloads"),
    Path("/c/$Recycle.Bin"),
]

MARKERS = [
    b"PROJECT CITADEL",
    b"V16.1 LAUNCH POLISH",
    b"V21A PRIMER",
    b"V21E LIVE GAME PRIMER",
    b"SELF-LOAD TEST 2",
    b"NEWGAME_HOME_T2",
    b"NEWGAME_HOME_T7",
    b"HOME FRAME-GATE TEST 4",
    b"SAVE KEYBOARD V2",
    b"KEYBOARD V3",
    b"unique mainloop",
    b"citadel_3ds_newgame_home",
    b"ngboot.dat",
]

ARCHIVE_SUFFIXES = {
    ".zip", ".7z", ".rar", ".tar", ".gz", ".bz2", ".xz"
}

SKIP_DIRS = {
    ".git",
    "node_modules",
    "citadel-recovery-probfucked",
}

MAX_CONTENT_SCAN = 64 * 1024 * 1024
CHUNK_SIZE = 8 * 1024 * 1024

report_lines = []
copied_count = 0
zip_member_count = 0
errors = []


def safe_component(value: str) -> str:
    return (
        value.replace(":", "_")
        .replace("\\", "/")
        .strip("/")
        .replace("../", "__/")
    )


def file_hash(path: Path) -> str:
    hasher = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            hasher.update(chunk)

    return hasher.hexdigest()


def bytes_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def candidate_name(name: str) -> bool:
    lower = name.replace("\\", "/").lower()
    base = lower.rsplit("/", 1)[-1]

    source_prefixes = (
        "shock",
        "setup",
        "mainloop",
        "wrapper",
        "gamewrap",
    )

    if base.endswith((".c", ".h", ".o")):
        if base.startswith(source_prefixes):
            return True

    if base in {
        "libgame_lib.a",
        "systemshock.elf",
        "systemshock.3dsx",
        "project_citadel_3dsx.elf",
        "project_citadel_3dsx.3dsx",
    }:
        return True

    if base.endswith((".elf", ".3dsx", ".a")):
        if "citadel" in base or "systemshock" in base:
            return True

    if base.endswith((".log", ".txt")):
        if any(token in base for token in (
            "mainloop",
            "newgame",
            "home",
            "gpu",
            "boot",
            "direct_setup",
            "audio",
            "input",
        )):
            return True

    if base.endswith(tuple(ARCHIVE_SUFFIXES)):
        if any(token in base for token in (
            "citadel",
            "shock",
            "v16",
            "v17",
            "v21",
            "home",
            "t2",
            "t7",
            "backup",
            "archive",
        )):
            return True

    return False


def read_for_markers(path: Path) -> tuple[list[str], bytes]:
    try:
        size = path.stat().st_size

        with path.open("rb") as handle:
            if size <= MAX_CONTENT_SCAN:
                data = handle.read()
            else:
                start = handle.read(CHUNK_SIZE)
                handle.seek(max(0, size - CHUNK_SIZE))
                end = handle.read(CHUNK_SIZE)
                data = start + end

    except OSError:
        return [], b""

    lowered = data.lower()

    hits = [
        marker.decode("ascii", errors="replace")
        for marker in MARKERS
        if marker.lower() in lowered
    ]

    return hits, data


def destination_for_file(source: Path) -> Path:
    source_string = safe_component(str(source))
    return DEST / "LIVE_AND_RECYCLE_FILES" / source_string


def copy_candidate(source: Path, reason: str, markers: list[str]) -> None:
    global copied_count

    destination = destination_for_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)

    try:
        shutil.copy2(source, destination)
        digest = file_hash(source)
    except OSError as exc:
        errors.append(f"COPY ERROR: {source}: {exc}")
        return

    copied_count += 1

    report_lines.extend([
        "============================================================",
        f"TYPE: FILE",
        f"SOURCE: {source}",
        f"COPY:   {destination}",
        f"REASON: {reason}",
        f"SIZE:   {source.stat().st_size}",
        f"SHA256: {digest}",
        f"MARKERS: {', '.join(markers) if markers else '(none found)'}",
        "",
    ])


def inspect_zip(archive: Path) -> None:
    global zip_member_count

    archive_destination = (
        DEST
        / "FROM_ZIP_ARCHIVES"
        / safe_component(str(archive))
    )

    try:
        with zipfile.ZipFile(archive, "r") as zipped:
            for info in zipped.infolist():
                if info.is_dir():
                    continue

                member_name = info.filename

                if info.file_size > MAX_CONTENT_SCAN:
                    marker_hits = []
                    data = b""
                else:
                    try:
                        data = zipped.read(info)
                    except Exception as exc:
                        errors.append(
                            f"ZIP READ ERROR: {archive}::{member_name}: {exc}"
                        )
                        continue

                    lowered = data.lower()
                    marker_hits = [
                        marker.decode("ascii", errors="replace")
                        for marker in MARKERS
                        if marker.lower() in lowered
                    ]

                name_match = candidate_name(member_name)

                if not name_match and not marker_hits:
                    continue

                destination = archive_destination / safe_component(member_name)
                destination.parent.mkdir(parents=True, exist_ok=True)

                try:
                    destination.write_bytes(data)
                except OSError as exc:
                    errors.append(
                        f"ZIP WRITE ERROR: {archive}::{member_name}: {exc}"
                    )
                    continue

                zip_member_count += 1

                report_lines.extend([
                    "============================================================",
                    "TYPE: ZIP MEMBER",
                    f"ARCHIVE: {archive}",
                    f"MEMBER:  {member_name}",
                    f"COPY:    {destination}",
                    f"SIZE:    {len(data)}",
                    f"SHA256:  {bytes_hash(data)}",
                    f"MARKERS: {', '.join(marker_hits) if marker_hits else '(none found)'}",
                    "",
                ])

    except (OSError, zipfile.BadZipFile, PermissionError) as exc:
        errors.append(f"ZIP ERROR: {archive}: {exc}")


DEST.mkdir(parents=True, exist_ok=True)

seen_paths = set()
archive_inventory = []

for root in ROOTS:
    if not root.exists():
        report_lines.append(f"MISSING ROOT: {root}")
        continue

    print(f"Scanning: {root}")

    for directory, subdirs, filenames in os.walk(root):
        directory_path = Path(directory)

        subdirs[:] = [
            name for name in subdirs
            if name.lower() not in SKIP_DIRS
            and (directory_path / name) != DEST
        ]

        for filename in filenames:
            path = directory_path / filename

            try:
                resolved = path.resolve()
            except OSError:
                resolved = path

            if resolved in seen_paths:
                continue

            seen_paths.add(resolved)

            suffix = path.suffix.lower()

            if suffix in ARCHIVE_SUFFIXES:
                archive_inventory.append(path)

                if suffix == ".zip":
                    inspect_zip(path)

                # Preserve likely relevant archive containers too.
                if candidate_name(path.name):
                    markers, _ = read_for_markers(path)
                    copy_candidate(path, "relevant archive filename", markers)

                continue

            name_match = candidate_name(path.name)
            marker_hits, _ = read_for_markers(path)

            if name_match or marker_hits:
                reasons = []

                if name_match:
                    reasons.append("relevant filename")

                if marker_hits:
                    reasons.append("embedded Citadel marker")

                copy_candidate(
                    path,
                    " + ".join(reasons),
                    marker_hits,
                )

report_lines.extend([
    "============================================================",
    "ARCHIVE INVENTORY",
    "",
])

for archive in archive_inventory:
    suffix = archive.suffix.lower()

    if suffix == ".zip":
        status = "ZIP inspected automatically"
    else:
        status = "NOT extracted automatically"

    report_lines.append(f"{status}: {archive}")

report_lines.extend([
    "",
    "============================================================",
    "SUMMARY",
    f"Files copied: {copied_count}",
    f"ZIP members extracted: {zip_member_count}",
    f"Errors: {len(errors)}",
    "",
])

if errors:
    report_lines.append("ERRORS:")
    report_lines.extend(errors)

report = DEST / "RECOVERY_REPORT.txt"
report.write_text("\n".join(report_lines), encoding="utf-8")

print()
print("============================================================")
print("FORENSIC RECOVERY SCAN COMPLETE")
print(f"Destination: {DEST}")
print(f"Files copied: {copied_count}")
print(f"ZIP members extracted: {zip_member_count}")
print(f"Report: {report}")
print("============================================================")
