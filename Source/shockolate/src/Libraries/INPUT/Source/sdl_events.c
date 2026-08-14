/*

Copyright (C) 2015-2018 Night Dive Studios, LLC.
Copyright (C) 2019 Shockolate Project

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

//
// DG 2018: (eventually) SDL versions of the functions previously in kbMac.c, mouse.c and kbcook.c
//

#include "lg.h"
#include "kb.h"
#include "mouse.h"
#include <stdlib.h>
#include <stdarg.h>
#include <stdio.h>
#include <SDL.h>
#include <OpenGL.h>
#include <ctype.h>

#if defined(__3DS__) || defined(_3DS)
#include <3ds.h>
#endif

#warning "PROJECT CITADEL INPUT V16.1: launch controls are ACTIVE"
#warning "PROJECT CITADEL 3D S2.1 INPUT: frame-time freelook normalization is ACTIVE"

extern SDL_Window *window;
extern SDL_Renderer *renderer;

#if defined(__3DS__) || defined(_3DS)
extern SDL_Surface *drawSurface;
#endif

#if defined(__3DS__) || defined(_3DS)
extern bool gPlayingGame;
extern bool citadel_3ds_system_close_requested;
extern void citadel_3ds_toggle_legacy_view(void);
extern bool citadel_3ds_split_layout_active(void);
extern bool citadel_3ds_gameplay_controls_active(void);
#endif

bool fullscreenActive = false;

static void toggleFullScreen() {
    fullscreenActive = !fullscreenActive;
    SDL_SetWindowFullscreen(window, fullscreenActive ? SDL_WINDOW_FULLSCREEN_DESKTOP : 0);

    if (!(SDL_GetWindowFlags(window) & SDL_WINDOW_MAXIMIZED))
        SDL_SetWindowPosition(window, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
}

// current state of the keys, based on the SystemShock/Mac Keycodes (sshockKeyStates[keyCode] has the state for that
// key) set at the beginning of each frame in pump_events()
uchar sshockKeyStates[256];

enum { kNumKBevents = 128, kNumMouseEvents = 128 };

// queue keyboard events, created in pump_events(), consumed by kb_next()
static kbs_event kbEvents[kNumKBevents];
static int nextKBevent = 0; // where next to insert (also, if 0 there are no events)

static void addKBevent(const kbs_event *ev) {
    if (nextKBevent < kNumKBevents) {
        kbEvents[nextKBevent] = *ev;
        ++nextKBevent;
    } else {
        // printf("WTF, the kbEvents queue is full?!");
        // drop the oldest event
        memmove(&kbEvents[0], &kbEvents[1], sizeof(kbs_event) * (kNumKBevents - 1));
        kbEvents[kNumKBevents - 1] = *ev;
    }
}

// same for mouse events, also created in pump_events(), consumed by mouse_next()
static ss_mouse_event mouseEvents[kNumMouseEvents];
static int nextMouseEvent = 0;

// latest mouse state as input for MousePollProc() in mouse.c
ss_mouse_event latestMouseEvent;

static void addMouseEvent(const ss_mouse_event *ev) {
    latestMouseEvent = *ev;

    if (nextMouseEvent < kNumMouseEvents) {
        mouseEvents[nextMouseEvent] = latestMouseEvent;
        ++nextMouseEvent;
    } else {
        // printf("WTF, the mouseEvents queue is full?!");
        // drop the oldest event
        memmove(&mouseEvents[0], &mouseEvents[1], sizeof(ss_mouse_event) * (kNumMouseEvents - 1));
        mouseEvents[kNumMouseEvents - 1] = latestMouseEvent;
    }
}

static uchar sdlKeyCodeToSSHOCKkeyCode(SDL_Keycode kc) {
    // apparently System Shock uses the same keycodes as Mac
    // which are luckily documented, see
    // see http://snipplr.com/view/42797/
    // and https://stackoverflow.com/a/16125341
    // see also GameSrc/movekeys.c for a very short list

    // printf("sdlKeyCodeToSSHOCKkeyCode: %x\n", kc);

    switch (kc) {
    case SDLK_a:
        return 0x00; //  kVK_ANSI_A = 0x00,
    case SDLK_s:
        return 0x01; //  kVK_ANSI_S = 0x01,
    case SDLK_d:
        return 0x02; //  kVK_ANSI_D = 0x02,
    case SDLK_f:
        return 0x03; //  kVK_ANSI_F = 0x03,
    case SDLK_h:
        return 0x04; //  kVK_ANSI_H = 0x04,
    case SDLK_g:
        return 0x05; //  kVK_ANSI_G = 0x05,
    case SDLK_z:
        return 0x06; //  kVK_ANSI_Z = 0x06,
    case SDLK_x:
        return 0x07; //  kVK_ANSI_X = 0x07,
    case SDLK_c:
        return 0x08; //  kVK_ANSI_C = 0x08,
    case SDLK_v:
        return 0x09; //  kVK_ANSI_V = 0x09,
    case SDLK_b:
        return 0x0B; //  kVK_ANSI_B = 0x0B,
    case SDLK_q:
        return 0x0C; //  kVK_ANSI_Q = 0x0C,
    case SDLK_w:
        return 0x0D; //  kVK_ANSI_W = 0x0D,
    case SDLK_e:
        return 0x0E; //  kVK_ANSI_E = 0x0E,
    case SDLK_r:
        return 0x0F; //  kVK_ANSI_R = 0x0F,
    case SDLK_y:
        return 0x10; //  kVK_ANSI_Y = 0x10,
    case SDLK_t:
        return 0x11; //  kVK_ANSI_T = 0x11,
    case SDLK_1:
        return 0x12; //  kVK_ANSI_1 = 0x12,
    case SDLK_2:
        return 0x13; //  kVK_ANSI_2 = 0x13,
    case SDLK_3:
        return 0x14; //  kVK_ANSI_3 = 0x14,
    case SDLK_4:
        return 0x15; //  kVK_ANSI_4 = 0x15,
    case SDLK_6:
        return 0x16; //  kVK_ANSI_6 = 0x16,
    case SDLK_5:
        return 0x17; //  kVK_ANSI_5 = 0x17,
    case SDLK_EQUALS:
        return 0x18; //  kVK_ANSI_Equal = 0x18,
    case SDLK_9:
        return 0x19; //  kVK_ANSI_9 = 0x19,
    case SDLK_7:
        return 0x1A; //  kVK_ANSI_7 = 0x1A,
    case SDLK_MINUS:
        return 0x1B; //  kVK_ANSI_Minus = 0x1B,
    case SDLK_8:
        return 0x1C; //  kVK_ANSI_8 = 0x1C,
    case SDLK_0:
        return 0x1D; //  kVK_ANSI_0 = 0x1D,
    case SDLK_RIGHTBRACKET:
        return 0x1E; //  kVK_ANSI_RightBracket = 0x1E,
    case SDLK_o:
        return 0x1F; //  kVK_ANSI_O = 0x1F,
    case SDLK_u:
        return 0x20; //  kVK_ANSI_U = 0x20,
    case SDLK_LEFTBRACKET:
        return 0x21; //  kVK_ANSI_LeftBracket = 0x21,
    case SDLK_i:
        return 0x22; //  kVK_ANSI_I = 0x22,
    case SDLK_p:
        return 0x23; //  kVK_ANSI_P = 0x23,
    case SDLK_l:
        return 0x25; //  kVK_ANSI_L = 0x25,
    case SDLK_j:
        return 0x26; //  kVK_ANSI_J = 0x26,
    case SDLK_QUOTE:
        return 0x27; //  kVK_ANSI_Quote = 0x27, // TODO: or QUOTEDBL ?
    case SDLK_k:
        return 0x28; //  kVK_ANSI_K = 0x28,
    case SDLK_SEMICOLON:
        return 0x29; //  kVK_ANSI_Semicolon = 0x29,
    case SDLK_BACKSLASH:
        return 0x2A; //  kVK_ANSI_Backslash = 0x2A,
    case SDLK_COMMA:
        return 0x2B; //  kVK_ANSI_Comma = 0x2B,
    case SDLK_SLASH:
        return 0x2C; //  kVK_ANSI_Slash = 0x2C,
    case SDLK_n:
        return 0x2D; //  kVK_ANSI_N = 0x2D,
    case SDLK_m:
        return 0x2E; //  kVK_ANSI_M = 0x2E,
    case SDLK_PERIOD:
        return 0x2F; //  kVK_ANSI_Period = 0x2F,
    case SDLK_BACKQUOTE:
        return 0x32; //  kVK_ANSI_Grave = 0x32, // TODO: really?
    case SDLK_KP_DECIMAL:
        return 0x41; //  kVK_ANSI_KeypadDecimal   = 0x41,
    case SDLK_KP_MULTIPLY:
        return 0x43; //  kVK_ANSI_KeypadMultiply = 0x43,
    case SDLK_KP_PLUS:
        return 0x45; //  kVK_ANSI_KeypadPlus = 0x45,
    case SDLK_KP_CLEAR:
        return 0x47; //  kVK_ANSI_KeypadClear = 0x47,
    case SDLK_KP_DIVIDE:
        return 0x4B; //  kVK_ANSI_KeypadDivide = 0x4B,
    case SDLK_KP_ENTER:
        return 0x4C; //  kVK_ANSI_KeypadEnter   = 0x4C, aka _ENTER2_
    case SDLK_KP_MINUS:
        return 0x4E; //  kVK_ANSI_KeypadMinus   = 0x4E,
    case SDLK_KP_EQUALS:
        return 0x51; //  kVK_ANSI_KeypadEquals = 0x51,
    case SDLK_KP_0:
        return 0x52; //  kVK_ANSI_Keypad0 = 0x52,
    case SDLK_KP_1:
        return 0x53; //  kVK_ANSI_Keypad1 = 0x53, aka _END2_
    case SDLK_KP_2:
        return 0x54; //  kVK_ANSI_Keypad2 = 0x54, aka _DOWN2_
    case SDLK_KP_3:
        return 0x55; //  kVK_ANSI_Keypad3 = 0x55, aka _PGDN2_
    case SDLK_KP_4:
        return 0x56; //  kVK_ANSI_Keypad4 = 0x56, aka _LEFT2_
    case SDLK_KP_5:
        return 0x57; //  kVK_ANSI_Keypad5 = 0x57, aka _PAD5_
    case SDLK_KP_6:
        return 0x58; //  kVK_ANSI_Keypad6 = 0x58, aka _RIGHT2_
    case SDLK_KP_7:
        return 0x59; //  kVK_ANSI_Keypad7 = 0x59, aka _HOME2_
    case SDLK_KP_8:
        return 0x5B; //  kVK_ANSI_Keypad8 = 0x5B, aka _UP2_
    case SDLK_KP_9:
        return 0x5C; //  kVK_ANSI_Keypad9 = 0x5C, aka _PGUP2_

    // keycodes for keys that are independent of keyboard layout
    case SDLK_RETURN:
        return 0x24; //  kVK_Return  = 0x24,
    case SDLK_TAB:
        return 0x30; //  kVK_Tab     = 0x30,
    case SDLK_SPACE:
        return 0x31; //  kVK_Space   = 0x31,
    case SDLK_DELETE:
        return 0x33; //  kVK_Delete  = 0x33,
    case SDLK_BACKSPACE:
        return 0x33; //  kVK_Delete  = 0x33,
    case SDLK_ESCAPE:
        return 0x35; //  kVK_Escape  = 0x35,

        //    returning these is unnecessary and can cause keypresses to be missed
        //    (esp keys with modifiers)
        // case SDLK_LGUI : // fall-through
        // case SDLK_RGUI : return 0x37; //  kVK_Command = 0x37, // FIXME: I think command is the windows/meta key?
        // case SDLK_LSHIFT : return 0x38; //  kVK_Shift   = 0x38,
        // case SDLK_CAPSLOCK : return 0x39; //  kVK_CapsLock= 0x39,
        // case SDLK_LALT : return 0x3A; //  kVK_Option  = 0x3A, Option == Aalt
        // case SDLK_LCTRL : return 0x3B; //  kVK_Control = 0x3B,
        // case SDLK_RSHIFT : return 0x3C; //  kVK_RightShift  = 0x3C,
        // case SDLK_RALT : return 0x3D; //  kVK_RightOption = 0x3D,
        // case SDLK_RCTRL : return 0x3E; //  kVK_RightControl = 0x3E,

    // case SDLK_ : return 0x3F; //  kVK_Function = 0x3F, // TODO: what's this?
    case SDLK_F17:
        return 0x40; //  kVK_F17 = 0x40,
    case SDLK_VOLUMEUP:
        return 0x48; //  kVK_VolumeUp = 0x48,
    case SDLK_VOLUMEDOWN:
        return 0x49; //  kVK_VolumeDown = 0x49,
    case SDLK_MUTE:
        return 0x4A; //  kVK_Mute = 0x4A,
    case SDLK_F18:
        return 0x4F; //  kVK_F18 = 0x4F,
    case SDLK_F19:
        return 0x50; //  kVK_F19 = 0x50,
    case SDLK_F20:
        return 0x5A; //  kVK_F20 = 0x5A,
    case SDLK_F5:
        return 0x60; //  kVK_F5  = 0x60,
    case SDLK_F6:
        return 0x61; //  kVK_F6  = 0x61,
    case SDLK_F7:
        return 0x62; //  kVK_F7  = 0x62,
    case SDLK_F3:
        return 0x63; //  kVK_F3  = 0x63,
    case SDLK_F8:
        return 0x64; //  kVK_F8  = 0x64,
    case SDLK_F9:
        return 0x65; //  kVK_F9  = 0x65,
    case SDLK_F11:
        return 0x67; //  kVK_F11 = 0x67,
    case SDLK_F13:
        return 0x69; //  kVK_F13 = 0x69,
    case SDLK_F16:
        return 0x6A; //  kVK_F16 = 0x6A,
    case SDLK_F14:
        return 0x6B; //  kVK_F14 = 0x6B,
    case SDLK_F10:
        return 0x6D; //  kVK_F10 = 0x6D,
    case SDLK_F12:
        return 0x6F; //  kVK_F12 = 0x6F,
    case SDLK_F15:
        return 0x71; //  kVK_F15 = 0x71,
    case SDLK_HELP:
        return 0x72; //  kVK_Help = 0x72,
    case SDLK_HOME:
        return 0x73; //  kVK_Home = 0x73,
    case SDLK_PAGEUP:
        return 0x74; //  kVK_PageUp = 0x74,
    // case SDLK_ : return 0x75; //  kVK_ForwardDelete = 0x75, // TODO: what's this?
    case SDLK_F4:
        return 0x76; //  kVK_F4 = 0x76,
    case SDLK_END:
        return 0x77; //  kVK_End = 0x77,
    case SDLK_F2:
        return 0x78; //  kVK_F2 = 0x78,
    case SDLK_PAGEDOWN:
        return 0x79; //  kVK_PageDown = 0x79,
    case SDLK_F1:
        return 0x7A; //  kVK_F1 = 0x7A,
    case SDLK_LEFT:
        return 0x7B; //  kVK_LeftArrow  = 0x7B, aka _LEFT_
    case SDLK_RIGHT:
        return 0x7C; //  kVK_RightArrow = 0x7C, aka _RIGHT
    case SDLK_DOWN:
        return 0x7D; //  kVK_DownArrow  = 0x7D, aka _DOWN_
    case SDLK_UP:
        return 0x7E; //  kVK_UpArrow    = 0x7E, aka _UP_
    default:
        return KBC_NONE;
    }
}

int MouseX;
int MouseY;

int MouseChaosX;
int MouseChaosY;

extern bool MouseCaptured;

#if defined(__3DS__) || defined(_3DS)

#define CITADEL_FALLBACK_MOUSE_WIDTH  640
#define CITADEL_FALLBACK_MOUSE_HEIGHT 480

static int citadel_current_mouse_width(void)
{
    if (drawSurface != NULL && drawSurface->w > 0)
        return drawSurface->w;

    return CITADEL_FALLBACK_MOUSE_WIDTH;
}

static int citadel_current_mouse_height(void)
{
    if (drawSurface != NULL && drawSurface->h > 0)
        return drawSurface->h;

    return CITADEL_FALLBACK_MOUSE_HEIGHT;
}

#endif

void SetMouseXY(int mx, int my) {
#if defined(__3DS__) || defined(_3DS)
    int mouse_width = citadel_current_mouse_width();
    int mouse_height = citadel_current_mouse_height();

    /*
     * Keep the software cursor in whatever internal game resolution is
     * currently active. This follows live changes such as 640x480 to
     * 1024x768 rather than trapping the pointer in the original bounds.
     */
    if (mx < 0)
        mx = 0;
    if (mx >= mouse_width)
        mx = mouse_width - 1;
    if (my < 0)
        my = 0;
    if (my >= mouse_height)
        my = mouse_height - 1;

    MouseX = mx;
    MouseY = my;
    SDL_ShowCursor(SDL_DISABLE);
    return;
