#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V14Y GPU TRANSPORT FIX
#
# Patches the working V14X/V14X-KEYFIX src/MacSrc/Shock.c while leaving all
# audio, input, gameplay, wrapper, and SDL lifecycle code unchanged.
#
# Default:
#     Creates Shock_3DS_V14Y_GPU_transport_fix.c as a preview.
#
# Install:
#     python apply_SS3DS_V14Y_GPU_transport_fix.py --install
#
# Install mode first creates:
#     src/MacSrc/Shock_V14X_GPU_before_V14Y.c

from __future__ import annotations

import argparse
from pathlib import Path
import re
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V14Y_GPU_transport_fix.c")
BACKUP = Path("src/MacSrc/Shock_V14X_GPU_before_V14Y.c")


NEW_MACROS = r'''#define CITADEL_GPU_TEXTURE_WIDTH    512
#define CITADEL_GPU_TEXTURE_HEIGHT   512

/*
 * V14Y transports the original 4:3 Shock frame as a 512x384 image inside a
 * 512x512 power-of-two texture. The unused lower 128 rows remain black.
 *
 * V14X used a 1024-pixel transfer stride. The successful-but-repeated visual
 * pattern on both LCDs proves that presentation worked while the shared tiled
 * texture was malformed. The conservative 512x512 path removes that variable.
 */
#define CITADEL_GPU_CONTENT_WIDTH    512
#define CITADEL_GPU_CONTENT_HEIGHT   384

#define CITADEL_GPU_TEXTURE_PIXELS \
    (CITADEL_GPU_TEXTURE_WIDTH * CITADEL_GPU_TEXTURE_HEIGHT)
#define CITADEL_GPU_STAGING_BYTES \
    (CITADEL_GPU_TEXTURE_PIXELS * sizeof(u16))'''


