#!/usr/bin/env python3
"""
Project Citadel 3D — S1 identical-eye transport

Starting point:
  C:/Projects/Citadel_3D_DEV/Source/shockolate

Purpose:
  Enable the physical stereoscopic top LCD, create a matching RGBA8
  GFX_RIGHT render target, and submit the exact existing top-screen image
  to both eyes. This creates zero parallax: it proves dual-eye transport
  without altering the System Shock world camera, HUD, bottom screen,
  gameplay, audio, APT/HOME hooks, or layout logic.

Only src/MacSrc/Shock.c is modified.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import difflib
import hashlib
import os
import shutil
import sys
import zipfile


ROOT = Path.cwd().resolve()
PROJECT_ROOT = ROOT.parent.parent
SAFE_ROOT = PROJECT_ROOT / "_PROTECTED_BASELINES"

SHOCK = Path("src/MacSrc/Shock.c")
SETUP = Path("src/GameSrc/setup.c")
MAINLOOP = Path("src/GameSrc/mainloop.c")
WRAPPER = Path("src/GameSrc/wrapper.c")
GAMEWRAP = Path("src/GameSrc/gamewrap.c")
SDLSOUND = Path("src/MacSrc/SDLSound.c")
CMAKE = Path("CMakeLists.txt")

SNAPSHOT_FILES = [
    SHOCK,
    SETUP,
    MAINLOOP,
    WRAPPER,
    GAMEWRAP,
    SDLSOUND,
    CMAKE,
]

MARKER = (
    "PROJECT CITADEL 3D S1: zero-parallax dual-eye transport is ACTIVE"
)


def fail(message: str) -> None:
    print()
    print(f"ERROR: {message}", file=sys.stderr)
    print("Nothing was installed.", file=sys.stderr)
    raise SystemExit(1)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_source(path: Path) -> tuple[bytes, str, str]:
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        fail(f"{path} is not valid UTF-8: {error}")

    newline = "\r\n" if "\r\n" in text else "\n"
    normalized = text.replace("\r\n", "\n")
    return raw, normalized, newline


def encode_source(text: str, newline: str) -> bytes:
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def replace_once(
    text: str,
    old: str,
    new: str,
    label: str,
) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly one anchor, found {count}.")
    return text.replace(old, new, 1)


def get_section(
    text: str,
    start: str,
    end: str,
    label: str,
) -> tuple[int, int, str]:
    start_i = text.find(start)
    if start_i < 0:
        fail(f"{label}: start anchor not found.")

    end_i = text.find(end, start_i + len(start))
    if end_i < 0:
        fail(f"{label}: end anchor not found.")

    if text.find(start, start_i + len(start)) >= 0:
        fail(f"{label}: start anchor is not unique.")

    return start_i, end_i, text[start_i:end_i]


def replace_in_section(
    text: str,
    start: str,
    end: str,
    old: str,
    new: str,
    label: str,
) -> str:
    start_i, end_i, section = get_section(text, start, end, label)
    count = section.count(old)
    if count != 1:
        fail(f"{label}: expected one section anchor, found {count}.")
    section = section.replace(old, new, 1)
    return text[:start_i] + section + text[end_i:]


def copy_snapshot(
    destination: Path,
    file_bytes: dict[Path, bytes],
    description: str,
) -> None:
    destination.mkdir(parents=True, exist_ok=False)

    for relative, data in file_bytes.items():
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)

    manifest_lines = [
        f"{sha256_bytes(data)}  {relative.as_posix()}"
        for relative, data in sorted(
            file_bytes.items(),
            key=lambda item: item[0].as_posix(),
        )
    ]
    (destination / "SHA256SUMS.txt").write_text(
        "\n".join(manifest_lines) + "\n",
        encoding="utf-8",
    )
    (destination / "BASELINE_INFO.txt").write_text(
        description.rstrip() + "\n",
        encoding="utf-8",
    )


def zip_snapshot(directory: Path) -> Path:
    archive = directory.with_suffix(".zip")
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as handle:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(directory.parent))
    return archive


def patch_shock(text: str) -> str:
    warning_anchor = (
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"\n'
    )
    text = replace_once(
        text,
        warning_anchor,
        warning_anchor
        + '#warning "PROJECT CITADEL 3D S1: '
          'zero-parallax dual-eye transport is ACTIVE"\n',
        "S1 compile marker",
    )

    text = replace_once(
        text,
        "static C3D_RenderTarget *citadel_gpu_top_target = NULL;\n"
        "static C3D_RenderTarget *citadel_gpu_bottom_target = NULL;\n",
        "static C3D_RenderTarget *citadel_gpu_top_target = NULL;\n"
        "static C3D_RenderTarget *citadel_gpu_top_right_target = NULL;\n"
        "static C3D_RenderTarget *citadel_gpu_bottom_target = NULL;\n",
        "right-eye target declaration",
    )

    shutdown_start = "static void citadel_gpu_shutdown(void)\n{"
    shutdown_end = (
        "\n\n/*\n"
        " * PROJECT CITADEL V15I: SDL-compatible Citro2D screen target."
    )
    text = replace_in_section(
        text,
        shutdown_start,
        shutdown_end,
        "    if (citadel_gpu_top_target != NULL) {\n"
        "        C3D_RenderTargetDelete(citadel_gpu_top_target);\n"
        "        citadel_gpu_top_target = NULL;\n"
        "    }\n\n"
        "    if (citadel_gpu_bottom_target != NULL) {\n",
        "    if (citadel_gpu_top_target != NULL) {\n"
        "        C3D_RenderTargetDelete(citadel_gpu_top_target);\n"
        "        citadel_gpu_top_target = NULL;\n"
        "    }\n\n"
        "    if (citadel_gpu_top_right_target != NULL) {\n"
        "        C3D_RenderTargetDelete(citadel_gpu_top_right_target);\n"
        "        citadel_gpu_top_right_target = NULL;\n"
        "    }\n\n"
        "    /* Return the top LCD to ordinary mono mode at final shutdown. */\n"
        "    gfxSet3D(false);\n\n"
        "    if (citadel_gpu_bottom_target != NULL) {\n",
        "right-eye target shutdown",
    )

    init_start = "static bool citadel_gpu_initialize(void)\n{"
    init_end = (
        "\n\n/*\n"
        " * Native PICA texture ordering:"
    )
    text = replace_in_section(
        text,
        init_start,
        init_end,
        "    citadel_gpu_c2d_initialized = true;\n"
        "    C2D_Prepare();\n\n"
        "    v5_log(\"GPU V16.1 SCREEN FORMAT before-targets \"\n",
        "    citadel_gpu_c2d_initialized = true;\n"
        "    C2D_Prepare();\n\n"
        "    /* S1: enable the physical stereoscopic top LCD. */\n"
        "    gfxSet3D(true);\n\n"
        "    v5_log(\"GPU V16.1 SCREEN FORMAT before-targets \"\n",
        "stereo enable",
    )

    text = replace_in_section(
        text,
        init_start,
        init_end,
        "    citadel_gpu_top_target =\n"
        "        citadel_gpu_create_sdl_rgba8_screen_target(\n"
        "            GFX_TOP,\n"
        "            GFX_LEFT);\n"
        "    citadel_gpu_bottom_target =\n",
        "    citadel_gpu_top_target =\n"
        "        citadel_gpu_create_sdl_rgba8_screen_target(\n"
        "            GFX_TOP,\n"
        "            GFX_LEFT);\n"
        "    citadel_gpu_top_right_target =\n"
        "        citadel_gpu_create_sdl_rgba8_screen_target(\n"
        "            GFX_TOP,\n"
        "            GFX_RIGHT);\n"
        "    citadel_gpu_bottom_target =\n",
        "right-eye target creation",
    )

    text = replace_in_section(
        text,
        init_start,
        init_end,
        "    v5_log(\"GPU V16.1 TARGET OUTPUT transfer_in=RGBA8 \"\n"
        "           \"transfer_out=RGBA8 screen_framebuffer=SDL_RGBA8\");\n\n"
        "    if (citadel_gpu_top_target == NULL ||\n"
        "        citadel_gpu_bottom_target == NULL) {\n"
        "        v5_log(\"GPU INIT FAIL stage=screen-targets top=%p bottom=%p\",\n"
        "               (void *)citadel_gpu_top_target,\n"
        "               (void *)citadel_gpu_bottom_target);\n",
        "    v5_log(\"GPU V16.1 TARGET OUTPUT transfer_in=RGBA8 \"\n"
        "           \"transfer_out=RGBA8 screen_framebuffer=SDL_RGBA8\");\n"
        "    v5_log(\"GPU 3D S1 mode=IDENTICAL_EYES slider=%0.3f \"\n"
        "           \"left=%p right=%p bottom=%p\",\n"
        "           (double)osGet3DSliderState(),\n"
        "           (void *)citadel_gpu_top_target,\n"
        "           (void *)citadel_gpu_top_right_target,\n"
        "           (void *)citadel_gpu_bottom_target);\n\n"
        "    if (citadel_gpu_top_target == NULL ||\n"
        "        citadel_gpu_top_right_target == NULL ||\n"
        "        citadel_gpu_bottom_target == NULL) {\n"
        "        v5_log(\"GPU INIT FAIL stage=screen-targets \"\n"
        "               \"left=%p right=%p bottom=%p\",\n"
        "               (void *)citadel_gpu_top_target,\n"
        "               (void *)citadel_gpu_top_right_target,\n"
        "               (void *)citadel_gpu_bottom_target);\n",
        "right-eye target validation",
    )

    text = replace_in_section(
        text,
        init_start,
        init_end,
        "    v5_log(\"GPU INIT SUCCESS backend=Citro2D texture=%dx%d format=RGB565 \"\n"
        "           \"top=%p bottom=%p texture_data=%p staging=%p\",\n"
        "           CITADEL_GPU_TEXTURE_WIDTH,\n"
        "           CITADEL_GPU_TEXTURE_HEIGHT,\n"
        "           (void *)citadel_gpu_top_target,\n"
        "           (void *)citadel_gpu_bottom_target,\n",
        "    v5_log(\"GPU INIT SUCCESS backend=Citro2D texture=%dx%d format=RGB565 \"\n"
        "           \"left=%p right=%p bottom=%p texture_data=%p staging=%p\",\n"
        "           CITADEL_GPU_TEXTURE_WIDTH,\n"
        "           CITADEL_GPU_TEXTURE_HEIGHT,\n"
        "           (void *)citadel_gpu_top_target,\n"
        "           (void *)citadel_gpu_top_right_target,\n"
        "           (void *)citadel_gpu_bottom_target,\n",
        "right-eye success log",
    )

    splash_start = "static bool citadel_v16_present_splash(void)\n{"
    splash_end = (
        "\n\nstatic bool citadel_gpu_present("
        "SDL_Surface *surface, bool magenta)"
    )

    text = replace_in_section(
        text,
        splash_start,
        splash_end,
        "    bool draw_ok;\n\n"
        "    if (!citadel_gpu_ready ||\n"
        "        !citadel_v16_splash_ready ||\n"
        "        citadel_v16_splash_image.subtex == NULL ||\n"
        "        citadel_gpu_top_target == NULL ||\n"
        "        citadel_gpu_bottom_target == NULL)\n",
        "    bool draw_ok;\n"
        "    bool draw_right_ok;\n\n"
        "    if (!citadel_gpu_ready ||\n"
        "        !citadel_v16_splash_ready ||\n"
        "        citadel_v16_splash_image.subtex == NULL ||\n"
        "        citadel_gpu_top_target == NULL ||\n"
        "        citadel_gpu_top_right_target == NULL ||\n"
        "        citadel_gpu_bottom_target == NULL)\n",
        "splash right-eye guard",
    )

    text = replace_in_section(
        text,
        splash_start,
        splash_end,
        "    C2D_TargetClear(citadel_gpu_top_target,\n"
        "                    C2D_Color32(0, 0, 0, 255));\n"
        "    C2D_TargetClear(citadel_gpu_bottom_target,\n",
        "    C2D_TargetClear(citadel_gpu_top_target,\n"
        "                    C2D_Color32(0, 0, 0, 255));\n"
        "    C2D_TargetClear(citadel_gpu_top_right_target,\n"
        "                    C2D_Color32(0, 0, 0, 255));\n"
        "    C2D_TargetClear(citadel_gpu_bottom_target,\n",
        "splash right-eye clear",
    )

    text = replace_in_section(
        text,
        splash_start,
        splash_end,
        "    draw_ok =\n"
        "        C2D_DrawImageAt(citadel_v16_splash_image,\n"
        "                        0.0f,\n"
        "                        0.0f,\n"
        "                        0.0f,\n"
        "                        NULL,\n"
        "                        scale_x,\n"
        "                        scale_y);\n\n"
        "    /*\n"
        "     * Explicitly submit a black bottom-screen scene.",
        "    draw_ok =\n"
        "        C2D_DrawImageAt(citadel_v16_splash_image,\n"
        "                        0.0f,\n"
        "                        0.0f,\n"
        "                        0.0f,\n"
        "                        NULL,\n"
        "                        scale_x,\n"
        "                        scale_y);\n\n"
        "    C2D_SceneBegin(citadel_gpu_top_right_target);\n"
        "    draw_right_ok =\n"
        "        C2D_DrawImageAt(citadel_v16_splash_image,\n"
        "                        0.0f,\n"
        "                        0.0f,\n"
        "                        0.0f,\n"
        "                        NULL,\n"
        "                        scale_x,\n"
        "                        scale_y);\n\n"
        "    /*\n"
        "     * Explicitly submit a black bottom-screen scene.",
        "splash right-eye draw",
    )

    text = replace_in_section(
        text,
        splash_start,
        splash_end,
        "    if (!draw_ok)\n"
        "        ++citadel_gpu_draw_failures;\n\n"
        "    return draw_ok;\n",
        "    if (!draw_ok || !draw_right_ok)\n"
        "        ++citadel_gpu_draw_failures;\n\n"
        "    return draw_ok && draw_right_ok;\n",
        "splash result",
    )

    present_start = (
        "static bool citadel_gpu_present("
        "SDL_Surface *surface, bool magenta)\n{"
    )
    present_end = "\n\nstatic void citadel_clear_bottom_screen(void)"

    text = replace_in_section(
        text,
        present_start,
        present_end,
        "    bool split_layout;\n"
        "    bool top_ok = true;\n"
        "    bool bottom_ok = true;\n",
        "    bool split_layout;\n"
        "    bool top_ok = true;\n"
        "    bool right_ok = true;\n"
        "    bool bottom_ok = true;\n",
        "present right-eye result",
    )

    text = replace_in_section(
        text,
        present_start,
        present_end,
        "    if (!citadel_gpu_ready ||\n"
        "        citadel_gpu_top_target == NULL ||\n"
        "        citadel_gpu_bottom_target == NULL)\n",
        "    if (!citadel_gpu_ready ||\n"
        "        citadel_gpu_top_target == NULL ||\n"
        "        citadel_gpu_top_right_target == NULL ||\n"
        "        citadel_gpu_bottom_target == NULL)\n",
        "present right-eye guard",
    )

    text = replace_in_section(
        text,
        present_start,
        present_end,
        "        C2D_TargetClear(citadel_gpu_top_target,\n"
        "                        C2D_Color32(255, 0, 255, 255));\n"
        "        C2D_TargetClear(citadel_gpu_bottom_target,\n",
        "        C2D_TargetClear(citadel_gpu_top_target,\n"
        "                        C2D_Color32(255, 0, 255, 255));\n"
        "        C2D_TargetClear(citadel_gpu_top_right_target,\n"
        "                        C2D_Color32(255, 0, 255, 255));\n"
        "        C2D_TargetClear(citadel_gpu_bottom_target,\n",
        "magenta right-eye clear",
    )

    text = replace_in_section(
        text,
        present_start,
        present_end,
        "    C2D_TargetClear(citadel_gpu_top_target,\n"
        "                    C2D_Color32(0, 0, 0, 255));\n"
        "    C2D_TargetClear(citadel_gpu_bottom_target,\n",
        "    C2D_TargetClear(citadel_gpu_top_target,\n"
        "                    C2D_Color32(0, 0, 0, 255));\n"
        "    C2D_TargetClear(citadel_gpu_top_right_target,\n"
        "                    C2D_Color32(0, 0, 0, 255));\n"
        "    C2D_TargetClear(citadel_gpu_bottom_target,\n",
        "normal right-eye clear",
    )

    left_finish = (
        "        top_ok = citadel_gpu_draw_region(\n"
        "            top_source.x,\n"
        "            top_source.y,\n"
        "            top_source.w,\n"
        "            top_source.h,\n"
        "            (float)CITADEL_3DS_GAME_X,\n"
        "            (float)CITADEL_3DS_GAME_Y,\n"
        "            (float)CITADEL_3DS_GAME_WIDTH,\n"
        "            (float)CITADEL_3DS_GAME_HEIGHT,\n"
        "            0.0f);\n"
        "    }\n\n"
        "    if (split_layout) {\n"
    )

    right_block = (
        "        top_ok = citadel_gpu_draw_region(\n"
        "            top_source.x,\n"
        "            top_source.y,\n"
        "            top_source.w,\n"
        "            top_source.h,\n"
        "            (float)CITADEL_3DS_GAME_X,\n"
        "            (float)CITADEL_3DS_GAME_Y,\n"
        "            (float)CITADEL_3DS_GAME_WIDTH,\n"
        "            (float)CITADEL_3DS_GAME_HEIGHT,\n"
        "            0.0f);\n"
        "    }\n\n"
        "    /*\n"
        "     * S1 repeats the exact same source crop and destination geometry\n"
        "     * for GFX_RIGHT. Both eyes therefore remain at zero parallax.\n"
        "     */\n"
        "    C2D_SceneBegin(citadel_gpu_top_right_target);\n\n"
        "    if (split_layout) {\n"
        "        right_ok = citadel_gpu_draw_region(\n"
        "            top_source.x,\n"
        "            top_source.y,\n"
        "            top_source.w,\n"
        "            top_source.h,\n"
        "            0.0f,\n"
        "            0.0f,\n"
        "            (float)CITADEL_3DS_TOP_WIDTH,\n"
        "            (float)CITADEL_3DS_TOP_HEIGHT,\n"
        "            0.0f);\n"
        "    } else {\n"
        "        right_ok = citadel_gpu_draw_region(\n"
        "            top_source.x,\n"
        "            top_source.y,\n"
        "            top_source.w,\n"
        "            top_source.h,\n"
        "            (float)CITADEL_3DS_GAME_X,\n"
        "            (float)CITADEL_3DS_GAME_Y,\n"
        "            (float)CITADEL_3DS_GAME_WIDTH,\n"
        "            (float)CITADEL_3DS_GAME_HEIGHT,\n"
        "            0.0f);\n"
        "    }\n\n"
        "    if (split_layout) {\n"
    )

    text = replace_in_section(
        text,
        present_start,
        present_end,
        left_finish,
        right_block,
        "right-eye live-frame draw",
    )

    text = replace_in_section(
        text,
        present_start,
        present_end,
        "        v5_log(\"GPU FRAME frame=%u split=%d top_ok=%d bottom_ok=%d \"\n"
        "               \"surface=%dx%d\",\n"
        "               citadel_gpu_presented_frames,\n"
        "               split_layout ? 1 : 0,\n"
        "               top_ok ? 1 : 0,\n"
        "               bottom_ok ? 1 : 0,\n",
        "        v5_log(\"GPU 3D S1 FRAME frame=%u slider=%0.3f split=%d \"\n"
        "               \"left_ok=%d right_ok=%d bottom_ok=%d surface=%dx%d\",\n"
        "               citadel_gpu_presented_frames,\n"
        "               (double)osGet3DSliderState(),\n"
        "               split_layout ? 1 : 0,\n"
        "               top_ok ? 1 : 0,\n"
        "               right_ok ? 1 : 0,\n"
        "               bottom_ok ? 1 : 0,\n",
        "S1 frame log",
    )

    text = replace_in_section(
        text,
        present_start,
        present_end,
        "    return top_ok && bottom_ok;\n",
        "    return top_ok && right_ok && bottom_ok;\n",
        "present result",
    )

    return text


def main() -> int:
    expected_suffix = Path("Citadel_3D_DEV/Source/shockolate")
    root_text = ROOT.as_posix().lower()

    if not root_text.endswith(expected_suffix.as_posix().lower()):
        fail(
            "Run this only from "
            "C:/Projects/Citadel_3D_DEV/Source/shockolate\n"
            f"Current directory: {ROOT}"
        )

    for path in SNAPSHOT_FILES:
        if not path.is_file():
            fail(f"Missing required active file: {path}")

    original_bytes = {
        path: path.read_bytes()
        for path in SNAPSHOT_FILES
    }
    original_hashes = {
        path: sha256_bytes(data)
        for path, data in original_bytes.items()
    }

    _shock_raw, shock_text, shock_newline = read_source(SHOCK)
    cmake_text = CMAKE.read_text(encoding="utf-8")

    if MARKER in shock_text:
        print("Citadel 3D S1 is already installed; nothing changed.")
        return 0

    required = (
        '#warning "PROJECT CITADEL V16.1: launch polish candidate is ACTIVE"',
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"',
        "static C3D_RenderTarget *citadel_gpu_top_target = NULL;",
        "static bool citadel_gpu_initialize(void)\n{",
        "static bool citadel_v16_present_splash(void)\n{",
        "static bool citadel_gpu_present(SDL_Surface *surface, bool magenta)\n{",
        'chdir("sdmc:/3ds/SystemShock3D")',
    )
    missing = [token for token in required if token not in shock_text]
    if missing:
        print("Required VX1/S0 anchors are missing:")
        for token in missing:
            print(f"  {token}")
        fail("Active Shock.c is not the expected walled VX1 starting point.")

    for forbidden in (
        "sdmc:/3ds/SystemShock/",
        "sdmc:/3ds/systemshock/",
        "PROJECT CITADEL STEREO S1.1:",
        "PROJECT CITADEL STEREO S1.2:",
        "PROJECT CITADEL STEREO S1.3:",
        "citadel_stereo_suspend_display",
        "MONO-PUBLISH",
        "HARD GPU",
    ):
        if forbidden in shock_text:
            fail(f"Unexpected old branch token in active Shock.c: {forbidden}")

    if "3D_Citadel_3DS.3dsx" not in cmake_text:
        fail("CMakeLists.txt does not contain the walled 3D output name.")

    if (
        "sdmc:/3ds/SystemShock/" in cmake_text
        or "sdmc:/3ds/systemshock/" in cmake_text
    ):
        fail("CMakeLists.txt still contains an active mono SD path.")

    hook_start = shock_text.find(
        "static void citadel_3ds_audio_apt_hook(\n"
    )
    hook_end = shock_text.find(
        "static void citadel_3ds_audio_register_apt_hook(void)\n",
        hook_start,
    )
    if hook_start < 0 or hook_end < 0:
        fail("Could not isolate the existing audio/APT hook.")
    original_hook = shock_text[hook_start:hook_end]

    patched_text = patch_shock(shock_text)

    patched_hook_start = patched_text.find(
        "static void citadel_3ds_audio_apt_hook(\n"
    )
    patched_hook_end = patched_text.find(
        "static void citadel_3ds_audio_register_apt_hook(void)\n",
        patched_hook_start,
    )
    patched_hook = patched_text[patched_hook_start:patched_hook_end]

    if patched_hook != original_hook:
        fail("The audio/APT hook changed during a 3D-only patch.")

    for token in (
        MARKER,
        "static C3D_RenderTarget *citadel_gpu_top_right_target = NULL;",
        "GFX_RIGHT",
        "gfxSet3D(true);",
        "GPU 3D S1 mode=IDENTICAL_EYES",
        "GPU 3D S1 FRAME",
        "return top_ok && right_ok && bottom_ok;",
    ):
        if token not in patched_text:
            fail(f"Post-transform verification missing: {token}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre_root = SAFE_ROOT / f"S1_PRE_IDENTICAL_EYES_{timestamp}"
    post_root = SAFE_ROOT / f"S1_IDENTICAL_EYES_CANDIDATE_{timestamp}"

    SAFE_ROOT.mkdir(parents=True, exist_ok=True)

    copy_snapshot(
        pre_root,
        original_bytes,
        (
            "PROJECT CITADEL 3D — PRE-S1 IDENTICAL-EYE BASELINE\n"
            "===================================================\n\n"
            "Exact active files immediately before the first stereoscopic "
            "rendering change.\n"
            "Only Shock.c is permitted to change in S1.\n"
            "No HOME/APT, audio, gameplay, layout, save/load, or input "
            "behavior is part of this patch.\n\n"
            f"Repository: {ROOT}\n"
            f"Saved: {datetime.now().isoformat(timespec='seconds')}\n"
        ),
    )
    pre_zip = zip_snapshot(pre_root)

    patched_bytes = encode_source(patched_text, shock_newline)
    temp = SHOCK.with_name(SHOCK.name + ".S1_TEMP")

    try:
        temp.write_bytes(patched_bytes)
        os.replace(temp, SHOCK)
    except Exception as error:
        temp.unlink(missing_ok=True)
        fail(f"Could not atomically install patched Shock.c: {error}")

    for path in SNAPSHOT_FILES:
        if path == SHOCK:
            continue
        actual = sha256_file(path)
        if actual != original_hashes[path]:
            fail(
                f"Unexpected non-render file change: {path}\n"
                f"Restore from: {pre_root}"
            )

    installed_text = read_source(SHOCK)[1]
    if installed_text.count(MARKER) != 1:
        fail(
            "Installed marker verification failed.\n"
            f"Restore from: {pre_root}"
        )

    active_bytes = {
        path: path.read_bytes()
        for path in SNAPSHOT_FILES
    }
    copy_snapshot(
        post_root,
        active_bytes,
        (
            "PROJECT CITADEL 3D — S1 IDENTICAL-EYE CANDIDATE\n"
            "================================================\n\n"
            "Stereoscopic transport is enabled.\n"
            "The complete existing top-screen composition is submitted "
            "unchanged to GFX_LEFT and GFX_RIGHT.\n"
            "Expected visible depth: none (zero parallax).\n"
            "Bottom screen and all non-render source files are unchanged.\n\n"
            f"Input baseline: {pre_root}\n"
            f"Repository: {ROOT}\n"
            f"Created: {datetime.now().isoformat(timespec='seconds')}\n"
        ),
    )

    diff = "".join(
        difflib.unified_diff(
            shock_text.splitlines(keepends=True),
            installed_text.splitlines(keepends=True),
            fromfile="src/MacSrc/Shock.c (VX1 walled baseline)",
            tofile="src/MacSrc/Shock.c (3D S1 identical eyes)",
        )
    )
    diff_dir = post_root / "DIFFS"
    diff_dir.mkdir(parents=True, exist_ok=True)
    (diff_dir / "S1_IDENTICAL_EYES.diff").write_text(
        diff,
        encoding="utf-8",
    )
    post_zip = zip_snapshot(post_root)

    print()
    print("============================================================")
    print("PROJECT CITADEL 3D S1 INSTALLED")
    print("============================================================")
    print("PASS: GFX_RIGHT RGBA8 target added.")
    print("PASS: Splash submitted identically to both eyes.")
    print("PASS: Live top-screen frame submitted identically to both eyes.")
    print("PASS: Bottom screen unchanged.")
    print("PASS: Existing audio/APT hook byte-for-byte unchanged.")
    print("PASS: setup/mainloop/wrapper/gamewrap/SDLSound/CMake unchanged.")
    print()
    print(f"PRE-S1 BASELINE: {pre_root}")
    print(f"PRE-S1 ZIP:      {pre_zip}")
    print(f"S1 CANDIDATE:    {post_root}")
    print(f"S1 ZIP:          {post_zip}")
    print()
    print("Next:")
    print("  cmake --build build --target project_citadel_3dsx -j\"$(nproc)\"")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
