/*

Copyright (C) 2015-2018 Night Dive Studios, LLC.

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

*/
//====================================================================================
//
//		System Shock - ©1994-1995 Looking Glass Technologies, Inc.
//
//		Shock.c	-	Mac-specific initialization and main event loop.
//
//====================================================================================

//--------------------
//  Includes
//--------------------
#include <math.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <SDL.h>

#if defined(__3DS__) || defined(_3DS)
/*
 * Shock's legacy keydefs.h is force-included before this source and defines
 * KEY_UP, KEY_DOWN, KEY_LEFT, and KEY_RIGHT as keyboard scan-code macros.
 * libctru uses those same names for HID enum entries. Temporarily hide the
 * Shock macros while parsing the 3DS/Citro headers, then restore them.
 */
#pragma push_macro("KEY_UP")
#pragma push_macro("KEY_DOWN")
#pragma push_macro("KEY_LEFT")
#pragma push_macro("KEY_RIGHT")

#undef KEY_UP
#undef KEY_DOWN
#undef KEY_LEFT
#undef KEY_RIGHT

#include <3ds.h>
#include <citro2d.h>
#include <citro3d.h>

#pragma pop_macro("KEY_RIGHT")
#pragma pop_macro("KEY_LEFT")
#pragma pop_macro("KEY_DOWN")
#pragma pop_macro("KEY_UP")
#endif

#include "InitMac.h"
#include "Modding.h"
#include "OpenGL.h"
#include "Prefs.h"
#include "Shock.h"
#include "ShockBitmap.h"

#include "amaploop.h"
#include "gr2ss.h"
#include "hkeyfunc.h"
#include "mainloop.h"
#include "setup.h"
#include "shockolate_version.h"
#include "status.h"
#include "version.h"

#warning "PROJECT CITADEL V15D: source-vs-Morton truth test is ACTIVE"

//--------------------
//  Globals
//--------------------
bool gPlayingGame;

grs_screen *cit_screen;
SDL_Window *window;
SDL_Palette *sdlPalette;
SDL_Renderer *renderer;

#if defined(__3DS__) || defined(_3DS)
SDL_Window *citadel_bottom_window;
SDL_Renderer *citadel_bottom_renderer;

/*
 * The in-game wrapper (save/load/options) remains in GAME_LOOP, so its own
 * visibility flag is also part of layout selection.
 */
extern uchar wrapper_panel_on;

/*
 * False: use the automatic SS3DS layout (split during active gameplay,
 * legacy everywhere else). True: force the centered legacy frame even while
 * active gameplay is otherwise eligible for the split presentation.
 */
static bool citadel_legacy_view_override = false;

/* -------------------------------------------------------------------------
 * PROJECT CITADEL V14X: direct Citro2D/PICA200 presentation.
 *
 * SDL still owns the 3DS gfx/hid lifecycle and continues to provide windows,
 * input, timing, and audio. Citro3D/Citro2D own only frame composition.
 * ------------------------------------------------------------------------- */
#define CITADEL_GPU_TEXTURE_WIDTH    512
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
    (CITADEL_GPU_TEXTURE_PIXELS * sizeof(u16))

static bool citadel_gpu_ready = false;
static bool citadel_gpu_c3d_initialized = false;
static bool citadel_gpu_c2d_initialized = false;
static bool citadel_gpu_texture_initialized = false;
static bool citadel_gpu_shutdown_complete = false;

static C3D_RenderTarget *citadel_gpu_top_target = NULL;
static C3D_RenderTarget *citadel_gpu_bottom_target = NULL;
static C3D_Tex citadel_gpu_texture;
static u16 *citadel_gpu_staging = NULL;
static u16 citadel_gpu_palette565[256];

static unsigned int citadel_gpu_presented_frames = 0;
static unsigned int citadel_gpu_upload_failures = 0;
static unsigned int citadel_gpu_draw_failures = 0;

/* V14Y: current Shock surface dimensions used for crop remapping. */
static int citadel_gpu_source_width = 0;
static int citadel_gpu_source_height = 0;
static bool citadel_gpu_first_upload_logged = false;

/* V15B: confirms that the previous GPU frame is drained before texture writes. */
static bool citadel_gpu_sync_order_logged = false;

/* V15C: confirms the live texture is explicitly rebound after every upload. */
static bool citadel_gpu_cache_rebind_logged = false;

/* V15D diagnostic state. */
static Uint32 citadel_gpu_v15d_started_at = 0;
static bool citadel_gpu_v15d_pattern_logged = false;
static bool citadel_gpu_v15d_live_logged = false;
static bool citadel_gpu_v15d_source_dump_attempted = false;

#endif

SDL_AudioDeviceID device;

int num_args;
char **arg_values;

/* -------------------------------------------------------------------------
 * PROJECT CITADEL V5: SDL presentation diagnostics.
 * ------------------------------------------------------------------------- */
static unsigned int v5_sdl_draw_calls = 0;
static Uint32 v5_magenta_until = 0;
static bool v5_magenta_announced = false;
static bool v5_normal_announced = false;

static void v5_log(const char *fmt, ...);
static void v5_log_error(const char *stage);

#if defined(__3DS__) || defined(_3DS)
extern SDL_Color gamePalette[256];

static SDL_Rect citadel_scale_reference_rect(SDL_Surface *surface,
                                              int x,
                                              int y,
                                              int w,
                                              int h);
static bool citadel_gpu_initialize(void);
static void citadel_gpu_shutdown(void);
static bool citadel_gpu_present(SDL_Surface *surface, bool magenta);
static void citadel_gpu_update_palette565(void);
#endif

#if defined(__3DS__) || defined(_3DS)
#define CITADEL_3DS_TOP_WIDTH  400
#define CITADEL_3DS_TOP_HEIGHT 240
#define CITADEL_3DS_GAME_WIDTH 320
#define CITADEL_3DS_GAME_HEIGHT 240
#define CITADEL_3DS_GAME_X ((CITADEL_3DS_TOP_WIDTH - CITADEL_3DS_GAME_WIDTH) / 2)
#define CITADEL_3DS_GAME_Y 0

#define CITADEL_3DS_BOTTOM_WIDTH  320
#define CITADEL_3DS_BOTTOM_HEIGHT 240

/*
 * V10 calibration in Shock's classic 640x480 canvas.
 *
 * The top crop now stops safely above the lower-interface message/header
 * pixels. The inventory begins higher so context text such as object names
 * remains readable. Both MFDs zoom out vertically, and the right MFD reaches
 * farther left so its inner border and controls are no longer clipped.
 */
#define CITADEL_REF_WIDTH              640
#define CITADEL_REF_HEIGHT             480

