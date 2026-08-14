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
/*
 * $Source: r:/prj/cit/src/RCS/mainloop.c $
 * $Revision: 1.42 $
 * $Author: xemu $
 * $Date: 1994/11/09 02:09:05 $
 */

/*
 * Citadel main loops
 *
 * The idea here is that we have a separate loop for each game mode/setup
 * There is a 4/12 bit change flag which is 4 global and 12 local
 * The global loop checks OS and input
 * Then calls the local loop, which does it's internal inlined functions
 *  and then processes it's change flags
 * The global loop then gets control and does it's own change flags
 * If you want to switch modes/loops you call change_loop which both sets
 *  global change bit 3 as well setting some variables.  When the main loop
 *  reaches the bottom it triggers on change bit 3 and calls the switch code
 */

#define __MAINLOOP_SRC

#include <stdio.h>

#if defined(__3DS__) || defined(_3DS)
/* Avoid <3ds.h>: Shock's keydefs.h already defines KEY_UP/KEY_DOWN/etc. */
#include <3ds/types.h>
#include <3ds/result.h>
#include <3ds/services/gspgpu.h>
#endif

#include "InitMac.h"
#include "Shock.h"
#include "amaploop.h"
#include "cutsloop.h"
#include "game_screen.h"
#include "fullscrn.h"
#include "loops.h"
#include "fullamap.h"
#include "input.h"
#include "sdl_events.h"
#include "setup.h"
#include "status.h"
#include "tickcount.h"
#include "tools.h"
#include "wrapper.h"

#if defined(__3DS__) || defined(_3DS)
void citadel_3ds_newgame_home_t7_pre_frame(void);
void citadel_3ds_newgame_home_t7_post_frame(void);
#endif

#warning "PROJECT CITADEL V4: unique mainloop log is ACTIVE"
#warning "PROJECT CITADEL T7: exact numbered-slot UI lifecycle hook is ACTIVE"

// how is the game doing, anyway, set to true at end of time
uchar cit_success = FALSE;

// are we "paused"
uchar game_paused = FALSE;

frc *_current_fr_context;
short _current_loop = SETUP_LOOP; /* which loop we currently are */
short _current_3d_flag = DEMOVIEW_UPDATE;
LGRegion *_current_view = NULL;
uint _change_flag = 0;   /* change flags for loop */
uint _static_change = 0; /* current static changes */
short _new_mode = 0;     /* mode to change to, if any */
short _last_mode = 0;    /* last mode, if you want to change back to it */
uchar time_passes = TRUE;
uchar saves_allowed = FALSE;
uchar physics_running = TRUE;
uchar ai_on = TRUE;
uchar anim_on = TRUE;
uchar player_invulnerable = FALSE;
uchar player_immortal = FALSE;
uchar always_render = FALSE;
uchar pal_fx_on = TRUE;

/*
 * --------------------------------------------------------------------------
 * 3DS MAIN-LOOP DIAGNOSTIC LOGGER
 * --------------------------------------------------------------------------
 * This creates "MAINLOOP_V4.log" beside the game's prefs/keybinds files.
 *
 * Detailed per-call logging is limited to the first five frames so that a
 * normally running game does not continuously write to the SD card.
 * Mode-entry, mode-exit, and mode-switch events are still recorded whenever
 * they occur because those events should be infrequent.
 *
 * Each marker opens, flushes, and closes the file immediately. This is slower
 * than keeping the file open, but it preserves the last completed marker if
 * the next call hangs or crashes.
 */
#define LOOP_LOG_FRAME_LIMIT 5

static unsigned int loop_log_step = 0;
static unsigned int loop_log_frame = 0;

static void loopmark(const char *message) {
    FILE *file = fopen("MAINLOOP_V4.log", "a");

    if (file == NULL)
        return;

    fprintf(file,
            "%03u: %s | frame=%u loop=%d playing=%u "
            "change=0x%08X static=0x%08X new=%d last=%d\n",
            ++loop_log_step,
            message,
            loop_log_frame,
            (int)_current_loop,
            (unsigned int)gPlayingGame,
            (unsigned int)_change_flag,
            (unsigned int)_static_change,
            (int)_new_mode,
            (int)_last_mode);

    fflush(file);
    fclose(file);
}

#if defined(__3DS__) || defined(_3DS)
/*
 * PROJECT CITADEL V21A — minimal cold-boot HOME primer.
 *
 * This deliberately touches only the GSP/VRAM operations that already occur
 * around a normal HOME transition. It runs once, after Journey has completed
 * several ordinary SETUP_LOOP frames and SDLDraw() has returned, so no
 * Citro3D frame should still be open. It does not jump to HOME, invoke game
 * save/load code, alter layout, or modify the existing APT hook.
 */
