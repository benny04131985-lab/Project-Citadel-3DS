#!/usr/bin/env python3
"""Project Citadel 3DS V15G fresh texture binding diagnostic.

Run from the Shockolate project root.

Preview:
    python apply_SS3DS_V15G_fresh_texture_binding.py

Install:
    python apply_SS3DS_V15G_fresh_texture_binding.py --install
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import sys

SOURCE = Path("src/MacSrc/Shock.c")
PREVIEW = Path("Shock_3DS_V15G_fresh_texture_binding.c")
BACKUP = Path("src/MacSrc/Shock_V15F_before_V15G.c")

STATE_INSERT = '\n/* V15G fresh texture object / format-control diagnostic state. */\n#define CITADEL_GPU_RGBA8_BYTES \\\n    (CITADEL_GPU_TEXTURE_PIXELS * sizeof(u32))\n\nenum {\n    CITADEL_V15G_PHASE_LIVE = 0,\n    CITADEL_V15G_PHASE_FRESH_RGB565 = 1,\n    CITADEL_V15G_PHASE_FRESH_RGBA8 = 2,\n    CITADEL_V15G_PHASE_COMPLETE = 3\n};\n\nstatic C3D_Tex citadel_gpu_v15g_rgb565_texture;\nstatic C3D_Tex citadel_gpu_v15g_rgba8_texture;\nstatic bool citadel_gpu_v15g_rgb565_initialized = false;\nstatic bool citadel_gpu_v15g_rgba8_initialized = false;\nstatic u32 *citadel_gpu_v15g_rgba8_staging = NULL;\n\nstatic Tex3DS_SubTexture citadel_gpu_v15g_subtexture;\nstatic C2D_Image citadel_gpu_v15g_rgb565_image;\nstatic C2D_Image citadel_gpu_v15g_rgba8_image;\n\nstatic Uint32 citadel_gpu_v15g_started_at = 0;\nstatic Uint32 citadel_gpu_v15g_phase_until = 0;\nstatic int citadel_gpu_v15g_phase = CITADEL_V15G_PHASE_LIVE;\nstatic bool citadel_gpu_v15g_capture_done = false;\n'
HELPERS = '\nstatic bool citadel_gpu_v15g_phase_active(void)\n{\n    return citadel_gpu_v15g_phase ==\n               CITADEL_V15G_PHASE_FRESH_RGB565 ||\n           citadel_gpu_v15g_phase ==\n               CITADEL_V15G_PHASE_FRESH_RGBA8;\n}\n\nstatic const char *citadel_gpu_v15g_phase_name(int phase)\n{\n    switch (phase) {\n        case CITADEL_V15G_PHASE_FRESH_RGB565:\n            return "FRESH_RGB565";\n        case CITADEL_V15G_PHASE_FRESH_RGBA8:\n            return "FRESH_RGBA8";\n        case CITADEL_V15G_PHASE_COMPLETE:\n            return "COMPLETE";\n        default:\n            return "LIVE";\n    }\n}\n\nstatic uint32_t citadel_gpu_v15g_hash_bytes(const void *data,\n                                             size_t size)\n{\n    const u8 *bytes = (const u8 *)data;\n    uint32_t hash = 2166136261u;\n    size_t i;\n\n    if (bytes == NULL)\n        return 0;\n\n    for (i = 0; i < size; ++i) {\n        hash ^= (uint32_t)bytes[i];\n        hash *= 16777619u;\n    }\n\n    return hash;\n}\n\nstatic void citadel_gpu_v15g_log_texture(const char *label,\n                                         C3D_Tex *texture)\n{\n    u32 physical = 0;\n\n    if (texture != NULL && texture->data != NULL)\n        physical = osConvertVirtToPhys(texture->data);\n\n    if (texture == NULL) {\n        v5_log("GPU V15G TEX %s NULL",\n               label != NULL ? label : "(null)");\n        return;\n    }\n\n    v5_log("GPU V15G TEX %s data=%p phys=0x%08lX "\n           "width=%u height=%u fmt=%u size=%lu "\n           "dim=0x%08lX param=0x%08lX lod=0x%08lX type=%u",\n           label != NULL ? label : "(null)",\n           texture->data,\n           (unsigned long)physical,\n           (unsigned int)texture->width,\n           (unsigned int)texture->height,\n           (unsigned int)texture->fmt,\n           (unsigned long)texture->size,\n           (unsigned long)texture->dim,\n           (unsigned long)texture->param,\n           (unsigned long)texture->lodParam,\n           (unsigned int)C3D_TexGetType(texture));\n}\n\nstatic void citadel_gpu_v15g_prepare_images(void)\n{\n    memset(&citadel_gpu_v15g_subtexture,\n           0,\n           sizeof(citadel_gpu_v15g_subtexture));\n\n    citadel_gpu_v15g_subtexture.width =\n        (u16)CITADEL_GPU_CONTENT_WIDTH;\n    citadel_gpu_v15g_subtexture.height =\n        (u16)CITADEL_GPU_CONTENT_HEIGHT;\n    citadel_gpu_v15g_subtexture.left = 0.0f;\n    citadel_gpu_v15g_subtexture.right =\n        (float)CITADEL_GPU_CONTENT_WIDTH /\n        (float)CITADEL_GPU_TEXTURE_WIDTH;\n    citadel_gpu_v15g_subtexture.top = 1.0f;\n    citadel_gpu_v15g_subtexture.bottom =\n        1.0f -\n        ((float)CITADEL_GPU_CONTENT_HEIGHT /\n         (float)CITADEL_GPU_TEXTURE_HEIGHT);\n\n    citadel_gpu_v15g_rgb565_image.tex =\n        &citadel_gpu_v15g_rgb565_texture;\n    citadel_gpu_v15g_rgb565_image.subtex =\n        &citadel_gpu_v15g_subtexture;\n\n    citadel_gpu_v15g_rgba8_image.tex =\n        &citadel_gpu_v15g_rgba8_texture;\n    citadel_gpu_v15g_rgba8_image.subtex =\n        &citadel_gpu_v15g_subtexture;\n}\n\n/*\n * Convert V15F\'s proven linear RGB565 frame into tex3ds-compatible RGBA8\n * bytes. tex3ds stores one RGBA8 texel as A, B, G, R bytes; writing the\n * little-endian u32 value 0xRRGGBBAA produces exactly that byte sequence.\n */\nstatic void citadel_gpu_v15g_build_rgba8_staging(void)\n{\n    int y;\n\n    memset(citadel_gpu_v15g_rgba8_staging,\n           0,\n           CITADEL_GPU_RGBA8_BYTES);\n\n    for (y = 0; y < CITADEL_GPU_CONTENT_HEIGHT; ++y) {\n        const u16 *source_row =\n            citadel_gpu_staging +\n            ((size_t)y *\n             (size_t)CITADEL_GPU_TEXTURE_WIDTH);\n        int x;\n\n        for (x = 0; x < CITADEL_GPU_CONTENT_WIDTH; ++x) {\n            const u16 value = source_row[x];\n            const unsigned int r5 =\n                (unsigned int)((value >> 11) & 0x1F);\n            const unsigned int g6 =\n                (unsigned int)((value >> 5) & 0x3F);\n            const unsigned int b5 =\n                (unsigned int)(value & 0x1F);\n            const unsigned int r8 =\n                (r5 << 3) | (r5 >> 2);\n            const unsigned int g8 =\n                (g6 << 2) | (g6 >> 4);\n            const unsigned int b8 =\n                (b5 << 3) | (b5 >> 2);\n            const size_t offset =\n                citadel_gpu_tiled_offset(\n                    (unsigned int)x,\n                    (unsigned int)y);\n\n            citadel_gpu_v15g_rgba8_staging[offset] =\n                ((u32)r8 << 24) |\n                ((u32)g8 << 16) |\n                ((u32)b8 << 8) |\n                0xFFu;\n        }\n    }\n}\n\nstatic bool citadel_gpu_v15g_capture_fresh_textures(Uint32 now,\n                                                     uint32_t linear_hash)\n{\n    int rgb565_compare;\n    int rgba8_compare;\n    uint32_t source565_hash;\n    uint32_t fresh565_hash;\n    uint32_t source_rgba8_hash;\n    uint32_t fresh_rgba8_hash;\n\n    if (!citadel_gpu_v15g_rgb565_initialized ||\n        !citadel_gpu_v15g_rgba8_initialized ||\n        citadel_gpu_v15g_rgba8_staging == NULL ||\n        citadel_gpu_texture.data == NULL)\n        return false;\n\n    /*\n     * Exercise Citro3D\'s official texture image loader with a brand-new\n     * RGB565 object, rather than continuing to mutate the original object.\n     */\n    C3D_TexLoadImage(&citadel_gpu_v15g_rgb565_texture,\n                     citadel_gpu_texture.data,\n                     GPU_TEXFACE_2D,\n                     0);\n    C3D_TexFlush(&citadel_gpu_v15g_rgb565_texture);\n\n    citadel_gpu_v15g_build_rgba8_staging();\n\n    C3D_TexLoadImage(&citadel_gpu_v15g_rgba8_texture,\n                     citadel_gpu_v15g_rgba8_staging,\n                     GPU_TEXFACE_2D,\n                     0);\n    C3D_TexFlush(&citadel_gpu_v15g_rgba8_texture);\n\n    rgb565_compare =\n        memcmp(citadel_gpu_v15g_rgb565_texture.data,\n               citadel_gpu_texture.data,\n               CITADEL_GPU_STAGING_BYTES);\n\n    rgba8_compare =\n        memcmp(citadel_gpu_v15g_rgba8_texture.data,\n               citadel_gpu_v15g_rgba8_staging,\n               CITADEL_GPU_RGBA8_BYTES);\n\n    source565_hash =\n        citadel_gpu_v15g_hash_bytes(\n            citadel_gpu_texture.data,\n            CITADEL_GPU_STAGING_BYTES);\n    fresh565_hash =\n        citadel_gpu_v15g_hash_bytes(\n            citadel_gpu_v15g_rgb565_texture.data,\n            CITADEL_GPU_STAGING_BYTES);\n    source_rgba8_hash =\n        citadel_gpu_v15g_hash_bytes(\n            citadel_gpu_v15g_rgba8_staging,\n            CITADEL_GPU_RGBA8_BYTES);\n    fresh_rgba8_hash =\n        citadel_gpu_v15g_hash_bytes(\n            citadel_gpu_v15g_rgba8_texture.data,\n            CITADEL_GPU_RGBA8_BYTES);\n\n    citadel_gpu_v15g_log_texture(\n        "ORIGINAL_RGB565",\n        &citadel_gpu_texture);\n    citadel_gpu_v15g_log_texture(\n        "FRESH_RGB565",\n        &citadel_gpu_v15g_rgb565_texture);\n    citadel_gpu_v15g_log_texture(\n        "FRESH_RGBA8",\n        &citadel_gpu_v15g_rgba8_texture);\n\n    v5_log("GPU V15G LOAD VERIFY rgb565_memcmp=%d "\n           "source_hash=0x%08lX fresh_hash=0x%08lX "\n           "rgba8_memcmp=%d source_hash=0x%08lX fresh_hash=0x%08lX "\n           "linear_hash=0x%08lX",\n           rgb565_compare,\n           (unsigned long)source565_hash,\n           (unsigned long)fresh565_hash,\n           rgba8_compare,\n           (unsigned long)source_rgba8_hash,\n           (unsigned long)fresh_rgba8_hash,\n           (unsigned long)linear_hash);\n\n    citadel_gpu_v15g_capture_done = true;\n    citadel_gpu_v15g_phase =\n        CITADEL_V15G_PHASE_FRESH_RGB565;\n    citadel_gpu_v15g_phase_until = now + 6000;\n\n    v5_log("GPU V15G PHASE begin=%s duration_ms=6000 "\n           "loader=C3D_TexLoadImage flush=C3D_TexFlush "\n           "bind=AFTER_C2D_SceneBegin draw=C2D_DrawImageAt "\n           "bottom_marker=BLUE",\n           citadel_gpu_v15g_phase_name(\n               citadel_gpu_v15g_phase));\n\n    return true;\n}\n\nstatic bool citadel_gpu_v15g_draw_phase(void)\n{\n    C3D_Tex *texture;\n    C2D_Image image;\n    u32 bottom_color;\n    bool draw_ok;\n\n    if (citadel_gpu_v15g_phase ==\n        CITADEL_V15G_PHASE_FRESH_RGB565) {\n        texture = &citadel_gpu_v15g_rgb565_texture;\n        image = citadel_gpu_v15g_rgb565_image;\n        bottom_color = C2D_Color32(0, 32, 96, 255);\n    } else if (citadel_gpu_v15g_phase ==\n               CITADEL_V15G_PHASE_FRESH_RGBA8) {\n        texture = &citadel_gpu_v15g_rgba8_texture;\n        image = citadel_gpu_v15g_rgba8_image;\n        bottom_color = C2D_Color32(0, 96, 32, 255);\n    } else {\n        return false;\n    }\n\n    C2D_TargetClear(citadel_gpu_top_target,\n                    C2D_Color32(0, 0, 0, 255));\n    C2D_TargetClear(citadel_gpu_bottom_target,\n                    bottom_color);\n\n    C2D_SceneBegin(citadel_gpu_top_target);\n\n    /*\n     * This bind occurs after SceneBegin, and the image itself points at the\n     * same fresh object, forcing Citro2D\'s queued draw to carry the new\n     * texture metadata into the PICA200 state.\n     */\n    C3D_TexBind(0, texture);\n\n    draw_ok =\n        C2D_DrawImageAt(\n            image,\n            (float)CITADEL_3DS_GAME_X,\n            (float)CITADEL_3DS_GAME_Y,\n            0.0f,\n            NULL,\n            (float)CITADEL_3DS_GAME_WIDTH /\n                (float)CITADEL_GPU_CONTENT_WIDTH,\n            (float)CITADEL_3DS_GAME_HEIGHT /\n                (float)CITADEL_GPU_CONTENT_HEIGHT);\n\n    /*\n     * Submit the queued image while the diagnostic texture binding and scene\n     * are unambiguous, instead of waiting for a later scene transition.\n     */\n    C2D_Flush();\n\n    if (!draw_ok)\n        ++citadel_gpu_draw_failures;\n\n    return draw_ok;\n}\n'
NEW_UPLOAD = 'static bool citadel_gpu_upload_surface(SDL_Surface *surface)\n{\n    Uint32 now;\n    Uint32 elapsed;\n    uint32_t linear_hash;\n    unsigned int palette_mismatches;\n\n    if (surface == NULL ||\n        surface->pixels == NULL ||\n        surface->format == NULL ||\n        surface->format->BytesPerPixel != 1 ||\n        surface->w <= 0 ||\n        surface->h <= 0 ||\n        citadel_gpu_staging == NULL ||\n        !citadel_gpu_texture_initialized ||\n        citadel_gpu_texture.data == NULL) {\n        ++citadel_gpu_upload_failures;\n        return false;\n    }\n\n    citadel_gpu_source_width = surface->w;\n    citadel_gpu_source_height = surface->h;\n\n    now = SDL_GetTicks();\n\n    if (citadel_gpu_v15g_started_at == 0)\n        citadel_gpu_v15g_started_at = now;\n\n    /*\n     * Hold the captured texture objects untouched while each format is shown.\n     */\n    if (citadel_gpu_v15g_phase ==\n        CITADEL_V15G_PHASE_FRESH_RGB565) {\n        if ((Sint32)(now - citadel_gpu_v15g_phase_until) < 0)\n            return true;\n\n        citadel_gpu_v15g_phase =\n            CITADEL_V15G_PHASE_FRESH_RGBA8;\n        citadel_gpu_v15g_phase_until = now + 6000;\n\n        v5_log("GPU V15G PHASE begin=%s duration_ms=6000 "\n               "loader=C3D_TexLoadImage flush=C3D_TexFlush "\n               "bind=AFTER_C2D_SceneBegin draw=C2D_DrawImageAt "\n               "bottom_marker=GREEN",\n               citadel_gpu_v15g_phase_name(\n                   citadel_gpu_v15g_phase));\n        return true;\n    }\n\n    if (citadel_gpu_v15g_phase ==\n        CITADEL_V15G_PHASE_FRESH_RGBA8) {\n        if ((Sint32)(now - citadel_gpu_v15g_phase_until) < 0)\n            return true;\n\n        citadel_gpu_v15g_phase =\n            CITADEL_V15G_PHASE_COMPLETE;\n\n        v5_log("GPU V15G PHASE complete; "\n               "normal live RGB565 presentation resumed");\n    }\n\n    palette_mismatches =\n        citadel_gpu_refresh_palette565();\n\n    linear_hash =\n        citadel_gpu_build_linear_frame(surface);\n    citadel_gpu_swizzle_staging_to_texture();\n\n    elapsed = now - citadel_gpu_v15g_started_at;\n\n    if (!citadel_gpu_v15g_capture_done &&\n        elapsed >= 3000) {\n        if (!citadel_gpu_v15g_capture_fresh_textures(\n                now,\n                linear_hash)) {\n            v5_log("GPU V15G CAPTURE FAIL "\n                   "fresh texture preparation unavailable");\n            citadel_gpu_v15g_capture_done = true;\n            citadel_gpu_v15g_phase =\n                CITADEL_V15G_PHASE_COMPLETE;\n        }\n    }\n\n    if (!citadel_gpu_first_upload_logged) {\n        v5_log("GPU V15G FIRST LIVE FEED src=%dx%d pitch=%d "\n               "linear=%dx%d texture=%dx%d "\n               "palette=AUTHORITATIVE_EVERY_FRAME "\n               "initial_mismatches=%u hash=0x%08lX",\n               surface->w,\n               surface->h,\n               surface->pitch,\n               CITADEL_GPU_CONTENT_WIDTH,\n               CITADEL_GPU_CONTENT_HEIGHT,\n               CITADEL_GPU_TEXTURE_WIDTH,\n               CITADEL_GPU_TEXTURE_HEIGHT,\n               palette_mismatches,\n               (unsigned long)linear_hash);\n        citadel_gpu_first_upload_logged = true;\n    }\n\n    return true;\n}'
NEW_BRANCH = '    /*\n     * V15G GPU-state isolation:\n     *\n     * Show the same frozen frame through two brand-new texture objects:\n     * first RGB565, then RGBA8. Both are loaded through C3D_TexLoadImage,\n     * flushed through C3D_TexFlush, explicitly bound after SceneBegin, and\n     * drawn with the simplest C2D_DrawImageAt path.\n     */\n    if (citadel_gpu_v15g_phase_active()) {\n        const bool diagnostic_ok =\n            citadel_gpu_v15g_draw_phase();\n\n        C3D_FrameEnd(0);\n        ++citadel_gpu_presented_frames;\n\n        return diagnostic_ok;\n    }\n\n'


def find_matching_brace(text: str, open_pos: int) -> int:
    if open_pos < 0 or open_pos >= len(text) or text[open_pos] != "{":
        raise RuntimeError("Invalid opening-brace position.")

    depth = 0
    i = open_pos
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
                    return i

        i += 1

    raise RuntimeError("Unterminated brace block.")


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise RuntimeError(f"Could not locate function: {signature}")

    opening = text.find("{", start)
    if opening < 0:
        raise RuntimeError(f"Could not locate function body: {signature}")

    closing = find_matching_brace(text, opening)
    return start, closing + 1


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} anchor, found {count}."
        )
    return text.replace(old, new, 1)


def patch(text: str) -> str:
    if "PROJECT CITADEL V15G" in text:
        raise RuntimeError("This source already appears to contain V15G.")

    marker = (
        '#warning "PROJECT CITADEL V15F: '
        'frozen frame roundtrip is ACTIVE"'
    )
    if marker not in text:
        raise RuntimeError(
            "The V15F compiler marker was not found. "
            "Start from the active V15F Shock.c."
        )

    result = text

    if "#include <string.h>" not in result:
        result = replace_once(
            result,
            "#include <stdio.h>\n",
            "#include <stdio.h>\n#include <string.h>\n",
            "stdio include",
        )

    result = replace_once(
        result,
        marker,
        '#warning "PROJECT CITADEL V15G: '
        'fresh texture binding test is ACTIVE"',
        "V15F compiler marker",
    )

    result = result.replace("GPU_C2D_V15F.log", "GPU_C2D_V15G.log")
    result = result.replace(
        "PROJECT CITADEL V15F FROZEN FRAME ROUNDTRIP START",
        "PROJECT CITADEL V15G FRESH TEXTURE BINDING START",
    )
    result = result.replace(
        "GPU V15F FROZEN FRAME ROUNDTRIP ready",
        "GPU V15G FRESH TEXTURE BINDING ready",
    )
    result = result.replace(
        "GPU V15F PALETTE SYNC",
        "GPU V15G PALETTE SYNC",
    )
    result = result.replace(
        "GPU V15F SYNC ORDER confirmed",
        "GPU V15G SYNC ORDER confirmed",
    )
    result = result.replace(
        "GPU V15F CACHE REBIND active",
        "GPU V15G CACHE REBIND active",
    )

    state_anchor = "static C2D_Image citadel_gpu_v15f_image;\n"
    result = replace_once(
        result,
        state_anchor,
        state_anchor + STATE_INSERT,
        "V15F diagnostic state",
    )

    prototype_anchor = (
        "static void citadel_gpu_update_palette565(void);\n"
    )
    prototype_insert = (
        prototype_anchor
        + "static void citadel_gpu_v15g_prepare_images(void);\n"
        + "static bool citadel_gpu_v15g_phase_active(void);\n"
        + "static bool citadel_gpu_v15g_draw_phase(void);\n"
    )
    result = replace_once(
        result,
        prototype_anchor,
        prototype_insert,
        "GPU prototype",
    )

    shutdown_anchor = """    if (citadel_gpu_texture_initialized) {
        C3D_TexDelete(&citadel_gpu_texture);
        citadel_gpu_texture_initialized = false;
    }