#define CITADEL_REF_GAME_X               0
#define CITADEL_REF_GAME_Y               0
#define CITADEL_REF_GAME_W             640
#define CITADEL_REF_GAME_H             328

#define CITADEL_REF_INVENTORY_X        168
#define CITADEL_REF_INVENTORY_Y        320
#define CITADEL_REF_INVENTORY_W        304
#define CITADEL_REF_INVENTORY_H        160

#define CITADEL_REF_LEFT_MFD_X           0
#define CITADEL_REF_LEFT_MFD_W         160
#define CITADEL_REF_RIGHT_MFD_X        472
#define CITADEL_REF_RIGHT_MFD_W        168
#define CITADEL_REF_MFD_Y              312
#define CITADEL_REF_MFD_H              156
#endif

#if defined(__3DS__) || defined(_3DS)

bool citadel_3ds_gameplay_controls_active(void)
{
    /*
     * Wrapper panels (save/load/options) stay inside GAME_LOOP, but they are
     * full-screen interfaces rather than live world interaction.
     */
    return _current_loop == GAME_LOOP && !wrapper_panel_on;
}

static bool citadel_3ds_use_split_layout(void)
{
    return !citadel_legacy_view_override &&
           citadel_3ds_gameplay_controls_active();
}

bool citadel_3ds_split_layout_active(void)
{
    return citadel_3ds_use_split_layout();
}

void citadel_3ds_toggle_legacy_view(void)
{
    citadel_legacy_view_override = !citadel_legacy_view_override;

    v5_log("SELECT legacy override=%d current_loop=%d wrapper=%d effective_layout=%s",
           citadel_legacy_view_override ? 1 : 0,
           (int)_current_loop,
           wrapper_panel_on ? 1 : 0,
           citadel_3ds_use_split_layout() ? "SPLIT" : "LEGACY");
}


static u16 citadel_gpu_pack_rgb565(SDL_Color color)
{
    return (u16)(((u16)(color.r >> 3) << 11) |
                 ((u16)(color.g >> 2) << 5) |
                 ((u16)(color.b >> 3)));
}

static void citadel_gpu_update_palette565(void)
{
    int i;

    for (i = 0; i < 256; ++i)
        citadel_gpu_palette565[i] =
            citadel_gpu_pack_rgb565(gamePalette[i]);
}

static void citadel_gpu_shutdown(void)
{
    if (citadel_gpu_shutdown_complete)
        return;

    citadel_gpu_shutdown_complete = true;
    citadel_gpu_ready = false;

    v5_log("GPU SHUTDOWN frames=%u upload_failures=%u draw_failures=%u",
           citadel_gpu_presented_frames,
           citadel_gpu_upload_failures,
           citadel_gpu_draw_failures);

    if (citadel_gpu_top_target != NULL) {
        C3D_RenderTargetDelete(citadel_gpu_top_target);
        citadel_gpu_top_target = NULL;
    }

    if (citadel_gpu_bottom_target != NULL) {
        C3D_RenderTargetDelete(citadel_gpu_bottom_target);
        citadel_gpu_bottom_target = NULL;
    }

    if (citadel_gpu_texture_initialized) {
        C3D_TexDelete(&citadel_gpu_texture);
        citadel_gpu_texture_initialized = false;
    }

    if (citadel_gpu_staging != NULL) {
        linearFree(citadel_gpu_staging);
        citadel_gpu_staging = NULL;
    }

    if (citadel_gpu_c2d_initialized) {
        C2D_Fini();
        citadel_gpu_c2d_initialized = false;
    }

    if (citadel_gpu_c3d_initialized) {
        C3D_Fini();
        citadel_gpu_c3d_initialized = false;
    }

    /*
     * Do not call gfxExit() or hidExit() here. SDL's N3DS video backend
     * initialized those services and SDL_Quit() remains their owner.
     */
}

static bool citadel_gpu_initialize(void)
{
    memset(&citadel_gpu_texture, 0, sizeof(citadel_gpu_texture));

    /*
     * SDL_Init(SDL_INIT_VIDEO) has already initialized the N3DS gfx service.
     * Calling gfxInitDefault() here would double-initialize the display stack.
     */
    if (!C3D_Init(C3D_DEFAULT_CMDBUF_SIZE)) {
        v5_log("GPU INIT FAIL stage=C3D_Init");
        return false;
    }
    citadel_gpu_c3d_initialized = true;

    if (!C2D_Init(C2D_DEFAULT_MAX_OBJECTS)) {
        v5_log("GPU INIT FAIL stage=C2D_Init");
        citadel_gpu_shutdown();
        citadel_gpu_shutdown_complete = false;
        return false;
    }
    citadel_gpu_c2d_initialized = true;
    C2D_Prepare();

    citadel_gpu_top_target =
        C2D_CreateScreenTarget(GFX_TOP, GFX_LEFT);
    citadel_gpu_bottom_target =
        C2D_CreateScreenTarget(GFX_BOTTOM, GFX_LEFT);

    if (citadel_gpu_top_target == NULL ||
        citadel_gpu_bottom_target == NULL) {
        v5_log("GPU INIT FAIL stage=screen-targets top=%p bottom=%p",
               (void *)citadel_gpu_top_target,
               (void *)citadel_gpu_bottom_target);
        citadel_gpu_shutdown();
        citadel_gpu_shutdown_complete = false;
        return false;
    }

    if (!C3D_TexInit(&citadel_gpu_texture,
                     CITADEL_GPU_TEXTURE_WIDTH,
                     CITADEL_GPU_TEXTURE_HEIGHT,
                     GPU_RGB565)) {
        v5_log("GPU INIT FAIL stage=C3D_TexInit size=%dx%d",
               CITADEL_GPU_TEXTURE_WIDTH,
               CITADEL_GPU_TEXTURE_HEIGHT);
        citadel_gpu_shutdown();
        citadel_gpu_shutdown_complete = false;
        return false;
    }
    citadel_gpu_texture_initialized = true;

    C3D_TexSetFilter(&citadel_gpu_texture,
                     GPU_NEAREST,
                     GPU_NEAREST);
    C3D_TexSetWrap(&citadel_gpu_texture,
                   GPU_CLAMP_TO_EDGE,
                   GPU_CLAMP_TO_EDGE);

    citadel_gpu_staging =
        (u16 *)linearAlloc(CITADEL_GPU_STAGING_BYTES);

    if (citadel_gpu_staging == NULL) {
        v5_log("GPU INIT FAIL stage=linearAlloc bytes=%u",
               (unsigned int)CITADEL_GPU_STAGING_BYTES);
        citadel_gpu_shutdown();
        citadel_gpu_shutdown_complete = false;
        return false;
    }

    memset(citadel_gpu_staging,
           0,
           CITADEL_GPU_STAGING_BYTES);

    citadel_gpu_update_palette565();

    citadel_gpu_ready = true;
    atexit(citadel_gpu_shutdown);

    v5_log("GPU V15D SOURCE-VS-MORTON DIAGNOSTIC ready texture=%dx%d content=%dx%d "
           "source-resample=nearest filter=NEAREST",
           CITADEL_GPU_TEXTURE_WIDTH,
           CITADEL_GPU_TEXTURE_HEIGHT,
           CITADEL_GPU_CONTENT_WIDTH,
           CITADEL_GPU_CONTENT_HEIGHT);

    v5_log("GPU INIT SUCCESS backend=Citro2D texture=%dx%d format=RGB565 "
           "top=%p bottom=%p texture_data=%p staging=%p",
           CITADEL_GPU_TEXTURE_WIDTH,
           CITADEL_GPU_TEXTURE_HEIGHT,
           (void *)citadel_gpu_top_target,
           (void *)citadel_gpu_bottom_target,
           citadel_gpu_texture.data,
           (void *)citadel_gpu_staging);

    return true;
}

