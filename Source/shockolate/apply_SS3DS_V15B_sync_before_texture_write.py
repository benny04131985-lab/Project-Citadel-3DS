#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V15B SYNC BEFORE TEXTURE WRITE
#
# Patches the working V15A direct-Morton source.
#
# V15A wrote the new live texture before C3D_FrameBegin(SYNCDRAW), allowing
# the CPU to overwrite memory while the previous GPU frame could still be
# sampling it. V15B begins/synchronizes the frame first, then updates the
# texture, then submits the new draws.

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V15B_sync_before_texture_write.c")
BACKUP = Path("src/MacSrc/Shock_V15A_before_V15B.c")


OLD_ORDER = r'''    if (!magenta && !citadel_gpu_upload_surface(surface))
        return false;

    if (!C3D_FrameBegin(C3D_FRAME_SYNCDRAW)) {
        ++citadel_gpu_draw_failures;
        return false;
    }

    if (magenta) {'''

NEW_ORDER = r'''    /*
     * V15B CRITICAL ORDER:
     *
     * C3D_FRAME_SYNCDRAW drains/synchronizes the previous GPU frame before
     * the CPU modifies the texture that frame may still be sampling.
     *
     * V15A performed citadel_gpu_upload_surface() before this call, creating
     * a live read/write race that a static diagnostic texture could hide.
     */
    if (!C3D_FrameBegin(C3D_FRAME_SYNCDRAW)) {
        ++citadel_gpu_draw_failures;
        return false;
    }

    if (!magenta && !citadel_gpu_upload_surface(surface)) {
        /*
         * Do not leave Citro3D in an active-frame state if an unexpected
         * surface validation/upload failure occurs.
         */
        C3D_FrameEnd(0);
        return false;
    }

    if (!magenta && !citadel_gpu_sync_order_logged) {
        v5_log("GPU V15B SYNC ORDER confirmed: "
               "FrameBegin(SYNCDRAW) -> direct texture write -> draw");
        citadel_gpu_sync_order_logged = true;
    }

    if (magenta) {'''


def patch(text: str) -> str:
    if "PROJECT CITADEL V15B" in text:
        raise RuntimeError("This source already appears to contain V15B.")

    if "PROJECT CITADEL V15A" not in text:
        raise RuntimeError(
            "V15A marker not found. Start from the currently working "
            "V15A direct-Morton Shock.c."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V15A: direct Morton live upload is ACTIVE"',
        '#warning "PROJECT CITADEL V15B: synchronized direct texture upload is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V15A.log", "GPU_C2D_V15B.log")
    text = text.replace(
        "PROJECT CITADEL V15A DIRECT MORTON LIVE UPLOAD START",
        "PROJECT CITADEL V15B SYNCHRONIZED DIRECT TEXTURE UPLOAD START",
    )
    text = text.replace(
        "GPU V15A DIRECT TILED ready",
        "GPU V15B SYNCHRONIZED DIRECT TILED ready",
        1,
    )
    text = text.replace(
        "GPU V15A FIRST DIRECT UPLOAD",
        "GPU V15B FIRST DIRECT UPLOAD",
        1,
    )

    state_anchor = "static bool citadel_gpu_first_upload_logged = false;"
    state_replacement = state_anchor + r'''

/* V15B: confirms that the previous GPU frame is drained before texture writes. */
static bool citadel_gpu_sync_order_logged = false;'''

    if state_anchor not in text:
        raise RuntimeError("Could not locate the GPU upload-log state anchor.")
    text = text.replace(state_anchor, state_replacement, 1)

    if OLD_ORDER not in text:
        raise RuntimeError(
            "Could not locate V15A's upload-before-FrameBegin sequence. "
            "The active source may differ from the expected V15A build."
        )
    text = text.replace(OLD_ORDER, NEW_ORDER, 1)

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
            "ERROR: src/MacSrc/Shock.c was not found.\n"
            "Run this script from the Shockolate project root.",
            file=sys.stderr,
        )
        return 1

    original = SOURCE.read_text(encoding="utf-8")

    try:
        result = patch(original)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    PREVIEW.write_text(result, encoding="utf-8", newline="\n")
    print(f"Created preview: {PREVIEW}")

    if args.install:
        if BACKUP.exists():
            print(
                f"ERROR: Backup already exists: {BACKUP}\n"
                "Move or rename it before installing again.",
                file=sys.stderr,
            )
            return 1

        BACKUP.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SOURCE, BACKUP)
        SOURCE.write_text(result, encoding="utf-8", newline="\n")
        print(f"Backup: {BACKUP}")
        print(f"Installed: {SOURCE}")
    else:
        print("The active source was not changed.")
        print("Install after reviewing the preview with:")
        print("  python apply_SS3DS_V15B_sync_before_texture_write.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V15B: synchronized direct texture upload is ACTIVE")
    print("Expected runtime log:")
    print("  GPU_C2D_V15B.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
