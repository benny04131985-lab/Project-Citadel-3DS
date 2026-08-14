#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V15D SOURCE VS MORTON TRUTH TEST
#
# Patches the working V15C source.
#
# For the first 3 seconds of real GPU presentation, V15D writes a detailed
# known per-pixel pattern through the exact live direct-Morton route.
#
# On the first normal Shock frame it also dumps the untouched CPU-side
# 640x480 indexed drawSurface to V15D_CPU_FRAME.ppm for inspection.
#
# This separates:
#   A) texture layout / per-pixel swizzle failure
#   B) corrupt or unexpected source surface before GPU upload

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V15D_source_vs_morton_truth_test.c")
BACKUP = Path("src/MacSrc/Shock_V15C_before_V15D.c")


NEW_UPLOAD_BLOCK = r'''/*
 * V15D detailed known-pattern generator.
 *
 * Unlike V14Z Phase B, every texel inside every 8x8 tile is intentionally
 * different. This tests the complete native Morton mapping, not merely the
 * outer physical-tile order.
 */
static void citadel_gpu_fill_detailed_morton_pattern(void)
{
    u16 *texture_pixels = (u16 *)citadel_gpu_texture.data;
    int y;

    memset(texture_pixels, 0, CITADEL_GPU_STAGING_BYTES);

    for (y = 0; y < CITADEL_GPU_CONTENT_HEIGHT; ++y) {
        int x;

        for (x = 0; x < CITADEL_GPU_CONTENT_WIDTH; ++x) {
            const unsigned int local_x = (unsigned int)x & 7u;
            const unsigned int local_y = (unsigned int)y & 7u;
            unsigned int r5 = (local_x * 31u) / 7u;
            unsigned int g6 = (local_y * 63u) / 7u;
            unsigned int b5 =
                (((unsigned int)(x >> 3) ^
                  (unsigned int)(y >> 3)) & 1u) ? 31u : 0u;
            u16 color;

            /*
             * Large quadrant identity remains visible even after scaling.
             * The local 8x8 gradient/checker pattern tests pixel ordering.
             */
            if (x < CITADEL_GPU_CONTENT_WIDTH / 2 &&
                y < CITADEL_GPU_CONTENT_HEIGHT / 2) {
                r5 = 31u;
                g6 = (local_y * 63u) / 7u;
            } else if (x >= CITADEL_GPU_CONTENT_WIDTH / 2 &&
                       y < CITADEL_GPU_CONTENT_HEIGHT / 2) {
                g6 = 63u;
                b5 = (local_x * 31u) / 7u;
            } else if (x < CITADEL_GPU_CONTENT_WIDTH / 2) {
                b5 = 31u;
                r5 = (local_y * 31u) / 7u;
            } else {
                r5 = (local_x * 31u) / 7u;
                g6 = (local_y * 63u) / 7u;
                b5 = 31u;
            }

            /* White 32-pixel grid and two black diagonals. */
            if ((x & 31) == 0 || (y & 31) == 0) {
                r5 = 31u;
                g6 = 63u;
                b5 = 31u;
            }

            if (x == y ||
                x == (CITADEL_GPU_CONTENT_WIDTH - 1 - y)) {
                r5 = 0u;
                g6 = 0u;
                b5 = 0u;
            }

            color = (u16)((r5 << 11) | (g6 << 5) | b5);

            texture_pixels[
                citadel_gpu_tiled_offset(
                    (unsigned int)x,
                    (unsigned int)y)
            ] = color;
        }
    }

    GSPGPU_FlushDataCache(citadel_gpu_texture.data,
                          CITADEL_GPU_STAGING_BYTES);
}

/*
 * Save exactly what the CPU software renderer produced before conversion,
 * scaling, tiling, texture caching, UVs, or Citro2D composition.
 *
 * PPM P6 is used because it needs no additional image library.
 */
static bool citadel_gpu_dump_cpu_frame_ppm(SDL_Surface *surface)
{
    FILE *file;
    unsigned char row[CITADEL_REF_WIDTH * 3];
    int width;
    int height;
    int y;

    if (surface == NULL ||
        surface->pixels == NULL ||
        surface->format == NULL ||
        surface->format->BytesPerPixel != 1)
        return false;

    width = surface->w;
    height = surface->h;

    if (width <= 0 ||
        height <= 0 ||
        width > CITADEL_REF_WIDTH)
        return false;

    file = fopen("V15D_CPU_FRAME.ppm", "wb");
    if (file == NULL)
        return false;

    fprintf(file, "P6\n%d %d\n255\n", width, height);

    for (y = 0; y < height; ++y) {
        const u8 *source_row =
            (const u8 *)surface->pixels +
            (y * surface->pitch);
        int x;

        for (x = 0; x < width; ++x) {
            SDL_Color color = gamePalette[source_row[x]];

            row[x * 3 + 0] = color.r;
            row[x * 3 + 1] = color.g;
            row[x * 3 + 2] = color.b;
        }

        if (fwrite(row, 3, (size_t)width, file) !=
            (size_t)width) {
            fclose(file);
            return false;
        }
    }

    fclose(file);
    return true;
}

static bool citadel_gpu_upload_surface(SDL_Surface *surface)
{
    int source_width;
    int source_height;
    const u8 *source_pixels;
    u16 *texture_pixels;
    uint32_t diagnostic_hash = 2166136261u;
    Uint32 now;
    Uint32 elapsed;
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

    now = SDL_GetTicks();

    if (citadel_gpu_v15d_started_at == 0)
        citadel_gpu_v15d_started_at = now;

    elapsed = now - citadel_gpu_v15d_started_at;

    /*
     * First three seconds: complete per-pixel direct-Morton diagnostic.
     */
    if (elapsed < 3000) {
        if (!citadel_gpu_v15d_pattern_logged) {
            v5_log("GPU V15D PHASE A begin: DETAILED PER-PIXEL "
                   "KNOWN PATTERN -> DIRECT 8x8 MORTON TEXTURE");
            citadel_gpu_v15d_pattern_logged = true;
        }

        citadel_gpu_fill_detailed_morton_pattern();
        return true;
    }

    /*
     * Before modifying or converting the first normal frame, preserve the
     * untouched CPU-side drawSurface as a PPM file.
     */
    if (!citadel_gpu_v15d_source_dump_attempted) {
        bool dump_ok;

        citadel_gpu_v15d_source_dump_attempted = true;
        dump_ok = citadel_gpu_dump_cpu_frame_ppm(surface);

        v5_log("GPU V15D CPU SOURCE DUMP file=V15D_CPU_FRAME.ppm "
               "result=%d src=%dx%d pitch=%d",
               dump_ok ? 1 : 0,
               source_width,
               source_height,
               surface->pitch);
    }

    if (!citadel_gpu_v15d_live_logged) {
        v5_log("GPU V15D PHASE B begin: NORMAL LIVE DIRECT-MORTON "
               "UPLOAD elapsed_ms=%lu",
               (unsigned long)elapsed);
        citadel_gpu_v15d_live_logged = true;
    }

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
        v5_log("GPU V15D FIRST LIVE DIRECT UPLOAD src=%dx%d pitch=%d "
               "content=%dx%d texture=%dx%d tile=8x8 "
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


def replace_function_with_block(text: str,
                                signature: str,
                                replacement: str) -> str:
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
    if "PROJECT CITADEL V15D" in text:
        raise RuntimeError("This source already appears to contain V15D.")

    if "PROJECT CITADEL V15C" not in text:
        raise RuntimeError(
            "V15C marker not found. Start from the current V15C "
            "forced-cache-rebind Shock.c."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V15C: forced texture-cache rebind is ACTIVE"',
        '#warning "PROJECT CITADEL V15D: source-vs-Morton truth test is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V15C.log", "GPU_C2D_V15D.log")
    text = text.replace(
        "PROJECT CITADEL V15C FORCED TEXTURE-CACHE REBIND START",
        "PROJECT CITADEL V15D SOURCE VS MORTON TRUTH TEST START",
    )
    text = text.replace(
        "GPU V15C CACHE-INVALIDATED DIRECT TILED ready",
        "GPU V15D SOURCE-VS-MORTON DIAGNOSTIC ready",
        1,
    )
    text = text.replace(
        "GPU V15C SYNC ORDER confirmed",
        "GPU V15D SYNC ORDER confirmed",
    )
    text = text.replace(
        "GPU V15C CACHE REBIND active",
        "GPU V15D CACHE REBIND active",
    )

    state_anchor = "static bool citadel_gpu_cache_rebind_logged = false;"
    state_replacement = state_anchor + r'''

/* V15D diagnostic state. */
static Uint32 citadel_gpu_v15d_started_at = 0;
static bool citadel_gpu_v15d_pattern_logged = false;
static bool citadel_gpu_v15d_live_logged = false;
static bool citadel_gpu_v15d_source_dump_attempted = false;'''

    if state_anchor not in text:
        raise RuntimeError(
            "Could not locate V15C's cache-rebind state anchor."
        )
    text = text.replace(state_anchor, state_replacement, 1)

    text = replace_function_with_block(
        text,
        "static bool citadel_gpu_upload_surface(SDL_Surface *surface)",
        NEW_UPLOAD_BLOCK,
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
        print("  python apply_SS3DS_V15D_source_vs_morton_truth_test.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V15D: source-vs-Morton truth test is ACTIVE")
    print("Expected runtime log:")
    print("  GPU_C2D_V15D.log")
    print("Expected source capture:")
    print("  V15D_CPU_FRAME.ppm")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