/*
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

/*
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
}

static bool citadel_gpu_draw_region(int source_x,
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
}

static bool citadel_gpu_present(SDL_Surface *surface, bool magenta)
{
    static int last_logged_layout = -1;
    bool split_layout;
    bool top_ok = true;
    bool bottom_ok = true;
    SDL_Rect top_source;

    if (!citadel_gpu_ready ||
        citadel_gpu_top_target == NULL ||
        citadel_gpu_bottom_target == NULL)
        return false;

    /*
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
        v5_log("GPU V15D SYNC ORDER confirmed: "
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
            v5_log("GPU V15D CACHE REBIND active: "
                   "C3D_TexBind(0, live_texture) after every upload");
            citadel_gpu_cache_rebind_logged = true;
        }
    }

    if (magenta) {
        C2D_TargetClear(citadel_gpu_top_target,
                        C2D_Color32(255, 0, 255, 255));
        C2D_TargetClear(citadel_gpu_bottom_target,
                        C2D_Color32(24, 24, 24, 255));
        C3D_FrameEnd(0);
        ++citadel_gpu_presented_frames;
        return true;
    }

    split_layout = citadel_3ds_use_split_layout();

    C2D_TargetClear(citadel_gpu_top_target,
                    C2D_Color32(0, 0, 0, 255));
    C2D_TargetClear(citadel_gpu_bottom_target,
                    C2D_Color32(0, 0, 0, 255));

    C2D_SceneBegin(citadel_gpu_top_target);

    if (split_layout) {
        top_source = citadel_scale_reference_rect(
            surface,
            CITADEL_REF_GAME_X,
            CITADEL_REF_GAME_Y,
            CITADEL_REF_GAME_W,
            CITADEL_REF_GAME_H);

        top_ok = citadel_gpu_draw_region(
            top_source.x,
            top_source.y,
            top_source.w,
            top_source.h,
            0.0f,
            0.0f,
            (float)CITADEL_3DS_TOP_WIDTH,
            (float)CITADEL_3DS_TOP_HEIGHT,
            0.0f);
    } else {
        top_source.x = 0;
        top_source.y = 0;
        top_source.w =
            surface != NULL ? surface->w : CITADEL_REF_WIDTH;
        top_source.h =
            surface != NULL ? surface->h : CITADEL_REF_HEIGHT;

        top_ok = citadel_gpu_draw_region(
            top_source.x,
            top_source.y,
            top_source.w,
            top_source.h,
            (float)CITADEL_3DS_GAME_X,
            (float)CITADEL_3DS_GAME_Y,
            (float)CITADEL_3DS_GAME_WIDTH,
            (float)CITADEL_3DS_GAME_HEIGHT,
            0.0f);
    }

    if (split_layout) {
        SDL_Rect inventory_source =
            citadel_scale_reference_rect(
                surface,
                CITADEL_REF_INVENTORY_X,
                CITADEL_REF_INVENTORY_Y,
                CITADEL_REF_INVENTORY_W,
                CITADEL_REF_INVENTORY_H);

        SDL_Rect left_mfd_source =
            citadel_scale_reference_rect(
                surface,
                CITADEL_REF_LEFT_MFD_X,
                CITADEL_REF_MFD_Y,
                CITADEL_REF_LEFT_MFD_W,
                CITADEL_REF_MFD_H);

        SDL_Rect right_mfd_source =
            citadel_scale_reference_rect(
                surface,
                CITADEL_REF_RIGHT_MFD_X,
                CITADEL_REF_MFD_Y,
                CITADEL_REF_RIGHT_MFD_W,
                CITADEL_REF_MFD_H);

        C2D_SceneBegin(citadel_gpu_bottom_target);

        bottom_ok =
            citadel_gpu_draw_region(
                inventory_source.x,
                inventory_source.y,
                inventory_source.w,
                inventory_source.h,
                0.0f,
                0.0f,
                320.0f,
                120.0f,
                0.0f) &&
            citadel_gpu_draw_region(
                left_mfd_source.x,
                left_mfd_source.y,
                left_mfd_source.w,
                left_mfd_source.h,
                0.0f,
                120.0f,
                160.0f,
                120.0f,
                0.0f) &&
            citadel_gpu_draw_region(
                right_mfd_source.x,
                right_mfd_source.y,
                right_mfd_source.w,
                right_mfd_source.h,
                160.0f,
                120.0f,
                160.0f,
                120.0f,
                0.0f);
    }

    C3D_FrameEnd(0);
    ++citadel_gpu_presented_frames;

    if (last_logged_layout != (split_layout ? 1 : 0)) {
        v5_log("GPU LAYOUT changed=%s top_src={%d,%d,%d,%d} "
               "frames=%u",
               split_layout ? "SPLIT" : "LEGACY",
               top_source.x,
               top_source.y,
               top_source.w,
               top_source.h,
               citadel_gpu_presented_frames);
        last_logged_layout = split_layout ? 1 : 0;
    }

    if (citadel_gpu_presented_frames == 1 ||
        (citadel_gpu_presented_frames % 600) == 0) {
        v5_log("GPU FRAME frame=%u split=%d top_ok=%d bottom_ok=%d "
               "surface=%dx%d",
               citadel_gpu_presented_frames,
               split_layout ? 1 : 0,
               top_ok ? 1 : 0,
               bottom_ok ? 1 : 0,
               surface != NULL ? surface->w : -1,
               surface != NULL ? surface->h : -1);
    }

    return top_ok && bottom_ok;
}

static void citadel_clear_bottom_screen(void)
{
    if (citadel_bottom_renderer == NULL)
        return;

    SDL_SetRenderDrawColor(citadel_bottom_renderer, 0, 0, 0, 255);
    SDL_RenderClear(citadel_bottom_renderer);
    SDL_RenderPresent(citadel_bottom_renderer);
}

static SDL_Rect citadel_scale_reference_rect(SDL_Surface *surface,
                                              int x,
                                              int y,
                                              int w,
                                              int h)
{
    SDL_Rect rect = {0, 0, 0, 0};

    if (surface == NULL || surface->w <= 0 || surface->h <= 0)
        return rect;

    rect.x = (x * surface->w) / CITADEL_REF_WIDTH;
    rect.y = (y * surface->h) / CITADEL_REF_HEIGHT;
    rect.w = (w * surface->w) / CITADEL_REF_WIDTH;
    rect.h = (h * surface->h) / CITADEL_REF_HEIGHT;

    /*
     * Keep rounding from extending a source rectangle beyond the surface.
     */
    if (rect.x < 0)
        rect.x = 0;
    if (rect.y < 0)
        rect.y = 0;
    if (rect.x + rect.w > surface->w)
        rect.w = surface->w - rect.x;
    if (rect.y + rect.h > surface->h)
        rect.h = surface->h - rect.y;

    return rect;
}

