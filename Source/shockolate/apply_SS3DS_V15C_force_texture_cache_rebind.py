#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V15C FORCE TEXTURE-CACHE REBIND
#
# Patches the working V15B synchronized direct-Morton source.
#
# Citro3D issue #71 documents that changing texture memory does not clear the
# PICA200 texture cache; the cache is cleared when a texture is bound.
# Citro2D caches the current C3D_Tex pointer and normally skips rebinding the
# same texture object. V15C therefore explicitly calls C3D_TexBind(0, ...)
# after every live upload and before any Citro2D draw.

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V15C_force_texture_cache_rebind.c")
BACKUP = Path("src/MacSrc/Shock_V15B_before_V15C.c")


OLD_PRESENT_ANCHOR = r'''    if (!magenta && !citadel_gpu_sync_order_logged) {
        v5_log("GPU V15B SYNC ORDER confirmed: "
               "FrameBegin(SYNCDRAW) -> direct texture write -> draw");
        citadel_gpu_sync_order_logged = true;
    }

    if (magenta) {'''

NEW_PRESENT_ANCHOR = r'''    if (!magenta && !citadel_gpu_sync_order_logged) {
        v5_log("GPU V15C SYNC ORDER confirmed: "
               "FrameBegin(SYNCDRAW) -> direct texture write -> "
               "forced texture rebind -> draw");
        citadel_gpu_sync_order_logged = true;
    }

    /*
     * V15C CRITICAL FIX:
     *
     * Updating citadel_gpu_texture.data and flushing the CPU data cache does
     * not invalidate the PICA200 texture cache. Citro2D normally avoids
     * C3D_TexBind when C2D_Image.tex is the same pointer as the preceding
     * draw, so a continuously updated single texture can be sampled from
     * stale cache lines.
     *
     * C3D_TexBind marks texture unit 0 dirty every time it is called, even
     * when the pointer is unchanged. The resulting register bind invalidates
     * the hardware texture cache before this frame's draw commands.
     */
    if (!magenta) {
        C3D_TexBind(0, &citadel_gpu_texture);

        if (!citadel_gpu_cache_rebind_logged) {
            v5_log("GPU V15C CACHE REBIND active: "
                   "C3D_TexBind(0, live_texture) after every upload");
            citadel_gpu_cache_rebind_logged = true;
        }
    }

    if (magenta) {'''


def patch(text: str) -> str:
    if "PROJECT CITADEL V15C" in text:
        raise RuntimeError("This source already appears to contain V15C.")

    if "PROJECT CITADEL V15B" not in text:
        raise RuntimeError(
            "V15B marker not found. Start from the currently working "
            "V15B synchronized direct-texture Shock.c."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V15B: synchronized direct texture upload is ACTIVE"',
        '#warning "PROJECT CITADEL V15C: forced texture-cache rebind is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V15B.log", "GPU_C2D_V15C.log")
    text = text.replace(
        "PROJECT CITADEL V15B SYNCHRONIZED DIRECT TEXTURE UPLOAD START",
        "PROJECT CITADEL V15C FORCED TEXTURE-CACHE REBIND START",
    )
    text = text.replace(
        "GPU V15B SYNCHRONIZED DIRECT TILED ready",
        "GPU V15C CACHE-INVALIDATED DIRECT TILED ready",
        1,
    )
    text = text.replace(
        "GPU V15B FIRST DIRECT UPLOAD",
        "GPU V15C FIRST DIRECT UPLOAD",
        1,
    )

    state_anchor = "static bool citadel_gpu_sync_order_logged = false;"
    state_replacement = state_anchor + r'''

/* V15C: confirms the live texture is explicitly rebound after every upload. */
static bool citadel_gpu_cache_rebind_logged = false;'''

    if state_anchor not in text:
        raise RuntimeError(
            "Could not locate V15B's synchronization state anchor."
        )
    text = text.replace(state_anchor, state_replacement, 1)

    if OLD_PRESENT_ANCHOR not in text:
        raise RuntimeError(
            "Could not locate V15B's confirmed upload/draw sequence. "
            "The active source may differ from the expected V15B build."
        )
    text = text.replace(OLD_PRESENT_ANCHOR, NEW_PRESENT_ANCHOR, 1)

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
        print("  python apply_SS3DS_V15C_force_texture_cache_rebind.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V15C: forced texture-cache rebind is ACTIVE")
    print("Expected runtime log:")
    print("  GPU_C2D_V15C.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
