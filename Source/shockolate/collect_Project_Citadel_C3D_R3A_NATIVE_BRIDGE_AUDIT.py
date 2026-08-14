#!/usr/bin/env python3
"""
Read-only source collector for Project Citadel's first native Citro3D milestone.

Default source:
  C:/Projects/Citadel_Citro3D_NATIVE_DEV/Source/shockolate

Creates:
  C:/Projects/CITADEL_C3D_R3A_NATIVE_BRIDGE_AUDIT_<timestamp>/
  C:/Projects/CITADEL_C3D_R3A_NATIVE_BRIDGE_AUDIT_<timestamp>.zip

It does not modify the source tree and does not collect game assets.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path

DEFAULT_ROOT = Path("/c/Projects/Citadel_Citro3D_NATIVE_DEV/Source/shockolate")
DEFAULT_OUTPUT = Path("/c/Projects")

R2C_MARKERS = (
    "PROJECT CITADEL C3D R2C PINGPONGTILED1 ACTIVE",
    "CITADEL-C3D-R2C-PINGPONGTILED1",
)

REQUIRED = (
    "CMakeLists.txt",
    "src/MacSrc/Shock.c",
    "src/MacSrc/OpenGL.cc",
    "src/MacSrc/OpenGL.h",
    "src/Libraries/3D/Source/polygon.c",
    "src/Libraries/3D/Source/tmap.c",
    "src/Libraries/3D/Source/Bitmap.c",
    "src/GameSrc/frmain.c",
    "src/GameSrc/frpipe.c",
)

WANTED = (
    "CMakeLists.txt",
    "src/CMakeLists.txt",
    "src/MacSrc/CMakeLists.txt",
    "src/GameSrc/CMakeLists.txt",
    "src/Libraries/CMakeLists.txt",

    "src/MacSrc/Shock.c",
    "src/MacSrc/Shock.h",
    "src/MacSrc/OpenGL.cc",
    "src/MacSrc/OpenGL.h",

    "src/GameSrc/render.c",
    "src/GameSrc/gamerend.c",
    "src/GameSrc/rendtool.c",
    "src/GameSrc/frmain.c",
    "src/GameSrc/frpipe.c",
    "src/GameSrc/frpts.c",
    "src/GameSrc/frclip.c",
    "src/GameSrc/frterr.c",
    "src/GameSrc/frobj.c",
    "src/GameSrc/frcamera.c",
    "src/GameSrc/frsetup.c",
    "src/GameSrc/frcompil.c",
    "src/GameSrc/FrUtils.c",

    "src/Libraries/3D/Source/3d.h",
    "src/Libraries/3D/Source/3dinterp.h",
    "src/Libraries/3D/Source/GlobalV.c",
    "src/Libraries/3D/Source/GlobalV.h",
    "src/Libraries/3D/Source/polygon.c",
    "src/Libraries/3D/Source/tmap.c",
    "src/Libraries/3D/Source/Bitmap.c",
    "src/Libraries/3D/Source/points.c",
    "src/Libraries/3D/Source/clip.c",
    "src/Libraries/3D/Source/matrix.c",
    "src/Libraries/3D/Source/instance.c",
    "src/Libraries/3D/Source/light.c",
    "src/Libraries/3D/Source/fov.c",

    "src/GameSrc/Headers/frintern.h",
    "src/GameSrc/Headers/frtypes.h",
    "src/GameSrc/Headers/frparams.h",
    "src/GameSrc/Headers/frflags.h",
    "src/GameSrc/Headers/frprotox.h",
    "src/GameSrc/Headers/fr3d.h",
    "src/GameSrc/Headers/frterr.h",
    "src/GameSrc/Headers/frpts.h",
    "src/GameSrc/Headers/frclip.h",
    "src/GameSrc/Headers/frpipe.h",
    "src/GameSrc/Headers/render.h",
    "src/GameSrc/Headers/gamerend.h",
    "src/GameSrc/Headers/map.h",
)

PATTERNS = (
    "USE_OPENGL",
    "ENABLE_OPENGL",
    "OpenGL.cc",
    "OpenGL.h",
    "init_opengl",
    "can_use_opengl",
    "use_opengl",
    "should_opengl_swap",
    "opengl_start_frame",
    "opengl_end_frame",
    "opengl_set_viewport",
    "opengl_draw_tmap",
    "opengl_light_tmap",
    "opengl_draw_poly",
    "opengl_bitmap",
    "opengl_cache_wall_texture",
    "g3_draw_tmap",
    "g3_light_tmap",
    "g3_draw_floor_map",
    "g3_light_floor_map",
    "g3_draw_wall_map",
    "g3_light_wall_map",
    "g3_draw_poly",
    "draw_poly_common",
    "draw_tmap_common",
    "g3_bitmap_common",
    "g3s_point",
    "g3s_phandle",
    "grs_bitmap",
    "fr_rend",
    "fr_pipe_go_3",
    "fr_draw_tile",
    "fr_rend_start",
    "C3D_FrameBegin",
    "C3D_RenderTarget",
    "C3D_Tex",
    "citadel_gpu_present",
    "PINGPONGTILED1",
)

TEXT_EXTS = {
    ".c", ".cc", ".cpp", ".cxx", ".h", ".hh", ".hpp",
    ".txt", ".md", ".cmake", ".pica", ".vert", ".frag", ".vsh", ".fsh",
}

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()

def skip(path: Path, root: Path) -> bool:
    parts = path.relative_to(root).parts
    return any(
        p == ".git" or p == "__pycache__" or p.startswith("build-")
        for p in parts
    )

def source_files(root: Path) -> list[Path]:
    found: set[Path] = set()
    for base in (root, root / "src"):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or skip(path, root):
                continue
            if path.name == "CMakeLists.txt" or path.suffix.lower() in TEXT_EXTS:
                found.add(path)
    return sorted(found)

def selected_files(root: Path) -> list[Path]:
    found: set[Path] = set()
    for item in WANTED:
        path = root / item
        if path.is_file():
            found.add(path)

    for base_name in ("shaders", "src/MacSrc"):
        base = root / base_name
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or skip(path, root):
                continue
            name = path.name.lower()
            if (
                path.suffix.lower() in {".pica", ".vert", ".frag", ".vsh", ".fsh"}
                or "opengl" in name
                or "citro" in name
                or "shader" in name
            ):
                found.add(path)
    return sorted(found)

def search(root: Path, files: list[Path]) -> dict[str, list[dict]]:
    result = {pattern: [] for pattern in PATTERNS}
    regexes = {pattern: re.compile(re.escape(pattern)) for pattern in PATTERNS}
    for path in files:
        try:
            lines = read_text(path).splitlines()
        except OSError:
            continue
        rel = relative(root, path)
        for number, line in enumerate(lines, 1):
            for pattern, regex in regexes.items():
                if regex.search(line):
                    result[pattern].append(
                        {"file": rel, "line": number, "text": line.strip()[:500]}
                    )
    return result

def copy_files(root: Path, files: list[Path], destination: Path) -> None:
    for source in files:
        target = destination / relative(root, source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)

def write_search_report(matches: dict[str, list[dict]], destination: Path) -> None:
    output = [
        "PROJECT CITADEL C3D R3A NATIVE BRIDGE SEARCH RESULTS",
        "=" * 78,
        "",
    ]
    for pattern in PATTERNS:
        entries = matches[pattern]
        output.append(f"[{pattern}] matches={len(entries)}")
        output.append("-" * 78)
        for item in entries[:100]:
            output.append(f"{item['file']}:{item['line']}: {item['text']}")
        if len(entries) > 100:
            output.append(f"... {len(entries) - 100} additional matches omitted ...")
        output.append("")
    destination.write_text("\n".join(output), encoding="utf-8")

def write_context_report(
    root: Path, matches: dict[str, list[dict]], destination: Path
) -> None:
    priority = (
        "init_opengl",
        "use_opengl",
        "opengl_start_frame",
        "opengl_set_viewport",
        "opengl_draw_tmap",
        "opengl_draw_poly",
        "opengl_bitmap",
        "draw_poly_common",
        "draw_tmap_common",
        "g3_bitmap_common",
        "fr_rend",
        "fr_pipe_go_3",
        "C3D_FrameBegin",
        "citadel_gpu_present",
    )
    output = [
        "PROJECT CITADEL C3D R3A NATIVE BRIDGE KEY CONTEXT",
        "=" * 78,
        "",
    ]
    emitted: set[tuple[str, int]] = set()
    for pattern in priority:
        output.extend((f"## {pattern}", ""))
        for item in matches[pattern][:30]:
            key = (item["file"], item["line"])
            if key in emitted:
                continue
            emitted.add(key)
            path = root / item["file"]
            lines = read_text(path).splitlines()
            start = max(1, item["line"] - 5)
            end = min(len(lines), item["line"] + 5)
            output.append(f"FILE: {item['file']}")
            for number in range(start, end + 1):
                marker = ">>" if number == item["line"] else "  "
                output.append(f"{marker} {number:6d}: {lines[number - 1]}")
            output.append("")
    destination.write_text("\n".join(output), encoding="utf-8")

def write_build_report(root: Path, files: list[Path], destination: Path) -> None:
    needles = (
        "ENABLE_OPENGL", "USE_OPENGL", "OpenGL.cc", "citro3d",
        "citro2d", "picasso", "shader", "C3D",
    )
    output = [
        "PROJECT CITADEL C3D R3A BUILD INTEGRATION",
        "=" * 78,
        "",
    ]
    found = False
    for path in files:
        if path.name != "CMakeLists.txt" and path.suffix.lower() != ".cmake":
            continue
        hits = []
        for number, line in enumerate(read_text(path).splitlines(), 1):
            if any(term.lower() in line.lower() for term in needles):
                hits.append((number, line))
        if hits:
            found = True
            output.extend((f"FILE: {relative(root, path)}", "-" * 78))
            output.extend(f"{number:6d}: {line}" for number, line in hits)
            output.append("")
    if not found:
        output.append("No relevant CMake lines found.")
    destination.write_text("\n".join(output), encoding="utf-8")

def zip_folder(folder: Path, archive: Path) -> None:
    with zipfile.ZipFile(
        archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zf:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-parent", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    root = args.root.resolve()
    output_parent = args.output_parent.resolve()

    print("=" * 72)
    print("PROJECT CITADEL C3D R3A NATIVE BRIDGE AUDIT")
    print("=" * 72)
    print(f"Root: {root}")

    if not root.is_dir():
        print(f"ERROR: Native source tree does not exist: {root}")
        return 2

    missing = [item for item in REQUIRED if not (root / item).is_file()]
    if missing:
        print("ERROR: Required bridge files are missing:")
        for item in missing:
            print(f"  - {item}")
        return 3

    shock = root / "src/MacSrc/Shock.c"
    marker = next((m for m in R2C_MARKERS if m in read_text(shock)), None)
    if marker is None:
        print("ERROR: Native tree does not prove the frozen R2C baseline.")
        return 4

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"CITADEL_C3D_R3A_NATIVE_BRIDGE_AUDIT_{stamp}"
    folder = output_parent / name
    archive = output_parent / f"{name}.zip"

    if folder.exists() or archive.exists():
        print("ERROR: Refusing to overwrite an existing audit.")
        return 5

    all_files = source_files(root)
    chosen = selected_files(root)
    matches = search(root, all_files)

    source_out = folder / "source"
    reports = folder / "reports"
    reports.mkdir(parents=True)
    copy_files(root, chosen, source_out)

    write_search_report(matches, reports / "NATIVE_BRIDGE_SEARCH_RESULTS.txt")
    write_context_report(root, matches, reports / "NATIVE_BRIDGE_KEY_CONTEXT.txt")
    write_build_report(root, chosen, reports / "BUILD_INTEGRATION.txt")

    collected = ["path\tsize\tsha256"]
    manifest_files = []
    for path in chosen:
        item = {
            "path": relative(root, path),
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        manifest_files.append(item)
        collected.append(f"{item['path']}\t{item['size']}\t{item['sha256']}")
    (reports / "COLLECTED_FILES.tsv").write_text(
        "\n".join(collected) + "\n", encoding="utf-8"
    )

    manifest = {
        "project": "Project Citadel 3D",
        "target": "CITADEL-C3D-R3A-WORLDPROOF1",
        "audit": "NATIVE_BRIDGE_AUDIT1",
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "source_root": str(root),
        "verified_r2c_marker": marker,
        "shock_c_sha256": sha256(shock),
        "selected_file_count": len(chosen),
        "searched_text_file_count": len(all_files),
        "match_counts": {key: len(value) for key, value in matches.items()},
        "read_only": True,
        "game_assets_collected": False,
        "files": manifest_files,
    }
    (folder / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )

    (folder / "README.txt").write_text(
        f"""PROJECT CITADEL C3D R3A NATIVE BRIDGE AUDIT
==========================================

Target:
  CITADEL-C3D-R3A-WORLDPROOF1

Verified frozen baseline:
  {marker}

This read-only package contains the exact local OpenGL backend, 3D primitive
dispatch, world traversal, renderer headers, build rules, shaders, line-numbered
search results, and hashes needed to implement the first Citro3D-native world
proof.

No original System Shock game assets are included.
""",
        encoding="utf-8",
    )

    zip_folder(folder, archive)

    print("")
    print("SUCCESS: Native bridge audit created.")
    print(f"Folder: {folder}")
    print(f"ZIP:    {archive}")
    print(f"ZIP SHA-256: {sha256(archive)}")
    print(f"Collected files: {len(chosen)}")
    print(f"Searched files:  {len(all_files)}")
    print("")
    print("Upload the ZIP for R3A-WORLDPROOF1 patch generation.")
    print("=" * 72)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
