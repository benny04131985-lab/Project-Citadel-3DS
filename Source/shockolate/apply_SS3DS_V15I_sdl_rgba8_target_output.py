#!/usr/bin/env python3
"""Apply Project Citadel V15I to the active V15H Shock.c."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

SOURCE = Path("src/MacSrc/Shock.c")
BACKUP = Path("src/MacSrc/Shock_V15H_before_V15I.c")
PREVIEW = Path("Shock_3DS_V15I_sdl_rgba8_target_output.c")

HELPER = r"""
/*
 * PROJECT CITADEL V15I: SDL-compatible Citro2D screen target.
 *
 * SDL2's Nintendo 3DS video backend initializes both LCD framebuffers as
 * GSP_RGBA8_OES (four bytes per pixel). Citro2D's convenience
 * C2D_CreateScreenTarget() assumes the libctru default BGR8 framebuffer and
 * hardcodes GX_TRANSFER_FMT_RGB8 (three bytes per pixel) as its output.
 *
 * Feeding a three-byte display transfer into SDL's four-byte framebuffer
 * changes the physical row stride and fractures the entire completed frame,
 * including target clears and untextured rectangles.
 *
 * Keep SDL's framebuffer ownership and mode intact. Only customize the final
 * Citro3D render-target transfer so its output format matches SDL's RGBA8
 * framebuffer exactly.
 */
static C3D_RenderTarget *
citadel_gpu_create_sdl_rgba8_screen_target(gfxScreen_t screen,
                                            gfx3dSide_t side)
{
    int height;
    C3D_RenderTarget *target;

    if (screen == GFX_TOP) {
        height = gfxIsWide()
            ? GSP_SCREEN_HEIGHT_TOP_2X
            : GSP_SCREEN_HEIGHT_TOP;
    } else {
        height = GSP_SCREEN_HEIGHT_BOTTOM;
    }

    target = C3D_RenderTargetCreate(GSP_SCREEN_WIDTH,
                                    height,
                                    GPU_RB_RGBA8,
                                    GPU_RB_DEPTH16);
    if (target == NULL)
        return NULL;

    C3D_RenderTargetSetOutput(
        target,
        screen,
        side,
        GX_TRANSFER_FLIP_VERT(0) |
        GX_TRANSFER_OUT_TILED(0) |
        GX_TRANSFER_RAW_COPY(0) |
        GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8) |
        GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGBA8) |
        GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO));

    return target;
}

"""

OLD_TARGETS = """    citadel_gpu_top_target =
        C2D_CreateScreenTarget(GFX_TOP, GFX_LEFT);
    citadel_gpu_bottom_target =
        C2D_CreateScreenTarget(GFX_BOTTOM, GFX_LEFT);
"""

NEW_TARGETS = """    v5_log("GPU V15I SCREEN FORMAT before-targets "
           "top=%u bottom=%u expected_rgba8=%u",
           (unsigned int)gfxGetScreenFormat(GFX_TOP),
           (unsigned int)gfxGetScreenFormat(GFX_BOTTOM),
           (unsigned int)GSP_RGBA8_OES);

    citadel_gpu_top_target =
        citadel_gpu_create_sdl_rgba8_screen_target(
            GFX_TOP,
            GFX_LEFT);
    citadel_gpu_bottom_target =
        citadel_gpu_create_sdl_rgba8_screen_target(
            GFX_BOTTOM,
            GFX_LEFT);

    v5_log("GPU V15I TARGET OUTPUT transfer_in=RGBA8 "
           "transfer_out=RGBA8 screen_framebuffer=SDL_RGBA8");
"""


def transform(text: str) -> str:
    marker = '#warning "PROJECT CITADEL V15H: official tex3ds control is ACTIVE"'
    init_anchor = "static bool citadel_gpu_initialize(void)\n{"

    if "PROJECT CITADEL V15I" in text:
        raise RuntimeError("The source already appears to contain V15I.")
    if marker not in text:
        raise RuntimeError(
            "V15H marker not found. Start from the currently compiled "
            "V15H Shock.c."
        )
    if OLD_TARGETS not in text:
        raise RuntimeError(
            "The expected V15H C2D_CreateScreenTarget block was not found."
        )
    if init_anchor not in text:
        raise RuntimeError("Could not locate citadel_gpu_initialize().")

    text = text.replace(
        marker,
        '#warning "PROJECT CITADEL V15I: SDL RGBA8 target-output fix is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V15H.log", "GPU_C2D_V15I.log")
    text = text.replace(
        "PROJECT CITADEL V15H OFFICIAL TEX3DS CONTROL START",
        "PROJECT CITADEL V15I SDL RGBA8 TARGET OUTPUT START",
    )
    text = text.replace('"GPU V15H ', '"GPU V15I ')
    text = text.replace(init_anchor, HELPER + init_anchor, 1)
    text = text.replace(OLD_TARGETS, NEW_TARGETS, 1)
    text = text.replace(
        "GPU V15I BASE PIPELINE ready texture=%dx%d content=%dx%d ",
        "GPU V15I RGBA8 TARGET PIPELINE ready texture=%dx%d content=%dx%d ",
        1,
    )

    required = (
        "GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGBA8)",
        "GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8)",
        "GPU_C2D_V15I.log",
        "V15H_CONTROL.t3x",
    )
    for token in required:
        if token not in text:
            raise RuntimeError(f"Generated source is missing: {token}")

    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--install",
        action="store_true",
        help="Back up and replace src/MacSrc/Shock.c",
    )
    args = parser.parse_args()

    if not SOURCE.is_file():
        print(
            "ERROR: src/MacSrc/Shock.c was not found. "
            "Run this from the Shockolate project root.",
            file=sys.stderr,
        )
        return 1

    try:
        result = transform(SOURCE.read_text(encoding="utf-8"))
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    PREVIEW.write_text(result, encoding="utf-8", newline="\n")
    print(f"Created preview: {PREVIEW}")

    if args.install:
        if BACKUP.exists():
            print(
                f"ERROR: Backup already exists: {BACKUP}",
                file=sys.stderr,
            )
            return 1
        shutil.copy2(SOURCE, BACKUP)
        SOURCE.write_text(result, encoding="utf-8", newline="\n")
        print(f"Backup: {BACKUP}")
        print(f"Installed: {SOURCE}")
    else:
        print("The active source was not changed.")
        print("Install with:")
        print("  python apply_SS3DS_V15I_sdl_rgba8_target_output.py --install")

    print()
    print("Build normally:")
    print("  cmake --build build-3ds")
    print()
    print("Keep V15H_CONTROL.t3x beside systemshock.3dsx.")
    print("Expected log: GPU_C2D_V15I.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
