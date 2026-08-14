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
 * $Source: r:/prj/cit/src/RCS/init.c $
 * $Revision: 1.185 $
 * $Author: xemu $
 * $Date: 1994/11/28 06:38:07 $
 */

#include <string.h>
#include <stdio.h>

#include "Shock.h"
#include "InitMac.h"
#include "ShockBitmap.h"

#include "criterr.h"
#include "cybmem.h"
#include "cybrnd.h"
#include "drugs.h"
#include "frprotox.h"
#include "gamepal.h"
#include "gamestrn.h"
#include "gamescr.h"
#include "init.h"
#include "input.h"
#include "map.h"
#include "mfdext.h"
#include "musicai.h"
#include "objects.h"
#include "objsim.h"
#include "palfx.h"
#include "physics.h"
#include "player.h"
#include "render.h"
#include "rendtool.h"
#include "sdl_events.h"
#include "sideicon.h"
#include "textmaps.h"
#include "tickcount.h"
#include "tools.h"
#include "gamerend.h"
#include "mainloop.h"
#include "game_screen.h"
#include "shodan.h"
#include "fullscrn.h"
#include "frcamera.h"
#include "dynmem.h"
#include "vitals.h"
#include "view360.h"

#include "shockolate_version.h" // for system shock version number

#include "Modding.h"

/*
#define AIL_SOUND
#include "tminit.h"
#include "mlimbs.h"
#include "fault.h"
#include "dbg.h"
#include "config.h"
#include "memstat.h"
#include "lgprntf.h"

#include "anim.h"
#include "dpaths.h"
#include "setup.h"
#include "cutscene.h"
#include "bugtrak.h"
#include "btfunc.h"
#include "ai.h"

// TOTALLY TEMPORARY
#include "textmaps.h"

#include "obj3d.h"   // for 3d base
#include "citmat.h"  // for materials base
#include "version.h"	// for system shock version number

#ifdef STARTUP_MEMSTATS
#include "mprintf.h"
#endif

#include "wsample.h"

#define CFG_LEVEL_VAR "LEVEL"
#define CFG_DEBUG_VAR "mono_debug"
#define CFG_NOFAULT_VAR "fault_off"
#define CFG_MEMCHECK_VAR  "mem_check"
#define CFG_BUGTRAK_VAR	"bugtrak"
#define CFG_BUGTRAK_RECORD_VAR "bugtrak_record"
#define CFG_ARCHIVE_VAR "archive"
#define CFG_SELFRUN_VAR "selfrun"
#define CFG_NORUN_VAR  "norun"
#define CFG_HEAPCHECK_VAR "heap_checking"
#define CFG_EDMS_SANITY_VAR "edms_sanity"
#define CFG_OPTION_CURSOR_VAR "option_cursor_check"
#define CFG_SERIAL_SECRET "serial_mprint"
*/
#define ORIGIN_DISPLAY_TIME (60 * 3)
#define LG_DISPLAY_TIME (60 * 3)
#define TITLE_DISPLAY_TIME (60 * 3)
#define MIN_WAIT_TIME (60)

//void DrawSplashScreen(short id, Boolean fadeIn);
void PreloadGameResources(void);
errtype init_gamesys();
errtype free_gamesys(void);
errtype init_load_resources();
errtype init_3d_objects();
errtype obj_3d_shutdown();
void init_popups();
uchar pause_for_input(ulong wait_time);

errtype init_pal_fx();
void byebyemessage(void);
/*
errtype init_kb();
errtype init_debug();

extern void load_weapons_data(void);
extern errtype setup_init(void);
extern uchar toggle_heap_check(short keycode, ulong context, void *data);
*/

errtype amap_init(void);
// extern long old_ticks;

/*Â¥Â¥
int   global_timer_id;
extern int mlimbs_peril;
*/
uchar init_done = FALSE;
uchar clear_player_data = TRUE;
uchar objdata_loaded = FALSE;

/*
extern void (*enter_modes[])(void);

extern int KeyGetch(void);
extern void start_intro_sound(void);
extern void start_setup_sound(void);
extern void end_intro_sound(void);
extern void end_setup_sound(void);

extern void init_watchpoints(void);
*/

uchar real_archive_fn[64];
/*
#define SPLASH_RES_FILE "splash.rsrc"
#ifndef EDITOR
#define MIN_SPLASH_TIME  1000
#else
#define MIN_SPLASH_TIME  0
#endif
*/
MemStack temp_memstack;
#define TEMP_STACK_SIZE (16 * 1024)