static SDL_Renderer *citadel_create_renderer_with_fallbacks(SDL_Window *target,
                                                             const char *label)
{
    SDL_Renderer *created = NULL;

    if (target == NULL)
        return NULL;

    SDL_ClearError();
    created = SDL_CreateRenderer(target, -1, SDL_RENDERER_PRESENTVSYNC);
    v5_log("%s SDL_CreateRenderer(PRESENTVSYNC) result=%p",
           label, (void *)created);
    v5_log_error(label);

    if (created == NULL) {
        SDL_ClearError();
        created = SDL_CreateRenderer(target, -1, SDL_RENDERER_SOFTWARE);
        v5_log("%s SDL_CreateRenderer(SOFTWARE) result=%p",
               label, (void *)created);
        v5_log_error(label);
    }

    if (created == NULL) {
        SDL_ClearError();
        created = SDL_CreateRenderer(target, -1, 0);
        v5_log("%s SDL_CreateRenderer(flags=0) result=%p",
               label, (void *)created);
        v5_log_error(label);
    }

    return created;
}

static void citadel_present_bottom_layout(SDL_Surface *surface)
{
    static bool first_bottom_frame_logged = false;
    SDL_Texture *texture;
    SDL_Rect inventory_src;
    SDL_Rect left_mfd_src;
    SDL_Rect right_mfd_src;
    SDL_Rect inventory_dst = {0, 0, 320, 120};
    SDL_Rect left_mfd_dst = {0, 120, 160, 120};
    SDL_Rect right_mfd_dst = {160, 120, 160, 120};
    int result;

    if (surface == NULL ||
        citadel_bottom_window == NULL ||
        citadel_bottom_renderer == NULL)
        return;

    /*
     * Never leave stale, disjointed interface fragments on the lower LCD
     * while menus or the SELECT legacy view are shown on top.
     */
    if (!citadel_3ds_use_split_layout()) {
        citadel_clear_bottom_screen();
        return;
    }

    inventory_src = citadel_scale_reference_rect(
        surface,
        CITADEL_REF_INVENTORY_X,
        CITADEL_REF_INVENTORY_Y,
        CITADEL_REF_INVENTORY_W,
        CITADEL_REF_INVENTORY_H);

    left_mfd_src = citadel_scale_reference_rect(
        surface,
        CITADEL_REF_LEFT_MFD_X,
        CITADEL_REF_MFD_Y,
        CITADEL_REF_LEFT_MFD_W,
        CITADEL_REF_MFD_H);

    right_mfd_src = citadel_scale_reference_rect(
        surface,
        CITADEL_REF_RIGHT_MFD_X,
        CITADEL_REF_MFD_Y,
        CITADEL_REF_RIGHT_MFD_W,
        CITADEL_REF_MFD_H);

    SDL_ClearError();
    texture = SDL_CreateTextureFromSurface(citadel_bottom_renderer, surface);
    if (texture == NULL) {
        if (!first_bottom_frame_logged) {
            v5_log("BOTTOM texture creation failed: %s", SDL_GetError());
            first_bottom_frame_logged = true;
        }
        return;
    }

    SDL_SetRenderDrawColor(citadel_bottom_renderer, 0, 0, 0, 255);
    SDL_RenderClear(citadel_bottom_renderer);

    result = SDL_RenderCopy(citadel_bottom_renderer,
                            texture,
                            &inventory_src,
                            &inventory_dst);
    if (result < 0)
        v5_log("BOTTOM inventory RenderCopy failed: %s", SDL_GetError());

    result = SDL_RenderCopy(citadel_bottom_renderer,
                            texture,
                            &left_mfd_src,
                            &left_mfd_dst);
    if (result < 0)
        v5_log("BOTTOM left-MFD RenderCopy failed: %s", SDL_GetError());

    result = SDL_RenderCopy(citadel_bottom_renderer,
                            texture,
                            &right_mfd_src,
                            &right_mfd_dst);
    if (result < 0)
        v5_log("BOTTOM right-MFD RenderCopy failed: %s", SDL_GetError());

    SDL_DestroyTexture(texture);
    SDL_RenderPresent(citadel_bottom_renderer);

    if (!first_bottom_frame_logged) {
        v5_log("BOTTOM FIRST FRAME SUCCESS surface=%dx%d "
               "inventory_src={%d,%d,%d,%d} dst={0,0,320,120} "
               "left_src={%d,%d,%d,%d} dst={0,120,160,120} "
               "right_src={%d,%d,%d,%d} dst={160,120,160,120}",
               surface->w,
               surface->h,
               inventory_src.x,
               inventory_src.y,
               inventory_src.w,
               inventory_src.h,
               left_mfd_src.x,
               left_mfd_src.y,
               left_mfd_src.w,
               left_mfd_src.h,
               right_mfd_src.x,
               right_mfd_src.y,
               right_mfd_src.w,
               right_mfd_src.h);
        first_bottom_frame_logged = true;
    }
}

#endif

static void v5_log(const char *fmt, ...)
{
    FILE *file = fopen("GPU_C2D_V15D.log", "a");
    va_list args;

    if (file == NULL)
        return;

    va_start(args, fmt);
    vfprintf(file, fmt, args);
    va_end(args);

    fputc('\n', file);
    fflush(file);
    fclose(file);
}

static void v5_log_error(const char *stage)
{
    const char *error = SDL_GetError();
    v5_log("%s | SDL_GetError=\"%s\"", stage, error != NULL ? error : "(null)");
}

