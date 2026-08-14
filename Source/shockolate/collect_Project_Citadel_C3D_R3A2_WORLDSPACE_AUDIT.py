#!/usr/bin/env python3
"""
PROJECT CITADEL C3D R3A2 WORLDSPACE AUDIT

Read-only collector for the post-R3A native tree.

Default source:
  C:/Projects/Citadel_Citro3D_NATIVE_DEV/Source/shockolate

Creates:
  C:/Projects/CITADEL_C3D_R3A2_WORLDSPACE_AUDIT_<timestamp>.zip

The archive contains only source/build metadata and optional diagnostic logs.
It does not collect original System Shock game data.
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

R3A_MARKERS = (
    "PROJECT CITADEL C3D R3A WORLDPROOF1",
    "CITADEL-C3D-R3A-WORLDPROOF1",
)

FILES = (
    "CMakeLists.txt",
    "C3D_R3A_WORLDPROOF1_BUILD.log",

    "src/MacSrc/Shock.c",
    "src/MacSrc/Shock.h",
    "src/MacSrc/Citro3DNative.c",
    "src/MacSrc/Citro3DNative.h",
    "src/MacSrc/citadel_directquad_vshader.v.pica",
    "src/MacSrc/OpenGL.cc",
    "src/MacSrc/OpenGL.h",

    "src/GameSrc/frsetup.c",
    "src/GameSrc/frmain.c",
    "src/GameSrc/frpipe.c",
    "src/GameSrc/frpts.c",
    "src/GameSrc/frterr.c",
    "src/GameSrc/frclip.c",
    "src/GameSrc/frcamera.c",
    "src/GameSrc/frcompil.c",
    "src/GameSrc/FrUtils.c",

    "src/GameSrc/Headers/fr3d.h",
    "src/GameSrc/Headers/frintern.h",
    "src/GameSrc/Headers/frtypes.h",
    "src/GameSrc/Headers/frflags.h",
    "src/GameSrc/Headers/frparams.h",
    "src/GameSrc/Headers/frprotox.h",
    "src/GameSrc/Headers/frterr.h",
    "src/GameSrc/Headers/frpts.h",
    "src/GameSrc/Headers/frclip.h",
    "src/GameSrc/Headers/frpipe.h",
    "src/GameSrc/Headers/map.h",

    "src/Libraries/3D/Source/3d.h",
    "src/Libraries/3D/Source/3dinterp.h",
    "src/Libraries/3D/Source/GlobalV.c",
    "src/Libraries/3D/Source/GlobalV.h",
    "src/Libraries/3D/Source/points.c",
    "src/Libraries/3D/Source/matrix.c",
    "src/Libraries/3D/Source/clip.c",
    "src/Libraries/3D/Source/tmap.c",
    "src/Libraries/3D/Source/polygon.c",
    "src/Libraries/3D/Source/instance.c",
    "src/Libraries/3D/Source/fov.c",
)

PATTERNS = (
    "typedef struct g3s_point",
    "fix x, y, z",
    "fix sx, sy",
    "g3_transform_point",
    "g3_rotate_point",
    "g3_transform_list",
    "g3_rotate_list",
    "g3_set_view_angles",
    "g3_set_view_matrix",
    "g3_start_frame",
    "_view_position",
    "_view_matrix",
    "_unscaled_matrix",
    "_matrix_scale",
    "_view_zoom",
    "viewer_position",
    "viewer_orientation",
    "system_matrix",
    "fr_camera_last",
    "fr_pipe_go_3",
    "fr_draw_tile",
    "g3_draw_tmap",
    "g3_light_tmap",
    "g3_draw_floor_map",
    "g3_draw_wall_map",
    "g3_light_floor_map",
    "g3_light_wall_map",
    "citadel_native_world_capture",
    "citadel_native_world_begin_view",
    "C3D_FVUnifMtx4x4",
    "Mtx_Persp",
    "Mtx_PerspTilt",
    "C3D_DepthTest",
)

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")

def copy_file(root: Path, source: Path, target_root: Path) -> dict:
    if source.is_relative_to(root):
        relative = source.relative_to(root)
    else:
        relative = Path("evidence") / source.name

    destination = target_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

    return {
        "path": relative.as_posix(),
        "size": source.stat().st_size,
        "sha256": sha256(source),
        "original": str(source),
    }

def make_search_report(root: Path, paths: list[Path], output: Path) -> None:
    compiled = [(term, re.compile(re.escape(term))) for term in PATTERNS]
    lines = [
        "PROJECT CITADEL C3D R3A2 WORLDSPACE SEARCH REPORT",
        "=" * 78,
        "",
    ]

    for term, regex in compiled:
        matches = []
        for path in paths:
            if not path.is_file():
                continue
            try:
                source_lines = read_text(path).splitlines()
            except OSError:
                continue
            for number, line in enumerate(source_lines, 1):
                if regex.search(line):
                    matches.append(
                        (
                            path.relative_to(root).as_posix(),
                            number,
                            line.strip(),
                        )
                    )

        lines.append(f"[{term}] matches={len(matches)}")
        lines.append("-" * 78)
        for filename, number, line in matches[:120]:
            lines.append(f"{filename}:{number}: {line}")
        if len(matches) > 120:
            lines.append(f"... {len(matches) - 120} more omitted ...")
        lines.append("")

    output.write_text("\n".join(lines), encoding="utf-8")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output-parent", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--worldproof-log", type=Path)
    parser.add_argument("--gpu-log", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    output_parent = args.output_parent.resolve()

    print("=" * 72)
    print("PROJECT CITADEL C3D R3A2 WORLDSPACE AUDIT")
    print("=" * 72)
    print(f"Root: {root}")

    if not root.is_dir():
        print(f"ERROR: Source tree not found: {root}")
        return 2

    shock = root / "src/MacSrc/Shock.c"
    native = root / "src/MacSrc/Citro3DNative.c"

    if not shock.is_file() or not native.is_file():
        print("ERROR: Post-R3A source files are missing.")
        return 3

    combined = read_text(shock) + "\n" + read_text(native)
    marker = next((value for value in R3A_MARKERS if value in combined), None)
    if marker is None:
        print("ERROR: Current source does not prove R3A WORLDPROOF1.")
        return 4

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    name = f"CITADEL_C3D_R3A2_WORLDSPACE_AUDIT_{stamp}"
    folder = output_parent / name
    archive = output_parent / f"{name}.zip"

    if folder.exists() or archive.exists():
        print("ERROR: Refusing to overwrite existing output.")
        return 5

    folder.mkdir(parents=True)
    selected = [root / value for value in FILES if (root / value).is_file()]

    manifest_files = []
    for path in selected:
        manifest_files.append(copy_file(root, path, folder / "source"))

    for optional in (args.worldproof_log, args.gpu_log):
        if optional is not None:
            path = optional.resolve()
            if not path.is_file():
                print(f"ERROR: Optional evidence file not found: {path}")
                return 6
            manifest_files.append(copy_file(root, path, folder))

    reports = folder / "reports"
    reports.mkdir(parents=True)
    make_search_report(root, selected, reports / "WORLDSPACE_SEARCH_RESULTS.txt")

    key_context = [
        "PROJECT CITADEL C3D R3A2 WORLDSPACE AUDIT",
        "=" * 78,
        "",
        "Confirmed engine fact:",
        "- g3s_point stores rotated/view-space x, y, z as fixed-point values.",
        "- sx and sy are separate projected screen coordinates.",
        "- R3A used sx/sy; R3A2 should use x/y/z.",
        "",
        "Target:",
        "- Feed g3s_point x/y/z into a dedicated Citro3D world shader.",
        "- Preserve Shock world traversal and clipping.",
        "- Exclude HUD/bitmap/screen-space geometry from the native stream.",
        "- Enable perspective and depth testing.",
        "",
        f"Verified marker: {marker}",
        f"Shock.c SHA-256: {sha256(shock)}",
        f"Citro3DNative.c SHA-256: {sha256(native)}",
    ]
    (reports / "R3A2_TARGET_NOTES.txt").write_text(
        "\n".join(key_context) + "\n", encoding="utf-8"
    )

    manifest = {
        "project": "Project Citadel 3D",
        "target": "CITADEL-C3D-R3A2-WORLDSPACE-SOLIDROOM1",
        "source_root": str(root),
        "created": dt.datetime.now().isoformat(timespec="seconds"),
        "verified_marker": marker,
        "read_only": True,
        "game_assets_collected": False,
        "files": manifest_files,
    }
    (folder / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as zip_file:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(folder).as_posix())

    print("")
    print("SUCCESS: R3A2 world-space audit created.")
    print(f"ZIP: {archive}")
    print(f"SHA-256: {sha256(archive)}")
    print(f"Collected source files: {len(selected)}")
    print("")
    print("Upload the ZIP and the R3A hardware log if not included.")
    print("=" * 72)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