/*
 * --------------------------------------------------------------------------
 * 3DS STARTUP DIAGNOSTIC LOGGER
 * --------------------------------------------------------------------------
 * This writes one completed startup step at a time to "boot.log" in the
 * program's current working directory. The game already creates prefs and
 * keybinds there, so boot.log should appear beside those files.
 *
 * Each call opens, flushes, and closes the file immediately. That is slower
 * than keeping it open, but it gives us the best chance of preserving the
 * final completed marker if the following startup call hangs or crashes.
 *
 * Remove this helper and the bootmark() calls after the startup problem is
 * identified.
 */
static unsigned int boot_step = 0;

static void bootmark(const char *message) {
    FILE *file = fopen("boot.log", "a");

    if (file == NULL)
        return;

    fprintf(file, "%03u: %s\n", ++boot_step, message);
    fflush(file);
    fclose(file);
}

uchar pause_for_input(ulong wait_time) {
    bool gotInput = false;

    uint32_t wait_until = TickCount() + wait_time;
    while (!gotInput && (TickCount() < wait_until)) {
        pump_events();
        SDLDraw();
    }

    // return if we got input
    return (gotInput);
}

extern char which_lang;
int mfdart_res_file;
//#ifdef DEMO
// uchar *mfdart_files[] = { "mfdart.rsrc", "mfdart.rsrc", "mfdart.rsrc" };
//#else
char *mfdart_files[] = {"res/data/mfdart.res", "res/data/mfdfrn.res", "res/data/mfdger.res"};
//#endif

/* MLA - don't need these
extern void *CitMalloc(int n);
extern void CitFree(void *p);
*/

#define PALETTE_SIZE 768
uchar ppall[PALETTE_SIZE];