static void v5_log_surface(const char *name, SDL_Surface *surface)
{
    if (surface == NULL) {
        v5_log("%s: NULL", name);
        return;
    }

    v5_log("%s: ptr=%p pixels=%p w=%d h=%d pitch=%d format=%p bpp=%d bytespp=%d palette=%p",
           name,
           (void *)surface,
           surface->pixels,
           surface->w,
           surface->h,
           surface->pitch,
           (void *)surface->format,
           surface->format != NULL ? surface->format->BitsPerPixel : -1,
           surface->format != NULL ? surface->format->BytesPerPixel : -1,
           surface->format != NULL ? (void *)surface->format->palette : NULL);

    if (surface->pixels != NULL &&
        surface->format != NULL &&
        surface->format->BytesPerPixel == 1) {
        uint64_t count_zero = 0;
        uint64_t count_255 = 0;
        uint64_t count_other = 0;
        uint8_t first = 0;
        uint8_t middle = 0;
        uint8_t last = 0;

        const uint8_t *pixels = (const uint8_t *)surface->pixels;
        const int width = surface->w;
        const int height = surface->h;

        if (width > 0 && height > 0) {
            first = pixels[0];
            middle = pixels[(height / 2) * surface->pitch + (width / 2)];
            last = pixels[(height - 1) * surface->pitch + (width - 1)];
        }

        for (int y = 0; y < height; ++y) {
            const uint8_t *row = pixels + y * surface->pitch;
            for (int x = 0; x < width; ++x) {
                if (row[x] == 0)
                    ++count_zero;
                else if (row[x] == 255)
                    ++count_255;
                else
                    ++count_other;
            }
        }

        v5_log("%s pixels: index0=%llu index255=%llu other=%llu samples=%u,%u,%u",
               name,
               (unsigned long long)count_zero,
               (unsigned long long)count_255,
               (unsigned long long)count_other,
               (unsigned int)first,
               (unsigned int)middle,
               (unsigned int)last);
    }

    if (surface->format != NULL &&
        surface->format->palette != NULL &&
        surface->format->palette->ncolors > 255) {
        SDL_Color c0 = surface->format->palette->colors[0];
        SDL_Color c1 = surface->format->palette->colors[1];
        SDL_Color c255 = surface->format->palette->colors[255];

        v5_log("%s palette: [0]=%u,%u,%u,%u [1]=%u,%u,%u,%u [255]=%u,%u,%u,%u",
               name,
               c0.r, c0.g, c0.b, c0.a,
               c1.r, c1.g, c1.b, c1.a,
               c255.r, c255.g, c255.b, c255.a);
    }
}

static bool v5_present_with_window_surface(SDL_Surface *source, bool magenta)
{
    SDL_Surface *window_surface;
    int result;

    if (window == NULL)
        return false;

    SDL_ClearError();
    window_surface = SDL_GetWindowSurface(window);
    v5_log("Window-surface fallback: surface=%p magenta=%d", (void *)window_surface, magenta ? 1 : 0);

    if (window_surface == NULL) {
        v5_log_error("SDL_GetWindowSurface failed");
        return false;
    }

    if (magenta) {
        Uint32 color = SDL_MapRGB(window_surface->format, 255, 0, 255);
        result = SDL_FillRect(window_surface, NULL, color);
        v5_log("SDL_FillRect(magenta) result=%d", result);
    } else {
        if (source == NULL)
            return false;

        result = SDL_BlitScaled(source, NULL, window_surface, NULL);
        v5_log("SDL_BlitScaled(drawSurface -> windowSurface) result=%d", result);
    }

    if (result < 0)
        v5_log_error("Window-surface drawing failed");

    SDL_ClearError();
    result = SDL_UpdateWindowSurface(window);
    v5_log("SDL_UpdateWindowSurface result=%d", result);

    if (result < 0)
        v5_log_error("SDL_UpdateWindowSurface failed");

    return result == 0;
}

extern grs_screen *svga_screen;
extern frc *svga_render_context;

//--------------------
//  Prototypes
//--------------------
extern void init_all(void);
extern void inv_change_fullscreen(uchar on);
extern void object_data_flush(void);
extern errtype load_da_palette(void);

// see Prefs.c
extern void CreateDefaultKeybindsFile(void);
extern void LoadHotkeyKeybinds(void);
extern void LoadMoveKeybinds(void);

//------------------------------------------------------------------------------------
//		Main function.
//------------------------------------------------------------------------------------
int main(int argc, char **argv) {
    // Save the arguments for later

    num_args = argc;
    arg_values = argv;

    // FIXME externalize this
    log_set_quiet(0);
    log_set_level(LOG_INFO);

    INFO("Logger initialized");

    // init mac managers

    InitMac();

    // Initialize the preferences file.

    SetDefaultPrefs();
    LoadPrefs();

    // see Prefs.c
    CreateDefaultKeybindsFile(); // only if it doesn't already exist
    // even if keybinds file still doesn't exist, defaults will be set here
    LoadHotkeyKeybinds();
    LoadMoveKeybinds();

    // Process some startup arguments

    bool show_splash = !CheckArgument("-nosplash");

    // CC: Modding support! This is so exciting.

    ProcessModArgs(argc, argv);

    // Initialize

    init_all();
    setup_init();

    gPlayingGame = true;

    load_da_palette();
    gr_clear(0xFF);

    // Draw the splash screen

    INFO("Showing splash screen");
    splash_draw(show_splash);

    // Start in the Main Menu loop

    _new_mode = _current_loop = SETUP_LOOP;
    loopmode_enter(SETUP_LOOP);

    // Start the main loop

    INFO("Showing main menu, starting game loop");
    mainloop(argc, argv);

    status_bio_end();
    stop_music();

    return 0;
}

bool CheckArgument(char *arg) {
    if (arg == NULL)
        return false;

    for (int i = 1; i < num_args; i++) {
        if (strcmp(arg_values[i], arg) == 0) {
            return true;
        }
    }

    return false;
}

