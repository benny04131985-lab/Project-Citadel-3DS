#!/usr/bin/env python3
"""Apply Project Citadel V15J to the currently compiled V15I Shock.c."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

SOURCE = Path("src/MacSrc/Shock.c")
BACKUP = Path("src/MacSrc/Shock_V15I_before_V15J.c")
PREVIEW = Path("Shock_3DS_V15J_full_640x480_transport.c")

DIAG_BLOCK = """    citadel_gpu_v15g_prepare_images();

    if (!citadel_gpu_v15h_initialize_control()) {
        v5_log("GPU V15I CONTROL unavailable; diagnostic will not start");
    }

    /* Disable the older V15G timed phase machine in this build. */
    citadel_gpu_v15g_capture_done = true;
    citadel_gpu_v15g_phase = CITADEL_V15G_PHASE_COMPLETE;

    citadel_gpu_update_palette565();

    citadel_gpu_ready = true;
    atexit(citadel_gpu_shutdown);

    v5_log("GPU V15I RGBA8 TARGET PIPELINE ready texture=%dx%d content=%dx%d "
           "source-resample=nearest filter=NEAREST",
           CITADEL_GPU_TEXTURE_WIDTH,
           CITADEL_GPU_TEXTURE_HEIGHT,
           CITADEL_GPU_CONTENT_WIDTH,
           CITADEL_GPU_CONTENT_HEIGHT);
"""

REPLACEMENT_DIAG = """    citadel_gpu_v15g_prepare_images();

    /* V15J is a production-quality transport pass. Disable all timed
     * diagnostic phases and remove the external control-asset requirement.
     */
    citadel_gpu_v15h_asset_ready = false;
    citadel_gpu_v15h_capture_done = true;
    citadel_gpu_v15h_phase = CITADEL_V15H_PHASE_COMPLETE;

    citadel_gpu_v15g_capture_done = true;
    citadel_gpu_v15g_phase = CITADEL_V15G_PHASE_COMPLETE;

    citadel_gpu_update_palette565();

    citadel_gpu_ready = true;
    atexit(citadel_gpu_shutdown);

    v5_log("GPU V15J FULL-FRAME TRANSPORT ready texture=%dx%d content=%dx%d "
           "source-resample=none filter=NEAREST",
           CITADEL_GPU_TEXTURE_WIDTH,
           CITADEL_GPU_TEXTURE_HEIGHT,
           CITADEL_GPU_CONTENT_WIDTH,
           CITADEL_GPU_CONTENT_HEIGHT);
"""

OLD_PHASE_ACTIVE = """static bool citadel_gpu_v15h_phase_active(void)
{
    return citadel_gpu_v15h_phase ==
               CITADEL_V15H_PHASE_OFFICIAL_TEX3DS ||
           citadel_gpu_v15h_phase ==
               CITADEL_V15H_PHASE_RUNTIME_CONTROL;
}
"""

NEW_PHASE_ACTIVE = """static bool citadel_gpu_v15h_phase_active(void)
{
    /* V15J ships without the timed tex3ds/runtime control phases. */
    return false;
}
"""


def transform(text: str) -> str:
    marker = '#warning "PROJECT CITADEL V15I: SDL RGBA8 target-output fix is ACTIVE"'
    if "PROJECT CITADEL V15J" in text:
        raise RuntimeError("The source already appears to contain V15J.")
    if marker not in text:
        raise RuntimeError("V15I marker not found. Start from the current V15I Shock.c.")
    if DIAG_BLOCK not in text:
        raise RuntimeError("Expected V15I diagnostic init block not found.")
    if OLD_PHASE_ACTIVE not in text:
        raise RuntimeError("Expected V15H phase helper not found.")

    text = text.replace(DIAG_BLOCK, REPLACEMENT_DIAG, 1)
    text = text.replace(OLD_PHASE_ACTIVE, NEW_PHASE_ACTIVE, 1)

    text = text.replace(
        marker,
        '#warning "PROJECT CITADEL V15J: full 640x480 texture transport is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V15I.log", "GPU_C2D_V15J.log")
    text = text.replace(
        "PROJECT CITADEL V15I SDL RGBA8 TARGET OUTPUT START",
        "PROJECT CITADEL V15J FULL 640x480 TEXTURE TRANSPORT START",
        1,
    )
    text = text.replace('"GPU V15I ', '"GPU V15J ')
    text = text.replace('"GPU V15H ', '"GPU V15J ')
    text = text.replace('"GPU V15G ', '"GPU V15J ')

    text = text.replace(
        "#define CITADEL_GPU_TEXTURE_WIDTH    512",
        "#define CITADEL_GPU_TEXTURE_WIDTH    1024",
        1,
    )
    text = text.replace(
        "#define CITADEL_GPU_CONTENT_WIDTH    512",
        "#define CITADEL_GPU_CONTENT_WIDTH    640",
        1,
    )
    text = text.replace(
        "#define CITADEL_GPU_CONTENT_HEIGHT   384",
        "#define CITADEL_GPU_CONTENT_HEIGHT   480",
        1,
    )

    text = text.replace(
        " * V14Y transports the original 4:3 Shock frame as a 512x384 image inside a\n"
        " * 512x512 power-of-two texture. The unused lower 128 rows remain black.\n"
        " *\n"
        " * V14X used a 1024-pixel transfer stride. The successful-but-repeated visual\n"
        " * pattern on both LCDs proves that presentation worked while the shared tiled\n"
        " * texture was malformed. The conservative 512x512 path removes that variable.\n",
        " * V15J transports the original 4:3 Shock frame at its full 640x480 size\n"
        " * inside a 1024x512 power-of-two texture. The unused right and lower regions\n"
        " * remain black padding. This removes the intermediate 512x384 resample so\n"
        " * menu text and thin UI details survive until the one final LCD scale step.\n",
        1,
    )

    text = text.replace(
        "     * Translate the original Shock-space crop into the 512x384 transport\n"
        "     * rectangle. Round the far edges upward so the final source row/column\n"
        "     * cannot disappear because of integer truncation.\n",
        "     * Translate the original Shock-space crop into the active transport\n"
        "     * rectangle. V15J uses a full 640x480 content image, so menu views map\n"
        "     * 1:1 into texture space and only the final LCD presentation scales.\n",
        1,
    )

    must_have = (
        'PROJECT CITADEL V15J: full 640x480 texture transport is ACTIVE',
        'GPU_C2D_V15J.log',
        '#define CITADEL_GPU_TEXTURE_WIDTH    1024',
        '#define CITADEL_GPU_CONTENT_WIDTH    640',
        '#define CITADEL_GPU_CONTENT_HEIGHT   480',
        'GPU V15J FULL-FRAME TRANSPORT ready',
    )
    for token in must_have:
        if token not in text:
            raise RuntimeError(f"Generated source is missing: {token}")

    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()

    if not SOURCE.is_file():
        print("ERROR: src/MacSrc/Shock.c was not found. Run this from the Shockolate project root.", file=sys.stderr)
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
            print(f"ERROR: Backup already exists: {BACKUP}", file=sys.stderr)
            return 1
        shutil.copy2(SOURCE, BACKUP)
        SOURCE.write_text(result, encoding="utf-8", newline="\n")
        print(f"Backup: {BACKUP}")
        print(f"Installed: {SOURCE}")
    else:
        print("The active source was not changed.")
        print("Install with:")
        print("  python apply_SS3DS_V15J_full_640x480_transport.py --install")

    print()
    print("Build normally:")
    print("  cmake --build build-3ds")
    print("Expected log: GPU_C2D_V15J.log")
    print("No external V15H_CONTROL.t3x asset is required.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