//-------------------------------------------------
//  Initialize everything!
//-------------------------------------------------
void init_all(void) {
    /*
       char buf[256];
       char norun[1];
       extern char savegame_dir[50];
       extern Datapath savegame_dpath; */
    ulong pause_time;
    int i;
    bool speed_splash = FALSE;
    /*

       uchar        dofault = TRUE;
            int dummy_count;
       int   data[1];
       int   cnt;
       extern void init_config(int argc,char* argv[]);
       extern errtype terrain_palette_popup(void);
       extern uchar cam_mode;
    */

    /*
     * Start a fresh diagnostic log for this launch.
     * The compile date/time confirms that the newly rebuilt 3DSX is running.
     */
    boot_step = 0;
    remove("boot.log");
    bootmark("Entered init_all");
    bootmark("Diagnostic build: " __DATE__ " " __TIME__);

    bootmark("Before slorkatron_memory_check");
    start_mem = slorkatron_memory_check();
    bootmark("After slorkatron_memory_check");

    if (start_mem < MINIMUM_GAME_THRESHOLD) {
        bootmark("ERROR: available memory is below MINIMUM_GAME_THRESHOLD");
        critical_error(CRITERR_MEM | 1);
    }

    // register the bye message
    bootmark("Before atexit(byebyemessage)");
    atexit(byebyemessage);
    bootmark("After atexit(byebyemessage)");

    bootmark("Before ResInit");
    ResInit();
    bootmark("After ResInit");

    // Where are these defined?
    //   restemp_buffer = ALTERNATE_BUFFER;
    //   restemp_buffer_size = ALTERNATE_BUFFER_SIZE;

    /*
       init_early_dpaths();
       init_config(argc,argv);
       if (config_get_raw(CFG_NORUN_VAR,norun,1))
       {
          if (norun[0]=='1')
             critical_error(CRITERR_EXEC|1);
       }
    */
    //   Spew(DSRC_SYSTEM_Memory, ("initial memory: %d\n",start_mem));
    /*
       dofault = !config_get_raw(CFG_NOFAULT_VAR,NULL,0);
       DBG(DSRC_SYSTEM_FaultDisable,{ dofault = FALSE;});
       if (dofault)
          ex_startup(EXM_ALL);
    */
    //   KLC - this is done in uiInit() [in UI:EVENT.C]   kb_startup(NULL);
    //   kb_set_state(0x54,KBA_SIGNAL);

    // Use our own buffer for LZW
    bootmark("Before LzwSetBuffer");
    LzwSetBuffer((void *)big_buffer, BIG_BUFFER_SIZE);
    bootmark("After LzwSetBuffer");

    // use it for rsd unpacking too....this might be fill'd with danger
    bootmark("Before gr_set_unpack_buf");
    gr_set_unpack_buf(big_buffer);
    bootmark("After gr_set_unpack_buf");

    // set up temporary memory stuff
    bootmark("Before temporary memory initialization");
    temp_memstack.baseptr = big_buffer + sizeof(big_buffer) - TEMP_STACK_SIZE;
    temp_memstack.sz = TEMP_STACK_SIZE;
    MemStackInit(&temp_memstack);
    TempMemInit(&temp_memstack);
    bootmark("After temporary memory initialization");

    // initialize random seeds
    bootmark("Before rnd_init");
    rnd_init();
    bootmark("After rnd_init");

    // initialize strings
    bootmark("Before init_strings");
    init_strings();
    bootmark("After init_strings");

    // KLC - not in Mac version
    // Initialize the Animation system
    //   AnimInit();

    // Initialize low-level keyboard and mouse input.  KLC - taken out of uiInit.
    bootmark("Before mouse_init");
    mouse_init(grd_cap->w, grd_cap->h);
    bootmark("After mouse_init");

    bootmark("Before kb_init");
    kb_init(NULL);
    bootmark("After kb_init");

    // Initialize map
    DEBUG("- Map Startup");
    bootmark("Before map_init");
    map_init();
    bootmark("After map_init");

    DEBUG("- Physics Startup");
    bootmark("Before physics_init");
    physics_init();
    bootmark("After physics_init");

    // KLC - done in InitMac.c.
    // atexit(free_all);

    DEBUG("- Load Resources");
    bootmark("Before init_load_resources");
    init_load_resources();
    bootmark("After init_load_resources");

    DEBUG("- 3d Objects Startup");
    bootmark("Before init_3d_objects");
    init_3d_objects();
    bootmark("After init_3d_objects");

    DEBUG("- Popups Startup");
    bootmark("Before init_popups");
    init_popups();
    bootmark("After init_popups");

    DEBUG("- Gamesys Startup");
    bootmark("Before init_gamesys");
    init_gamesys();
    bootmark("After init_gamesys");

    // Start up the 3d...
    DEBUG("- Renderer Startup");
    bootmark("Before fr_startup");
    fr_startup();
    bootmark("After fr_startup");

    bootmark("Before game_fr_startup");
    game_fr_startup();
    bootmark("After game_fr_startup");

    // initialize renderer
    DEBUG("- SDL Startup");
    bootmark("Before InitSDL");
    InitSDL();
    bootmark("After InitSDL");

    // Initialize the main game screen
    DEBUG("- Main game screen Startup");
    bootmark("Before region_begin_sequence");
    region_begin_sequence();
    bootmark("After region_begin_sequence");

    /*
     * These calls are still present in this file even when the project is
     * configured with ENABLE_SOUND=OFF. The build may turn them into stubs,
     * but the individual markers will show whether one fails to return.
     */
    DEBUG("- Sound startup");
    bootmark("Before snd_startup");
    snd_startup();
    bootmark("After snd_startup");

    bootmark("Before snd_start_digital");
    snd_start_digital();
    bootmark("After snd_start_digital");

    bootmark("Before music_init");
    music_init();
    bootmark("After music_init");

    bootmark("Before digifx_init");
    digifx_init();
    bootmark("After digifx_init");

    // Initialize the palette effects (for fades and color cycling)
    DEBUG("- PAL startup");
    bootmark("Before palfx_init");
    palfx_init();
    bootmark("After palfx_init");

    // Initialize animation callbacks
    {
        extern void init_animlist();

        bootmark("Before init_animlist");
        init_animlist();
        bootmark("After init_animlist");
    }

    /*
     * The original startup movie is already disabled in this source path.
     * No movie function is called here.
     */
    {
        // FSSpec fSpec;
        // FSMakeFSSpec(gDataVref, gDataDirID, "Origin", &fSpec);
        // PlayStartupMovie(&fSpec, 0, 0);
    }

    DEBUG("- Screen init");
    bootmark("Before screen_init");
    screen_init();
    bootmark("After screen_init");

    bootmark("Before fullscreen_init");
    fullscreen_init();
    bootmark("After fullscreen_init");

    bootmark("Before amap_init");
    amap_init();
    bootmark("After amap_init");

    bootmark("Before init_side_icon_popups");
    init_side_icon_popups(); // KLC - new call.
    bootmark("After init_side_icon_popups");

    DEBUG("- Input init");
    bootmark("Before init_input");
    init_input(); // KLC - moved here, after uiInit (in screen_init)
    bootmark("After init_input");

    bootmark("Before uiHideMouse");
    uiHideMouse(NULL); // KLC - added to hide mouse cursor
    bootmark("After uiHideMouse");

    DEBUG("- VR init");
    bootmark("Before view360_init");
    view360_init();
    bootmark("After view360_init");

    // KLC - no longer needed   olh_init();

    /*
     * The splash image draw and splash wait are commented out below.
     * uiFlush itself is still active, so it remains instrumented.
     */
    DEBUG("- Make splash");
    bootmark("Before first uiFlush");
    uiFlush();
    bootmark("After first uiFlush");

    // DrawSplashScreen(REF_IMG_bmOriginSplash, TRUE);
    // SDLDraw();

    // Set the wait time for our screen.
    // This value is calculated but the corresponding pause_for_input call is
    // commented out later, so this should not itself delay startup.
    bootmark("Before first TickCount");
    pause_time = TickCount();
    bootmark("After first TickCount");

    if (!speed_splash)
        pause_time += LG_DISPLAY_TIME;
    else
        pause_time += MIN_WAIT_TIME;

    DEBUG("- Start vitals");
    bootmark("Before status_vitals_start");
    status_vitals_start();
    bootmark("After status_vitals_start");

    bootmark("Before loved_textures initialization");
    for (i = 0; i < NUM_LOADED_TEXTURES; i++)
        loved_textures[i] = i;
    bootmark("After loved_textures initialization");

    DEBUG("- Gamerenderer startup");
    bootmark("Before gamerend_init");
    gamerend_init();
    bootmark("After gamerend_init");

    DEBUG("- Cameras startup");
    bootmark("Before init_hack_cameras");
    init_hack_cameras();
    bootmark("After init_hack_cameras");

    DEBUG("- End Sequence");
    bootmark("Before region_end_sequence");
    region_end_sequence(FALSE);
    bootmark("After region_end_sequence");

    DEBUG("- Lighting startup");
    bootmark("Before Init_Lighting");
    Init_Lighting();
    bootmark("After Init_Lighting");

    // set default difficulty levels for player
    bootmark("Before default difficulty initialization");
    for (i = 0; i < 4; i++)
        player_struct.difficulty[i] = 2;
    bootmark("After default difficulty initialization");

    // KLC - no config stuff for Mac version
    // if (!config_get_value(CFG_ARCHIVE_VAR, CONFIG_STRING_TYPE, &real_archive_fn, &dummy_count))
    //     BlockMove(ARCHIVE_FNAME, real_archive_fn, 20);

    // KLC init_kb();
    // KLC DbgInstallGetch(KeyGetch);

    // Start out game with high peril, to sound cool...
    mlimbs_peril = 95;
    bootmark("Set mlimbs_peril");

    // LG splash screen wait is already disabled.
    // pause_for_input(pause_time);
    // speed_splash = TRUE;

    bootmark("Before init_pal_fx");
    init_pal_fx();
    bootmark("After init_pal_fx");

    // Put up title screen
    bootmark("Before second uiFlush");
    uiFlush();
    bootmark("After second uiFlush");

    // Preload and lock resources that are used often in the game.
    bootmark("Before PreloadGameResources");
    PreloadGameResources();
    bootmark("After PreloadGameResources");

    // Draw something to avoid startup flash
    bootmark("Before gr_clear");
    gr_clear(0x00);
    bootmark("After gr_clear");

    bootmark("Before SDLDraw");
    SDLDraw();
    bootmark("After SDLDraw");

    // set the wait time for system shock title screen
    bootmark("Before second TickCount");
    pause_time = TickCount();
    bootmark("After second TickCount");

    if (!speed_splash)
        pause_time += TITLE_DISPLAY_TIME;
    else
        pause_time += MIN_WAIT_TIME;

    if ((_current_loop != SETUP_LOOP) && (_current_loop != CUTSCENE_LOOP)) {
        // for now object_data_load();

        // gr_clear(0xFF);
        // gr_set_pal(0, 256, ppall);
    }

    // perhaps shouldnt do this if we are going to go into editor...
    // fade down for last time
    if (_current_loop != EDIT_LOOP) {
        // pause_for_input(TickCount() + 10);
        // if (pal_fx_on)
        //     palfx_fade_down();
    }

    bootmark("Before final uiFlush");
    uiFlush();
    bootmark("After final uiFlush");

    init_done = TRUE;
    bootmark("init_all complete: init_done is TRUE");
}