#endif

    int physical_width, physical_height;
    SDL_GetWindowSize(window, &physical_width, &physical_height);

    int w, h;
    SDL_RenderGetLogicalSize(renderer, &w, &h);

    float scale_x = (float)physical_width / w;
    float scale_y = (float)physical_height / h;

    int x, y;
    if (scale_x >= scale_y) {
        x = (physical_width - w * scale_x) / 2;
        y = 0;
    } else {
        x = 0;
        y = (physical_height - h * scale_y) / 2;
    }

    bool inside = (mx >= x && mx < x + w && my >= y && my < y + h);
    bool focus = (SDL_GetWindowFlags(window) & SDL_WINDOW_INPUT_FOCUS); //checking mouse focus isn't what we want here

    if (!inside && focus) {
        if (mx < x)
            mx = x;
        if (mx > x + w - 1)
            mx = x + w - 1;
        if (my < y)
            my = y;
        if (my > y + h - 1)
            my = y + h - 1;
    }

    if (focus) {
        MouseX = mx;
        MouseY = my;
    }

    SDL_ShowCursor((!focus || (!inside && !MouseCaptured)) ? SDL_ENABLE : SDL_DISABLE);
}

void get_mouselook_vel(int *vx, int *vy);

extern bool TriggerRelMouseMode;