void InitSDL() {
    int result;
    Uint32 window_flags;

    remove("GPU_C2D_V15D.log");
    v5_log("PROJECT CITADEL V15D SOURCE VS MORTON TRUTH TEST START | build=%s %s", __DATE__, __TIME__);

    SDL_SetHint(SDL_HINT_NO_SIGNAL_HANDLERS, "1");
    SDL_SetHint(SDL_HINT_RENDER_DRIVER, "software");

    SDL_ClearError();
    result = SDL_Init(SDL_INIT_VIDEO | SDL_INIT_TIMER | SDL_INIT_AUDIO);
    v5_log("SDL_Init result=%d", result);
    v5_log_error("After SDL_Init");

    if (result < 0) {
        DEBUG("%s: Init failed", __FUNCTION__);
    }

    // TODO: figure out some universal set of settings that work...
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 2);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
    SDL_GL_SetAttribute(SDL_GL_RED_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_GREEN_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_BLUE_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_DEPTH_SIZE, 24);
    SDL_GL_SetAttribute(SDL_GL_STENCIL_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_DOUBLEBUFFER, 1);
    SDL_GL_SetAttribute(SDL_GL_ALPHA_SIZE, 8);
    SDL_GL_SetAttribute(SDL_GL_BUFFER_SIZE, 32);

    gr_init();

    extern short svga_mode_data[];
    gr_set_mode(svga_mode_data[gShockPrefs.doVideoMode], TRUE);

    INFO("Setting up screen and render contexts");

    // Create a canvas to draw to
    SetupOffscreenBitmaps(grd_cap->w, grd_cap->h);

    v5_log("After SetupOffscreenBitmaps: grd_cap=%p size=%dx%d gScreen=%dx%d",
           (void *)grd_cap,
           grd_cap != NULL ? grd_cap->w : -1,
           grd_cap != NULL ? grd_cap->h : -1,
           gScreenWide,
           gScreenHigh);
    v5_log_surface("drawSurface at InitSDL", drawSurface);
    v5_log_surface("offscreenDrawSurface at InitSDL", offscreenDrawSurface);

    // Open our window.
    char window_title[128];
    sprintf(window_title, "System Shock - %s", SHOCKOLATE_VERSION);

#if defined(__3DS__) || defined(_3DS)
    /*
     * The 3DS backend does not need a hidden, resizable OpenGL window for
     * this software-rendered build. Those desktop flags can prevent a usable
     * renderer from being created.
     */
    window_flags = SDL_WINDOW_SHOWN;
#else
    window_flags = SDL_WINDOW_HIDDEN |
                   SDL_WINDOW_RESIZABLE |
                   SDL_WINDOW_ALLOW_HIGHDPI |
                   SDL_WINDOW_OPENGL;
#endif

    SDL_ClearError();
#if defined(__3DS__) || defined(_3DS)
    window = SDL_CreateWindow(window_title,
                              SDL_WINDOWPOS_UNDEFINED,
                              SDL_WINDOWPOS_UNDEFINED,
                              CITADEL_3DS_TOP_WIDTH,
                              CITADEL_3DS_TOP_HEIGHT,
                              window_flags);
#else
    window = SDL_CreateWindow(window_title,
                              SDL_WINDOWPOS_CENTERED,
                              SDL_WINDOWPOS_CENTERED,
                              grd_cap->w,
                              grd_cap->h,
                              window_flags);
#endif
    v5_log("SDL_CreateWindow flags=0x%08X result=%p", (unsigned int)window_flags, (void *)window);
    v5_log_error("After SDL_CreateWindow");

    if (window == NULL) {
        SDL_ClearError();
#if defined(__3DS__) || defined(_3DS)
        window = SDL_CreateWindow(window_title,
                                  SDL_WINDOWPOS_UNDEFINED,
                                  SDL_WINDOWPOS_UNDEFINED,
                                  CITADEL_3DS_TOP_WIDTH,
                                  CITADEL_3DS_TOP_HEIGHT,
                                  0);
#else
        window = SDL_CreateWindow(window_title,
                                  SDL_WINDOWPOS_UNDEFINED,
                                  SDL_WINDOWPOS_UNDEFINED,
                                  grd_cap->w,
                                  grd_cap->h,
                                  0);
#endif
        v5_log("SDL_CreateWindow fallback flags=0 result=%p", (void *)window);
        v5_log_error("After fallback SDL_CreateWindow");
    }

    // Create the palette
    sdlPalette = SDL_AllocPalette(256);
    v5_log("SDL_AllocPalette result=%p", (void *)sdlPalette);
    v5_log_error("After SDL_AllocPalette");

    // Setup the screen
    svga_screen = cit_screen = gr_alloc_screen(grd_cap->w, grd_cap->h);
    gr_set_screen(svga_screen);

    gr_alloc_ipal();

    SDL_ShowCursor(SDL_DISABLE);

    atexit(SDL_Quit);

    if (window != NULL) {
        SDL_ShowWindow(window);
        SDL_RaiseWindow(window);
    }

    /*
     * Try the existing request first, then progressively safer fallbacks.
     */
    SDL_ClearError();
    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_PRESENTVSYNC);
    v5_log("SDL_CreateRenderer(PRESENTVSYNC) result=%p", (void *)renderer);
    v5_log_error("After PRESENTVSYNC renderer creation");

    if (renderer == NULL) {
        SDL_ClearError();
        renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE);
        v5_log("SDL_CreateRenderer(SOFTWARE) result=%p", (void *)renderer);
        v5_log_error("After SOFTWARE renderer creation");
    }

    if (renderer == NULL) {
        SDL_ClearError();
        renderer = SDL_CreateRenderer(window, -1, 0);
        v5_log("SDL_CreateRenderer(flags=0) result=%p", (void *)renderer);
        v5_log_error("After flags=0 renderer creation");
    }

    if (renderer != NULL) {
        SDL_RendererInfo info;
        memset(&info, 0, sizeof(info));

        SDL_ClearError();
        result = SDL_GetRendererInfo(renderer, &info);
        v5_log("SDL_GetRendererInfo result=%d name=%s flags=0x%08X formats=%u max=%dx%d",
               result,
               info.name != NULL ? info.name : "(null)",
               (unsigned int)info.flags,
               (unsigned int)info.num_texture_formats,
               info.max_texture_width,
               info.max_texture_height);
        v5_log_error("After SDL_GetRendererInfo");

        {
            int output_width = -1;
            int output_height = -1;

            SDL_ClearError();
            result = SDL_GetRendererOutputSize(renderer, &output_width, &output_height);
            v5_log("SDL_GetRendererOutputSize result=%d size=%dx%d",
                   result,
                   output_width,
                   output_height);
            v5_log_error("After SDL_GetRendererOutputSize");
        }

        SDL_ClearError();
#if defined(__3DS__) || defined(_3DS)
        result = SDL_RenderSetLogicalSize(renderer,
                                          CITADEL_3DS_TOP_WIDTH,
                                          CITADEL_3DS_TOP_HEIGHT);
        v5_log("SDL_RenderSetLogicalSize(%d,%d) result=%d",
               CITADEL_3DS_TOP_WIDTH,
               CITADEL_3DS_TOP_HEIGHT,
               result);
#else
        result = SDL_RenderSetLogicalSize(renderer, grd_cap->w, grd_cap->h);
        v5_log("SDL_RenderSetLogicalSize(%d,%d) result=%d",
               grd_cap->w,
               grd_cap->h,
               result);
#endif
        v5_log_error("After SDL_RenderSetLogicalSize");
    }

