#!/usr/bin/env python3
# PROJECT CITADEL 3DS — V15F FROZEN FRAME ROUNDTRIP
#
# Patches the working V15E source.
#
# V15F captures one real frame after roughly three seconds, then:
#   1. builds a linear 512x384 RGB565 image;
#   2. writes V15F_LINEAR_FRAME.ppm;
#   3. swizzles that image into the C3D texture;
#   4. reads the texture back through the inverse address lookup;
#   5. writes V15F_ROUNDTRIP_FRAME.ppm;
#   6. writes V15F_TEXTURE_TILED_RGB565.bin;
#   7. displays the frozen texture for seven seconds using one persistent
#      Tex3DS_SubTexture and one persistent C2D_Image.
#
# After the diagnostic hold, ordinary V15E live presentation resumes.

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys


SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V15F_frozen_frame_roundtrip.c")
BACKUP = Path("src/MacSrc/Shock_V15E_before_V15F.c")


NEW_UPLOAD_AND_HELPERS = r'''/*
 * Write an RGB565 image to a binary PPM file.
 *
 * Pixels are supplied in ordinary top-origin row-major order.
 */
static bool citadel_gpu_write_rgb565_ppm(const char *path,
                                         const u16 *pixels,
                                         int width,
                                         int height,
                                         int pitch_pixels)
{
    FILE *file;
    unsigned char row[CITADEL_GPU_CONTENT_WIDTH * 3];
    int y;

    if (path == NULL ||
        pixels == NULL ||
        width <= 0 ||
        height <= 0 ||
        width > CITADEL_GPU_CONTENT_WIDTH ||
        pitch_pixels < width)
        return false;

    file = fopen(path, "wb");
    if (file == NULL)
        return false;

    fprintf(file, "P6\n%d %d\n255\n", width, height);

    for (y = 0; y < height; ++y) {
        const u16 *source_row =
            pixels + ((size_t)y * (size_t)pitch_pixels);
        int x;

        for (x = 0; x < width; ++x) {
            const u16 value = source_row[x];
            const unsigned int r5 =
                (unsigned int)((value >> 11) & 0x1F);
            const unsigned int g6 =
                (unsigned int)((value >> 5) & 0x3F);
            const unsigned int b5 =
                (unsigned int)(value & 0x1F);

            row[x * 3 + 0] =
                (unsigned char)((r5 * 255u + 15u) / 31u);
            row[x * 3 + 1] =
                (unsigned char)((g6 * 255u + 31u) / 63u);
            row[x * 3 + 2] =
                (unsigned char)((b5 * 255u + 15u) / 31u);
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

/*
 * Read the current tiled texture through the same coordinate-address lookup
 * used for writing and export the reconstructed top-origin image.
 *
 * This does not assume texture rows are contiguous in memory.
 */
static bool citadel_gpu_write_roundtrip_ppm(const char *path)
{
    FILE *file;
    const u16 *texture_pixels =
        (const u16 *)citadel_gpu_texture.data;
    unsigned char row[CITADEL_GPU_CONTENT_WIDTH * 3];
    int y;

    if (path == NULL || texture_pixels == NULL)
        return false;

    file = fopen(path, "wb");
    if (file == NULL)
        return false;

    fprintf(file,
            "P6\n%d %d\n255\n",
            CITADEL_GPU_CONTENT_WIDTH,
            CITADEL_GPU_CONTENT_HEIGHT);

    for (y = 0; y < CITADEL_GPU_CONTENT_HEIGHT; ++y) {
        int x;

        for (x = 0; x < CITADEL_GPU_CONTENT_WIDTH; ++x) {
            const size_t offset =
                citadel_gpu_tiled_offset(
                    (unsigned int)x,
                    (unsigned int)y);
            const u16 value = texture_pixels[offset];
            const unsigned int r5 =
                (unsigned int)((value >> 11) & 0x1F);
            const unsigned int g6 =
                (unsigned int)((value >> 5) & 0x3F);
            const unsigned int b5 =
                (unsigned int)(value & 0x1F);

            row[x * 3 + 0] =
                (unsigned char)((r5 * 255u + 15u) / 31u);
            row[x * 3 + 1] =
                (unsigned char)((g6 * 255u + 31u) / 63u);
            row[x * 3 + 2] =
                (unsigned char)((b5 * 255u + 15u) / 31u);
        }

        if (fwrite(row,
                   3,
                   (size_t)CITADEL_GPU_CONTENT_WIDTH,
                   file) !=
            (size_t)CITADEL_GPU_CONTENT_WIDTH) {
            fclose(file);
            return false;
        }
    }

    fclose(file);
    return true;
}

static bool citadel_gpu_write_tiled_binary(const char *path)
{
    FILE *file;
    size_t written;

    if (path == NULL || citadel_gpu_texture.data == NULL)
        return false;

    file = fopen(path, "wb");
    if (file == NULL)
        return false;

    written = fwrite(citadel_gpu_texture.data,
                     1,
                     CITADEL_GPU_STAGING_BYTES,
                     file);
    fclose(file);

    return written == CITADEL_GPU_STAGING_BYTES;
}

/*
 * Convert the current indexed Shock surface into an ordinary linear
 * 512x384 RGB565 image inside citadel_gpu_staging.
 */
static uint32_t citadel_gpu_build_linear_frame(SDL_Surface *surface)
{
    const u8 *source_pixels =
        (const u8 *)surface->pixels;
    uint32_t hash = 2166136261u;
    int destination_y;

    memset(citadel_gpu_staging,
           0,
           CITADEL_GPU_STAGING_BYTES);

    for (destination_y = 0;
         destination_y < CITADEL_GPU_CONTENT_HEIGHT;
         ++destination_y) {
        int source_y =
            (destination_y * surface->h) /
            CITADEL_GPU_CONTENT_HEIGHT;
        const u8 *source_row;
        u16 *destination_row;
        int destination_x;

        if (source_y >= surface->h)
            source_y = surface->h - 1;

        source_row =
            source_pixels +
            ((size_t)source_y * (size_t)surface->pitch);
        destination_row =
            citadel_gpu_staging +
            ((size_t)destination_y *
             (size_t)CITADEL_GPU_TEXTURE_WIDTH);

        for (destination_x = 0;
             destination_x < CITADEL_GPU_CONTENT_WIDTH;
             ++destination_x) {
            int source_x =
                (destination_x * surface->w) /
                CITADEL_GPU_CONTENT_WIDTH;
            u16 converted;

            if (source_x >= surface->w)
                source_x = surface->w - 1;

            converted =
                citadel_gpu_palette565[source_row[source_x]];
            destination_row[destination_x] = converted;

            hash ^= (uint32_t)converted;
            hash *= 16777619u;
        }
    }

    return hash;
}

/*
 * Swizzle the complete linear staging image into the live C3D texture.
 */
static void citadel_gpu_swizzle_staging_to_texture(void)
{
    u16 *texture_pixels =
        (u16 *)citadel_gpu_texture.data;
    int y;

    memset(texture_pixels, 0, CITADEL_GPU_STAGING_BYTES);

    for (y = 0; y < CITADEL_GPU_CONTENT_HEIGHT; ++y) {
        const u16 *source_row =
            citadel_gpu_staging +
            ((size_t)y *
             (size_t)CITADEL_GPU_TEXTURE_WIDTH);
        int x;

        for (x = 0; x < CITADEL_GPU_CONTENT_WIDTH; ++x) {
            texture_pixels[
                citadel_gpu_tiled_offset(
                    (unsigned int)x,
                    (unsigned int)y)
            ] = source_row[x];
        }
    }

    GSPGPU_FlushDataCache(citadel_gpu_texture.data,
                          CITADEL_GPU_STAGING_BYTES);
}

/*
 * Compare the linear staging image with the texture reconstructed through
 * citadel_gpu_tiled_offset(). Return the mismatch count and optionally report
 * the first differing coordinate and values.
 */
static unsigned long citadel_gpu_compare_roundtrip(
    int *first_x,
    int *first_y,
    u16 *first_linear,
    u16 *first_tiled)
{
    const u16 *texture_pixels =
        (const u16 *)citadel_gpu_texture.data;
    unsigned long mismatches = 0;
    int y;

    if (first_x != NULL)
        *first_x = -1;
    if (first_y != NULL)
        *first_y = -1;
    if (first_linear != NULL)
        *first_linear = 0;
    if (first_tiled != NULL)
        *first_tiled = 0;

    for (y = 0; y < CITADEL_GPU_CONTENT_HEIGHT; ++y) {
        const u16 *linear_row =
            citadel_gpu_staging +
            ((size_t)y *
             (size_t)CITADEL_GPU_TEXTURE_WIDTH);
        int x;

        for (x = 0; x < CITADEL_GPU_CONTENT_WIDTH; ++x) {
            const u16 linear_value = linear_row[x];
            const u16 tiled_value =
                texture_pixels[
                    citadel_gpu_tiled_offset(
                        (unsigned int)x,
                        (unsigned int)y)
                ];

            if (linear_value != tiled_value) {
                if (mismatches == 0) {
                    if (first_x != NULL)
                        *first_x = x;
                    if (first_y != NULL)
                        *first_y = y;
                    if (first_linear != NULL)
                        *first_linear = linear_value;
                    if (first_tiled != NULL)
                        *first_tiled = tiled_value;
                }

                ++mismatches;
            }
        }
    }

    return mismatches;
}

static void citadel_gpu_prepare_frozen_image(void)
{
    memset(&citadel_gpu_v15f_subtexture,
           0,
           sizeof(citadel_gpu_v15f_subtexture));

    citadel_gpu_v15f_subtexture.width =
        (u16)CITADEL_GPU_CONTENT_WIDTH;
    citadel_gpu_v15f_subtexture.height =
        (u16)CITADEL_GPU_CONTENT_HEIGHT;
    citadel_gpu_v15f_subtexture.left = 0.0f;
    citadel_gpu_v15f_subtexture.right =
        (float)CITADEL_GPU_CONTENT_WIDTH /
        (float)CITADEL_GPU_TEXTURE_WIDTH;
    citadel_gpu_v15f_subtexture.top = 1.0f;
    citadel_gpu_v15f_subtexture.bottom =
        1.0f -
        ((float)CITADEL_GPU_CONTENT_HEIGHT /
         (float)CITADEL_GPU_TEXTURE_HEIGHT);

    citadel_gpu_v15f_image.tex =
        &citadel_gpu_texture;
    citadel_gpu_v15f_image.subtex =
        &citadel_gpu_v15f_subtexture;
}

static bool citadel_gpu_upload_surface(SDL_Surface *surface)
{
    Uint32 now;
    Uint32 elapsed;
    uint32_t linear_hash;
    unsigned int palette_mismatches;

    if (surface == NULL ||
        surface->pixels == NULL ||
        surface->format == NULL ||
        surface->format->BytesPerPixel != 1 ||
        surface->w <= 0 ||
        surface->h <= 0 ||
        citadel_gpu_staging == NULL ||
        !citadel_gpu_texture_initialized ||
        citadel_gpu_texture.data == NULL) {
        ++citadel_gpu_upload_failures;
        return false;
    }

    citadel_gpu_source_width = surface->w;
    citadel_gpu_source_height = surface->h;

    now = SDL_GetTicks();

    if (citadel_gpu_v15f_started_at == 0)
        citadel_gpu_v15f_started_at = now;

    /*
     * During the seven-second hold, do not touch the captured texture.
     */
    if (citadel_gpu_v15f_freeze_active) {
        if ((Sint32)(now - citadel_gpu_v15f_freeze_until) < 0)
            return true;

        citadel_gpu_v15f_freeze_active = false;

        if (!citadel_gpu_v15f_resume_logged) {
            v5_log("GPU V15F FROZEN HOLD complete; "
                   "normal live upload resumed");
            citadel_gpu_v15f_resume_logged = true;
        }
    }

    palette_mismatches =
        citadel_gpu_refresh_palette565();

    linear_hash =
        citadel_gpu_build_linear_frame(surface);
    citadel_gpu_swizzle_staging_to_texture();

    elapsed = now - citadel_gpu_v15f_started_at;

    /*
     * Capture one real frame after roughly three seconds. V15D showed that
     * this timing generally lands on a complete Origin/logo frame.
     */
    if (!citadel_gpu_v15f_capture_done &&
        elapsed >= 3000) {
        int first_x;
        int first_y;
        u16 first_linear;
        u16 first_tiled;
        unsigned long roundtrip_mismatches;
        bool linear_ppm_ok;
        bool roundtrip_ppm_ok;
        bool tiled_bin_ok;

        linear_ppm_ok =
            citadel_gpu_write_rgb565_ppm(
                "V15F_LINEAR_FRAME.ppm",
                citadel_gpu_staging,
                CITADEL_GPU_CONTENT_WIDTH,
                CITADEL_GPU_CONTENT_HEIGHT,
                CITADEL_GPU_TEXTURE_WIDTH);

        roundtrip_mismatches =
            citadel_gpu_compare_roundtrip(
                &first_x,
                &first_y,
                &first_linear,
                &first_tiled);

        roundtrip_ppm_ok =
            citadel_gpu_write_roundtrip_ppm(
                "V15F_ROUNDTRIP_FRAME.ppm");

        tiled_bin_ok =
            citadel_gpu_write_tiled_binary(
                "V15F_TEXTURE_TILED_RGB565.bin");

        citadel_gpu_prepare_frozen_image();

        citadel_gpu_v15f_capture_done = true;
        citadel_gpu_v15f_freeze_active = true;
        citadel_gpu_v15f_freeze_until =
            now + 7000;

        v5_log("GPU V15F CAPTURE elapsed_ms=%lu "
               "linear_ppm=%d roundtrip_ppm=%d tiled_bin=%d "
               "linear_hash=0x%08lX palette_mismatches=%u",
               (unsigned long)elapsed,
               linear_ppm_ok ? 1 : 0,
               roundtrip_ppm_ok ? 1 : 0,
               tiled_bin_ok ? 1 : 0,
               (unsigned long)linear_hash,
               palette_mismatches);

        v5_log("GPU V15F ROUNDTRIP mismatches=%lu "
               "first={x=%d y=%d linear=0x%04X tiled=0x%04X}",
               roundtrip_mismatches,
               first_x,
               first_y,
               (unsigned int)first_linear,
               (unsigned int)first_tiled);

        v5_log("GPU V15F FROZEN HOLD begin duration_ms=7000 "
               "draw=persistent-full-frame-C2D_Image");
    }

    if (!citadel_gpu_first_upload_logged) {
        v5_log("GPU V15F FIRST LIVE FEED src=%dx%d pitch=%d "
               "linear=%dx%d texture=%dx%d "
               "palette=AUTHORITATIVE_EVERY_FRAME "
               "initial_mismatches=%u hash=0x%08lX",
               surface->w,
               surface->h,
               surface->pitch,
               CITADEL_GPU_CONTENT_WIDTH,
               CITADEL_GPU_CONTENT_HEIGHT,
               CITADEL_GPU_TEXTURE_WIDTH,
               CITADEL_GPU_TEXTURE_HEIGHT,
               palette_mismatches,
               (unsigned long)linear_hash);
        citadel_gpu_first_upload_logged = true;
    }

    return true;
}'''