static SDL_bool saved_rel_mouse = FALSE;

// same codes as returned by sdlKeyCodeToSSHOCKkeyCode()
uchar Ascii2Code[95] = {
    0x31, // space
    0x12, // !
    0x27, // "
    0x14, // #
    0x15, // $
    0x17, // %
    0x1A, // &
    0x27, // '
    0x19, // (
    0x1D, // )
    0x1C, // *
    0x18, // +
    0x2B, // ,
    0x1B, // -
    0x2F, // .
    0x2C, // /
    0x1D, // 0
    0x12, // 1
    0x13, // 2
    0x14, // 3
    0x15, // 4
    0x17, // 5
    0x16, // 6
    0x1A, // 7
    0x1C, // 8
    0x19, // 9
    0x29, // :
    0x29, // ;
    0x2B, // <
    0x18, // =
    0x2F, // >
    0x2C, // ?
    0x13, // @
    0x00, // A
    0x0B, // B
    0x08, // C
    0x02, // D
    0x0E, // E
    0x03, // F
    0x05, // G
    0x04, // H
    0x22, // I
    0x26, // J
    0x28, // K
    0x25, // L
    0x2E, // M
    0x2D, // N
    0x1F, // O
    0x23, // P
    0x0C, // Q
    0x0F, // R
    0x01, // S
    0x11, // T
    0x20, // U
    0x09, // V
    0x0D, // W
    0x07, // X
    0x10, // Y
    0x06, // Z
    0x21, // [
    0x2A, // backslash
    0x1E, // ]
    0x16, // ^
    0x1B, // _
    0x32, // `
    0x00, // a
    0x0B, // b
    0x08, // c
    0x02, // d
    0x0E, // e
    0x03, // f
    0x05, // g
    0x04, // h
    0x22, // i
    0x26, // j
    0x28, // k
    0x25, // l
    0x2E, // m
    0x2D, // n
    0x1F, // o
    0x23, // p
    0x0C, // q
    0x0F, // r
    0x01, // s
    0x11, // t
    0x20, // u
    0x09, // v
    0x0D, // w
    0x07, // x
    0x10, // y
    0x06, // z
    0x21, // {
    0x2A, // |
    0x1E, // }
    0x32  // ~
};



#if defined(__3DS__) || defined(_3DS)

#define CITADEL_TOUCH_WIDTH              320
#define CITADEL_TOUCH_HEIGHT             240
#define CITADEL_TOP_WIDTH                400
#define CITADEL_TOP_HEIGHT               240

#define CITADEL_REF_WIDTH                640
#define CITADEL_REF_HEIGHT               480

#define CITADEL_REF_GAME_X                 0
#define CITADEL_REF_GAME_Y                 0
#define CITADEL_REF_GAME_W               640
#define CITADEL_REF_GAME_H               328

#define CITADEL_REF_INVENTORY_X          168
#define CITADEL_REF_INVENTORY_Y          320
#define CITADEL_REF_INVENTORY_W          304
#define CITADEL_REF_INVENTORY_H          160

#define CITADEL_REF_LEFT_MFD_X             0
#define CITADEL_REF_LEFT_MFD_W           160
#define CITADEL_REF_RIGHT_MFD_X          472
#define CITADEL_REF_RIGHT_MFD_W          168
#define CITADEL_REF_MFD_Y                320
#define CITADEL_REF_MFD_H                160

#define CITADEL_BOTTOM_INVENTORY_W       320
#define CITADEL_BOTTOM_INVENTORY_H       120
#define CITADEL_BOTTOM_MFD_Y             120
#define CITADEL_BOTTOM_MFD_W             160
#define CITADEL_BOTTOM_MFD_H             120

#define CITADEL_CPAD_DEADZONE              20
#define CITADEL_CPAD_RAW_MAX              156
#define CITADEL_STRAFE_CONTROL_MAX         54
#define CITADEL_BACK_CONTROL_MAX           54
#define CITADEL_FORWARD_CONTROL_MAX       108
#define CITADEL_CSTICK_POINTER_DEADZONE   14
#define CITADEL_CSTICK_POINTER_DIVISOR     8
#define CITADEL_CSTICK_LOOK_DEADZONE      10
#define CITADEL_CSTICK_LOOK_DIVISOR_X      8
#define CITADEL_CSTICK_LOOK_DIVISOR_Y     10
#define CITADEL_CSTICK_SPEED_NUMERATOR      6
#define CITADEL_CSTICK_SPEED_DENOMINATOR    5

static bool citadel_input_log_initialized = false;
static bool citadel_r_left_down = false;
static bool citadel_touch_left_down = false;
static bool citadel_l_right_down = false;
static unsigned int citadel_mouse_buttons = 0;

enum {
    CITADEL_CURSOR_PANEL_TOP = 0,
    CITADEL_CURSOR_PANEL_INVENTORY,
    CITADEL_CURSOR_PANEL_LEFT_MFD,
    CITADEL_CURSOR_PANEL_RIGHT_MFD
};

static int citadel_cursor_panel = CITADEL_CURSOR_PANEL_TOP;
static int citadel_cursor_local_x = CITADEL_TOP_WIDTH / 2;
static int citadel_cursor_local_y = CITADEL_TOP_HEIGHT / 2;
static int citadel_touch_panel = CITADEL_CURSOR_PANEL_TOP;
static bool citadel_last_split_layout = false;

static bool citadel_cstick_init_attempted = false;
static bool citadel_cstick_available = false;
static bool citadel_freelook_desired = false;
static int citadel_freelook_velocity_x = 0;
static int citadel_freelook_velocity_y = 0;
static u64 citadel_3ds_freelook_last_update_ms = 0;

static int citadel_cpad_raw_x = 0;
static int citadel_cpad_raw_y = 0;
static bool citadel_analog_gameplay_active = false;

static bool citadel_menu_up_down = false;
static bool citadel_menu_down_down = false;
static bool citadel_menu_left_down = false;
static bool citadel_menu_right_down = false;

static void citadel_input_log(const char *fmt, ...)
{
    FILE *file;
    va_list args;

    if (!citadel_input_log_initialized) {
        remove("INPUT_3DS_V16_1.log");
        citadel_input_log_initialized = true;
    }

    file = fopen("INPUT_3DS_V16_1.log", "a");
    if (file == NULL)
        return;

    va_start(args, fmt);
    vfprintf(file, fmt, args);
    va_end(args);

    fputc('\n', file);
    fflush(file);
    fclose(file);
}

static int citadel_clamp_int(int value, int low, int high)
{
    if (value < low)
        return low;
    if (value > high)
        return high;
    return value;
}

static void citadel_set_mouse_position(int x, int y, bool queue_motion)
{
    ss_mouse_event mouseEvent = {0};
    int old_x = MouseX;
    int old_y = MouseY;
    int mouse_width = citadel_current_mouse_width();
    int mouse_height = citadel_current_mouse_height();

    x = citadel_clamp_int(x, 0, mouse_width - 1);
    y = citadel_clamp_int(y, 0, mouse_height - 1);

    MouseX = x;
    MouseY = y;

    latestMouseEvent.x = MouseX;
    latestMouseEvent.y = MouseY;
    latestMouseEvent.buttons = citadel_mouse_buttons;

    if (!queue_motion || (old_x == MouseX && old_y == MouseY))
        return;

    mouseEvent.type = MOUSE_MOTION;
    mouseEvent.x = MouseX;
    mouseEvent.y = MouseY;
    mouseEvent.buttons = citadel_mouse_buttons;
    mouseEvent.timestamp = mouse_get_time();
    mouseEvent.modifiers = 0;
    addMouseEvent(&mouseEvent);
}

static void citadel_emit_mouse_button(bool left, bool down)
{
    ss_mouse_event mouseEvent = {0};
    unsigned int mask = (1U << (left ? MOUSE_LBUTTON : MOUSE_RBUTTON));

    if (down)
        citadel_mouse_buttons |= mask;
    else
        citadel_mouse_buttons &= ~mask;

    mouseEvent.type = left
        ? (down ? MOUSE_LDOWN : MOUSE_LUP)
        : (down ? MOUSE_RDOWN : MOUSE_RUP);
    mouseEvent.x = MouseX;
    mouseEvent.y = MouseY;
    mouseEvent.buttons = citadel_mouse_buttons;
    mouseEvent.timestamp = mouse_get_time();
    mouseEvent.modifiers = 0;
    addMouseEvent(&mouseEvent);

    citadel_input_log("%s mouse %s at %d,%d buttons=0x%X",
                      left ? "LEFT" : "RIGHT",
                      down ? "DOWN" : "UP",
                      MouseX,
                      MouseY,
                      citadel_mouse_buttons);
}