#define CITADEL_V21_PRIMER_SETUP_FRAMES 8U

static unsigned int citadel_3ds_v21_setup_frames = 0;
static bool citadel_3ds_v21_primer_done = false;

static void citadel_3ds_v21_run_minimal_primer(void)
{
    GSPGPU_CaptureInfo capture_info = {0};
    Result save_result;
    Result capture_result;
    Result release_result;
    Result acquire_result = (Result)-1;
    Result restore_result = (Result)-1;
    char message[256];

    /* Never retry this automatically during the same process. */
    citadel_3ds_v21_primer_done = true;

    loopmark("V21A PRIMER BEGIN: waiting for completed Journey VBlank");
    gspWaitForVBlank();

    if (!gspHasGpuRight()) {
        loopmark("V21A PRIMER ABORTED: application does not own GPU right");
        return;
    }

    save_result = GSPGPU_SaveVramSysArea();
    capture_result = GSPGPU_ImportDisplayCaptureInfo(&capture_info);
    release_result = GSPGPU_ReleaseRight();

    if (R_SUCCEEDED(release_result)) {
        acquire_result = GSPGPU_AcquireRight(0);
        if (R_SUCCEEDED(acquire_result))
            restore_result = GSPGPU_RestoreVramSysArea();
    }

    /* Let GSP consume the restored display state before the next SDLDraw(). */
    if (R_SUCCEEDED(acquire_result))
        gspWaitForVBlank();

    snprintf(message,
             sizeof(message),
             "V21A PRIMER RESULTS save=0x%08lX capture=0x%08lX "
             "release=0x%08lX acquire=0x%08lX restore=0x%08lX "
             "topL=%p topR=%p bottom=%p",
             (unsigned long)save_result,
             (unsigned long)capture_result,
             (unsigned long)release_result,
             (unsigned long)acquire_result,
             (unsigned long)restore_result,
             (void *)capture_info.screencapture[GSP_SCREEN_TOP].framebuf0_vaddr,
             (void *)capture_info.screencapture[GSP_SCREEN_TOP].framebuf1_vaddr,
             (void *)capture_info.screencapture[GSP_SCREEN_BOTTOM].framebuf0_vaddr);
    loopmark(message);

    if (R_SUCCEEDED(save_result) &&
        R_SUCCEEDED(capture_result) &&
        R_SUCCEEDED(release_result) &&
        R_SUCCEEDED(acquire_result) &&
        R_SUCCEEDED(restore_result))
        loopmark("V21A PRIMER COMPLETE");
    else
        loopmark("V21A PRIMER COMPLETE WITH ERROR; do not treat as primed");
}
#endif

/*
 * Temporary diagnostic bypass:
 *
 * play_cutscene() has been confirmed to return, but another startup code path
 * queues CUTSCENE_LOOP afterward. Catch that transition at the final point
 * before loopmode_switch() can consume it.
 */
static void block_cutscene_transition_if_pending(const char *where)
{
    if (_new_mode == CUTSCENE_LOOP &&
        (_change_flag & (ML_CHG_BASE << 3)))
    {
        char message[160];

        snprintf(message,
                 sizeof(message),
                 "3DS CUTSCENE TRAP at %s: cancelling pending mode 6",
                 where);
        loopmark(message);

        _new_mode = SETUP_LOOP;
        chg_unset_flg(ML_CHG_BASE << 3);

        loopmark("3DS CUTSCENE TRAP: forced SETUP_LOOP and cleared global loop-change bit");
    }
}

// Note that in the shipping version, the edit_loop stuff should never
// get called, but needs to be SOMETHING as a place holder
// void
// (*citadel_loops[])(void)={game_loop,game_loop,game_loop,game_loop,setup_loop,game_loop,cutscene_loop,game_loop,automap_loop};
// void
// (*enter_modes[])(void)={screen_start,fullscreen_start,screen_start,screen_start,setup_start,screen_start,cutscene_start,fullscreen_start,amap_start};
// void (*exit_modes[])(void)={screen_exit,fullscreen_exit,screen_exit,
// screen_exit,setup_exit,screen_exit,cutscene_exit,fullscreen_exit,amap_exit};

void (*citadel_loops[])(void) = {game_loop, game_loop, game_loop, game_loop, setup_loop, game_loop, cutscene_loop, game_loop, automap_loop};
void (*enter_modes[])(void) = {screen_start, fullscreen_start, NULL, NULL, setup_start, NULL, cutscene_start, fullscreen_start, amap_start};
void (*exit_modes[])(void) = {screen_exit, fullscreen_exit, NULL, NULL, setup_exit, NULL, cutscene_exit, fullscreen_exit, amap_exit};