FROZEN_DRAW_BRANCH = r'''
    /*
     * V15F presentation isolation:
     *
     * During the diagnostic hold, bypass all dynamic Shock crop rectangles
     * and all stack-local subtexture descriptors. Draw the captured texture
     * through one persistent full-frame C2D_Image.
     */
    if (citadel_gpu_v15f_freeze_active) {
        C2D_DrawParams frozen_parameters;
        bool frozen_ok;

        memset(&frozen_parameters,
               0,
               sizeof(frozen_parameters));

        frozen_parameters.pos.x =
            (float)CITADEL_3DS_GAME_X;
        frozen_parameters.pos.y =
            (float)CITADEL_3DS_GAME_Y;
        frozen_parameters.pos.w =
            (float)CITADEL_3DS_GAME_WIDTH;
        frozen_parameters.pos.h =
            (float)CITADEL_3DS_GAME_HEIGHT;
        frozen_parameters.center.x = 0.0f;
        frozen_parameters.center.y = 0.0f;
        frozen_parameters.depth = 0.0f;
        frozen_parameters.angle = 0.0f;

        C2D_TargetClear(citadel_gpu_top_target,
                        C2D_Color32(0, 0, 0, 255));
        C2D_TargetClear(citadel_gpu_bottom_target,
                        C2D_Color32(0, 0, 0, 255));

        C2D_SceneBegin(citadel_gpu_top_target);

        frozen_ok =
            C2D_DrawImage(
                citadel_gpu_v15f_image,
                &frozen_parameters,
                NULL);

        if (!frozen_ok)
            ++citadel_gpu_draw_failures;

        C3D_FrameEnd(0);
        ++citadel_gpu_presented_frames;

        return frozen_ok;
    }

'''


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
    if "PROJECT CITADEL V15F" in text:
        raise RuntimeError("This source already appears to contain V15F.")

    if "PROJECT CITADEL V15E" not in text:
        raise RuntimeError(
            "V15E marker not found. Start from the current V15E "
            "authoritative-palette Shock.c."
        )

    text = text.replace(
        '#warning "PROJECT CITADEL V15E: authoritative palette sync is ACTIVE"',
        '#warning "PROJECT CITADEL V15F: frozen frame roundtrip is ACTIVE"',
        1,
    )
    text = text.replace("GPU_C2D_V15E.log", "GPU_C2D_V15F.log")
    text = text.replace(
        "PROJECT CITADEL V15E AUTHORITATIVE PALETTE SYNC START",
        "PROJECT CITADEL V15F FROZEN FRAME ROUNDTRIP START",
    )
    text = text.replace(
        "GPU V15E AUTHORITATIVE PALETTE ready",
        "GPU V15F FROZEN FRAME ROUNDTRIP ready",
        1,
    )
    text = text.replace(
        "GPU V15E SYNC ORDER confirmed",
        "GPU V15F SYNC ORDER confirmed",
    )
    text = text.replace(
        "GPU V15E CACHE REBIND active",
        "GPU V15F CACHE REBIND active",
    )
    text = text.replace(
        "GPU V15E PALETTE SYNC",
        "GPU V15F PALETTE SYNC",
    )

    state_anchor = (
        "static unsigned long citadel_gpu_palette_refreshes = 0;\n"
        "static unsigned int citadel_gpu_palette_change_logs = 0;"
    )

    state_replacement = state_anchor + r'''

/* V15F frozen-frame and persistent-image diagnostic state. */
static Uint32 citadel_gpu_v15f_started_at = 0;
static Uint32 citadel_gpu_v15f_freeze_until = 0;
static bool citadel_gpu_v15f_capture_done = false;
static bool citadel_gpu_v15f_freeze_active = false;
static bool citadel_gpu_v15f_resume_logged = false;
static Tex3DS_SubTexture citadel_gpu_v15f_subtexture;
static C2D_Image citadel_gpu_v15f_image;'''

    if state_anchor not in text:
        raise RuntimeError(
            "Could not locate V15E's palette instrumentation state."
        )
    text = text.replace(state_anchor, state_replacement, 1)

    upload_start = text.find(
        "static bool citadel_gpu_upload_surface(SDL_Surface *surface)"
    )
    if upload_start < 0:
        raise RuntimeError(
            "Could not locate V15E's live upload function."
        )

    upload_end = function_end(
        text,
        "static bool citadel_gpu_upload_surface(SDL_Surface *surface)",
    )

    text = (
        text[:upload_start] +
        NEW_UPLOAD_AND_HELPERS +
        text[upload_end:]
    )

    # Insert the persistent frozen draw immediately after the magenta
    # branch and before ordinary split/legacy layout selection.
    present_anchor = (
        "    split_layout = citadel_3ds_use_split_layout();"
    )

    if present_anchor not in text:
        raise RuntimeError(
            "Could not locate the ordinary layout-selection anchor in "
            "citadel_gpu_present()."
        )

    text = text.replace(
        present_anchor,
        FROZEN_DRAW_BRANCH + present_anchor,
        1,
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
        print("  python apply_SS3DS_V15F_frozen_frame_roundtrip.py --install")

    print()
    print("Expected compiler marker:")
    print("  PROJECT CITADEL V15F: frozen frame roundtrip is ACTIVE")
    print("Expected runtime log:")
    print("  GPU_C2D_V15F.log")
    print("Expected diagnostic files:")
    print("  V15F_LINEAR_FRAME.ppm")
    print("  V15F_ROUNDTRIP_FRAME.ppm")
    print("  V15F_TEXTURE_TILED_RGB565.bin")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