static void citadel_update_left_button(void)
{
    static bool emitted_down = false;
    bool should_be_down = citadel_r_left_down || citadel_touch_left_down;

    if (should_be_down != emitted_down) {
        emitted_down = should_be_down;
        citadel_emit_mouse_button(true, emitted_down);
    }
}

static void citadel_update_right_button(void)
{
    static bool emitted_down = false;
    bool should_be_down = citadel_l_right_down;

    if (should_be_down != emitted_down) {
        emitted_down = should_be_down;
        citadel_emit_mouse_button(false, emitted_down);
    }
}

static void citadel_emit_key(SDL_Keycode sym, bool down)
{
    uchar code = sdlKeyCodeToSSHOCKkeyCode(sym);
    kbs_event keyEvent = {0};

    if (code == KBC_NONE)
        return;

    keyEvent.code = code;
    keyEvent.ascii = 0;

    if (sym == SDLK_SPACE)
        keyEvent.ascii = ' ';
    else if (sym == SDLK_RETURN)
        keyEvent.ascii = '\r';
    else if (sym == SDLK_ESCAPE)
        keyEvent.ascii = 27;

    keyEvent.modifiers = 0;
    keyEvent.state = down ? KBS_DOWN : KBS_UP;

    addKBevent(&keyEvent);
    sshockKeyStates[code] = down ? KB_MOD_PRESSED : 0;

    citadel_input_log("KEY %s sym=%ld shock_code=0x%02X",
                      down ? "DOWN" : "UP",
                      (long)sym,
                      code);
}

static void citadel_set_virtual_key(SDL_Keycode sym,
                                    bool should_be_down,
                                    bool *is_down)
{
    if (should_be_down == *is_down)
        return;

    *is_down = should_be_down;
    citadel_emit_key(sym, should_be_down);
}

static int citadel_axis_step(int value, int deadzone, int divisor)
{
    int magnitude;

    if (value > -deadzone && value < deadzone)
        return 0;

    magnitude = value > 0
        ? value - deadzone
        : value + deadzone;

    magnitude /= divisor;

    if (magnitude == 0)
        magnitude = value > 0 ? 1 : -1;

    return magnitude;
}

static int citadel_scale_ref_x(int value)
{
    return (value * citadel_current_mouse_width()) / CITADEL_REF_WIDTH;
}

static int citadel_scale_ref_y(int value)
{
    return (value * citadel_current_mouse_height()) / CITADEL_REF_HEIGHT;
}

static int citadel_panel_destination_width(int panel)
{
    return panel == CITADEL_CURSOR_PANEL_TOP ? CITADEL_TOP_WIDTH :
           panel == CITADEL_CURSOR_PANEL_INVENTORY ? CITADEL_BOTTOM_INVENTORY_W :
           CITADEL_BOTTOM_MFD_W;
}

static int citadel_panel_destination_height(int panel)
{
    return panel == CITADEL_CURSOR_PANEL_TOP ? CITADEL_TOP_HEIGHT :
           panel == CITADEL_CURSOR_PANEL_INVENTORY ? CITADEL_BOTTOM_INVENTORY_H :
           CITADEL_BOTTOM_MFD_H;
}

static void citadel_panel_reference_rect(int panel, int *x, int *y, int *w, int *h)
{
    switch (panel) {
    case CITADEL_CURSOR_PANEL_INVENTORY:
        *x=CITADEL_REF_INVENTORY_X; *y=CITADEL_REF_INVENTORY_Y;
        *w=CITADEL_REF_INVENTORY_W; *h=CITADEL_REF_INVENTORY_H; break;
    case CITADEL_CURSOR_PANEL_LEFT_MFD:
        *x=CITADEL_REF_LEFT_MFD_X; *y=CITADEL_REF_MFD_Y;
        *w=CITADEL_REF_LEFT_MFD_W; *h=CITADEL_REF_MFD_H; break;
    case CITADEL_CURSOR_PANEL_RIGHT_MFD:
        *x=CITADEL_REF_RIGHT_MFD_X; *y=CITADEL_REF_MFD_Y;
        *w=CITADEL_REF_RIGHT_MFD_W; *h=CITADEL_REF_MFD_H; break;
    default:
        *x=CITADEL_REF_GAME_X; *y=CITADEL_REF_GAME_Y;
        *w=CITADEL_REF_GAME_W; *h=CITADEL_REF_GAME_H; break;
    }
}

static void citadel_apply_panel_cursor(bool queue_motion)
{
    int rx,ry,rw,rh;
    int dw=citadel_panel_destination_width(citadel_cursor_panel);
    int dh=citadel_panel_destination_height(citadel_cursor_panel);
    citadel_cursor_local_x=citadel_clamp_int(citadel_cursor_local_x,0,dw-1);
    citadel_cursor_local_y=citadel_clamp_int(citadel_cursor_local_y,0,dh-1);
    citadel_panel_reference_rect(citadel_cursor_panel,&rx,&ry,&rw,&rh);
    citadel_set_mouse_position(
        citadel_scale_ref_x(rx+(citadel_cursor_local_x*rw)/dw),
        citadel_scale_ref_y(ry+(citadel_cursor_local_y*rh)/dh),
        queue_motion);
}

static void citadel_center_cursor_on_top(void)
{
    const int old_panel = citadel_cursor_panel;

    citadel_cursor_panel = CITADEL_CURSOR_PANEL_TOP;
    citadel_cursor_local_x = CITADEL_TOP_WIDTH / 2;
    citadel_cursor_local_y = CITADEL_TOP_HEIGHT / 2;
    citadel_apply_panel_cursor(true);

    citadel_input_log("CENTER TOP old_panel=%d local=%d,%d logical=%d,%d",
                      old_panel,
                      citadel_cursor_local_x,
                      citadel_cursor_local_y,
                      MouseX,
                      MouseY);
}

static void citadel_sync_panel_from_logical(void)
{
    int rx=(MouseX*CITADEL_REF_WIDTH)/citadel_current_mouse_width();
    int ry=(MouseY*CITADEL_REF_HEIGHT)/citadel_current_mouse_height();
    int x,y,w,h,dw,dh;
    if (ry < CITADEL_REF_GAME_H) citadel_cursor_panel=CITADEL_CURSOR_PANEL_TOP;
    else if (rx < CITADEL_REF_LEFT_MFD_W) citadel_cursor_panel=CITADEL_CURSOR_PANEL_LEFT_MFD;
    else if (rx >= CITADEL_REF_RIGHT_MFD_X) citadel_cursor_panel=CITADEL_CURSOR_PANEL_RIGHT_MFD;
    else citadel_cursor_panel=CITADEL_CURSOR_PANEL_INVENTORY;
    citadel_panel_reference_rect(citadel_cursor_panel,&x,&y,&w,&h);
    dw=citadel_panel_destination_width(citadel_cursor_panel);
    dh=citadel_panel_destination_height(citadel_cursor_panel);
    citadel_cursor_local_x=citadel_clamp_int(((rx-x)*dw)/w,0,dw-1);
    citadel_cursor_local_y=citadel_clamp_int(((ry-y)*dh)/h,0,dh-1);
    citadel_apply_panel_cursor(false);
}