void loopmode_switch(short *cmode) {
#ifdef SVGA_SUPPORT
    extern uchar wrapper_screenmode_hack;
#endif

    loopmark("loopmode_switch: entered");

    // Actually switch mode
    _last_mode = *cmode;
    loopmark("loopmode_switch: before old mode exit");
    (*exit_modes[_last_mode])();
    loopmark("loopmode_switch: after old mode exit");

    *cmode = _new_mode;
    _static_change = 0;
    loopmark("loopmode_switch: assigned new current mode");

    if (*cmode >= 0) {
        loopmark("loopmode_switch: before new mode enter");
        (*enter_modes[*cmode])();
        loopmark("loopmode_switch: after new mode enter");
    }

#ifdef SVGA_SUPPORT
    if (wrapper_screenmode_hack) {
        loopmark("loopmode_switch: before wrapper_start");
        wrapper_start(screenmode_screen_init);
        loopmark("loopmode_switch: after wrapper_start");
    }
#endif

    loopmark("loopmode_switch: complete");
}

void loopmode_exit(short loopmode) {
    loopmark("loopmode_exit: entered");

    if (exit_modes[loopmode]) {
        loopmark("loopmode_exit: before exit function");
        (*exit_modes[loopmode])();
        loopmark("loopmode_exit: after exit function");
    }

    loopmark("loopmode_exit: complete");
}

void loopmode_enter(short loopmode) {
    loopmark("loopmode_enter: before enter function");
    (*enter_modes[loopmode])();
    loopmark("loopmode_enter: after enter function");
}