NEW_UPLOAD = r'''static bool citadel_gpu_upload_surface(SDL_Surface *surface)
{
    int source_width;
    int source_height;
    int destination_y;
    const u8 *source_pixels;
    uint32_t diagnostic_hash = 2166136261u;

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

    /*
     * Clear the complete texture every frame. This prevents unused rows,
     * columns, or a prior mode from surviving into the next upload.
     */
    memset(citadel_gpu_staging, 0, CITADEL_GPU_STAGING_BYTES);

    /*
     * Keep exactly one System Shock software render. While converting the
     * indexed pixels to RGB565, presentation-resample the current frame into
     * the 512x384 transport rectangle.
     */
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

            /*
             * Lightweight first-frame signature. It proves the converted
             * transport contains changing game data without logging pixels.
             */
            if (((destination_x | destination_y) & 31) == 0) {
                diagnostic_hash ^= (uint32_t)converted;
                diagnostic_hash *= 16777619u;
            }
        }
    }

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

    if (!citadel_gpu_first_upload_logged) {
        v5_log("GPU V14Y FIRST UPLOAD src=%dx%d pitch=%d "
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


NEW_DRAW = r'''static bool citadel_gpu_draw_region(int source_x,
                                    int source_y,
                                    int source_w,
                                    int source_h,
                                    float destination_x,
                                    float destination_y,
                                    float destination_w,
                                    float destination_h,
                                    float depth)
{
    Tex3DS_SubTexture subtexture;
    C2D_Image image;
    C2D_DrawParams parameters;
    int source_right;
    int source_bottom;
    int texture_left;
    int texture_right;
    int texture_top;
    int texture_bottom;

    if (source_w <= 0 ||
        source_h <= 0 ||
        citadel_gpu_source_width <= 0 ||
        citadel_gpu_source_height <= 0)
        return false;

    if (source_x < 0)
        source_x = 0;
    if (source_y < 0)
        source_y = 0;

    source_right = source_x + source_w;
    source_bottom = source_y + source_h;

    if (source_right > citadel_gpu_source_width)
        source_right = citadel_gpu_source_width;
    if (source_bottom > citadel_gpu_source_height)
        source_bottom = citadel_gpu_source_height;

    if (source_right <= source_x || source_bottom <= source_y)
        return false;

    /*
     * Translate the original Shock-space crop into the 512x384 transport
     * rectangle. Round the far edges upward so the final source row/column
     * cannot disappear because of integer truncation.
     */
    texture_left =
        (source_x * CITADEL_GPU_CONTENT_WIDTH) /
        citadel_gpu_source_width;
    texture_top =
        (source_y * CITADEL_GPU_CONTENT_HEIGHT) /
        citadel_gpu_source_height;

    texture_right =
        ((source_right * CITADEL_GPU_CONTENT_WIDTH) +
         citadel_gpu_source_width - 1) /
        citadel_gpu_source_width;
    texture_bottom =
        ((source_bottom * CITADEL_GPU_CONTENT_HEIGHT) +
         citadel_gpu_source_height - 1) /
        citadel_gpu_source_height;

    if (texture_left < 0)
        texture_left = 0;
    if (texture_top < 0)
        texture_top = 0;
    if (texture_right > CITADEL_GPU_CONTENT_WIDTH)
        texture_right = CITADEL_GPU_CONTENT_WIDTH;
    if (texture_bottom > CITADEL_GPU_CONTENT_HEIGHT)
        texture_bottom = CITADEL_GPU_CONTENT_HEIGHT;

    if (texture_right <= texture_left ||
        texture_bottom <= texture_top)
        return false;

    memset(&subtexture, 0, sizeof(subtexture));
    memset(&parameters, 0, sizeof(parameters));

    subtexture.width =
        (u16)(texture_right - texture_left);
    subtexture.height =
        (u16)(texture_bottom - texture_top);

    subtexture.left =
        (float)texture_left /
        (float)CITADEL_GPU_TEXTURE_WIDTH;
    subtexture.right =
        (float)texture_right /
        (float)CITADEL_GPU_TEXTURE_WIDTH;

    /*
     * Preserve V14X's confirmed orientation. Only the underlying transport
     * dimensions and Shock-to-transport mapping change in V14Y.
     */
    subtexture.top =
        1.0f -
        ((float)texture_top /
         (float)CITADEL_GPU_TEXTURE_HEIGHT);
    subtexture.bottom =
        1.0f -
        ((float)texture_bottom /
         (float)CITADEL_GPU_TEXTURE_HEIGHT);

    image.tex = &citadel_gpu_texture;
    image.subtex = &subtexture;

    parameters.pos.x = destination_x;
    parameters.pos.y = destination_y;
    parameters.pos.w = destination_w;
    parameters.pos.h = destination_h;
    parameters.center.x = 0.0f;
    parameters.center.y = 0.0f;
    parameters.depth = depth;
    parameters.angle = 0.0f;

    if (!C2D_DrawImage(image, &parameters, NULL)) {
        ++citadel_gpu_draw_failures;
        return false;
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
                    end = i + 1
                    return text[:start] + replacement + text[end:]
        i += 1

    raise RuntimeError(f"Unterminated function: {signature}")


def patch(text: str) -> str:
    if "PROJECT CITADEL V14Y" in text:
        raise RuntimeError("This source already appears to contain V14Y.")

    if "PROJECT CITADEL V14X" not in text:
        raise RuntimeError(
            "V14X marker not found. Start from the working "
            "Shock_3DS_V14X_GPU_fullsend_KEYFIX.c build."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V14X: Citro2D GPU full-send compositor is ACTIVE"',
        '#warning "PROJECT CITADEL V14Y: 512x512 GPU transport correction is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V14X.log", "GPU_C2D_V14Y.log")
    text = text.replace(
        "PROJECT CITADEL V14X GPU FULL-SEND START",
        "PROJECT CITADEL V14Y GPU TRANSPORT START",
    )

    macro_pattern = re.compile(
        r"#define CITADEL_GPU_TEXTURE_WIDTH\s+1024\s*\n"
        r"#define CITADEL_GPU_TEXTURE_HEIGHT\s+512\s*\n"
        r"#define CITADEL_GPU_TEXTURE_PIXELS\s*\\\s*\n"
        r"\s*\(CITADEL_GPU_TEXTURE_WIDTH \* CITADEL_GPU_TEXTURE_HEIGHT\)\s*\n"
        r"#define CITADEL_GPU_STAGING_BYTES\s*\\\s*\n"
        r"\s*\(CITADEL_GPU_TEXTURE_PIXELS \* sizeof\(u16\)\)"
    )
    text, count = macro_pattern.subn(NEW_MACROS, text, count=1)
    if count != 1:
        raise RuntimeError("Could not replace the V14X GPU dimension block.")

    counter_anchor = (
        "static unsigned int citadel_gpu_presented_frames = 0;\n"
        "static unsigned int citadel_gpu_upload_failures = 0;\n"
        "static unsigned int citadel_gpu_draw_failures = 0;"
    )
    counter_replacement = counter_anchor + r'''

/* V14Y: current Shock surface dimensions used for crop remapping. */
static int citadel_gpu_source_width = 0;
static int citadel_gpu_source_height = 0;
static bool citadel_gpu_first_upload_logged = false;'''
    if counter_anchor not in text:
        raise RuntimeError("Could not locate the V14X GPU counter block.")
    text = text.replace(counter_anchor, counter_replacement, 1)

    filter_pattern = re.compile(
        r"C3D_TexSetFilter\(&citadel_gpu_texture,\s*"
        r"GPU_LINEAR,\s*GPU_LINEAR\);"
    )
    text, count = filter_pattern.subn(
        "C3D_TexSetFilter(&citadel_gpu_texture,\n"
        "                     GPU_NEAREST,\n"
        "                     GPU_NEAREST);",
        text,
        count=1,
    )
    if count != 1:
        raise RuntimeError("Could not replace the V14X texture filter.")

    text = replace_function(
        text,
        "static bool citadel_gpu_upload_surface(SDL_Surface *surface)",
        NEW_UPLOAD,
    )
    text = replace_function(
        text,
        "static bool citadel_gpu_draw_region(int source_x,",
        NEW_DRAW,
    )

    init_marker = "    citadel_gpu_ready = true;\n    atexit(citadel_gpu_shutdown);"
    init_replacement = init_marker + r'''

    v5_log("GPU V14Y TRANSPORT ready texture=%dx%d content=%dx%d "
           "source-resample=nearest filter=NEAREST",
           CITADEL_GPU_TEXTURE_WIDTH,
           CITADEL_GPU_TEXTURE_HEIGHT,
           CITADEL_GPU_CONTENT_WIDTH,
           CITADEL_GPU_CONTENT_HEIGHT);'''
    if init_marker not in text:
        raise RuntimeError("Could not locate the GPU-ready initialization marker.")
    text = text.replace(init_marker, init_replacement, 1)

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
        print("Source was not changed.")
        print("Review the preview, then install with:")
        print("  python apply_SS3DS_V14Y_GPU_transport_fix.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V14Y: 512x512 GPU transport correction is ACTIVE")
    print("Expected runtime log:")
    print("  GPU_C2D_V14Y.log")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