static void citadel_move_panel_cursor(int sx, int sy)
{
    int old=citadel_cursor_panel;
    int x=citadel_cursor_local_x+sx, y=citadel_cursor_local_y+sy;
    switch (citadel_cursor_panel) {
    case CITADEL_CURSOR_PANEL_TOP:
        x=citadel_clamp_int(x,0,CITADEL_TOP_WIDTH-1);
        if (y>=CITADEL_TOP_HEIGHT) { citadel_cursor_panel=CITADEL_CURSOR_PANEL_INVENTORY; x=(x*CITADEL_BOTTOM_INVENTORY_W)/CITADEL_TOP_WIDTH; y-=CITADEL_TOP_HEIGHT; }
        else y=citadel_clamp_int(y,0,CITADEL_TOP_HEIGHT-1);
        break;
    case CITADEL_CURSOR_PANEL_INVENTORY:
        x=citadel_clamp_int(x,0,CITADEL_BOTTOM_INVENTORY_W-1);
        if (y<0) { citadel_cursor_panel=CITADEL_CURSOR_PANEL_TOP; x=(x*CITADEL_TOP_WIDTH)/CITADEL_BOTTOM_INVENTORY_W; y+=CITADEL_TOP_HEIGHT; }
        else if (y>=CITADEL_BOTTOM_INVENTORY_H) { y-=CITADEL_BOTTOM_INVENTORY_H; if (x<CITADEL_BOTTOM_MFD_W) citadel_cursor_panel=CITADEL_CURSOR_PANEL_LEFT_MFD; else { citadel_cursor_panel=CITADEL_CURSOR_PANEL_RIGHT_MFD; x-=CITADEL_BOTTOM_MFD_W; } }
        else y=citadel_clamp_int(y,0,CITADEL_BOTTOM_INVENTORY_H-1);
        break;
    case CITADEL_CURSOR_PANEL_LEFT_MFD:
        if (y<0) { citadel_cursor_panel=CITADEL_CURSOR_PANEL_INVENTORY; y+=CITADEL_BOTTOM_INVENTORY_H; }
        else { y=citadel_clamp_int(y,0,CITADEL_BOTTOM_MFD_H-1); if (x>=CITADEL_BOTTOM_MFD_W) { citadel_cursor_panel=CITADEL_CURSOR_PANEL_RIGHT_MFD; x-=CITADEL_BOTTOM_MFD_W; } else x=citadel_clamp_int(x,0,CITADEL_BOTTOM_MFD_W-1); }
        break;
    case CITADEL_CURSOR_PANEL_RIGHT_MFD:
        if (y<0) { citadel_cursor_panel=CITADEL_CURSOR_PANEL_INVENTORY; x+=CITADEL_BOTTOM_MFD_W; y+=CITADEL_BOTTOM_INVENTORY_H; }
        else { y=citadel_clamp_int(y,0,CITADEL_BOTTOM_MFD_H-1); if (x<0) { citadel_cursor_panel=CITADEL_CURSOR_PANEL_LEFT_MFD; x+=CITADEL_BOTTOM_MFD_W; } else x=citadel_clamp_int(x,0,CITADEL_BOTTOM_MFD_W-1); }
        break;
    }
    citadel_cursor_local_x=x; citadel_cursor_local_y=y;
    citadel_apply_panel_cursor(true);
    if (old!=citadel_cursor_panel) citadel_input_log("PANEL transition %d -> %d local=%d,%d logical=%d,%d",old,citadel_cursor_panel,x,y,MouseX,MouseY);
}

static int citadel_touch_panel_at(const touchPosition *t)
{
    if (t->py<CITADEL_BOTTOM_INVENTORY_H) return CITADEL_CURSOR_PANEL_INVENTORY;
    return t->px<CITADEL_BOTTOM_MFD_W ? CITADEL_CURSOR_PANEL_LEFT_MFD : CITADEL_CURSOR_PANEL_RIGHT_MFD;
}

static void citadel_set_panel_from_touch(const touchPosition *t, int panel)
{
    citadel_cursor_panel=panel;
    if (panel==CITADEL_CURSOR_PANEL_INVENTORY) { citadel_cursor_local_x=t->px; citadel_cursor_local_y=t->py; }
    else if (panel==CITADEL_CURSOR_PANEL_LEFT_MFD) { citadel_cursor_local_x=t->px; citadel_cursor_local_y=(int)t->py-CITADEL_BOTTOM_MFD_Y; }
    else { citadel_cursor_local_x=(int)t->px-CITADEL_BOTTOM_MFD_W; citadel_cursor_local_y=(int)t->py-CITADEL_BOTTOM_MFD_Y; }
    citadel_apply_panel_cursor(true);
}

static void citadel_shutdown_cstick(void)
{
    if (citadel_cstick_available)
        irrstExit();

    citadel_cstick_available = false;
}

static void citadel_init_cstick_once(void)
{
    Result result;

    if (citadel_cstick_init_attempted)
        return;

    citadel_cstick_init_attempted = true;
    result = irrstInit();

    if (R_SUCCEEDED(result)) {
        citadel_cstick_available = true;
        atexit(citadel_shutdown_cstick);
        citadel_input_log("C-STICK service initialized");
    } else {
        citadel_input_log("C-STICK service unavailable result=0x%08lX",
                          (unsigned long)result);
    }
}

static void citadel_read_cstick(circlePosition *cstick)
{
    cstick->dx = 0;
    cstick->dy = 0;

    citadel_init_cstick_once();
    if (!citadel_cstick_available)
        return;

    irrstScanInput();
    hidCstickRead(cstick);
}

static int citadel_scale_control_axis(int raw, int positive_max, int negative_max)
{
    int magnitude,scaled;
    if (raw>-CITADEL_CPAD_DEADZONE && raw<CITADEL_CPAD_DEADZONE) return 0;
    magnitude=(raw>0?raw:-raw)-CITADEL_CPAD_DEADZONE;
    magnitude=citadel_clamp_int(magnitude,0,CITADEL_CPAD_RAW_MAX-CITADEL_CPAD_DEADZONE);
    if (raw>0) { scaled=(magnitude*positive_max)/(CITADEL_CPAD_RAW_MAX-CITADEL_CPAD_DEADZONE); return citadel_clamp_int(scaled,0,positive_max); }
    scaled=(magnitude*negative_max)/(CITADEL_CPAD_RAW_MAX-CITADEL_CPAD_DEADZONE);
    return -citadel_clamp_int(scaled,0,negative_max);
}

void citadel_3ds_get_analog_movement(int *xvel, int *yvel)
{
    if (!xvel || !yvel) return;
    if (!citadel_analog_gameplay_active) { *xvel=0; *yvel=0; return; }
    *xvel=citadel_scale_control_axis(citadel_cpad_raw_x,CITADEL_STRAFE_CONTROL_MAX,CITADEL_STRAFE_CONTROL_MAX);
    *yvel=citadel_scale_control_axis(citadel_cpad_raw_y,CITADEL_FORWARD_CONTROL_MAX,CITADEL_BACK_CONTROL_MAX);
}

int citadel_3ds_freelook_is_desired(void)
{
    return citadel_freelook_desired ? 1 : 0;
}

static void citadel_update_menu_dpad(u32 keys_held, bool gameplay_active)
{
    bool menu_active = !gameplay_active;

    citadel_set_virtual_key(SDLK_UP,
                            menu_active && (keys_held & KEY_DUP) != 0,
                            &citadel_menu_up_down);
    citadel_set_virtual_key(SDLK_DOWN,
                            menu_active && (keys_held & KEY_DDOWN) != 0,
                            &citadel_menu_down_down);
    citadel_set_virtual_key(SDLK_LEFT,
                            menu_active && (keys_held & KEY_DLEFT) != 0,
                            &citadel_menu_left_down);
    citadel_set_virtual_key(SDLK_RIGHT,
                            menu_active && (keys_held & KEY_DRIGHT) != 0,
                            &citadel_menu_right_down);
}

static int citadel_panel_step(int source_step, bool horizontal)
{
    int x,y,w,h,dst,step;
    citadel_panel_reference_rect(citadel_cursor_panel,&x,&y,&w,&h);
    dst=horizontal?citadel_panel_destination_width(citadel_cursor_panel):citadel_panel_destination_height(citadel_cursor_panel);
    step=(source_step*dst)/(horizontal?w:h);
    if (source_step>0 && step==0) step=1; else if (source_step<0 && step==0) step=-1;
    return step;
}

/*
 * S2.1 keeps the established mono C-stick calibration intact.
 *
 * The C-stick produces a per-main-loop velocity. True stereo adds a second
 * software world render, reducing loop frequency on demanding frames. Scale
 * only freelook by elapsed frame time while the physical 3D slider is active.
 * A 16-34 ms clamp preserves 60 Hz behavior and caps compensation near 30 Hz.
 */
static int citadel_3ds_stereo_freelook_frame_scale(void)
{
    const u64 target_ms = 16;
    const u64 maximum_ms = 34;
    u64 now = osGetTime();
    u64 elapsed = target_ms;

    if (citadel_3ds_freelook_last_update_ms != 0 &&
        now >= citadel_3ds_freelook_last_update_ms)
        elapsed = now - citadel_3ds_freelook_last_update_ms;

    citadel_3ds_freelook_last_update_ms = now;

    if (osGet3DSliderState() < 0.015f)
        return (int)target_ms;

    if (elapsed < target_ms) elapsed = target_ms;
    if (elapsed > maximum_ms) elapsed = maximum_ms;

    return (int)elapsed;
}

static int citadel_3ds_scale_signed_round(int value,
                                          int numerator,
                                          int denominator)
{
    if (value > 0)
        return (value * numerator + denominator / 2) / denominator;
    if (value < 0)
        return -(((-value) * numerator + denominator / 2) / denominator);
    return 0;
}

