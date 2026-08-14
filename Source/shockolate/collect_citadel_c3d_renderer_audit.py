#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path

ROOT = Path.cwd()
AUDIT = ROOT / "CITADEL_C3D_R0_AUDIT"
SHOCK = ROOT / "src/MacSrc/Shock.c"

KEYWORDS = [
    "citadel_gpu_present",
    "citadel_gpu_draw_region",
    "citadel_gpu_build_linear_frame",
    "citadel_gpu_swizzle",
    "citadel_gpu_init",
    "citadel_gpu_shutdown",
    "C2D_SceneBegin",
    "C2D_DrawImageAt",
    "C2D_DrawRectSolid",
    "C2D_Flush",
    "C2D_Init",
    "C2D_Fini",
    "C3D_FrameBegin",
    "C3D_FrameDrawOn",
    "C3D_FrameEnd",
    "C3D_RenderTarget",
    "C3D_TexInit",
    "C3D_TexUpload",
    "C3D_TexBind",
    "C3D_BufInfo",
    "C3D_AttrInfo",
    "shaderProgram",
    "DVLB_ParseFile",
    "GSPGPU_FlushDataCache",
    "GX_DisplayTransfer",
    "SDL_Surface",
    "SDL_LockSurface",
    "SDL_UnlockSurface",
    "SDL_Flip",
    "SDL_UpdateRect",
    "SDL_UpdateWindowSurface",
    "osGet3DSliderState",
]

FUNCTIONS = [
    "citadel_gpu_present",
    "citadel_gpu_draw_region",
    "citadel_gpu_build_linear_frame",
    "citadel_gpu_swizzle",
    "citadel_gpu_init",
    "citadel_gpu_shutdown",
    "I_FinishUpdate",
]

EXTS = {".c", ".cc", ".cpp", ".h", ".hh", ".hpp"}
SKIP = {".git", "CITADEL_C3D_R0_AUDIT"}


def fail(msg: str) -> None:
    raise SystemExit(f"ERROR: {msg}")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def source_files():
    for p in ROOT.rglob("*"):
        if not p.is_file() or p.suffix.lower() not in EXTS:
            continue
        if any(part in SKIP or part.startswith("build") for part in p.parts):
            continue
        yield p


def function_block(lines: list[str], name: str):
    pattern = re.compile(rf"\b{re.escape(name)}\s*\(")
    for i, line in enumerate(lines):
        if not pattern.search(line):
            continue
        stop = min(len(lines), i + 12)
        opening = None
        saw_semicolon = False
        for j in range(i, stop):
            if ";" in lines[j] and opening is None:
                saw_semicolon = True
            if "{" in lines[j]:
                opening = j
                break
        if opening is None or saw_semicolon:
            continue

        depth = 0
        started = False
        for j in range(opening, len(lines)):
            for ch in lines[j]:
                if ch == "{":
                    depth += 1
                    started = True
                elif ch == "}":
                    depth -= 1
                    if started and depth == 0:
                        return i + 1, j + 1
        return i + 1, min(len(lines), opening + 250)
    return None


def main() -> None:
    print("PROJECT CITADEL CITRO3D R0 RENDERER AUDIT")

    if not SHOCK.is_file():
        fail(
            "src/MacSrc/Shock.c was not found. Run this from "
            "C:/Projects/Citadel_Citro3D_DEV/Source/shockolate"
        )

    if AUDIT.exists():
        shutil.rmtree(AUDIT)
    AUDIT.mkdir(parents=True)

    shock_text = SHOCK.read_text(encoding="utf-8-sig", errors="replace")
    if "1.0.1-DIAG2-FPS-SPLIT" not in shock_text:
        print("WARNING: DIAG2 marker not found in Shock.c.")

    copied_shock = AUDIT / "Shock.c"
    shutil.copy2(SHOCK, copied_shock)

    report = [
        "PROJECT CITADEL CITRO3D R0 RENDERER AUDIT",
        "=" * 72,
        f"Root: {ROOT}",
        f"Shock.c SHA-256: {digest(SHOCK)}",
        "",
        "Target milestone: CITADEL-C3D-R0-DIRECTQUAD1",
        "Goal: replace only the Citro2D presentation layer with direct Citro3D.",
        "",
        "=" * 72,
        "MATCHES BY FILE",
        "=" * 72,
    ]

    matched_files = []
    scanned = 0
    match_count = 0

    for path in sorted(source_files()):
        scanned += 1
        lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
        hits = []

        for number, line in enumerate(lines, 1):
            for keyword in KEYWORDS:
                if keyword in line:
                    hits.append((number, keyword))
                    break

        if not hits:
            continue

        rel = path.relative_to(ROOT)
        matched_files.append(str(rel))
        report.extend(["", f"FILE: {rel}", "-" * 72])

        for number, keyword in hits:
            match_count += 1
            start = max(1, number - 5)
            end = min(len(lines), number + 5)
            report.append(f"[{keyword}] line {number}")
            for current in range(start, end + 1):
                marker = ">>" if current == number else "  "
                report.append(f"{marker} {current:6d}: {lines[current - 1]}")
            report.append("")

    shock_lines = shock_text.splitlines()
    report.extend(["", "=" * 72, "FUNCTION BODIES", "=" * 72])
    functions_found = 0

    for name in FUNCTIONS:
        block = function_block(shock_lines, name)
        if block is None:
            continue
        functions_found += 1
        start, end = block
        report.extend(["", f"FUNCTION: {name}", f"LINES: {start}-{end}", "-" * 72])
        for number in range(start, end + 1):
            report.append(f"{number:6d}: {shock_lines[number - 1]}")

    report.extend([
        "",
        "=" * 72,
        "SUMMARY",
        "=" * 72,
        f"Source files scanned: {scanned}",
        f"Files containing matches: {len(matched_files)}",
        f"Total keyword matches: {match_count}",
        f"Function bodies extracted: {functions_found}",
        "",
        "FIRST PATCH SCOPE",
        "  Preserve the software world renderer and current frame texture.",
        "  Replace C2D scene/image drawing with direct Citro3D triangles.",
        "  Keep an immediate fallback to the proven v1.0.1 path.",
    ])

    report_path = AUDIT / "CITADEL_C3D_RENDER_AUDIT.txt"
    matched_path = AUDIT / "CITADEL_C3D_MATCHED_FILES.txt"
    sums_path = AUDIT / "SHA256SUMS.txt"

    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")
    matched_path.write_text("\n".join(matched_files) + ("\n" if matched_files else ""), encoding="utf-8")
    sums_path.write_text(
        f"{digest(report_path)}  {report_path.name}\n"
        f"{digest(matched_path)}  {matched_path.name}\n"
        f"{digest(copied_shock)}  {copied_shock.name}\n",
        encoding="utf-8",
    )

    print(f"Audit folder: {AUDIT}")
    print(f"Files scanned: {scanned}")
    print(f"Matched files: {len(matched_files)}")
    print(f"Keyword matches: {match_count}")
    print(f"Function bodies extracted: {functions_found}")
    print("No source files were modified.")


if __name__ == "__main__":
    main()