/*
//-----------------------------------------------------------
//  Draw a splash screen in its associated color table.
//-----------------------------------------------------------
void DrawSplashScreen(short id, Boolean fadeIn) {
    byte pal_id;
    uchar savep[768];
    grs_bitmap bits;
    // CTabHandle		ctab;
    extern void finish_pal_effect(byte id);
    extern byte palfx_start_fade_up(uchar * new_pal);

    // gr_clear(0xFF);

    // First, clear the screen and load in the color table for this picture.
    // gr_clear(0xFF);
    ctab = GetCTable(id);														// Get the pict's
CLUT if (ctab)
    {
            BlockMove((**(ctab)).ctTable, (**(gMainColorHand)).ctTable, 256 * sizeof(ColorSpec));
            SetEntries(0, 255, (**(gMainColorHand)).ctTable);
            ResetCTSeed();
            DisposCTable(ctab);

#ifdef DO_FADES
            if (fadeIn)																	// Get it in a form for
palette fade
            {
                    mac_get_pal(0, 256, savep);
                    gr_set_pal(0, 256, savep);
            }
#endif
            LoadPictShockBitmap(&gMainOffScreen, id);

#ifdef DO_FADES
            if (fadeIn)
                    pal_id = palfx_start_fade_up(savep);
#endif
            gr_init_bm(&bits, (uchar *)gMainOffScreen.Address, BMT_FLAT8, 0, 640, 480);
            gr_bitmap(&bits, 0, 0);

#ifdef DO_FADES
            if (fadeIn)
                    finish_pal_effect(pal_id);
#endif
    }
}
*/