static void citadel_update_cstick(const circlePosition *cstick, bool gameplay_active, bool split_layout, bool touch_held)
{
    int sx,sy,lx,ly;
    int stereo_frame_scale =
        citadel_3ds_stereo_freelook_frame_scale();
    citadel_freelook_velocity_x=0; citadel_freelook_velocity_y=0;
    if (citadel_freelook_desired && gameplay_active) {
        citadel_freelook_velocity_x=citadel_axis_step(cstick->dx,CITADEL_CSTICK_LOOK_DEADZONE,CITADEL_CSTICK_LOOK_DIVISOR_X);
        citadel_freelook_velocity_y=-citadel_axis_step(cstick->dy,CITADEL_CSTICK_LOOK_DEADZONE,CITADEL_CSTICK_LOOK_DIVISOR_Y);
        citadel_freelook_velocity_x=(citadel_freelook_velocity_x*CITADEL_CSTICK_SPEED_NUMERATOR)/CITADEL_CSTICK_SPEED_DENOMINATOR;
        citadel_freelook_velocity_y=(citadel_freelook_velocity_y*CITADEL_CSTICK_SPEED_NUMERATOR)/CITADEL_CSTICK_SPEED_DENOMINATOR;
        citadel_freelook_velocity_x =
            citadel_3ds_scale_signed_round(
                citadel_freelook_velocity_x,
                stereo_frame_scale,
                16);
        citadel_freelook_velocity_y =
            citadel_3ds_scale_signed_round(
                citadel_freelook_velocity_y,
                stereo_frame_scale,
                16);
        return;
    }
    if (touch_held) return;
    sx=citadel_axis_step(cstick->dx,CITADEL_CSTICK_POINTER_DEADZONE,CITADEL_CSTICK_POINTER_DIVISOR);
    sy=-citadel_axis_step(cstick->dy,CITADEL_CSTICK_POINTER_DEADZONE,CITADEL_CSTICK_POINTER_DIVISOR);
    sx=(sx*CITADEL_CSTICK_SPEED_NUMERATOR)/CITADEL_CSTICK_SPEED_DENOMINATOR;
    sy=(sy*CITADEL_CSTICK_SPEED_NUMERATOR)/CITADEL_CSTICK_SPEED_DENOMINATOR;
    if (!sx && !sy) return;
    if (split_layout) { citadel_move_panel_cursor(citadel_panel_step(sx,true),citadel_panel_step(sy,false)); return; }
    lx=(sx*citadel_current_mouse_width())/CITADEL_REF_WIDTH; ly=(sy*citadel_current_mouse_height())/CITADEL_REF_HEIGHT;
    if (sx && !lx) lx=sx>0?1:-1; if (sy && !ly) ly=sy>0?1:-1;
    citadel_set_mouse_position(MouseX+lx,MouseY+ly,true);
}

static void citadel_process_3ds_input(u32 keys_down, u32 keys_up, u32 keys_held)
{
    circlePosition circle={0,0},cstick={0,0};
    touchPosition touch;
    int mouse_width=citadel_current_mouse_width(),mouse_height=citadel_current_mouse_height();
    bool split_layout=citadel_3ds_split_layout_active();
    bool gameplay_active=citadel_3ds_gameplay_controls_active();
    bool touch_held=(keys_held&KEY_TOUCH)!=0;
    hidCircleRead(&circle); citadel_read_cstick(&cstick);
    citadel_cpad_raw_x=circle.dx; citadel_cpad_raw_y=circle.dy; citadel_analog_gameplay_active=gameplay_active;
    if (split_layout && !citadel_last_split_layout) citadel_sync_panel_from_logical();
    citadel_last_split_layout=split_layout;
    if ((keys_down&KEY_A) && gameplay_active) { citadel_freelook_desired=!citadel_freelook_desired; citadel_input_log("FREELOOK desired=%d trigger=A panel=%d local=%d,%d logical=%d,%d",citadel_freelook_desired,citadel_cursor_panel,citadel_cursor_local_x,citadel_cursor_local_y,MouseX,MouseY); }
    if (keys_down&KEY_START) { citadel_freelook_desired=false; citadel_emit_key(SDLK_ESCAPE,true); }
    if (keys_up&KEY_START) citadel_emit_key(SDLK_ESCAPE,false);
    if (keys_down&KEY_SELECT) { citadel_freelook_desired=false; citadel_3ds_toggle_legacy_view(); }
    if (!gameplay_active) citadel_freelook_desired=false;
    citadel_update_menu_dpad(keys_held,gameplay_active);
    citadel_update_cstick(&cstick,gameplay_active,split_layout,touch_held);
    if (keys_down&KEY_R) { citadel_r_left_down=true; citadel_update_left_button(); }
    if (keys_up&KEY_R) { citadel_r_left_down=false; citadel_update_left_button(); }
    if (keys_down&KEY_TOUCH) {
        hidTouchRead(&touch); citadel_freelook_desired=false;
        if (split_layout) { citadel_touch_panel=citadel_touch_panel_at(&touch); citadel_set_panel_from_touch(&touch,citadel_touch_panel); citadel_input_log("TOUCH START panel=%d screen=%u,%u local=%d,%d logical=%d,%d",citadel_touch_panel,touch.px,touch.py,citadel_cursor_local_x,citadel_cursor_local_y,MouseX,MouseY); }
        else citadel_set_mouse_position(((int)touch.px*mouse_width)/CITADEL_TOUCH_WIDTH,((int)touch.py*mouse_height)/CITADEL_TOUCH_HEIGHT,true);
        citadel_touch_left_down=true; citadel_update_left_button();
    }
    if (keys_held&KEY_TOUCH) { hidTouchRead(&touch); if (split_layout) citadel_set_panel_from_touch(&touch,citadel_touch_panel); else citadel_set_mouse_position(((int)touch.px*mouse_width)/CITADEL_TOUCH_WIDTH,((int)touch.py*mouse_height)/CITADEL_TOUCH_HEIGHT,true); }
    if (keys_up&KEY_TOUCH) { citadel_touch_left_down=false; citadel_update_left_button(); citadel_input_log("TOUCH END panel=%d local=%d,%d logical=%d,%d",citadel_cursor_panel,citadel_cursor_local_x,citadel_cursor_local_y,MouseX,MouseY); }
    if (keys_down&KEY_L) { citadel_l_right_down=true; citadel_update_right_button(); }
    if (keys_up&KEY_L) { citadel_l_right_down=false; citadel_update_right_button(); }
    if (keys_down&KEY_B) {
        /*
         * B is the fast recovery button: leave freelook/camera mode and put
         * the logical cursor back in the center of the upper world view.
         * A can then immediately re-enter freelook for combat.
         */
        citadel_freelook_desired=false;
        citadel_center_cursor_on_top();
    }
    if (keys_down&KEY_X) citadel_emit_key(SDLK_SPACE,true); if (keys_up&KEY_X) citadel_emit_key(SDLK_SPACE,false);
    if (keys_down&KEY_Y) citadel_emit_key(SDLK_RETURN,true); if (keys_up&KEY_Y) citadel_emit_key(SDLK_RETURN,false);
}

#endif


