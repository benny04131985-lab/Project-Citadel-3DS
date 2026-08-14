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
#include <string.h>
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

#warning "PROJECT CITADEL V16: release candidate is ACTIVE"

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
#define CITADEL_GPU_TEXTURE_WIDTH    1024
#define CITADEL_GPU_TEXTURE_HEIGHT   512

/*
 * V15J transports the original 4:3 Shock frame at its full 640x480 size
 * inside a 1024x512 power-of-two texture. The unused right and lower regions
 * remain black padding. This removes the intermediate 512x384 resample so
 * menu text and thin UI details survive until the one final LCD scale step.
 */
#define CITADEL_GPU_CONTENT_WIDTH    640
#define CITADEL_GPU_CONTENT_HEIGHT   480

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

/* V15E authoritative palette synchronization instrumentation. */
static unsigned long citadel_gpu_palette_refreshes = 0;
static unsigned int citadel_gpu_palette_change_logs = 0;

/* V15F frozen-frame and persistent-image diagnostic state. */
static Uint32 citadel_gpu_v15f_started_at = 0;
static Uint32 citadel_gpu_v15f_freeze_until = 0;
static bool citadel_gpu_v15f_capture_done = false;
static bool citadel_gpu_v15f_freeze_active = false;
static bool citadel_gpu_v15f_resume_logged = false;
static Tex3DS_SubTexture citadel_gpu_v15f_subtexture;
static C2D_Image citadel_gpu_v15f_image;

/* V15G fresh texture object / format-control diagnostic state. */
#define CITADEL_GPU_RGBA8_BYTES \
    (CITADEL_GPU_TEXTURE_PIXELS * sizeof(u32))

enum {
    CITADEL_V15G_PHASE_LIVE = 0,
    CITADEL_V15G_PHASE_FRESH_RGB565 = 1,
    CITADEL_V15G_PHASE_FRESH_RGBA8 = 2,
    CITADEL_V15G_PHASE_COMPLETE = 3
};

static C3D_Tex citadel_gpu_v15g_rgb565_texture;
static C3D_Tex citadel_gpu_v15g_rgba8_texture;
static bool citadel_gpu_v15g_rgb565_initialized = false;
static bool citadel_gpu_v15g_rgba8_initialized = false;
static u32 *citadel_gpu_v15g_rgba8_staging = NULL;

static Tex3DS_SubTexture citadel_gpu_v15g_subtexture;
static C2D_Image citadel_gpu_v15g_rgb565_image;
static C2D_Image citadel_gpu_v15g_rgba8_image;

static Uint32 citadel_gpu_v15g_started_at = 0;
static Uint32 citadel_gpu_v15g_phase_until = 0;
static int citadel_gpu_v15g_phase = CITADEL_V15G_PHASE_LIVE;
static bool citadel_gpu_v15g_capture_done = false;


/* V15H official tex3ds asset vs runtime-generated control texture. */
#define CITADEL_V15H_CONTROL_SIZE 256
#define CITADEL_V15H_CONTROL_PIXELS \
    (CITADEL_V15H_CONTROL_SIZE * CITADEL_V15H_CONTROL_SIZE)
#define CITADEL_V15H_CONTROL_BYTES \
    (CITADEL_V15H_CONTROL_PIXELS * sizeof(u16))

enum {
    CITADEL_V15H_PHASE_LIVE = 0,
    CITADEL_V15H_PHASE_OFFICIAL_TEX3DS = 1,
    CITADEL_V15H_PHASE_RUNTIME_CONTROL = 2,
    CITADEL_V15H_PHASE_COMPLETE = 3
};

static C2D_SpriteSheet citadel_gpu_v15h_sheet = NULL;
static C2D_Image citadel_gpu_v15h_official_image;
static C3D_Tex citadel_gpu_v15h_manual_texture;
static bool citadel_gpu_v15h_manual_initialized = false;
static u16 *citadel_gpu_v15h_candidate = NULL;
static Tex3DS_SubTexture citadel_gpu_v15h_manual_subtexture;
static C2D_Image citadel_gpu_v15h_manual_image;
static bool citadel_gpu_v15h_asset_ready = false;
static bool citadel_gpu_v15h_capture_done = false;
static Uint32 citadel_gpu_v15h_phase_until = 0;
static int citadel_gpu_v15h_phase = CITADEL_V15H_PHASE_LIVE;

/* Project Citadel V16 branded startup splash. */
#define CITADEL_V16_SPLASH_DURATION_MS 2200