void PreloadGameResources(void) {
    // Images
    ResLock(RES_gamescrGfx);

    // Fonts
    ResLock(RES_tinyTechFont);
    ResLock(RES_doubleTinyTechFont);
    ResLock(RES_citadelFont);
    ResLock(RES_mediumLEDFont);

    // Strings
    ResLock(RES_objlongnames);
    ResLock(RES_traps);
    ResLock(RES_words);
    ResLock(RES_texnames);
    ResLock(RES_texuse);
    ResLock(RES_inventory);
    ResLock(RES_objshortnames);
    ResLock(RES_HUDstrings);
    ResLock(RES_lognames);
    ResLock(RES_messages);
    ResLock(RES_plotware);
    ResLock(RES_screenText);
    ResLock(RES_cyberspaceText);
    ResLock(RES_accessCards);
    ResLock(RES_miscellaneous);
    ResLock(RES_games);
}

void object_data_flush(void) {
    if (!objdata_loaded)
        return;

    free_dynamic_memory(DYNMEM_ALL);
    objdata_loaded = FALSE;
    obj_shutdown();
}

errtype object_data_load(void) {
    LGRect bounds;
    extern cams objmode_cam;

    //	char buf[256];
    //   MemStat  data;
    //	extern Datapath savegame_dpath;

    if (objdata_loaded)
        return (ERR_NOEFFECT);

    //   if(MemStats(&data))
    //  {
    //      Warning(("Heap is bad before starting object_data_load\n"));
    //      critical_error(CRITERR_MEM|7);
    //   }
    //   mprintf("Hey we have %d memory avail before object data load\n", data.free.sizeTot);

    // KLC - Mac cursor showing at this time   begin_wait();

    // Initialize DOS (Doofy Object System)
    DEBUG("ObjsInit");
    ObjsInit();

    obj_init();

    // initialize player struct
    DEBUG("Initialize player");
    if (clear_player_data)
        init_player(&player_struct);
    clear_player_data = TRUE;

    // Start up some subsystems
    DEBUG("init mfd");
    init_newmfd();

    /*
    //   strcpy(buf,"DATA\\");
       strcpy(buf,"");
       // NOTE: is there any other loop we start in which doesnt overwrite the map
       // if not
    */
    bounds.ul.x = bounds.ul.y = 0;
    bounds.lr.x = global_fullmap->x_size;
    bounds.lr.y = global_fullmap->y_size;

    DEBUG("process tilemap");
    rendedit_process_tilemap(global_fullmap, &bounds, TRUE);

    // Make the objmode camera....
    DEBUG("create camera");
    fr_camera_create(&objmode_cam, CAMTYPE_OBJ, player_struct.rep, NULL, NULL);

    DEBUG("load_dynamic_memory");
    objdata_loaded = TRUE;
    load_dynamic_memory(DYNMEM_ALL);

    // KLC   end_wait();
    return (OK);
}