void pump_events(void) {
    SDL_Event ev;

#if defined(__3DS__) || defined(_3DS)
    u32 citadel_keys_down;
    u32 citadel_keys_up;
    u32 citadel_keys_held;
    static bool citadel_input_started = false;

    /*
     * Capture libctru state before SDL_PollEvent() has a chance to perform
     * its own backend scan.
     */
    hidScanInput();
    citadel_keys_down = hidKeysDown();
    citadel_keys_up = hidKeysUp();
    citadel_keys_held = hidKeysHeld();

    if (!citadel_input_started) {
        citadel_input_started = true;
        citadel_set_mouse_position(citadel_current_mouse_width() / 2,
                                   citadel_current_mouse_height() / 2,
                                   false);
        citadel_input_log("PROJECT CITADEL INPUT V16.1 START build=%s %s mouse=%d,%d",
                          __DATE__,
                          __TIME__,
                          MouseX,
                          MouseY);
        citadel_input_log("CONTROLS circle=direct-analog cstick=panel-cursor "
                          "A=native-freelook R=activate-left L=fire-right "
                          "B=center-top touch=direct-lower X=space Y=enter "
                          "START=escape SELECT=legacy");
    }
#endif

    while (SDL_PollEvent(&ev)) {
        switch (ev.type) {
        case SDL_QUIT:
#if defined(__3DS__) || defined(_3DS)
            /*
             * Do not call exit(0) from inside SDL's applet event handling.
             * Let Shock's main loop unwind and run its normal shutdown path.
             */
            citadel_input_log("SDL_QUIT received; requesting V16.1 HOME cleanup");
            citadel_3ds_system_close_requested = true;
            gPlayingGame = false;
            return;
#else
            // a bit hacky at this place, but this would allow exiting the game via the window's [x] button
            exit(0); // TODO: I guess there is a better way.
            break;
#endif

        // TODO: really also handle key up here? the mac code apparently didn't, but where else do
        //       kbs_events with .state == KBS_UP come from?
        case SDL_KEYUP:
        case SDL_KEYDOWN: {
            uchar c = sdlKeyCodeToSSHOCKkeyCode(ev.key.keysym.sym);
            if (c != KBC_NONE) {
                kbs_event keyEvent = {0};

                keyEvent.code = c;
                keyEvent.ascii = 0;
                keyEvent.modifiers = 0;

                // https://wiki.libsdl.org/SDLKeycodeLookup
                // Keycodes for keys with printable characters are represented by the
                // character byte in parentheses. Keycodes without character representations
                // are determined by their scancode bitwise OR-ed with 1<<30 (0x40000000).

                if (ev.key.keysym.sym >= 0x08 && ev.key.keysym.sym <= 127)
                    keyEvent.ascii = ev.key.keysym.sym;
                else {
                    // use these invented "ascii" codes for hotkey system
                    // see MacSrc/Prefs.c
                    switch (ev.key.keysym.sym) {
                    case SDLK_F1:
                        keyEvent.ascii = 128 + 0;
                        break;
                    case SDLK_F2:
                        keyEvent.ascii = 128 + 1;
                        break;
                    case SDLK_F3:
                        keyEvent.ascii = 128 + 2;
                        break;
                    case SDLK_F4:
                        keyEvent.ascii = 128 + 3;
                        break;
                    case SDLK_F5:
                        keyEvent.ascii = 128 + 4;
                        break;
                    case SDLK_F6:
                        keyEvent.ascii = 128 + 5;
                        break;
                    case SDLK_F7:
                        keyEvent.ascii = 128 + 6;
                        break;
                    case SDLK_F8:
                        keyEvent.ascii = 128 + 7;
                        break;
                    case SDLK_F9:
                        keyEvent.ascii = 128 + 8;
                        break;
                    case SDLK_F10:
                        keyEvent.ascii = 128 + 9;
                        break;
                    case SDLK_F11:
                        keyEvent.ascii = 128 + 10;
                        break;
                    case SDLK_F12:
                        keyEvent.ascii = 128 + 11;
                        break;
                    case SDLK_KP_DIVIDE:
                        keyEvent.ascii = 128 + 12;
                        break;
                    case SDLK_KP_MULTIPLY:
                        keyEvent.ascii = 128 + 13;
                        break;
                    case SDLK_KP_MINUS:
                        keyEvent.ascii = 128 + 14;
                        break;
                    case SDLK_KP_PLUS:
                        keyEvent.ascii = 128 + 15;
                        break;
                    case SDLK_KP_ENTER:
                        keyEvent.ascii = 128 + 16;
                        break;
                    case SDLK_KP_DECIMAL:
                        keyEvent.ascii = 128 + 17;
                        break;
                    case SDLK_KP_0:
                        keyEvent.ascii = 128 + 18;
                        break;
                    }
                }

                Uint16 mod = ev.key.keysym.mod;

                if (mod & KMOD_SHIFT)
                    keyEvent.modifiers |= KB_MOD_SHIFT;
                if (mod & KMOD_CTRL)
                    keyEvent.modifiers |= KB_MOD_CTRL;
                if (mod & KMOD_ALT)
                    keyEvent.modifiers |= KB_MOD_ALT;

                if (ev.key.state == SDL_PRESSED) {
                    if (ev.key.keysym.sym == SDLK_RETURN && mod & KMOD_ALT) {
                        toggleFullScreen();
                        break;
                    }

                    // handle non-printable or ctrl'd or alt'd keys here
                    // other cases are handled by text input event below
                    if (ev.key.keysym.sym < 32 || ev.key.keysym.sym > 126 || (mod & KMOD_CTRL) || (mod & KMOD_ALT)) {
                        keyEvent.state = KBS_DOWN;
                        addKBevent(&keyEvent);

                        sshockKeyStates[c] = keyEvent.modifiers | KB_MOD_PRESSED;
                    }
                } else {
                    // key up following text input event case below is handled here

                    keyEvent.state = KBS_UP;
                    addKBevent(&keyEvent);

                    sshockKeyStates[c] = 0;
                }
            }

            // hack to allow pressing shift after move key
            // sets all current shock states in array to shifted or non-shifted
            if (ev.key.keysym.sym == SDLK_LSHIFT || ev.key.keysym.sym == SDLK_RSHIFT) {
                for (int i = 0; i < 256; i++)
                    if (sshockKeyStates[i]) {
                        if (ev.key.state == SDL_PRESSED)
                            sshockKeyStates[i] |= KB_MOD_SHIFT;
                        else
                            sshockKeyStates[i] &= ~KB_MOD_SHIFT;
                    }
            }
        } break;

        case SDL_TEXTINPUT: {
            uint32_t len = strlen(ev.text.text);

            // for every utf8 char in null-terminated string
            for (uint32_t i = 0; i < len; i++) {
                int ch = ev.text.text[i];

                // ignore if non-printable key
                if (!isprint(ch))
                    continue;

                kbs_event keyEvent = {0};

                keyEvent.modifiers = 0;

                // if uppercase, lower it and set shift modifier
                if (isupper(ch)) {
                    ch = tolower(ch);
                    keyEvent.modifiers |= KB_MOD_SHIFT;
                }

                // get code for this printable ascii key
                int c = Ascii2Code[ch - 32];

                keyEvent.code = c;
                keyEvent.ascii = ch;

                // this is a key down event; key up will be handled in event case above
                keyEvent.state = KBS_DOWN;
                addKBevent(&keyEvent);

                sshockKeyStates[c] = keyEvent.modifiers | KB_MOD_PRESSED;
            }
        } break;

        case SDL_MOUSEBUTTONDOWN:
        case SDL_MOUSEBUTTONUP: {
#if defined(__3DS__) || defined(_3DS)
            break;
#endif
            bool down = (ev.button.state == SDL_PRESSED);
            ss_mouse_event mouseEvent = {0};
            mouseEvent.type = 0;

            // TODO: the old mac code used to emulate right mouse clicks if space, enter, or return
            //       was pressed at the same time - do the same? (=> could check sshockKeyStates[])

            mouseEvent.buttons = 0;

            switch (ev.button.button) {
            case SDL_BUTTON_LEFT:
                mouseEvent.type = down ? MOUSE_LDOWN : MOUSE_LUP;
                mouseEvent.buttons |= down ? (1 << MOUSE_LBUTTON) : 0;
                break;

            case SDL_BUTTON_RIGHT:
                mouseEvent.type = down ? MOUSE_RDOWN : MOUSE_RUP;
                mouseEvent.buttons |= down ? (1 << MOUSE_RBUTTON) : 0;
                break;

                // case SDL_BUTTON_MIDDLE: // TODO: is this MOUSE_CDOWN/UP ?
                // break;
            }

            if (mouseEvent.type != 0) {
                bool shifted = ((SDL_GetModState() & KMOD_SHIFT) != 0);

                mouseEvent.x = MouseX;
                mouseEvent.y = MouseY;
                mouseEvent.timestamp = mouse_get_time();
                mouseEvent.modifiers = (shifted ? 1 : 0);
                addMouseEvent(&mouseEvent);
            }
        } break;

        case SDL_MOUSEMOTION: {
#if defined(__3DS__) || defined(_3DS)
            break;
#endif
            // call this first; it sets MouseX and MouseY
            if (SDL_GetRelativeMouseMode() == SDL_TRUE)
                SetMouseXY(MouseX + ev.motion.xrel, MouseY + ev.motion.yrel);
            else
                SetMouseXY(ev.motion.x, ev.motion.y);

            ss_mouse_event mouseEvent = {0};
            mouseEvent.type = MOUSE_MOTION;
            mouseEvent.x = MouseX;
            mouseEvent.y = MouseY;
            mouseEvent.buttons = 0;
            if (ev.motion.state & SDL_BUTTON_LMASK)
                mouseEvent.buttons |= (1 << MOUSE_LBUTTON);
            if (ev.motion.state & SDL_BUTTON_RMASK)
                mouseEvent.buttons |= (1 << MOUSE_RBUTTON);
            mouseEvent.timestamp = mouse_get_time();
            addMouseEvent(&mouseEvent);

            if (TriggerRelMouseMode) {
                TriggerRelMouseMode = FALSE;

                SDL_SetRelativeMouseMode(SDL_TRUE);
                // throw away this first relative mouse reading
                int mvelx, mvely;
                get_mouselook_vel(&mvelx, &mvely);
            }
        } break;

        case SDL_MOUSEWHEEL:
#if defined(__3DS__) || defined(_3DS)
            break;
#endif
            if (ev.wheel.y != 0) {
                ss_mouse_event mouseEvent = {0};
                mouseEvent.type = ev.wheel.y < 0 ? MOUSE_WHEELDN : MOUSE_WHEELUP;
                mouseEvent.x = MouseX;
                mouseEvent.y = MouseY;
                mouseEvent.buttons = 0;
                mouseEvent.timestamp = mouse_get_time();
                addMouseEvent(&mouseEvent);
            }
            break;

        case SDL_WINDOWEVENT:
            switch (ev.window.event) {
            case SDL_WINDOWEVENT_SIZE_CHANGED:
                if (can_use_opengl())
                    opengl_resize(ev.window.data1, ev.window.data2);
                break;

            case SDL_WINDOWEVENT_MOVED:
            case SDL_WINDOWEVENT_RESIZED:
                break;

            case SDL_WINDOWEVENT_FOCUS_GAINED:
                SDL_SetRelativeMouseMode(saved_rel_mouse);
                if (saved_rel_mouse == SDL_TRUE) {
                    // throw away this first relative mouse reading
                    int mvelx, mvely;
                    get_mouselook_vel(&mvelx, &mvely);
                }
                SDL_ShowCursor(SDL_DISABLE);
                break;

            case SDL_WINDOWEVENT_FOCUS_LOST:
                saved_rel_mouse = SDL_GetRelativeMouseMode();
                SDL_SetRelativeMouseMode(SDL_FALSE);
                SDL_ShowCursor(SDL_ENABLE);
                break;
            }
            break;
        }
    }
#if defined(__3DS__) || defined(_3DS)
    citadel_process_3ds_input(citadel_keys_down,
                              citadel_keys_up,
                              citadel_keys_held);
#endif
}