#if defined(__3DS__) || defined(_3DS)
    /*
     * The N3DS SDL2 backend exposes the top and bottom LCDs as display 0 and
     * display 1. Position macros select the second display at creation time.
     * This build is deliberately visual-only: the existing top presentation
     * and all input behavior remain unchanged.
     */
    if (SDL_GetNumVideoDisplays() >= 2) {
        int bottom_position = SDL_WINDOWPOS_UNDEFINED_DISPLAY(1);

        SDL_ClearError();
        citadel_bottom_window = SDL_CreateWindow(
            "System Shock - Bottom Interface",
            bottom_position,
            bottom_position,
            CITADEL_3DS_BOTTOM_WIDTH,
            CITADEL_3DS_BOTTOM_HEIGHT,
            SDL_WINDOW_SHOWN);

        v5_log("BOTTOM SDL_CreateWindow display_count=%d result=%p display_index=%d error=\"%s\"",
               SDL_GetNumVideoDisplays(),
               (void *)citadel_bottom_window,
               citadel_bottom_window != NULL
                   ? SDL_GetWindowDisplayIndex(citadel_bottom_window)
                   : -1,
               SDL_GetError());

        if (citadel_bottom_window != NULL) {
            SDL_ShowWindow(citadel_bottom_window);

            citadel_bottom_renderer =
                citadel_create_renderer_with_fallbacks(
                    citadel_bottom_window,
                    "BOTTOM");

            if (citadel_bottom_renderer != NULL) {
                SDL_ClearError();
                result = SDL_RenderSetLogicalSize(
                    citadel_bottom_renderer,
                    CITADEL_3DS_BOTTOM_WIDTH,
                    CITADEL_3DS_BOTTOM_HEIGHT);

                v5_log("BOTTOM SDL_RenderSetLogicalSize(320,240) result=%d error=\"%s\"",
                       result,
                       SDL_GetError());
            }
        }
    } else {
        v5_log("BOTTOM unavailable: SDL reports only %d video display(s)",
               SDL_GetNumVideoDisplays());
    }
#endif

#if defined(__3DS__) || defined(_3DS)
    if (!citadel_gpu_initialize()) {
        v5_log("GPU PRIMARY PATH unavailable; retaining SDL fallback");
    }
#endif

    // Startup OpenGL
    init_opengl();

    /*
     * Start the visual diagnostic after the window is visible.
     * SDLDraw() will hold solid magenta for approximately three seconds,
     * then switch to the actual game surface.
     */
    SDLDraw();
}

SDL_Color gamePalette[256];
bool UseCutscenePalette = FALSE; // see cutsloop.c
void SetSDLPalette(int index, int count, uchar *pal) {
    static bool gammalut_init = 0;
    static uchar gammalut[100 - 10 + 1][256];
    if (!gammalut_init) {
        double factor = (use_opengl() ? 1.0 : 2.2); // OpenGL uses 2.2
        int i, j;
        for (i = 10; i <= 100; i++) {
            double gamma = (double)i * 1.0 / 100;
            gamma = 1 - gamma;
            gamma *= gamma;
            gamma = 1 - gamma;
            gamma = 1 / (gamma * factor);
            for (j = 0; j < 256; j++)
                gammalut[i - 10][j] = (uchar)(pow((double)j / 255, gamma) * 255);
        }
        gammalut_init = 1;
        INFO("Gamma LUT init\'ed");
    }

    int gam = gShockPrefs.doGamma;
    if (gam < 10)
        gam = 10;
    if (gam > 100)
        gam = 100;
    gam -= 10;

    for (int i = index; i < index + count; i++) {
        gamePalette[i].r = gammalut[gam][*pal++];
        gamePalette[i].g = gammalut[gam][*pal++];
        gamePalette[i].b = gammalut[gam][*pal++];
        gamePalette[i].a = 0xff;
    }

    if (!UseCutscenePalette) {
        // Hack black!
        gamePalette[255].r = 0x0;
        gamePalette[255].g = 0x0;
        gamePalette[255].b = 0x0;
        gamePalette[255].a = 0xff;
    }

#if defined(__3DS__) || defined(_3DS)
    citadel_gpu_update_palette565();
#endif

    SDL_SetPaletteColors(sdlPalette, gamePalette, 0, 256);
    SDL_SetSurfacePalette(drawSurface, sdlPalette);
    SDL_SetSurfacePalette(offscreenDrawSurface, sdlPalette);

    if (should_opengl_swap())
        opengl_change_palette();
}