#ifdef DUMMY ///Â¥

errtype init_kb() {
    // Keyboard frobbing
    if (config_get_raw(CHAINING_VAR, NULL, 0))
        kb_set_flags(kb_get_flags() | KBF_CHAIN);
    kb_set_state(0x16, KBA_REPEAT);
    kb_set_state(0x17, KBA_REPEAT);
    kb_set_state(0x18, KBA_REPEAT);
    kb_set_state(0x1A, KBA_REPEAT);
    kb_set_state(0x1B, KBA_REPEAT);
    kb_set_state(0x24, KBA_REPEAT);
    kb_set_state(0x25, KBA_REPEAT);
    kb_set_state(0x26, KBA_REPEAT);
    kb_set_state(0x09, KBA_REPEAT);
    kb_set_state(0x33, KBA_REPEAT);
    kb_set_state(0x32, KBA_REPEAT);
    kb_set_state(0x34, KBA_REPEAT);
    return (OK);
}

#endif // Â¥ DUMMY

errtype load_da_palette(void) {
    int pal_file;

    bootmark("Palette: before opening gamepal.res");
    pal_file = ResOpenFile("res/data/gamepal.res");
    if (pal_file < 0) {
        bootmark("ERROR: failed to open gamepal.res");
        critical_error(CRITERR_RES | 4);
    }
    bootmark("Palette: after opening gamepal.res");

    bootmark("Palette: before ResExtract game palette");
    ResExtract(RES_gamePalette, FORMAT_RAW, ppall);
    bootmark("Palette: after ResExtract game palette");
    bootmark("Palette: before ResCloseFile(gamepal.res)");
    ResCloseFile(pal_file);
    bootmark("Palette: after ResCloseFile(gamepal.res)");

    bootmark("Palette: before gr_set_pal");
    gr_set_pal(0, 256, ppall);
    bootmark("Palette: after gr_set_pal");

    return (OK);
}

