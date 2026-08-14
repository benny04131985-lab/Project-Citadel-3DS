#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V14Z GPU TILE LIE DETECTOR
#
# Patches the working V14Y src/MacSrc/Shock.c.
#
# First five seconds after the magenta test:
#   Phase A: known linear pattern through current OUT_TILED transfer
#   Phase B: known solid 8x8 tiles written directly to texture memory
#   Phase C: normal System Shock V14Y presentation resumes

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V14Z_GPU_tile_lie_detector.c")
BACKUP = Path("src/MacSrc/Shock_V14Y_before_V14Z.c")


NEW_GPU_BLOCK = r'''static void citadel_gpu_transfer_staging(void)
{
    GSPGPU_FlushDataCache(citadel_gpu_staging,
                          CITADEL_GPU_STAGING_BYTES);

    C3D_SyncDisplayTransfer(
        (u32 *)citadel_gpu_staging,
        GX_BUFFER_DIM(CITADEL_GPU_TEXTURE_WIDTH,
                      CITADEL_GPU_TEXTURE_HEIGHT),
        (u32 *)citadel_gpu_texture.data,
        GX_BUFFER_DIM(CITADEL_GPU_TEXTURE_WIDTH,
                      CITADEL_GPU_TEXTURE_HEIGHT),
        GX_TRANSFER_FLIP_VERT(0) |
        GX_TRANSFER_OUT_TILED(1) |
        GX_TRANSFER_RAW_COPY(0) |
        GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGB565) |
        GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGB565) |
        GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO));
}

/*
 * Phase A ignores Shock and fills the ordinary LINEAR staging buffer with
 * unmistakable geometry. The exact V14Y display-transfer path then converts
 * the buffer into a tiled texture.
 */
static void citadel_gpu_fill_linear_diagnostic(void)
{
    int y;

    for (y = 0; y < CITADEL_GPU_TEXTURE_HEIGHT; ++y) {
        int x;
        u16 *row =
            citadel_gpu_staging +
            (y * CITADEL_GPU_TEXTURE_WIDTH);

        for (x = 0; x < CITADEL_GPU_TEXTURE_WIDTH; ++x) {
            u16 color = 0x0000;

            if (y < CITADEL_GPU_CONTENT_HEIGHT) {
                if (x < CITADEL_GPU_TEXTURE_WIDTH / 2 &&
                    y < CITADEL_GPU_CONTENT_HEIGHT / 2)
                    color = 0xF800; /* red */
                else if (x >= CITADEL_GPU_TEXTURE_WIDTH / 2 &&
                         y < CITADEL_GPU_CONTENT_HEIGHT / 2)
                    color = 0x07E0; /* green */
                else if (x < CITADEL_GPU_TEXTURE_WIDTH / 2)
                    color = 0x001F; /* blue */
                else
                    color = 0xFFFF; /* white */

                if ((x & 31) < 2 || (y & 31) < 2)
                    color = 0x0000;

                if (x == y ||
                    x == (CITADEL_GPU_TEXTURE_WIDTH - 1 - y))
                    color = 0xFFE0; /* yellow */
            }

            row[x] = color;
        }
    }
}

/*
 * Phase B bypasses display-transfer tiling.
 *
 * Each physical 8x8 tile is one solid color. The internal Morton ordering of
 * its 64 pixels therefore cannot alter the appearance of that tile.
 */
static void citadel_gpu_fill_direct_tile_diagnostic(void)
{
    u16 *texture_pixels = (u16 *)citadel_gpu_texture.data;
    const int tiles_x = CITADEL_GPU_TEXTURE_WIDTH / 8;
    const int tiles_y = CITADEL_GPU_TEXTURE_HEIGHT / 8;
    int tile_y;

    for (tile_y = 0; tile_y < tiles_y; ++tile_y) {
        int tile_x;

        for (tile_x = 0; tile_x < tiles_x; ++tile_x) {
            const int visible_tile_rows =
                CITADEL_GPU_CONTENT_HEIGHT / 8;
            u16 color = 0x0000;
            int tile_base;
            int pixel;

            if (tile_y < visible_tile_rows) {
                if (tile_x < tiles_x / 2 &&
                    tile_y < visible_tile_rows / 2)
                    color = 0xF800; /* red */
                else if (tile_x >= tiles_x / 2 &&
                         tile_y < visible_tile_rows / 2)
                    color = 0x07E0; /* green */
                else if (tile_x < tiles_x / 2)
                    color = 0x001F; /* blue */
                else
                    color = 0xFFFF; /* white */

                if ((tile_x & 3) == 0 || (tile_y & 3) == 0)
                    color = 0x0000;

                if (tile_x == tile_y ||
                    tile_x == (tiles_x - 1 - tile_y))
                    color = 0x07FF; /* cyan */
            }

            tile_base =
                ((tile_y * tiles_x) + tile_x) * 64;

            for (pixel = 0; pixel < 64; ++pixel)
                texture_pixels[tile_base + pixel] = color;
        }
    }

    GSPGPU_FlushDataCache(citadel_gpu_texture.data,
                          CITADEL_GPU_STAGING_BYTES);
}

static bool citadel_gpu_upload_surface(SDL_Surface *surface)
{
    int source_width;
    int source_height;
    int destination_y;
    const u8 *source_pixels;
    uint32_t diagnostic_hash = 2166136261u;
    Uint32 now;
    Uint32 elapsed;

    if (surface == NULL ||
        surface->pixels == NULL ||
        surface->format == NULL ||
        surface->format->BytesPerPixel != 1 ||
        citadel_gpu_staging == NULL ||
        !citadel_gpu_texture_initialized) {
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

    now = SDL_GetTicks();
    if (citadel_gpu_diagnostic_started_at == 0)
        citadel_gpu_diagnostic_started_at = now;

    elapsed = now - citadel_gpu_diagnostic_started_at;

    if (elapsed < 2500) {
        citadel_gpu_diagnostic_phase = 1;

        if (!citadel_gpu_phase_a_logged) {
            v5_log("GPU V14Z PHASE A begin: LINEAR KNOWN PATTERN -> "
                   "C3D_SyncDisplayTransfer OUT_TILED");
            citadel_gpu_phase_a_logged = true;
        }

        citadel_gpu_fill_linear_diagnostic();
        citadel_gpu_transfer_staging();
        return true;
    }

    if (elapsed < 5000) {
        citadel_gpu_diagnostic_phase = 2;

        if (!citadel_gpu_phase_b_logged) {
            v5_log("GPU V14Z PHASE B begin: DIRECT 8x8 SOLID-TILE "
                   "TEXTURE WRITE; display transfer bypassed");
            citadel_gpu_phase_b_logged = true;
        }

        citadel_gpu_fill_direct_tile_diagnostic();
        return true;
    }

    citadel_gpu_diagnostic_phase = 3;

    if (!citadel_gpu_phase_c_logged) {
        v5_log("GPU V14Z PHASE C begin: NORMAL SHOCK V14Y "
               "UPLOAD RESUMED elapsed_ms=%lu",
               (unsigned long)elapsed);
        citadel_gpu_phase_c_logged = true;
    }

    memset(citadel_gpu_staging, 0, CITADEL_GPU_STAGING_BYTES);

    for (destination_y = 0;
         destination_y < CITADEL_GPU_CONTENT_HEIGHT;
         ++destination_y) {
        int source_y =
            (destination_y * source_height) /
            CITADEL_GPU_CONTENT_HEIGHT;
        const u8 *source_row;
        u16 *destination_row;
        int destination_x;

        if (source_y >= source_height)
            source_y = source_height - 1;

        source_row =
            source_pixels + (source_y * surface->pitch);
        destination_row =
            citadel_gpu_staging +
            (destination_y * CITADEL_GPU_TEXTURE_WIDTH);

        for (destination_x = 0;
             destination_x < CITADEL_GPU_CONTENT_WIDTH;
             ++destination_x) {
            int source_x =
                (destination_x * source_width) /
                CITADEL_GPU_CONTENT_WIDTH;
            u16 converted;

            if (source_x >= source_width)
                source_x = source_width - 1;

            converted =
                citadel_gpu_palette565[source_row[source_x]];
            destination_row[destination_x] = converted;

            if (((destination_x | destination_y) & 31) == 0) {
                diagnostic_hash ^= (uint32_t)converted;
                diagnostic_hash *= 16777619u;
            }
        }
    }

    citadel_gpu_transfer_staging();

    if (!citadel_gpu_first_upload_logged) {
        v5_log("GPU V14Z FIRST NORMAL UPLOAD src=%dx%d pitch=%d "
               "content=%dx%d texture=%dx%d filter=NEAREST "
               "hash=0x%08lX",
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


def replace_function(text: str, signature: str, replacement: str) -> str:
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
                    return text[:start] + replacement + text[i + 1:]
        i += 1

    raise RuntimeError(f"Unterminated function: {signature}")


def patch(text: str) -> str:
    if "PROJECT CITADEL V14Z" in text:
        raise RuntimeError("This source already appears to contain V14Z.")

    if "PROJECT CITADEL V14Y" not in text:
        raise RuntimeError(
            "V14Y marker not found. Start from the currently working "
            "V14Y Shock.c."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V14Y: 512x512 GPU transport correction is ACTIVE"',
        '#warning "PROJECT CITADEL V14Z: GPU tile lie detector is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V14Y.log", "GPU_C2D_V14Z.log")
    text = text.replace(
        "PROJECT CITADEL V14Y GPU TRANSPORT START",
        "PROJECT CITADEL V14Z GPU TILE LIE DETECTOR START",
    )
    text = text.replace(
        "GPU V14Y TRANSPORT ready",
        "GPU V14Z DIAGNOSTIC ready",
        1,
    )

    state_anchor = (
        "static int citadel_gpu_source_width = 0;\n"
        "static int citadel_gpu_source_height = 0;\n"
        "static bool citadel_gpu_first_upload_logged = false;"
    )
    state_replacement = state_anchor + r'''

/* V14Z automatic diagnostic timing and phase markers. */
static Uint32 citadel_gpu_diagnostic_started_at = 0;
static int citadel_gpu_diagnostic_phase = 0;
static bool citadel_gpu_phase_a_logged = false;
static bool citadel_gpu_phase_b_logged = false;
static bool citadel_gpu_phase_c_logged = false;'''

    if state_anchor not in text:
        raise RuntimeError("Could not locate the V14Y GPU state anchor.")
    text = text.replace(state_anchor, state_replacement, 1)

    text = replace_function(
        text,
        "static bool citadel_gpu_upload_surface(SDL_Surface *surface)",
        NEW_GPU_BLOCK,
    )

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
        print("  python apply_SS3DS_V14Z_GPU_tile_lie_detector.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V14Z: GPU tile lie detector is ACTIVE")
    print("Expected log:")
    print("  GPU_C2D_V14Z.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
