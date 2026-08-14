#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V15A DIRECT MORTON LIVE UPLOAD
#
# Patches the working V14Z diagnostic source.
#
# V15A removes the display-transfer tiling step from normal presentation.
# Each live Shock frame is palette-converted and written directly into the
# C3D texture's native 8x8 tiled/Morton layout.

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V15A_direct_Morton_live_upload.c")
BACKUP = Path("src/MacSrc/Shock_V14Z_before_V15A.c")


NEW_GPU_BLOCK = r'''/*
 * Native PICA texture ordering:
 *
 *   - the complete texture is divided into physical 8x8 tiles;
 *   - tiles are stored row-by-row;
 *   - pixels inside each tile use 3-bit Morton interleaving:
 *       x0,y0,x1,y1,x2,y2.
 *
 * Phase B of V14Z proved that direct CPU writes to this C3D texture are
 * visible and substantially coherent. V15A extends that test from solid
 * tiles to every live System Shock pixel.
 */
static inline unsigned int citadel_gpu_morton8(unsigned int x,
                                               unsigned int y)
{
    static const unsigned char morton_x[8] = {
        0, 1, 4, 5, 16, 17, 20, 21
    };
    static const unsigned char morton_y[8] = {
        0, 2, 8, 10, 32, 34, 40, 42
    };

    return (unsigned int)morton_x[x & 7] +
           (unsigned int)morton_y[y & 7];
}

static inline size_t citadel_gpu_tiled_offset(unsigned int x,
                                              unsigned int y)
{
    const unsigned int tiles_per_row =
        CITADEL_GPU_TEXTURE_WIDTH / 8;
    const unsigned int tile_x = x >> 3;
    const unsigned int tile_y = y >> 3;
    const size_t tile_base =
        ((size_t)tile_y * (size_t)tiles_per_row +
         (size_t)tile_x) * 64u;

    return tile_base + (size_t)citadel_gpu_morton8(x, y);
}

static bool citadel_gpu_upload_surface(SDL_Surface *surface)
{
    int source_width;
    int source_height;
    const u8 *source_pixels;
    u16 *texture_pixels;
    uint32_t diagnostic_hash = 2166136261u;
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
     * Clear the full 512x512 texture. Only the upper 512x384 content region
     * is populated; the remaining physical tiles stay black.
     */
    memset(texture_pixels, 0, CITADEL_GPU_STAGING_BYTES);

    /*
     * Iterate in physical tile order. This keeps destination writes close
     * together while converting the 640x480 indexed Shock frame directly
     * into 512x384 RGB565 content.
     */
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

    /*
     * Phase B proved that direct texture writes become visible after this
     * cache flush. No display transfer or PPF wait is used in V15A.
     */
    GSPGPU_FlushDataCache(citadel_gpu_texture.data,
                          CITADEL_GPU_STAGING_BYTES);

    if (!citadel_gpu_first_upload_logged) {
        v5_log("GPU V15A FIRST DIRECT UPLOAD src=%dx%d pitch=%d "
               "content=%dx%d texture=%dx%d tile=8x8 morton=XYZ "
               "display_transfer=DISABLED hash=0x%08lX",
               source_width,
               source_height,
               surface->pitch,
               CITADEL_GPU_CONTENT_WIDTH,
               CITADEL_GPU_CONTENT_HEIGHT,
               CITADEL_GPU_TEXTURE_WIDTH,
               CITADEL_GPU_TEXTURE_HEIGHT,
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
    if "PROJECT CITADEL V15A" in text:
        raise RuntimeError("This source already appears to contain V15A.")

    if "PROJECT CITADEL V14Z" not in text:
        raise RuntimeError(
            "V14Z marker not found. Start from the successful V14Z "
            "tile-lie-detector Shock.c."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V14Z: GPU tile lie detector is ACTIVE"',
        '#warning "PROJECT CITADEL V15A: direct Morton live upload is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V14Z.log", "GPU_C2D_V15A.log")
    text = text.replace(
        "PROJECT CITADEL V14Z GPU TILE LIE DETECTOR START",
        "PROJECT CITADEL V15A DIRECT MORTON LIVE UPLOAD START",
    )
    text = text.replace(
        "GPU V14Z DIAGNOSTIC ready",
        "GPU V15A DIRECT TILED ready",
        1,
    )

    diagnostic_state = r'''
/* V14Z automatic diagnostic timing and phase markers. */
static Uint32 citadel_gpu_diagnostic_started_at = 0;
static int citadel_gpu_diagnostic_phase = 0;
static bool citadel_gpu_phase_a_logged = false;
static bool citadel_gpu_phase_b_logged = false;
static bool citadel_gpu_phase_c_logged = false;'''
    if diagnostic_state not in text:
        raise RuntimeError("Could not locate the V14Z diagnostic state block.")
    text = text.replace(diagnostic_state, "", 1)

    region_start = text.find(
        "static void citadel_gpu_transfer_staging(void)"
    )
    if region_start < 0:
        raise RuntimeError(
            "Could not locate the beginning of the V14Z GPU diagnostic block."
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
        print("  python apply_SS3DS_V15A_direct_Morton_live_upload.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V15A: direct Morton live upload is ACTIVE")
    print("Expected runtime log:")
    print("  GPU_C2D_V15A.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