errtype init_pal_fx() {
    int i;
    FILE *ipalHdl;

    bootmark("init_pal_fx: entered");
    i = 1;

    // gr_clear(0xFF);

    // Initialize the palette
    bootmark("init_pal_fx: before load_da_palette");
    load_da_palette();
    bootmark("init_pal_fx: after load_da_palette");

    // if we arent doing tlucs from a file
    bootmark("init_pal_fx: before gr_alloc_tluc8_spoly_table");
    gr_alloc_tluc8_spoly_table(16);
    bootmark("init_pal_fx: after gr_alloc_tluc8_spoly_table");

    // alloc ipal after the above - since we free ipal earlier
    // prevents fragmenting a bit
    bootmark("init_pal_fx: before shock_alloc_ipal");
    shock_alloc_ipal();
    bootmark("init_pal_fx: after shock_alloc_ipal");
    // ipalHdl = shock_alloc_ipal();

    for (i = 0; i < 16; i++)
        gr_init_tluc8_spoly_table(i, fix_make(0, 0xe000), fix_make(0, 0x8000), gr_bind_rgb(255, 64, 64),
                                  gr_bind_rgb(127 + (i << 3), 127 + (i << 3), 127 + (i << 3)));

#ifdef OLD_TLUCS
    gr_make_tluc8_table(255, fix_make(0, 0x8000), fix_make(0, 0x8000), gr_bind_rgb(255, 0, 0));
    gr_make_tluc8_table(254, fix_make(0, 0x8000), fix_make(0, 0x8000), gr_bind_rgb(0, 255, 0));
    gr_make_tluc8_table(253, fix_make(0, 0x8000), fix_make(0, 0x8000), gr_bind_rgb(0, 0, 255));
    gr_make_tluc8_table(252, fix_make(0, 0x8000), fix_make(0, 0x8000), gr_bind_rgb(80, 80, 80));
    gr_make_tluc8_table(251, fix_make(0, 0x8000), fix_make(0, 0x8000), gr_bind_rgb(255, 255, 255));
    gr_make_tluc8_table(250, fix_make(0, 0x8000), fix_make(0, 0x8000), gr_bind_rgb(0, 0, 0));
#else

#define CIT_FOG_OPAC fix_make(0, 0x3000)
#define CIT_FOG_PURE fix_make(0, 0x6000)

#define CIT_FORCE_OPAC fix_make(0, 0x5000)
#define CIT_FORCE_PURE fix_make(0, 0x8000)

    gr_make_tluc8_table(249, CIT_FOG_OPAC, CIT_FOG_PURE, gr_bind_rgb(255, 0, 0));
    gr_make_tluc8_table(250, CIT_FOG_OPAC, CIT_FOG_PURE, gr_bind_rgb(0, 255, 0));
    gr_make_tluc8_table(251, CIT_FOG_OPAC, CIT_FOG_PURE, gr_bind_rgb(0, 0, 255));
    gr_make_tluc8_table(248, CIT_FOG_OPAC, CIT_FOG_PURE, gr_bind_rgb(170, 170, 170));
    gr_make_tluc8_table(252, CIT_FOG_OPAC, CIT_FOG_PURE, gr_bind_rgb(240, 240, 240));
    gr_make_tluc8_table(247, CIT_FOG_OPAC, CIT_FOG_PURE, gr_bind_rgb(120, 120, 120));

    gr_make_tluc8_table(255, CIT_FORCE_OPAC, CIT_FORCE_PURE, gr_bind_rgb(255, 0, 0));
    gr_make_tluc8_table(254, CIT_FORCE_OPAC, CIT_FORCE_PURE, gr_bind_rgb(0, 255, 0));
    gr_make_tluc8_table(253, CIT_FORCE_OPAC, CIT_FORCE_PURE, gr_bind_rgb(0, 0, 255));
#endif

    {
        extern uchar _g3d_enable_blend;
        uchar tmppal_lower[32 * 3];
        extern uchar ppall[]; // pointer to main shadow palette

        _g3d_enable_blend = (start_mem >= BLEND_THRESHOLD);
        if (_g3d_enable_blend) {
            LG_memcpy(tmppal_lower, ppall, 32 * 3);
            LG_memset(ppall, 0, 32 * 3);
            gr_set_pal(0, 256, ppall);

            gr_init_blend(1); // we want 2 tables, really, basically, and all

            LG_memcpy(ppall, tmppal_lower, 32 * 3);
            gr_set_pal(0, 256, ppall);
        }
    }

    // fclose(ipalHdl); // reclaim the memory, fight the power
    grd_ipal = NULL; // hack hack hack

    bootmark("init_pal_fx: complete");

    //  Spew(DSRC_EDITOR_Screen, ("Loaded the palette...\n"));
    return (OK);
}

void shock_alloc_ipal() {

    // CC: Make sure we always allocate an ipal first
    bootmark("IPAL: before gr_alloc_ipal");
    gr_alloc_ipal();
    bootmark("IPAL: after gr_alloc_ipal");

    bootmark("IPAL: before opening ipal.dat");
    FILE *temp = fopen_caseless("res/data/ipal.dat", "rb");
    if (temp == NULL) {
        bootmark("ERROR: failed to open ipal.dat");
        ERROR("Failed to open ipal.dat");
        return;
    }
    bootmark("IPAL: after opening ipal.dat");

    bootmark("IPAL: before fread");
    fread(grd_ipal, 1, 32768, temp);
    bootmark("IPAL: after fread");
    return;
    // return(temp);
}

errtype init_gamesys() {
    // Load data for weapons, drugs, wares
    drugs_init();
    init_all_side_icons();
    // KLC wares_init();						doesn't do anything.  leave it out.
    game_sched_init();

    return (OK);
}

errtype free_gamesys(void) {
    game_sched_free();

    return (OK);
}

    // Okay, this should all move to somewhere more real, but I really
    // can't put it in the right place until the new 3d regime comes into
    // being

#define MAX_CUSTOMS 30

errtype init_3d_objects() {
    vx_init(16);
    return (OK);
}

errtype obj_3d_shutdown() {
    vx_close();
    return (OK);
}