"""
    shutdown_insert = """    if (citadel_gpu_v15g_rgb565_initialized) {
        C3D_TexDelete(&citadel_gpu_v15g_rgb565_texture);
        citadel_gpu_v15g_rgb565_initialized = false;
    }

    if (citadel_gpu_v15g_rgba8_initialized) {
        C3D_TexDelete(&citadel_gpu_v15g_rgba8_texture);
        citadel_gpu_v15g_rgba8_initialized = false;
    }

    if (citadel_gpu_v15g_rgba8_staging != NULL) {
        linearFree(citadel_gpu_v15g_rgba8_staging);
        citadel_gpu_v15g_rgba8_staging = NULL;
    }

""" + shutdown_anchor
    result = replace_once(
        result,
        shutdown_anchor,
        shutdown_insert,
        "GPU shutdown texture cleanup",
    )

    init_start = """static bool citadel_gpu_initialize(void)
{
    memset(&citadel_gpu_texture, 0, sizeof(citadel_gpu_texture));
"""
    init_replacement = """static bool citadel_gpu_initialize(void)
{
    memset(&citadel_gpu_texture, 0, sizeof(citadel_gpu_texture));
    memset(&citadel_gpu_v15g_rgb565_texture,
           0,
           sizeof(citadel_gpu_v15g_rgb565_texture));
    memset(&citadel_gpu_v15g_rgba8_texture,
           0,
           sizeof(citadel_gpu_v15g_rgba8_texture));
"""
    result = replace_once(
        result,
        init_start,
        init_replacement,
        "GPU initialize opening",
    )

    allocation_anchor = """    memset(citadel_gpu_staging,
           0,
           CITADEL_GPU_STAGING_BYTES);

    citadel_gpu_update_palette565();
"""
    allocation_insert = """    memset(citadel_gpu_staging,
           0,
           CITADEL_GPU_STAGING_BYTES);

    if (!C3D_TexInit(&citadel_gpu_v15g_rgb565_texture,
                     CITADEL_GPU_TEXTURE_WIDTH,
                     CITADEL_GPU_TEXTURE_HEIGHT,
                     GPU_RGB565)) {
        v5_log("GPU INIT FAIL stage=V15G-fresh-RGB565");
        citadel_gpu_shutdown();
        citadel_gpu_shutdown_complete = false;
        return false;
    }
    citadel_gpu_v15g_rgb565_initialized = true;

    C3D_TexSetFilter(&citadel_gpu_v15g_rgb565_texture,
                     GPU_NEAREST,
                     GPU_NEAREST);
    C3D_TexSetWrap(&citadel_gpu_v15g_rgb565_texture,
                   GPU_CLAMP_TO_EDGE,
                   GPU_CLAMP_TO_EDGE);

    if (!C3D_TexInit(&citadel_gpu_v15g_rgba8_texture,
                     CITADEL_GPU_TEXTURE_WIDTH,
                     CITADEL_GPU_TEXTURE_HEIGHT,
                     GPU_RGBA8)) {
        v5_log("GPU INIT FAIL stage=V15G-fresh-RGBA8");
        citadel_gpu_shutdown();
        citadel_gpu_shutdown_complete = false;
        return false;
    }
    citadel_gpu_v15g_rgba8_initialized = true;

    C3D_TexSetFilter(&citadel_gpu_v15g_rgba8_texture,
                     GPU_NEAREST,
                     GPU_NEAREST);
    C3D_TexSetWrap(&citadel_gpu_v15g_rgba8_texture,
                   GPU_CLAMP_TO_EDGE,
                   GPU_CLAMP_TO_EDGE);

    citadel_gpu_v15g_rgba8_staging =
        (u32 *)linearAlloc(CITADEL_GPU_RGBA8_BYTES);

    if (citadel_gpu_v15g_rgba8_staging == NULL) {
        v5_log("GPU INIT FAIL stage=V15G-RGBA8-staging bytes=%u",
               (unsigned int)CITADEL_GPU_RGBA8_BYTES);
        citadel_gpu_shutdown();
        citadel_gpu_shutdown_complete = false;
        return false;
    }

    memset(citadel_gpu_v15g_rgba8_staging,
           0,
           CITADEL_GPU_RGBA8_BYTES);

    citadel_gpu_v15g_prepare_images();

    citadel_gpu_update_palette565();
"""
    result = replace_once(
        result,
        allocation_anchor,
        allocation_insert,
        "GPU staging initialization",
    )

    upload_start, upload_end = function_span(
        result,
        "static bool citadel_gpu_upload_surface(SDL_Surface *surface)",
    )
    result = (
        result[:upload_start]
        + HELPERS
        + "\n"
        + NEW_UPLOAD
        + result[upload_end:]
    )

    bind_anchor = """    if (!magenta) {
        C3D_TexBind(0, &citadel_gpu_texture);
"""
    bind_replacement = """    if (!magenta && !citadel_gpu_v15g_phase_active()) {
        C3D_TexBind(0, &citadel_gpu_texture);
"""
    result = replace_once(
        result,
        bind_anchor,
        bind_replacement,
        "live texture bind condition",
    )
    result = result.replace(
        "C3D_TexBind(0, live_texture) after every upload",
        "C3D_TexBind(0, live_texture) after every live upload",
        1,
    )

    branch_if = result.find(
        "    if (citadel_gpu_v15f_freeze_active) {"
    )
    if branch_if < 0:
        raise RuntimeError("Could not locate the V15F frozen draw branch.")

    branch_comment = result.rfind("    /*", 0, branch_if)
    if branch_comment < 0:
        raise RuntimeError("Could not locate the V15F branch comment.")

    branch_open = result.find("{", branch_if)
    branch_close = find_matching_brace(result, branch_open) + 1

    while branch_close < len(result) and result[branch_close] == "\n":
        branch_close += 1

    result = (
        result[:branch_comment]
        + NEW_BRANCH
        + result[branch_close:]
    )

    return result


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
        modified = patch(original)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    PREVIEW.write_text(modified, encoding="utf-8", newline="\n")
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
        SOURCE.write_text(modified, encoding="utf-8", newline="\n")

        print(f"Backup: {BACKUP}")
        print(f"Installed: {SOURCE}")
    else:
        print("The active source was not changed.")
        print("Install after reviewing the preview with:")
        print(
            "  python "
            "apply_SS3DS_V15G_fresh_texture_binding.py --install"
        )

    print()
    print("Expected compiler marker:")
    print(
        "  PROJECT CITADEL V15G: "
        "fresh texture binding test is ACTIVE"
    )
    print("Expected runtime log:")
    print("  GPU_C2D_V15G.log")
    print("Build:")
    print("  cmake --build build-3ds")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
