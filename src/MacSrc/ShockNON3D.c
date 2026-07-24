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

#warning "PROJECT CITADEL V12E: native SHODAN and audio-log stream is ACTIVE"

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
    FILE *file = fopen("SDL_SPLIT_V12E.log", "a");
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

    remove("SDL_SPLIT_V12E.log");
    v5_log("PROJECT CITADEL V12E START | build=%s %s", __DATE__, __TIME__);

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