errtype init_load_resources() {
    /*
     * Resource filenames remain unchanged. These markers identify the exact
     * required RES file being opened if startup stops inside this function.
     */

    // Open the screen resource stuff
    bootmark("Resource: before gamescr.res");
    if (ResOpenFile("res/data/gamescr.res") < 0) {
        bootmark("ERROR: failed to open gamescr.res");
        critical_error(CRITERR_RES | 1);
    }
    bootmark("Resource: after gamescr.res");

    // Open the appropriate mfd art file
    bootmark("Resource: before mfdart.res");
    if ((mfdart_res_file = ResOpenFile("res/data/mfdart.res")) < 0) {
        bootmark("ERROR: failed to open mfdart.res");
        critical_error(CRITERR_RES | 2);
    }
    bootmark("Resource: after mfdart.res");

    // Open the 3d objects
    bootmark("Resource: before obj3d.res");
    if (ResOpenFile("res/data/obj3d.res") < 0) {
        bootmark("ERROR: failed to open obj3d.res");
        critical_error(CRITERR_RES | 9);
    }
    bootmark("Resource: after obj3d.res");

    // Open the Citadel materials file
    bootmark("Resource: before citmat.res");
    if (ResOpenFile("res/data/citmat.res") < 0) {
        bootmark("ERROR: failed to open citmat.res");
        critical_error(CRITERR_RES | 9);
    }
    bootmark("Resource: after citmat.res");

    // Open the Digital sound FX file
    bootmark("Resource: before digifx.res");
    if (ResOpenFile("res/data/digifx.res") < 0) {
        bootmark("ERROR: failed to open digifx.res");
        critical_error(CRITERR_RES | 9);
    }
    bootmark("Resource: after digifx.res");

    // Go load the additional mod files
    bootmark("Resource: before LoadModFiles");
    LoadModFiles();
    bootmark("Resource: after LoadModFiles");

    return (OK);
}

#ifdef DUMMY // later

errtype init_debug() {
    errtype retval = OK;
    return (retval);
}

errtype init_editor_gadgets() { return (OK); }

void free_all(void) {
    extern void shutdown_config(void);
    extern uchar cit_success;
    extern void map_free(void);
    extern void music_free(void);
    extern void free_dpaths(void);
    extern view360_shutdown(void);

    _MARK_("free_all");

    Spew(DSRC_TESTING_Test6, ("shutdown - 1\n"));
    tm_close();
    tm_remove_process(global_timer_id);
    Spew(DSRC_TESTING_Test6, ("shutdown - 2\n"));
    game_fr_shutdown();
    cutscene_free();
    map_free();
    music_free();
    Spew(DSRC_TESTING_Test6, ("shutdown - 3\n"));
    player_shutdown();
    Spew(DSRC_TESTING_Test6, ("shutdown - 4\n"));
    if (cit_success)
        free_dynamic_memory(DYNMEM_ALL);
    Spew(DSRC_TESTING_Test6, ("shutdown - 5\n"));
    mlimbs_shutdown(); // should shutdown music here too...?

    snd_shutdown();
    Spew(DSRC_TESTING_Test6, ("shutdown - 6\n"));
    obj_3d_shutdown();
    Spew(DSRC_TESTING_Test6, ("shutdown - 7\n"));
    object_data_flush();
    Spew(DSRC_TESTING_Test6, ("shutdown - 8\n"));
    fr_shutdown();
    Spew(DSRC_TESTING_Test6, ("shutdown - 9\n"));
    screen_shutdown();
    view360_shutdown();
    status_vitals_end();
    Spew(DSRC_TESTING_Test6, ("shutdown - 10\n"));
    shutdown_input();
    Spew(DSRC_TESTING_Test6, ("shutdown - 11\n"));
    palette_shutdown();
    //   free_dpaths();
    Spew(DSRC_TESTING_Test6, ("shutdown - 12\n"));
    shutdown_config();
    Spew(DSRC_TESTING_Test6, ("shutdown - 13\n"));

    Spew(DSRC_TESTING_Test6, ("shutdown - final\n"));

    _MARK_("free_all done");
}

#endif // DUMMY

// when you need those arms around you, you wont find my arms around you
// im going im going im going im gone
void byebyemessage(void) {
    extern uchar cit_success;
    if (cit_success)
#ifdef DEMO
        printf("Thanks for playing the System Shock CD Demo %s.\n", SYSTEM_SHOCK_VERSION);
#else
        printf("Thanks for playing System Shock %s.\n", SHOCKOLATE_VERSION);
#endif
    else
        printf("Our system has been shocked!!!\b But remember to Salt The Fries\n");
}