void SDLDraw() {
    Uint32 now;
    int result;
    int source_width;
    int source_height;

    ++v5_sdl_draw_calls;
    now = SDL_GetTicks();

    if (v5_magenta_until == 0) {
        v5_magenta_until = now + 500;
        v5_log("SDLDraw first call: renderer=%p window=%p drawSurface=%p magenta_until=%u",
               (void *)renderer,
               (void *)window,
               (void *)drawSurface,
               (unsigned int)v5_magenta_until);
    }

    /*
     * Brief visual confirmation:
     * - Magenta visible: window/renderer presentation is functional.
     * - Still black: renderer presentation is broken; inspect V5 log/fallback.
     */
    if (!SDL_TICKS_PASSED(now, v5_magenta_until)) {
        if (!v5_magenta_announced) {
            v5_log("MAGENTA TEST ACTIVE for approximately half a second");
            v5_magenta_announced = true;
        }

#if defined(__3DS__) || defined(_3DS)
        if (citadel_gpu_ready) {
            if (!citadel_gpu_present(NULL, true)) {
                v5_log("GPU MAGENTA presentation failed; disabling GPU primary path");
                citadel_gpu_ready = false;
            } else {
                return;
            }
        }
#endif

        if (renderer != NULL) {
            SDL_ClearError();
            result = SDL_SetRenderDrawColor(renderer, 255, 0, 255, 255);
            v5_log("SDL_SetRenderDrawColor(magenta) result=%d", result);

            SDL_ClearError();
            result = SDL_RenderClear(renderer);
            v5_log("SDL_RenderClear(magenta) result=%d", result);
            if (result < 0)
                v5_log_error("Magenta SDL_RenderClear failed");

            SDL_RenderPresent(renderer);
        } else {
            v5_present_with_window_surface(NULL, true);
        }

#if defined(__3DS__) || defined(_3DS)
        if (citadel_bottom_renderer != NULL) {
            SDL_SetRenderDrawColor(citadel_bottom_renderer, 24, 24, 24, 255);
            SDL_RenderClear(citadel_bottom_renderer);
            SDL_RenderPresent(citadel_bottom_renderer);
        }
#endif
        return;
    }

    if (!v5_normal_announced) {
        v5_log("MAGENTA TEST COMPLETE; beginning real drawSurface presentation");
        v5_normal_announced = true;
    }

#if defined(__3DS__) || defined(_3DS)
    if (citadel_gpu_ready) {
        if (!citadel_gpu_present(drawSurface, false)) {
            v5_log("GPU presentation failed at frame=%u; disabling GPU primary path",
                   v5_sdl_draw_calls);
            citadel_gpu_ready = false;
        } else {
            return;
        }
    }
#endif

    if (should_opengl_swap()) {
        v5_log("SDLDraw call %u: OpenGL swap path active", v5_sdl_draw_calls);

        // We want the UI background to be transparent!
        sdlPalette->colors[255].a = 0x00;

        // Draw the OpenGL view
        opengl_swap_and_restore(drawSurface);

        // Set the palette back, and we are done
        sdlPalette->colors[255].a = 0xff;
        return;
    }

    if (v5_sdl_draw_calls <= 190 || (v5_sdl_draw_calls % 300) == 0) {
        v5_log("SDLDraw call=%u renderer=%p drawSurface=%p gScreen=%dx%d",
               v5_sdl_draw_calls,
               (void *)renderer,
               (void *)drawSurface,
               gScreenWide,
               gScreenHigh);
        v5_log_surface("drawSurface during presentation", drawSurface);
    }

    /*
     * Never pass a zero-sized or out-of-range source rectangle. The original
     * code blindly used gScreenWide/gScreenHigh, which may be unset on 3DS.
     */
    source_width = gScreenWide;
    source_height = gScreenHigh;

    if (drawSurface != NULL) {
        if (source_width <= 0 || source_width > drawSurface->w)
            source_width = drawSurface->w;
        if (source_height <= 0 || source_height > drawSurface->h)
            source_height = drawSurface->h;
    }

    if (renderer == NULL) {
        v5_log("Renderer is NULL; using window-surface fallback");
        v5_present_with_window_surface(drawSurface, false);
        return;
    }

    SDL_ClearError();
    result = SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255);
    if (result < 0)
        v5_log_error("SDL_SetRenderDrawColor(black) failed");

    SDL_ClearError();
    result = SDL_RenderClear(renderer);
    if (v5_sdl_draw_calls <= 190)
        v5_log("SDL_RenderClear(real frame) result=%d", result);
    if (result < 0)
        v5_log_error("SDL_RenderClear(real frame) failed");

    SDL_ClearError();
    SDL_Texture *texture = SDL_CreateTextureFromSurface(renderer, drawSurface);
    if (v5_sdl_draw_calls <= 190 || texture == NULL) {
        v5_log("SDL_CreateTextureFromSurface result=%p source=%dx%d",
               (void *)texture,
               source_width,
               source_height);
        v5_log_error("After SDL_CreateTextureFromSurface");
    }

    if (texture == NULL) {
        v5_log("Texture creation failed; trying window-surface fallback");
        v5_present_with_window_surface(drawSurface, false);
        return;
    }

    SDL_Rect srcRect = {0, 0, source_width, source_height};

    SDL_ClearError();
#if defined(__3DS__) || defined(_3DS)
    {
        static int last_logged_layout = -1;
        bool split_layout = citadel_3ds_use_split_layout();
        SDL_Rect dstRect;

        if (split_layout) {
            /*
             * SS3DS gameplay view: crop away the relocated lower interface,
             * then stretch the complete gameplay/HUD region across 400x240.
             * Both side icon columns and the top status strip remain visible.
             */
            srcRect = citadel_scale_reference_rect(
                drawSurface,
                CITADEL_REF_GAME_X,
                CITADEL_REF_GAME_Y,
                CITADEL_REF_GAME_W,
                CITADEL_REF_GAME_H);

            dstRect.x = 0;
            dstRect.y = 0;
            dstRect.w = CITADEL_3DS_TOP_WIDTH;
            dstRect.h = CITADEL_3DS_TOP_HEIGHT;
        } else {
            /*
             * Menus and SELECT legacy mode: show the full 4:3 frame exactly
             * like the proven V6/V7 presentation.
             */
            srcRect.x = 0;
            srcRect.y = 0;
            srcRect.w = source_width;
            srcRect.h = source_height;

            dstRect.x = CITADEL_3DS_GAME_X;
            dstRect.y = CITADEL_3DS_GAME_Y;
            dstRect.w = CITADEL_3DS_GAME_WIDTH;
            dstRect.h = CITADEL_3DS_GAME_HEIGHT;
        }

        result = SDL_RenderCopy(renderer, texture, &srcRect, &dstRect);

        if (last_logged_layout != (split_layout ? 1 : 0)) {
            v5_log("TOP LAYOUT changed to %s current_loop=%d "
                   "src={%d,%d,%d,%d} dst={%d,%d,%d,%d}",
                   split_layout ? "SPLIT" : "LEGACY",
                   (int)_current_loop,
                   srcRect.x,
                   srcRect.y,
                   srcRect.w,
                   srcRect.h,
                   dstRect.x,
                   dstRect.y,
                   dstRect.w,
                   dstRect.h);
            last_logged_layout = split_layout ? 1 : 0;
        }

        if (v5_sdl_draw_calls <= 190 || result < 0) {
            v5_log("SDL_RenderCopy result=%d layout=%s "
                   "src={%d,%d,%d,%d} dst={%d,%d,%d,%d}",
                   result,
                   split_layout ? "SPLIT" : "LEGACY",
                   srcRect.x,
                   srcRect.y,
                   srcRect.w,
                   srcRect.h,
                   dstRect.x,
                   dstRect.y,
                   dstRect.w,
                   dstRect.h);
            v5_log_error("After SDL_RenderCopy");
        }
    }
#else
    result = SDL_RenderCopy(renderer, texture, &srcRect, NULL);
    if (v5_sdl_draw_calls <= 190 || result < 0) {
        v5_log("SDL_RenderCopy result=%d src={0,0,%d,%d}",
               result,
               source_width,
               source_height);
        v5_log_error("After SDL_RenderCopy");
    }
#endif

    SDL_DestroyTexture(texture);

    SDL_RenderPresent(renderer);

#if defined(__3DS__) || defined(_3DS)
    citadel_present_bottom_layout(drawSurface);
#endif
}

bool MouseCaptured = FALSE;

extern int mlook_enabled;

void CaptureMouse(bool capture) {
    MouseCaptured = (capture && gShockPrefs.goCaptureMouse);

    if (!MouseCaptured && mlook_enabled && SDL_GetRelativeMouseMode() == SDL_TRUE) {
        SDL_SetRelativeMouseMode(SDL_FALSE);

        int w, h;
        SDL_GetWindowSize(window, &w, &h);
        SDL_WarpMouseInWindow(window, w / 2, h / 2);
    } else
        SDL_SetRelativeMouseMode(MouseCaptured ? SDL_TRUE : SDL_FALSE);
}