static C2D_SpriteSheet citadel_v16_splash_sheet = NULL;
static C2D_Image citadel_v16_splash_image;
static bool citadel_v16_splash_ready = false;
static bool citadel_v16_splash_started = false;
static bool citadel_v16_splash_finished_logged = false;
static Uint32 citadel_v16_splash_until = 0;

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
static void citadel_gpu_v15g_prepare_images(void);
static bool citadel_gpu_v15g_phase_active(void);
static bool citadel_gpu_v15g_draw_phase(void);
static bool citadel_gpu_v15h_initialize_control(void);
static bool citadel_gpu_v15h_phase_active(void);
static bool citadel_gpu_v15h_draw_phase(void);
static bool citadel_v16_load_splash(void);
static bool citadel_v16_present_splash(void);
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

    if (citadel_v16_splash_sheet != NULL) {
        C2D_SpriteSheetFree(citadel_v16_splash_sheet);
        citadel_v16_splash_sheet = NULL;
        citadel_v16_splash_ready = false;
    }

    if (citadel_gpu_top_target != NULL) {
        C3D_RenderTargetDelete(citadel_gpu_top_target);
        citadel_gpu_top_target = NULL;
    }

    if (citadel_gpu_bottom_target != NULL) {
        C3D_RenderTargetDelete(citadel_gpu_bottom_target);
        citadel_gpu_bottom_target = NULL;
    }

    if (citadel_gpu_v15h_sheet != NULL) {
        C2D_SpriteSheetFree(citadel_gpu_v15h_sheet);
        citadel_gpu_v15h_sheet = NULL;
    }

    if (citadel_gpu_v15h_manual_initialized) {
        C3D_TexDelete(&citadel_gpu_v15h_manual_texture);
        citadel_gpu_v15h_manual_initialized = false;
    }

    if (citadel_gpu_v15h_candidate != NULL) {
        linearFree(citadel_gpu_v15h_candidate);
        citadel_gpu_v15h_candidate = NULL;
    }

    if (citadel_gpu_v15g_rgb565_initialized) {
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


/*
 * PROJECT CITADEL V15I: SDL-compatible Citro2D screen target.
 *
 * SDL2's Nintendo 3DS video backend initializes both LCD framebuffers as
 * GSP_RGBA8_OES (four bytes per pixel). Citro2D's convenience
 * C2D_CreateScreenTarget() assumes the libctru default BGR8 framebuffer and
 * hardcodes GX_TRANSFER_FMT_RGB8 (three bytes per pixel) as its output.
 *
 * Feeding a three-byte display transfer into SDL's four-byte framebuffer
 * changes the physical row stride and fractures the entire completed frame,
 * including target clears and untextured rectangles.
 *
 * Keep SDL's framebuffer ownership and mode intact. Only customize the final
 * Citro3D render-target transfer so its output format matches SDL's RGBA8
 * framebuffer exactly.
 */
static C3D_RenderTarget *
citadel_gpu_create_sdl_rgba8_screen_target(gfxScreen_t screen,
                                            gfx3dSide_t side)
{
    int height;
    C3D_RenderTarget *target;

    if (screen == GFX_TOP) {
        height = gfxIsWide()
            ? GSP_SCREEN_HEIGHT_TOP_2X
            : GSP_SCREEN_HEIGHT_TOP;
    } else {
        height = GSP_SCREEN_HEIGHT_BOTTOM;
    }

    target = C3D_RenderTargetCreate(GSP_SCREEN_WIDTH,
                                    height,
                                    GPU_RB_RGBA8,
                                    GPU_RB_DEPTH16);
    if (target == NULL)
        return NULL;

    C3D_RenderTargetSetOutput(
        target,
        screen,
        side,
        GX_TRANSFER_FLIP_VERT(0) |
        GX_TRANSFER_OUT_TILED(0) |
        GX_TRANSFER_RAW_COPY(0) |
        GX_TRANSFER_IN_FORMAT(GX_TRANSFER_FMT_RGBA8) |
        GX_TRANSFER_OUT_FORMAT(GX_TRANSFER_FMT_RGBA8) |
        GX_TRANSFER_SCALING(GX_TRANSFER_SCALE_NO));

    return target;
}

static bool citadel_v16_load_splash(void)
{
    static const char *paths[] = {
        "Hack-i-Ben_Splash.t3x",
        "sdmc:/3ds/SystemShock/Hack-i-Ben_Splash.t3x",
        "sdmc:/3ds/systemshock/Hack-i-Ben_Splash.t3x"
    };
    unsigned int i;

    memset(&citadel_v16_splash_image,
           0,
           sizeof(citadel_v16_splash_image));

    for (i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i) {
        citadel_v16_splash_sheet =
            C2D_SpriteSheetLoad(paths[i]);

        if (citadel_v16_splash_sheet == NULL) {
            v5_log("GPU V16 SPLASH LOAD path=%s result=FAIL",
                   paths[i]);
            continue;
        }

        if (C2D_SpriteSheetCount(citadel_v16_splash_sheet) < 1) {
            v5_log("GPU V16 SPLASH LOAD path=%s result=FAIL reason=no-images",
                   paths[i]);
            C2D_SpriteSheetFree(citadel_v16_splash_sheet);
            citadel_v16_splash_sheet = NULL;
            continue;
        }

        citadel_v16_splash_image =
            C2D_SpriteSheetGetImage(
                citadel_v16_splash_sheet,
                0);

        if (citadel_v16_splash_image.tex == NULL ||
            citadel_v16_splash_image.subtex == NULL) {
            v5_log("GPU V16 SPLASH LOAD path=%s result=FAIL reason=invalid-image",
                   paths[i]);
            C2D_SpriteSheetFree(citadel_v16_splash_sheet);
            citadel_v16_splash_sheet = NULL;
            continue;
        }

        citadel_v16_splash_ready = true;

        v5_log("GPU V16 SPLASH LOAD path=%s result=SUCCESS "
               "image=%ux%u texture=%ux%u",
               paths[i],
               (unsigned int)citadel_v16_splash_image.subtex->width,
               (unsigned int)citadel_v16_splash_image.subtex->height,
               (unsigned int)citadel_v16_splash_image.tex->width,
               (unsigned int)citadel_v16_splash_image.tex->height);

        return true;
    }

    v5_log("GPU V16 SPLASH unavailable; continuing directly to game");
    return false;
}

static bool citadel_gpu_initialize(void)
{
    memset(&citadel_gpu_texture, 0, sizeof(citadel_gpu_texture));
    memset(&citadel_gpu_v15g_rgb565_texture,
           0,
           sizeof(citadel_gpu_v15g_rgb565_texture));
    memset(&citadel_gpu_v15g_rgba8_texture,
           0,
           sizeof(citadel_gpu_v15g_rgba8_texture));

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

    v5_log("GPU V16 SCREEN FORMAT before-targets "
           "top=%u bottom=%u expected_rgba8=%u",
           (unsigned int)gfxGetScreenFormat(GFX_TOP),
           (unsigned int)gfxGetScreenFormat(GFX_BOTTOM),
           (unsigned int)GSP_RGBA8_OES);

    citadel_gpu_top_target =
        citadel_gpu_create_sdl_rgba8_screen_target(
            GFX_TOP,
            GFX_LEFT);
    citadel_gpu_bottom_target =
        citadel_gpu_create_sdl_rgba8_screen_target(
            GFX_BOTTOM,
            GFX_LEFT);

    v5_log("GPU V16 TARGET OUTPUT transfer_in=RGBA8 "
           "transfer_out=RGBA8 screen_framebuffer=SDL_RGBA8");

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

    /*
     * V16 removes the V15G fresh-texture diagnostics from the live build.
     * This avoids allocating the extra RGB565/RGBA8 textures and staging
     * buffer now that the RGBA8 LCD transfer fix is proven.
     */
    citadel_gpu_v15g_rgb565_initialized = false;
    citadel_gpu_v15g_rgba8_initialized = false;
    citadel_gpu_v15g_rgba8_staging = NULL;


    /* V15J is a production-quality transport pass. Disable all timed
     * diagnostic phases and remove the external control-asset requirement.
     */
    citadel_gpu_v15h_asset_ready = false;
    citadel_gpu_v15h_capture_done = true;
    citadel_gpu_v15h_phase = CITADEL_V15H_PHASE_COMPLETE;

    citadel_gpu_v15g_capture_done = true;
    citadel_gpu_v15g_phase = CITADEL_V15G_PHASE_COMPLETE;

    citadel_gpu_update_palette565();
    citadel_v16_load_splash();

    citadel_gpu_ready = true;
    atexit(citadel_gpu_shutdown);

    v5_log("GPU V16 RELEASE PIPELINE ready texture=%dx%d content=%dx%d "
           "default-mode=640x400 source-resample=none filter=NEAREST",
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
/*
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
        v5_log("GPU V16 PALETTE SYNC refresh=%lu mismatches=%u "
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

/*
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
 * Convert the current indexed Shock surface into the full-resolution
 * 640x480 RGB565 transport image inside citadel_gpu_staging.
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


static bool citadel_gpu_v15g_phase_active(void)
{
    return citadel_gpu_v15g_phase ==
               CITADEL_V15G_PHASE_FRESH_RGB565 ||
           citadel_gpu_v15g_phase ==
               CITADEL_V15G_PHASE_FRESH_RGBA8;
}

static const char *citadel_gpu_v15g_phase_name(int phase)
{
    switch (phase) {
        case CITADEL_V15G_PHASE_FRESH_RGB565:
            return "FRESH_RGB565";
        case CITADEL_V15G_PHASE_FRESH_RGBA8:
            return "FRESH_RGBA8";
        case CITADEL_V15G_PHASE_COMPLETE:
            return "COMPLETE";
        default:
            return "LIVE";
    }
}

static uint32_t citadel_gpu_v15g_hash_bytes(const void *data,
                                             size_t size)
{
    const u8 *bytes = (const u8 *)data;
    uint32_t hash = 2166136261u;
    size_t i;

    if (bytes == NULL)
        return 0;

    for (i = 0; i < size; ++i) {
        hash ^= (uint32_t)bytes[i];
        hash *= 16777619u;
    }

    return hash;
}

static void citadel_gpu_v15g_log_texture(const char *label,
                                         C3D_Tex *texture)
{
    u32 physical = 0;

    if (texture != NULL && texture->data != NULL)
        physical = osConvertVirtToPhys(texture->data);

    if (texture == NULL) {
        v5_log("GPU V16 TEX %s NULL",
               label != NULL ? label : "(null)");
        return;
    }

    v5_log("GPU V16 TEX %s data=%p phys=0x%08lX "
           "width=%u height=%u fmt=%u size=%lu "
           "dim=0x%08lX param=0x%08lX lod=0x%08lX type=%u",
           label != NULL ? label : "(null)",
           texture->data,
           (unsigned long)physical,
           (unsigned int)texture->width,
           (unsigned int)texture->height,
           (unsigned int)texture->fmt,
           (unsigned long)texture->size,
           (unsigned long)texture->dim,
           (unsigned long)texture->param,
           (unsigned long)texture->lodParam,
           (unsigned int)C3D_TexGetType(texture));
}

static void citadel_gpu_v15g_prepare_images(void)
{
    memset(&citadel_gpu_v15g_subtexture,
           0,
           sizeof(citadel_gpu_v15g_subtexture));

    citadel_gpu_v15g_subtexture.width =
        (u16)CITADEL_GPU_CONTENT_WIDTH;
    citadel_gpu_v15g_subtexture.height =
        (u16)CITADEL_GPU_CONTENT_HEIGHT;
    citadel_gpu_v15g_subtexture.left = 0.0f;
    citadel_gpu_v15g_subtexture.right =
        (float)CITADEL_GPU_CONTENT_WIDTH /
        (float)CITADEL_GPU_TEXTURE_WIDTH;
    citadel_gpu_v15g_subtexture.top = 1.0f;
    citadel_gpu_v15g_subtexture.bottom =
        1.0f -
        ((float)CITADEL_GPU_CONTENT_HEIGHT /
         (float)CITADEL_GPU_TEXTURE_HEIGHT);

    citadel_gpu_v15g_rgb565_image.tex =
        &citadel_gpu_v15g_rgb565_texture;
    citadel_gpu_v15g_rgb565_image.subtex =
        &citadel_gpu_v15g_subtexture;

    citadel_gpu_v15g_rgba8_image.tex =
        &citadel_gpu_v15g_rgba8_texture;
    citadel_gpu_v15g_rgba8_image.subtex =
        &citadel_gpu_v15g_subtexture;
}

/*
 * Convert V15F's proven linear RGB565 frame into tex3ds-compatible RGBA8
 * bytes. tex3ds stores one RGBA8 texel as A, B, G, R bytes; writing the
 * little-endian u32 value 0xRRGGBBAA produces exactly that byte sequence.
 */
static void citadel_gpu_v15g_build_rgba8_staging(void)
{
    int y;

    memset(citadel_gpu_v15g_rgba8_staging,
           0,
           CITADEL_GPU_RGBA8_BYTES);

    for (y = 0; y < CITADEL_GPU_CONTENT_HEIGHT; ++y) {
        const u16 *source_row =
            citadel_gpu_staging +
            ((size_t)y *
             (size_t)CITADEL_GPU_TEXTURE_WIDTH);
        int x;

        for (x = 0; x < CITADEL_GPU_CONTENT_WIDTH; ++x) {
            const u16 value = source_row[x];
            const unsigned int r5 =
                (unsigned int)((value >> 11) & 0x1F);
            const unsigned int g6 =
                (unsigned int)((value >> 5) & 0x3F);
            const unsigned int b5 =
                (unsigned int)(value & 0x1F);
            const unsigned int r8 =
                (r5 << 3) | (r5 >> 2);
            const unsigned int g8 =
                (g6 << 2) | (g6 >> 4);
            const unsigned int b8 =
                (b5 << 3) | (b5 >> 2);
            const size_t offset =
                citadel_gpu_tiled_offset(
                    (unsigned int)x,
                    (unsigned int)y);

            citadel_gpu_v15g_rgba8_staging[offset] =
                ((u32)r8 << 24) |
                ((u32)g8 << 16) |
                ((u32)b8 << 8) |
                0xFFu;
        }
    }
}

static bool citadel_gpu_v15g_capture_fresh_textures(Uint32 now,
                                                     uint32_t linear_hash)
{
    int rgb565_compare;
    int rgba8_compare;
    uint32_t source565_hash;
    uint32_t fresh565_hash;
    uint32_t source_rgba8_hash;
    uint32_t fresh_rgba8_hash;

    if (!citadel_gpu_v15g_rgb565_initialized ||
        !citadel_gpu_v15g_rgba8_initialized ||
        citadel_gpu_v15g_rgba8_staging == NULL ||
        citadel_gpu_texture.data == NULL)
        return false;

    /*
     * Exercise Citro3D's official texture image loader with a brand-new
     * RGB565 object, rather than continuing to mutate the original object.
     */
    C3D_TexLoadImage(&citadel_gpu_v15g_rgb565_texture,
                     citadel_gpu_texture.data,
                     GPU_TEXFACE_2D,
                     0);
    C3D_TexFlush(&citadel_gpu_v15g_rgb565_texture);

    citadel_gpu_v15g_build_rgba8_staging();

    C3D_TexLoadImage(&citadel_gpu_v15g_rgba8_texture,
                     citadel_gpu_v15g_rgba8_staging,
                     GPU_TEXFACE_2D,
                     0);
    C3D_TexFlush(&citadel_gpu_v15g_rgba8_texture);

    rgb565_compare =
        memcmp(citadel_gpu_v15g_rgb565_texture.data,
               citadel_gpu_texture.data,
               CITADEL_GPU_STAGING_BYTES);

    rgba8_compare =
        memcmp(citadel_gpu_v15g_rgba8_texture.data,
               citadel_gpu_v15g_rgba8_staging,
               CITADEL_GPU_RGBA8_BYTES);

    source565_hash =
        citadel_gpu_v15g_hash_bytes(
            citadel_gpu_texture.data,
            CITADEL_GPU_STAGING_BYTES);
    fresh565_hash =
        citadel_gpu_v15g_hash_bytes(
            citadel_gpu_v15g_rgb565_texture.data,
            CITADEL_GPU_STAGING_BYTES);
    source_rgba8_hash =
        citadel_gpu_v15g_hash_bytes(
            citadel_gpu_v15g_rgba8_staging,
            CITADEL_GPU_RGBA8_BYTES);
    fresh_rgba8_hash =
        citadel_gpu_v15g_hash_bytes(
            citadel_gpu_v15g_rgba8_texture.data,
            CITADEL_GPU_RGBA8_BYTES);

    citadel_gpu_v15g_log_texture(
        "ORIGINAL_RGB565",
        &citadel_gpu_texture);
    citadel_gpu_v15g_log_texture(
        "FRESH_RGB565",
        &citadel_gpu_v15g_rgb565_texture);
    citadel_gpu_v15g_log_texture(
        "FRESH_RGBA8",
        &citadel_gpu_v15g_rgba8_texture);

    v5_log("GPU V16 LOAD VERIFY rgb565_memcmp=%d "
           "source_hash=0x%08lX fresh_hash=0x%08lX "
           "rgba8_memcmp=%d source_hash=0x%08lX fresh_hash=0x%08lX "
           "linear_hash=0x%08lX",
           rgb565_compare,
           (unsigned long)source565_hash,
           (unsigned long)fresh565_hash,
           rgba8_compare,
           (unsigned long)source_rgba8_hash,
           (unsigned long)fresh_rgba8_hash,
           (unsigned long)linear_hash);

    citadel_gpu_v15g_capture_done = true;
    citadel_gpu_v15g_phase =
        CITADEL_V15G_PHASE_FRESH_RGB565;
    citadel_gpu_v15g_phase_until = now + 6000;

    v5_log("GPU V16 PHASE begin=%s duration_ms=6000 "
           "loader=C3D_TexLoadImage flush=C3D_TexFlush "
           "bind=AFTER_C2D_SceneBegin draw=C2D_DrawImageAt "
           "bottom_marker=BLUE",
           citadel_gpu_v15g_phase_name(
               citadel_gpu_v15g_phase));

    return true;
}

static bool citadel_gpu_v15g_draw_phase(void)
{
    C3D_Tex *texture;
    C2D_Image image;
    u32 bottom_color;
    bool draw_ok;

    if (citadel_gpu_v15g_phase ==
        CITADEL_V15G_PHASE_FRESH_RGB565) {
        texture = &citadel_gpu_v15g_rgb565_texture;
        image = citadel_gpu_v15g_rgb565_image;
        bottom_color = C2D_Color32(0, 32, 96, 255);
    } else if (citadel_gpu_v15g_phase ==
               CITADEL_V15G_PHASE_FRESH_RGBA8) {
        texture = &citadel_gpu_v15g_rgba8_texture;
        image = citadel_gpu_v15g_rgba8_image;
        bottom_color = C2D_Color32(0, 96, 32, 255);
    } else {
        return false;
    }

    C2D_TargetClear(citadel_gpu_top_target,
                    C2D_Color32(0, 0, 0, 255));
    C2D_TargetClear(citadel_gpu_bottom_target,
                    bottom_color);

    C2D_SceneBegin(citadel_gpu_top_target);

    /*
     * This bind occurs after SceneBegin, and the image itself points at the
     * same fresh object, forcing Citro2D's queued draw to carry the new
     * texture metadata into the PICA200 state.
     */
    C3D_TexBind(0, texture);

    draw_ok =
        C2D_DrawImageAt(
            image,
            (float)CITADEL_3DS_GAME_X,
            (float)CITADEL_3DS_GAME_Y,
            0.0f,
            NULL,
            (float)CITADEL_3DS_GAME_WIDTH /
                (float)CITADEL_GPU_CONTENT_WIDTH,
            (float)CITADEL_3DS_GAME_HEIGHT /
                (float)CITADEL_GPU_CONTENT_HEIGHT);

    /*
     * Submit the queued image while the diagnostic texture binding and scene
     * are unambiguous, instead of waiting for a later scene transition.
     */
    C2D_Flush();

    if (!draw_ok)
        ++citadel_gpu_draw_failures;

    return draw_ok;
}


static const char *citadel_gpu_v15h_phase_name(int phase)
{
    switch (phase) {
        case CITADEL_V15H_PHASE_OFFICIAL_TEX3DS:
            return "OFFICIAL_TEX3DS";
        case CITADEL_V15H_PHASE_RUNTIME_CONTROL:
            return "RUNTIME_CONTROL";
        case CITADEL_V15H_PHASE_COMPLETE:
            return "COMPLETE";
        default:
            return "LIVE";
    }
}

static bool citadel_gpu_v15h_phase_active(void)
{
    /* V15J ships without the timed tex3ds/runtime control phases. */
    return false;
}

static u16 citadel_gpu_v15h_pattern_rgb565(unsigned int x,
                                           unsigned int y)
{
    unsigned int r = x & 0xFFu;
    unsigned int g = y & 0xFFu;
    unsigned int b = ((x * 37u) ^
                      (y * 73u) ^
                      ((x >> 3) * 11u) ^
                      ((y >> 3) * 19u)) & 0xFFu;

    if ((x & 31u) < 2u || (y & 31u) < 2u) {
        r = 255u - r;
        g = 255u - g;
        b = 255u;
    }

    if (x < 8u || x >= 248u || y < 8u || y >= 248u) {
        r = 255u;
        g = 255u;
        b = 255u;
    }

    if (x == y || (x + y) == 255u) {
        r = 255u;
        g = 0u;
        b = 255u;
    }

    return (u16)(((r >> 3) << 11) |
                 ((g >> 2) << 5) |
                 (b >> 3));
}

static size_t citadel_gpu_v15h_offset_variant(unsigned int x,
                                               unsigned int y,
                                               int variant)
{
    const unsigned int size = CITADEL_V15H_CONTROL_SIZE;
    const unsigned int tiles_per_row = size / 8u;
    unsigned int tile_x = x >> 3;
    unsigned int tile_y = y >> 3;
    unsigned int local_x = x & 7u;
    unsigned int local_y = y & 7u;

    switch (variant) {
        case 1: /* Complete vertical pixel flip. */
            y = (size - 1u) - y;
            tile_y = y >> 3;
            local_y = y & 7u;
            break;
        case 2: /* Reverse only the physical 8-row tile bands. */
            tile_y = (tiles_per_row - 1u) - tile_y;
            break;
        case 3: /* Reverse rows inside every 8x8 tile. */
            local_y = 7u - local_y;
            break;
        case 4: /* Swap X/Y contribution to intra-tile Morton order. */
            {
                const unsigned int temporary = local_x;
                local_x = local_y;
                local_y = temporary;
            }
            break;
        case 5: /* Transpose the entire physical image. */
            {
                const unsigned int temporary = tile_x;
                tile_x = tile_y;
                tile_y = temporary;
            }
            {
                const unsigned int temporary = local_x;
                local_x = local_y;
                local_y = temporary;
            }
            break;
        default:
            break;
    }

    return (((size_t)tile_y * (size_t)tiles_per_row +
             (size_t)tile_x) * 64u) +
           (size_t)citadel_gpu_morton8(local_x, local_y);
}

static void citadel_gpu_v15h_build_candidate(int variant)
{
    unsigned int y;

    memset(citadel_gpu_v15h_candidate,
           0,
           CITADEL_V15H_CONTROL_BYTES);

    for (y = 0; y < CITADEL_V15H_CONTROL_SIZE; ++y) {
        unsigned int x;

        for (x = 0; x < CITADEL_V15H_CONTROL_SIZE; ++x) {
            const size_t offset =
                citadel_gpu_v15h_offset_variant(x, y, variant);

            citadel_gpu_v15h_candidate[offset] =
                citadel_gpu_v15h_pattern_rgb565(x, y);
        }
    }
}

static unsigned long citadel_gpu_v15h_count_byte_mismatches(
    const void *left,
    const void *right,
    size_t size,
    size_t *first_offset,
    unsigned int *first_left,
    unsigned int *first_right)
{
    const u8 *a = (const u8 *)left;
    const u8 *b = (const u8 *)right;
    unsigned long mismatches = 0;
    size_t i;

    if (first_offset != NULL)
        *first_offset = (size_t)-1;
    if (first_left != NULL)
        *first_left = 0;
    if (first_right != NULL)
        *first_right = 0;

    for (i = 0; i < size; ++i) {
        if (a[i] != b[i]) {
            if (mismatches == 0) {
                if (first_offset != NULL)
                    *first_offset = i;
                if (first_left != NULL)
                    *first_left = a[i];
                if (first_right != NULL)
                    *first_right = b[i];
            }
            ++mismatches;
        }
    }

    return mismatches;
}

static void citadel_gpu_v15h_log_texture(const char *label,
                                          C3D_Tex *texture)
{
    u32 physical = 0;

    if (texture != NULL && texture->data != NULL)
        physical = osConvertVirtToPhys(texture->data);

    if (texture == NULL) {
        v5_log("GPU V16 TEX %s NULL",
               label != NULL ? label : "(null)");
        return;
    }

    v5_log("GPU V16 TEX %s data=%p phys=0x%08lX "
           "width=%u height=%u fmt=%u size=%lu "
           "dim=0x%08lX param=0x%08lX lod=0x%08lX type=%u",
           label != NULL ? label : "(null)",
           texture->data,
           (unsigned long)physical,
           (unsigned int)texture->width,
           (unsigned int)texture->height,
           (unsigned int)texture->fmt,
           (unsigned long)texture->size,
           (unsigned long)texture->dim,
           (unsigned long)texture->param,
           (unsigned long)texture->lodParam,
           (unsigned int)C3D_TexGetType(texture));
}

static bool citadel_gpu_v15h_load_sheet(void)
{
    static const char *paths[] = {
        "V15H_CONTROL.t3x",
        "sdmc:/3ds/systemshock/V15H_CONTROL.t3x",
        "sdmc:/3ds/SystemShock/V15H_CONTROL.t3x"
    };
    unsigned int i;

    for (i = 0; i < sizeof(paths) / sizeof(paths[0]); ++i) {
        citadel_gpu_v15h_sheet = C2D_SpriteSheetLoad(paths[i]);

        if (citadel_gpu_v15h_sheet != NULL) {
            v5_log("GPU V16 TEX3DS LOAD path=%s result=SUCCESS count=%lu",
                   paths[i],
                   (unsigned long)C2D_SpriteSheetCount(
                       citadel_gpu_v15h_sheet));
            return true;
        }

        v5_log("GPU V16 TEX3DS LOAD path=%s result=FAIL",
               paths[i]);
    }

    return false;
}

static bool citadel_gpu_v15h_initialize_control(void)
{
    size_t official_size;
    int variant;

    memset(&citadel_gpu_v15h_manual_texture,
           0,
           sizeof(citadel_gpu_v15h_manual_texture));
    memset(&citadel_gpu_v15h_official_image,
           0,
           sizeof(citadel_gpu_v15h_official_image));
    memset(&citadel_gpu_v15h_manual_image,
           0,
           sizeof(citadel_gpu_v15h_manual_image));
    memset(&citadel_gpu_v15h_manual_subtexture,
           0,
           sizeof(citadel_gpu_v15h_manual_subtexture));

    if (!citadel_gpu_v15h_load_sheet())
        return false;

    if (C2D_SpriteSheetCount(citadel_gpu_v15h_sheet) < 1) {
        v5_log("GPU V16 TEX3DS LOAD FAIL reason=no-images");
        return false;
    }

    citadel_gpu_v15h_official_image =
        C2D_SpriteSheetGetImage(citadel_gpu_v15h_sheet, 0);

    if (citadel_gpu_v15h_official_image.tex == NULL ||
        citadel_gpu_v15h_official_image.subtex == NULL ||
        citadel_gpu_v15h_official_image.tex->data == NULL) {
        v5_log("GPU V16 TEX3DS LOAD FAIL reason=invalid-image");
        return false;
    }

    citadel_gpu_v15h_log_texture(
        "OFFICIAL_TEX3DS_RGB565",
        citadel_gpu_v15h_official_image.tex);

    v5_log("GPU V16 SUBTEX official width=%u height=%u "
           "left=%f right=%f top=%f bottom=%f",
           (unsigned int)citadel_gpu_v15h_official_image.subtex->width,
           (unsigned int)citadel_gpu_v15h_official_image.subtex->height,
           citadel_gpu_v15h_official_image.subtex->left,
           citadel_gpu_v15h_official_image.subtex->right,
           citadel_gpu_v15h_official_image.subtex->top,
           citadel_gpu_v15h_official_image.subtex->bottom);

    if (citadel_gpu_v15h_official_image.tex->width !=
            CITADEL_V15H_CONTROL_SIZE ||
        citadel_gpu_v15h_official_image.tex->height !=
            CITADEL_V15H_CONTROL_SIZE ||
        citadel_gpu_v15h_official_image.tex->fmt != GPU_RGB565) {
        v5_log("GPU V16 TEX3DS LOAD FAIL "
               "reason=unexpected-texture expected=256x256/RGB565");
        return false;
    }

    if (!C3D_TexInit(&citadel_gpu_v15h_manual_texture,
                     CITADEL_V15H_CONTROL_SIZE,
                     CITADEL_V15H_CONTROL_SIZE,
                     GPU_RGB565)) {
        v5_log("GPU V16 MANUAL INIT FAIL stage=C3D_TexInit");
        return false;
    }
    citadel_gpu_v15h_manual_initialized = true;

    C3D_TexSetFilter(&citadel_gpu_v15h_manual_texture,
                     GPU_NEAREST,
                     GPU_NEAREST);
    C3D_TexSetWrap(&citadel_gpu_v15h_manual_texture,
                   GPU_CLAMP_TO_EDGE,
                   GPU_CLAMP_TO_EDGE);

    citadel_gpu_v15h_candidate =
        (u16 *)linearAlloc(CITADEL_V15H_CONTROL_BYTES);

    if (citadel_gpu_v15h_candidate == NULL) {
        v5_log("GPU V16 MANUAL INIT FAIL stage=linearAlloc bytes=%u",
               (unsigned int)CITADEL_V15H_CONTROL_BYTES);
        return false;
    }

    official_size =
        citadel_gpu_v15h_official_image.tex->size <
                CITADEL_V15H_CONTROL_BYTES
            ? citadel_gpu_v15h_official_image.tex->size
            : CITADEL_V15H_CONTROL_BYTES;

    for (variant = 0; variant <= 5; ++variant) {
        size_t first_offset;
        unsigned int first_manual;
        unsigned int first_official;
        unsigned long mismatches;

        citadel_gpu_v15h_build_candidate(variant);

        mismatches =
            citadel_gpu_v15h_count_byte_mismatches(
                citadel_gpu_v15h_candidate,
                citadel_gpu_v15h_official_image.tex->data,
                official_size,
                &first_offset,
                &first_manual,
                &first_official);

        v5_log("GPU V16 GOLDEN COMPARE variant=%d "
               "mismatches=%lu compared_bytes=%lu "
               "first={offset=%lu manual=0x%02X official=0x%02X}",
               variant,
               mismatches,
               (unsigned long)official_size,
               (unsigned long)first_offset,
               first_manual,
               first_official);
    }

    /* The displayed runtime control deliberately uses our current mapping. */
    citadel_gpu_v15h_build_candidate(0);
    C3D_TexLoadImage(&citadel_gpu_v15h_manual_texture,
                     citadel_gpu_v15h_candidate,
                     GPU_TEXFACE_2D,
                     0);
    C3D_TexFlush(&citadel_gpu_v15h_manual_texture);

    citadel_gpu_v15h_manual_subtexture =
        *citadel_gpu_v15h_official_image.subtex;
    citadel_gpu_v15h_manual_image.tex =
        &citadel_gpu_v15h_manual_texture;
    citadel_gpu_v15h_manual_image.subtex =
        &citadel_gpu_v15h_manual_subtexture;

    citadel_gpu_v15h_log_texture(
        "RUNTIME_CONTROL_RGB565",
        &citadel_gpu_v15h_manual_texture);

    citadel_gpu_v15h_asset_ready = true;
    v5_log("GPU V16 CONTROL READY "
           "official=C2D_SpriteSheetLoad runtime=C3D_TexLoadImage "
           "state_reset=C2D_Prepare");
    return true;
}

static bool citadel_gpu_v15h_draw_phase(void)
{
    C2D_Image image;
    u32 top_color;
    u32 bottom_color;
    float scale_x;
    float scale_y;
    float draw_x;
    float draw_y;
    bool draw_ok;

    if (citadel_gpu_v15h_phase ==
        CITADEL_V15H_PHASE_OFFICIAL_TEX3DS) {
        image = citadel_gpu_v15h_official_image;
        top_color = C2D_Color32(0, 32, 160, 255);
        bottom_color = C2D_Color32(0, 16, 96, 255);
    } else if (citadel_gpu_v15h_phase ==
               CITADEL_V15H_PHASE_RUNTIME_CONTROL) {
        image = citadel_gpu_v15h_manual_image;
        top_color = C2D_Color32(176, 24, 24, 255);
        bottom_color = C2D_Color32(96, 8, 8, 255);
    } else {
        return false;
    }

    if (image.tex == NULL || image.subtex == NULL)
        return false;

    /*
     * V15H deliberately reasserts all Citro2D-owned GPU state every frame.
     * No direct C3D_TexBind is used; C2D_DrawImageAt owns texture selection.
     */
    C2D_Prepare();

    C2D_TargetClear(citadel_gpu_top_target, top_color);
    C2D_TargetClear(citadel_gpu_bottom_target, bottom_color);

    scale_x = 224.0f / (float)image.subtex->width;
    scale_y = 224.0f / (float)image.subtex->height;
    draw_x = ((float)CITADEL_3DS_TOP_WIDTH - 224.0f) * 0.5f;
    draw_y = 8.0f;

    C2D_SceneBegin(citadel_gpu_top_target);
    draw_ok =
        C2D_DrawImageAt(image,
                        draw_x,
                        draw_y,
                        0.0f,
                        NULL,
                        scale_x,
                        scale_y);
    C2D_Flush();

    C2D_SceneBegin(citadel_gpu_bottom_target);
    C2D_DrawRectSolid(0.0f,
                      0.0f,
                      0.0f,
                      320.0f,
                      240.0f,
                      bottom_color);
    C2D_DrawRectSolid(16.0f,
                      104.0f,
                      0.1f,
                      288.0f,
                      32.0f,
                      C2D_Color32(255, 255, 255, 255));
    C2D_Flush();

    if (!draw_ok)
        ++citadel_gpu_draw_failures;

    return draw_ok;
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

    if (citadel_gpu_v15g_started_at == 0)
        citadel_gpu_v15g_started_at = now;

    if (citadel_gpu_v15h_phase ==
        CITADEL_V15H_PHASE_OFFICIAL_TEX3DS) {
        if ((Sint32)(now - citadel_gpu_v15h_phase_until) < 0)
            return true;

        citadel_gpu_v15h_phase =
            CITADEL_V15H_PHASE_RUNTIME_CONTROL;
        citadel_gpu_v15h_phase_until = now + 6000;

        v5_log("GPU V16 PHASE begin=%s duration_ms=6000 "
               "marker=RED state_reset=C2D_Prepare "
               "bind_owner=C2D_DrawImageAt",
               citadel_gpu_v15h_phase_name(
                   citadel_gpu_v15h_phase));
        return true;
    }

    if (citadel_gpu_v15h_phase ==
        CITADEL_V15H_PHASE_RUNTIME_CONTROL) {
        if ((Sint32)(now - citadel_gpu_v15h_phase_until) < 0)
            return true;

        citadel_gpu_v15h_phase =
            CITADEL_V15H_PHASE_COMPLETE;

        v5_log("GPU V16 PHASE complete; "
               "normal live presentation resumed");
    }

    /*
     * Hold the captured texture objects untouched while each format is shown.
     */
    if (citadel_gpu_v15g_phase ==
        CITADEL_V15G_PHASE_FRESH_RGB565) {
        if ((Sint32)(now - citadel_gpu_v15g_phase_until) < 0)
            return true;

        citadel_gpu_v15g_phase =
            CITADEL_V15G_PHASE_FRESH_RGBA8;
        citadel_gpu_v15g_phase_until = now + 6000;

        v5_log("GPU V16 PHASE begin=%s duration_ms=6000 "
               "loader=C3D_TexLoadImage flush=C3D_TexFlush "
               "bind=AFTER_C2D_SceneBegin draw=C2D_DrawImageAt "
               "bottom_marker=GREEN",
               citadel_gpu_v15g_phase_name(
                   citadel_gpu_v15g_phase));
        return true;
    }

    if (citadel_gpu_v15g_phase ==
        CITADEL_V15G_PHASE_FRESH_RGBA8) {
        if ((Sint32)(now - citadel_gpu_v15g_phase_until) < 0)
            return true;

        citadel_gpu_v15g_phase =
            CITADEL_V15G_PHASE_COMPLETE;

        v5_log("GPU V16 PHASE complete; "
               "normal live RGB565 presentation resumed");
    }

    palette_mismatches =
        citadel_gpu_refresh_palette565();

    linear_hash =
        citadel_gpu_build_linear_frame(surface);
    citadel_gpu_swizzle_staging_to_texture();

    elapsed = now - citadel_gpu_v15g_started_at;

    if (!citadel_gpu_v15h_capture_done &&
        elapsed >= 3000) {
        citadel_gpu_v15h_capture_done = true;

        if (citadel_gpu_v15h_asset_ready) {
            citadel_gpu_v15h_phase =
                CITADEL_V15H_PHASE_OFFICIAL_TEX3DS;
            citadel_gpu_v15h_phase_until = now + 6000;

            v5_log("GPU V16 PHASE begin=%s duration_ms=6000 "
                   "marker=BLUE loader=C2D_SpriteSheetLoad "
                   "state_reset=C2D_Prepare bind_owner=C2D_DrawImageAt",
                   citadel_gpu_v15h_phase_name(
                       citadel_gpu_v15h_phase));
        } else {
            citadel_gpu_v15h_phase =
                CITADEL_V15H_PHASE_COMPLETE;
            v5_log("GPU V16 PHASE SKIPPED reason=asset-unavailable");
        }
    }

    if (!citadel_gpu_first_upload_logged) {
        v5_log("GPU V16 FIRST LIVE FEED src=%dx%d pitch=%d "
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
     * Translate the original Shock-space crop into the active transport
     * rectangle. V15J uses a full 640x480 content image, so menu views map
     * 1:1 into texture space and only the final LCD presentation scales.
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

static bool citadel_v16_present_splash(void)
{
    const Tex3DS_SubTexture *subtexture;
    float scale_x;
    float scale_y;
    bool draw_ok;

    if (!citadel_gpu_ready ||
        !citadel_v16_splash_ready ||
        citadel_v16_splash_image.subtex == NULL ||
        citadel_gpu_top_target == NULL ||
        citadel_gpu_bottom_target == NULL)
        return false;

    subtexture = citadel_v16_splash_image.subtex;

    if (!C3D_FrameBegin(C3D_FRAME_SYNCDRAW)) {
        ++citadel_gpu_draw_failures;
        return false;
    }

    C2D_TargetClear(citadel_gpu_top_target,
                    C2D_Color32(0, 0, 0, 255));
    C2D_TargetClear(citadel_gpu_bottom_target,
                    C2D_Color32(0, 0, 0, 255));

    C2D_SceneBegin(citadel_gpu_top_target);

    scale_x =
        (float)CITADEL_3DS_TOP_WIDTH /
        (float)subtexture->width;
    scale_y =
        (float)CITADEL_3DS_TOP_HEIGHT /
        (float)subtexture->height;

    draw_ok =
        C2D_DrawImageAt(citadel_v16_splash_image,
                        0.0f,
                        0.0f,
                        0.0f,
                        NULL,
                        scale_x,
                        scale_y);

    /*
     * Explicitly submit a black bottom-screen scene. A target clear alone
     * does not replace the previously displayed lower framebuffer.
     */
    C2D_SceneBegin(citadel_gpu_bottom_target);
    C2D_DrawRectSolid(0.0f,
                      0.0f,
                      0.0f,
                      (float)CITADEL_3DS_BOTTOM_WIDTH,
                      (float)CITADEL_3DS_BOTTOM_HEIGHT,
                      C2D_Color32(0, 0, 0, 255));

    C3D_FrameEnd(0);
    ++citadel_gpu_presented_frames;

    if (!draw_ok)
        ++citadel_gpu_draw_failures;

    return draw_ok;
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
        v5_log("GPU V16 SYNC ORDER confirmed: "
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
    if (!magenta &&
        !citadel_gpu_v15g_phase_active() &&
        !citadel_gpu_v15h_phase_active()) {
        C3D_TexBind(0, &citadel_gpu_texture);

        if (!citadel_gpu_cache_rebind_logged) {
            v5_log("GPU V16 CACHE REBIND active: "
                   "C3D_TexBind(0, live_texture) after every live upload");
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


    /*
     * V15H official-control isolation:
     * blue = tex3ds-generated T3X through C2D_SpriteSheetLoad;
     * red  = runtime-generated bytes through a fresh C3D_Tex.
     */
    if (citadel_gpu_v15h_phase_active()) {
        const bool diagnostic_ok =
            citadel_gpu_v15h_draw_phase();

        C3D_FrameEnd(0);
        ++citadel_gpu_presented_frames;

        return diagnostic_ok;
    }

    /*
     * V15G GPU-state isolation:
     *
     * Show the same frozen frame through two brand-new texture objects:
     * first RGB565, then RGBA8. Both are loaded through C3D_TexLoadImage,
     * flushed through C3D_TexFlush, explicitly bound after SceneBegin, and
     * drawn with the simplest C2D_DrawImageAt path.
     */
    if (citadel_gpu_v15g_phase_active()) {
        const bool diagnostic_ok =
            citadel_gpu_v15g_draw_phase();

        C3D_FrameEnd(0);
        ++citadel_gpu_presented_frames;

        return diagnostic_ok;
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
    } else {
        /*
         * Pause, options, save/load, menus, and SELECT legacy view must
         * actively submit a black bottom-screen scene. Clearing a target
         * without beginning that scene leaves the preceding gameplay frame
         * visible on the physical LCD.
         */
        C2D_SceneBegin(citadel_gpu_bottom_target);
        bottom_ok =
            C2D_DrawRectSolid(
                0.0f,
                0.0f,
                0.0f,
                (float)CITADEL_3DS_BOTTOM_WIDTH,
                (float)CITADEL_3DS_BOTTOM_HEIGHT,
                C2D_Color32(0, 0, 0, 255));
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
    FILE *file = fopen("GPU_C2D_V16.log", "a");
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

    remove("GPU_C2D_V16.log");
    v5_log("PROJECT CITADEL V16 RELEASE CANDIDATE START | build=%s %s", __DATE__, __TIME__);

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

#if defined(__3DS__) || defined(_3DS)
    if (!citadel_v16_splash_started) {
        citadel_v16_splash_started = true;
        citadel_v16_splash_until =
            now + CITADEL_V16_SPLASH_DURATION_MS;

        v5_log("GPU V16 SPLASH begin duration_ms=%u ready=%d",
               (unsigned int)CITADEL_V16_SPLASH_DURATION_MS,
               citadel_v16_splash_ready ? 1 : 0);
    }

    if (citadel_v16_splash_ready &&
        !SDL_TICKS_PASSED(now, citadel_v16_splash_until)) {
        if (citadel_v16_present_splash())
            return;

        v5_log("GPU V16 SPLASH presentation failed; continuing to game");
        citadel_v16_splash_ready = false;
    }

    if (!citadel_v16_splash_finished_logged) {
        v5_log("GPU V16 SPLASH complete; beginning System Shock presentation");
        citadel_v16_splash_finished_logged = true;
    }
#endif

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
