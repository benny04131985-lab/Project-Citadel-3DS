#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V15E AUTHORITATIVE PALETTE SYNC
#
# Patches the working V15D source.
#
# V15E removes the V15D startup diagnostic and CPU-frame dump, then rebuilds
# the complete 256-entry RGB565 GPU palette from authoritative gamePalette at
# the start of every live texture upload.
#
# This intentionally does not depend on SetSDLPalette(), a dirty flag, or any
# single palette-update call path. Fades, palette effects, direct palette
# writes, and future code changes therefore cannot leave the GPU lookup stale.

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V15E_authoritative_palette_sync.c")
BACKUP = Path("src/MacSrc/Shock_V15D_before_V15E.c")


NEW_GPU_BLOCK = r'''/*
 * Convert one SDL_Color from the authoritative gamePalette into the exact
 * RGB565 packing used by the proven V15D procedural texture.
 */
static inline u16 citadel_gpu_color_to_rgb565(SDL_Color color)
{
    const u16 r5 = (u16)(color.r >> 3);
    const u16 g6 = (u16)(color.g >> 2);
    const u16 b5 = (u16)(color.b >> 3);

    return (u16)((r5 << 11) | (g6 << 5) | b5);
}

/*
 * V15E future-proof palette policy:
 *
 * Rebuild all 256 entries at the beginning of every live upload from
 * gamePalette, which is the same authoritative palette that generated the
 * clean V15D_CPU_FRAME.ppm.
 *
 * This is deliberately unconditional. Updating 256 entries is negligible
 * beside converting approximately 196,608 destination pixels, while it makes
 * missed callbacks, direct palette mutations, fades, and palette effects
 * impossible to desynchronize from the GPU conversion.
 *
 * Return the number of entries that differed from the old cached table before
 * replacement. This gives us decisive runtime evidence about stale state.
 */
static unsigned int citadel_gpu_refresh_palette565(void)
{
    unsigned int mismatches = 0;
    int index;

    for (index = 0; index < 256; ++index) {
        const u16 expected =
            citadel_gpu_color_to_rgb565(gamePalette[index]);

        if (citadel_gpu_palette565[index] != expected)
            ++mismatches;

        citadel_gpu_palette565[index] = expected;
    }

    ++citadel_gpu_palette_refreshes;

    if (citadel_gpu_palette_refreshes == 1 ||
        (mismatches > 0 && citadel_gpu_palette_change_logs < 16)) {
        v5_log("GPU V15E PALETTE SYNC refresh=%lu mismatches=%u "
               "rgb565[0]=0x%04X rgb565[1]=0x%04X "
               "rgb565[255]=0x%04X",
               (unsigned long)citadel_gpu_palette_refreshes,
               mismatches,
               (unsigned int)citadel_gpu_palette565[0],
               (unsigned int)citadel_gpu_palette565[1],
               (unsigned int)citadel_gpu_palette565[255]);

        if (mismatches > 0)
            ++citadel_gpu_palette_change_logs;
    }

    return mismatches;
}

static bool citadel_gpu_upload_surface(SDL_Surface *surface)
{
    int source_width;
    int source_height;
    const u8 *source_pixels;
    u16 *texture_pixels;
    uint32_t diagnostic_hash = 2166136261u;
    unsigned int palette_mismatches;
    int tile_y;

    if (surface == NULL ||
        surface->pixels == NULL ||
        surface->format == NULL ||
        surface->format->BytesPerPixel != 1 ||
        !citadel_gpu_texture_initialized ||
        citadel_gpu_texture.data == NULL) {
        ++citadel_gpu_upload_failures;
        return false;
    }

    source_width = surface->w;
    source_height = surface->h;

    if (source_width <= 0 || source_height <= 0) {
        ++citadel_gpu_upload_failures;
        return false;
    }

    citadel_gpu_source_width = source_width;
    citadel_gpu_source_height = source_height;
    source_pixels = (const u8 *)surface->pixels;
    texture_pixels = (u16 *)citadel_gpu_texture.data;

    /*
     * Critical V15E correction: synchronize from gamePalette before a single
     * indexed source pixel is converted.
     */
    palette_mismatches = citadel_gpu_refresh_palette565();

    memset(texture_pixels, 0, CITADEL_GPU_STAGING_BYTES);

    for (tile_y = 0;
         tile_y < CITADEL_GPU_CONTENT_HEIGHT;
         tile_y += 8) {
        int tile_x;

        for (tile_x = 0;
             tile_x < CITADEL_GPU_CONTENT_WIDTH;
             tile_x += 8) {
            int local_y;

            for (local_y = 0; local_y < 8; ++local_y) {
                const int destination_y = tile_y + local_y;
                int source_y =
                    (destination_y * source_height) /
                    CITADEL_GPU_CONTENT_HEIGHT;
                const u8 *source_row;
                int local_x;

                if (source_y >= source_height)
                    source_y = source_height - 1;

                source_row =
                    source_pixels + (source_y * surface->pitch);

                for (local_x = 0; local_x < 8; ++local_x) {
                    const int destination_x = tile_x + local_x;
                    int source_x =
                        (destination_x * source_width) /
                        CITADEL_GPU_CONTENT_WIDTH;
                    u16 converted;
                    size_t tiled_offset;

                    if (source_x >= source_width)
                        source_x = source_width - 1;

                    converted =
                        citadel_gpu_palette565[source_row[source_x]];

                    tiled_offset =
                        citadel_gpu_tiled_offset(
                            (unsigned int)destination_x,
                            (unsigned int)destination_y);

                    texture_pixels[tiled_offset] = converted;

                    if (((destination_x | destination_y) & 31) == 0) {
                        diagnostic_hash ^= (uint32_t)converted;
                        diagnostic_hash *= 16777619u;
                    }
                }
            }
        }
    }

    GSPGPU_FlushDataCache(citadel_gpu_texture.data,
                          CITADEL_GPU_STAGING_BYTES);

    if (!citadel_gpu_first_upload_logged) {
        v5_log("GPU V15E FIRST LIVE UPLOAD src=%dx%d pitch=%d "
               "content=%dx%d texture=%dx%d tile=8x8 "
               "palette=AUTHORITATIVE_EVERY_FRAME "
               "initial_mismatches=%u hash=0x%08lX",
               source_width,
               source_height,
               surface->pitch,
               CITADEL_GPU_CONTENT_WIDTH,
               CITADEL_GPU_CONTENT_HEIGHT,
               CITADEL_GPU_TEXTURE_WIDTH,
               CITADEL_GPU_TEXTURE_HEIGHT,
               palette_mismatches,
               (unsigned long)diagnostic_hash);
        citadel_gpu_first_upload_logged = true;
    }

    return true;
}'''