extern void MousePollProc(void);
void mainloop(int argc, char *argv[]) {
    int log_this_frame;
    short loop_at_frame_start;

    /*
     * Start a new loop log for this launch. If this file never appears,
     * mainloop() was never entered.
     */
    loop_log_step = 0;
    loop_log_frame = 0;
    remove("MAINLOOP_V4.log");

    loopmark("V4_UNMISTAKABLE_MAINLOOP_ENTERED");
    loopmark("V4 mainloop build: " __DATE__ " " __TIME__);

    /*
     * The intro caller has already returned by this point. Cancel any mode-6
     * request that was queued afterward.
     */
    block_cutscene_transition_if_pending("mainloop entry");

    /*
     * The while condition is the first major diagnostic:
     *   _current_loop must be >= 0
     *   gPlayingGame must be nonzero
     */
    if (!(_current_loop >= 0 && gPlayingGame))
        loopmark("Main-loop guard is FALSE on entry; no frame will run");
    else
        loopmark("Main-loop guard is TRUE on entry");

    while (_current_loop >= 0 && gPlayingGame) {
        loop_at_frame_start = _current_loop;
        loop_log_frame++;
        log_this_frame = (loop_log_frame <= LOOP_LOG_FRAME_LIMIT);

        if (log_this_frame)
            loopmark("FRAME START");

#if defined(__3DS__) || defined(_3DS)
        /*
         * A real wrapper selection is handled before the active game frame is
         * rendered. T7 performs its queued Save/Load selection here, after the
         * wrapper has already remained open and visible for a complete frame.
         */
        if (loop_at_frame_start == GAME_LOOP && gPlayingGame)
            citadel_3ds_newgame_home_t7_pre_frame();
#endif

        if (log_this_frame)
            loopmark("Before TickCount");
        gShockTicks = TickCount();
        if (log_this_frame)
            loopmark("After TickCount");

        if (!(_change_flag & (ML_CHG_BASE << 1))) {
            if (log_this_frame)
                loopmark("Before input_chk");
            loopLine(ML | 1, input_chk()); // go get the UI stuff going
            if (log_this_frame)
                loopmark("After input_chk");
        } else if (log_this_frame) {
            loopmark("input_chk skipped by change flag");
        }

        // DG: at the beginning of each frame, get all the events from SDL
        if (log_this_frame)
            loopmark("Before pump_events");
        pump_events();

#if defined(__3DS__) || defined(_3DS)
        /*
         * PROJECT CITADEL V16.1: stop immediately after SDL system-close request
         *
         * SDL's 3DS backend emits SDL_QUIT when aptMainLoop() becomes false.
         * Do not run the active game loop, cursor update, or another GPU
         * presentation after that lifecycle event.
         */
        if (!gPlayingGame)
            break;
#endif

        if (log_this_frame)
            loopmark("After pump_events");

        /*
         * On the initial SETUP_LOOP this dispatches setup_loop().
         * If the log ends at "Before current loop dispatch", the active local
         * loop never returned.
         */
        if (log_this_frame)
            loopmark("Before current loop dispatch");
        (*citadel_loops[_current_loop])();
        if (log_this_frame)
            loopmark("After current loop dispatch");

        /*
         * setup_loop() or another startup routine may queue the cutscene again.
         * Cancel it at the last possible moment before globalChanges is handled.
         */
        block_cutscene_transition_if_pending("after local loop dispatch");

        if (globalChanges) { // really, only loopmode_switch (the <<3 case)
            if (log_this_frame)
                loopmark("globalChanges is set");

            // if (_change_flag&(ML_CHG_BASE<<0)) { loopLine(ML|0x10,loop_debug()); }
            if (_change_flag & (ML_CHG_BASE << 3)) {
                if (log_this_frame)
                    loopmark("Before loopmode_switch");
                loopLine(ML | 0x13, loopmode_switch(&_current_loop));
                if (log_this_frame)
                    loopmark("After loopmode_switch");
            }

            if (log_this_frame)
                loopmark("Before clearing global mode-change flag");
            chg_unset_flg(ML_CHG_BASE << 3);
            if (log_this_frame)
                loopmark("After clearing global mode-change flag");
        } else if (log_this_frame) {
            loopmark("No globalChanges this frame");
        }

#ifdef ALWAYS_SHOW_FR
        if (log_this_frame)
            loopmark("Before fr_show_rate");
        fr_show_rate(-1);
        if (log_this_frame)
            loopmark("After fr_show_rate");
#endif

        // OR in the static change flags...
        if (log_this_frame)
            loopmark("Before chg_set_flg(_static_change)");
        chg_set_flg(_static_change);
        if (log_this_frame)
            loopmark("After chg_set_flg(_static_change)");

        if (log_this_frame)
            loopmark("Before MousePollProc");
        MousePollProc(); // update the cursor, was 35 times/sec originally
        if (log_this_frame)
            loopmark("After MousePollProc");

        if (log_this_frame)
            loopmark("Before status_bio_update");
        status_bio_update();
        if (log_this_frame)
            loopmark("After status_bio_update");

        if (log_this_frame)
            loopmark("Before ZoomDrawProc(FALSE)");
        ZoomDrawProc(FALSE); // draw zoom rectangle if enabled; if not, returns immediately
        if (log_this_frame)
            loopmark("After ZoomDrawProc(FALSE)");

        if (log_this_frame)
            loopmark("Before SDLDraw");
        SDLDraw();
        if (log_this_frame)
            loopmark("After SDLDraw");

        if (log_this_frame)
            loopmark("Before ZoomDrawProc(TRUE)");
        ZoomDrawProc(TRUE); // erase zoom rectangle if enabled; if not, returns immediately
        if (log_this_frame)
            loopmark("After ZoomDrawProc(TRUE)");

#if defined(__3DS__) || defined(_3DS)
        /*
         * V21A runs once on Journey after several fully presented SETUP frames.
         * Keeping this directly after SDLDraw()/ZoomDrawProc() makes it a narrow
         * addition to the already-completed frame path.
         */
        if (!citadel_3ds_v21_primer_done &&
            loop_at_frame_start == SETUP_LOOP &&
            _current_loop == SETUP_LOOP &&
            gPlayingGame) {
            citadel_3ds_v21_setup_frames++;
            if (citadel_3ds_v21_setup_frames >= CITADEL_V21_PRIMER_SETUP_FRAMES)
                citadel_3ds_v21_run_minimal_primer();
        }

        /*
         * Advance T7 only after a frame that both began and ended in GAME_LOOP.
         * This guarantees that each real Save/Load wrapper is presented for a
         * complete frame before its genuine selection callback is invoked.
         */
        if (loop_at_frame_start == GAME_LOOP &&
            _current_loop == GAME_LOOP &&
            gPlayingGame) {
            citadel_3ds_newgame_home_t7_post_frame();
        }
#endif

        if (log_this_frame)
            loopmark("FRAME END");

        if (loop_log_frame == LOOP_LOG_FRAME_LIMIT)
            loopmark("Detailed frame logging limit reached; loop continues without per-frame writes");
    }

    loopmark("Exited main-loop while condition");

    cit_success = TRUE;
    loopmark("cit_success set TRUE; leaving mainloop");
    // hit them atexit's
}

errtype static_change_copy() {
    if (always_render)
        chg_set_sta(_current_3d_flag);
    else
        chg_unset_sta(_current_3d_flag);
    return (OK);
}