//===============================================================
//
// This section is adapted from:
// kbMac.c - All the keyboard handling routines that are specific to the Macintosh.
//
//===============================================================

//------------------
//  Globals
//------------------
int pKbdStatusFlags;

//---------------------------------------------------------------
//  Startup and keyboard handlers and initialize globals.   Shutdown follows.
//---------------------------------------------------------------
int kb_startup(void *v) {
    pKbdStatusFlags = 0;

    memset(sshockKeyStates, 0, sizeof(sshockKeyStates));
    nextKBevent = 0;

    return (0);
}

int kb_shutdown(void) { return (0); }

//---------------------------------------------------------------
//  Get and set the global flags.
//---------------------------------------------------------------
int kb_get_flags() { return (pKbdStatusFlags); }

void kb_set_flags(int flags) { pKbdStatusFlags = flags; }

//---------------------------------------------------------------
//  Get the next available key from the event queue.
//---------------------------------------------------------------
kbs_event kb_next(void) {
    kbs_event retEvent = kb_look_next();
    // kb_look_next() doesn't remove events from the queue, this function does,
    // right here (but only if there actually was an event in the queue, of course):
    if (nextKBevent > 0) {
        --nextKBevent;
        memmove(&kbEvents[0], &kbEvents[1], sizeof(kbs_event) * (kNumKBevents - 1));
    }
    return retEvent;

#if 0
	bool gotKey = FALSE;
	EventRecord	theEvent;
	while(!gotKey)
	{
		gotKey = GetOSEvent(keyDownMask | autoKeyMask, &theEvent);		// Get a key
		if (gotKey)
		{
			retEvent.code = (uchar)(theEvent.message >> 8); // keyCodeMask == 0x0000FF00
			retEvent.state = KBS_DOWN;
			retEvent.ascii = (uchar)(theEvent.message & charCodeMask);
			retEvent.modifiers = (uchar)(theEvent.modifiers >> 8);
		}
		else if ((flags & KBF_BLOCK) == 0)					// If there was no key and we're
			return (retEvent);										// not blocking, then return.
	}
	return (retEvent);
#endif
}

//---------------------------------------------------------------
//  See if there is a key waiting in the queue.
//---------------------------------------------------------------
kbs_event kb_look_next(void) {
    kbs_event retEvent = {0xFF, 0x00};

    int flags = kb_get_flags();
    if (flags & KBF_BLOCK) {
        while (nextKBevent == 0) {
            pump_events();
        }
    }

    if (nextKBevent > 0) {
        retEvent = kbEvents[0];
    }
    return retEvent;

#if 0
	bool				gotKey = FALSE;
	EventRecord	theEvent;
	while(!gotKey)
	{
		gotKey = OSEventAvail(keyDownMask | autoKeyMask, &theEvent);		// Get a key
		if (gotKey)
		{
			retEvent.code = (uchar)(theEvent.message >> 8);
			retEvent.state = KBS_DOWN;
			retEvent.ascii = (uchar)(theEvent.message & charCodeMask);
			retEvent.modifiers = (uchar)(theEvent.modifiers >> 8);
		}
		else if (flags & KBF_BLOCK == 0)					// If there was no key and we're
			return (retEvent);										// not blocking, then return.
	}
	return (retEvent);
#endif
}

//---------------------------------------------------------------
//  Flush keyboard events from the event queue.
//---------------------------------------------------------------
void kb_flush(void) {
    // http://mirror.informatimago.com/next/developer.apple.com/documentation/Carbon/Reference/Event_Manager/event_mgr_ref/function_group_5.html#//apple_ref/c/func/FlushEvents
    // FlushEvents(keyDownMask | autoKeyMask, 0);

    SDL_FlushEvents(SDL_KEYDOWN, SDL_KEYUP); // Note: that's a range!

    nextKBevent = 0; // this flushes the keyboard events already buffered - TODO is that desirable?
}

//---------------------------------------------------------------
//  Return the state of the indicated key (scan code).
//---------------------------------------------------------------

uchar kb_state(uchar code) {
    // see
    // http://mirror.informatimago.com/next/developer.apple.com/documentation/Carbon/Reference/Event_Manager/event_mgr_ref/function_group_4.html#//apple_ref/c/func/GetKeys
    // GetKeys((UInt32 *) pKbdGetKeys);
    // return ((pKbdGetKeys[code>>3] >> (code & 7)) & 1);

    return sshockKeyStates[code] != 0;
}

//---------------------------
//
// MOUSE STUFF
//
//---------------------------

// ---------------------------------------------------------
// mouse_next gets the event in the front event queue,
// and removes the event from the queue.
// res = ptr to event to be filled.
//	---------------------------------------------------------
//  For Mac version: Get event from the normal Mac event queue for mouse events.
//  The events looked for depend on the 'mouseMask' setting.

uchar btn_left = FALSE;
uchar btn_right = FALSE;
errtype mouse_next(ss_mouse_event *res) {
    if (nextMouseEvent <= 0)
        return ERR_DUNDERFLOW;

    *res = mouseEvents[0];

    --nextMouseEvent;
    memmove(&mouseEvents[0], &mouseEvents[1], sizeof(ss_mouse_event) * (kNumMouseEvents - 1));

    return OK;
}

errtype mouse_flush(void) {
    // FlushEvents(mouseDown | mouseUp, 0);
    //   Spew(DSRC_MOUSE_Flush,("Entering mouse_flush()\n"));
    // mouseQueueIn = mouseQueueOut = 0;
    nextMouseEvent = 0;
    // TODO: anything else?
    return OK;
}

errtype mouse_get_xy(short *x, short *y) {
    *x = MouseX;
    *y = MouseY;

    return OK;
}

void middleize_mouse(void) {
#if defined(__3DS__) || defined(_3DS)
    MouseX = latestMouseEvent.x = citadel_current_mouse_width() / 2;
    MouseY = latestMouseEvent.y = citadel_current_mouse_height() / 2;
#else
    int w, h;
    SDL_RenderGetLogicalSize(renderer, &w, &h);

    MouseX = latestMouseEvent.x = w / 2;
    MouseY = latestMouseEvent.y = h / 2;
#endif
}

void get_mouselook_vel(int *vx, int *vy) {
#if defined(__3DS__) || defined(_3DS)
    /*
     * The 3DS has no desktop relative-mouse stream. While A-toggle freelook
     * is active, feed Shockolate the C-stick deltas sampled in pump_events().
     */
    if (citadel_freelook_desired &&
        citadel_3ds_gameplay_controls_active()) {
        *vx = citadel_freelook_velocity_x + MouseChaosX;
        *vy = citadel_freelook_velocity_y + MouseChaosY;
        MouseChaosX = 0;
        MouseChaosY = 0;
        return;
    }
#endif

    if (SDL_ShowCursor(SDL_QUERY) == SDL_ENABLE)
        *vx = *vy = 0;
    else {
        SDL_GetRelativeMouseState(vx, vy);

        *vx += MouseChaosX;
        MouseChaosX = 0;
        *vy += MouseChaosY;
        MouseChaosY = 0;
    }
}

errtype mouse_put_xy(short x, short y) {
#if defined(__3DS__) || defined(_3DS)
    citadel_set_mouse_position((int)x, (int)y, false);
#else
    MouseX = x;
    MouseY = y;
#endif

    return OK;
}

void set_mouse_chaos(short dx, short dy) {
    MouseChaosX = dx;
    MouseChaosY = dy;
}

void sdl_mouse_init(void) {
    nextMouseEvent = 0;

#if defined(__3DS__) || defined(_3DS)
    MouseX = citadel_current_mouse_width() / 2;
    MouseY = citadel_current_mouse_height() / 2;
    latestMouseEvent.x = MouseX;
    latestMouseEvent.y = MouseY;
    latestMouseEvent.buttons = 0;
#endif
}