def function_end(text: str, signature: str) -> int:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"Could not locate function: {signature}")

    brace = text.find("{", start)
    if brace < 0:
        raise RuntimeError(f"Could not locate opening brace: {signature}")

    depth = 0
    i = brace
    in_string = False
    in_char = False
    escaped = False
    line_comment = False
    block_comment = False

    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if c == "\n":
                line_comment = False
        elif block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 1
        elif in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == '"':
                in_string = False
        elif in_char:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == "'":
                in_char = False
        else:
            if c == "/" and n == "/":
                line_comment = True
                i += 1
            elif c == "/" and n == "*":
                block_comment = True
                i += 1
            elif c == '"':
                in_string = True
            elif c == "'":
                in_char = True
            elif c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1

    raise RuntimeError(f"Unterminated function: {signature}")


def patch(text: str) -> str:
    if "PROJECT CITADEL V15E" in text:
        raise RuntimeError("This source already appears to contain V15E.")

    if "PROJECT CITADEL V15D" not in text:
        raise RuntimeError(
            "V15D marker not found. Start from the current V15D "
            "source-vs-Morton truth-test Shock.c."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V15D: source-vs-Morton truth test is ACTIVE"',
        '#warning "PROJECT CITADEL V15E: authoritative palette sync is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V15D.log", "GPU_C2D_V15E.log")
    text = text.replace(
        "PROJECT CITADEL V15D SOURCE VS MORTON TRUTH TEST START",
        "PROJECT CITADEL V15E AUTHORITATIVE PALETTE SYNC START",
    )
    text = text.replace(
        "GPU V15D SOURCE-VS-MORTON DIAGNOSTIC ready",
        "GPU V15E AUTHORITATIVE PALETTE ready",
        1,
    )
    text = text.replace(
        "GPU V15D SYNC ORDER confirmed",
        "GPU V15E SYNC ORDER confirmed",
    )
    text = text.replace(
        "GPU V15D CACHE REBIND active",
        "GPU V15E CACHE REBIND active",
    )

    old_state = r'''
/* V15D diagnostic state. */
static Uint32 citadel_gpu_v15d_started_at = 0;
static bool citadel_gpu_v15d_pattern_logged = false;
static bool citadel_gpu_v15d_live_logged = false;
static bool citadel_gpu_v15d_source_dump_attempted = false;'''

    new_state = r'''
/* V15E authoritative palette synchronization instrumentation. */
static unsigned long citadel_gpu_palette_refreshes = 0;
static unsigned int citadel_gpu_palette_change_logs = 0;'''

    if old_state not in text:
        raise RuntimeError("Could not locate the V15D diagnostic state block.")
    text = text.replace(old_state, new_state, 1)

    region_start = text.find(
        "static void citadel_gpu_fill_detailed_morton_pattern(void)"
    )
    if region_start < 0:
        raise RuntimeError(
            "Could not locate the beginning of the V15D diagnostic GPU block."
        )

    region_end = function_end(
        text,
        "static bool citadel_gpu_upload_surface(SDL_Surface *surface)",
    )

    text = text[:region_start] + NEW_GPU_BLOCK + text[region_end:]
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
        print("  python apply_SS3DS_V15E_authoritative_palette_sync.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V15E: authoritative palette sync is ACTIVE")
    print("Expected runtime log:")
    print("  GPU_C2D_V15E.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
