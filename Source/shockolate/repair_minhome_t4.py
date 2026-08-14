#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import sys

SHOCK = Path("src/MacSrc/Shock.c")
MAIN_ACTIVE = Path("src/GameSrc/mainloop.c")
MAIN_BASE = Path("src/GameSrc/mainloop_BEFORE_HOME_T4.c")

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = Path(f"BACKUP_BEFORE_MINHOME_T4_{stamp}")


def fail(message):
    raise SystemExit(f"ERROR: {message}")


def once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly 1 anchor, found {count}")
    return text.replace(old, new, 1)


for path in (SHOCK, MAIN_ACTIVE, MAIN_BASE):
    if not path.is_file():
        fail(f"Missing required file: {path}")

base = MAIN_BASE.read_text(encoding="utf-8")

for forbidden in (
    "citadel_3ds_newgame_home_t7_pre_frame",
    "citadel_3ds_newgame_home_t7_post_frame",
    "NEWGAME_HOME_T7",
):
    if forbidden in base:
        fail(
            f"{MAIN_BASE} contains T7 code ({forbidden}); "
            "refusing to use it as the clean baseline"
        )

shock = SHOCK.read_text(encoding="utf-8")

# Refuse to patch a T7/T7P Shock file accidentally.
for forbidden in (
    "NEWGAME_HOME_T7",
    "citadel_3ds_draw_t7",
    "GPU T7P MASK",
):
    if forbidden in shock:
        fail(
            f"{SHOCK} contains T7/T7P code ({forbidden}). "
            "Restore the recovered V16.1 Shock.c first."
        )

backup_dir.mkdir()
shutil.copy2(SHOCK, backup_dir / "Shock.c")
shutil.copy2(MAIN_ACTIVE, backup_dir / "mainloop.c")
shutil.copy2(MAIN_BASE, backup_dir / "mainloop_BEFORE_HOME_T4.c")

print(f"Backup directory: {backup_dir}")

# ----------------------------------------------------------------------
# Patch Shock.c only when the complete T4 support is not already present.
# ----------------------------------------------------------------------

shock_required = (
    "volatile bool citadel_3ds_suspend_active = false;",
    "volatile bool citadel_3ds_suspend_seen = false;",
    "volatile bool citadel_3ds_restore_seen = false;",
    "void citadel_3ds_prepare_gpu_for_apt(void)",
    "bool citadel_3ds_apt_should_close(void)",
    "void citadel_3ds_home_gate_idle(void)",
)

present = [token in shock for token in shock_required]

if all(present):
    print("Shock.c already contains complete T4 support; leaving it unchanged.")

elif any(present):
    fail("Shock.c contains a partial T4 patch; restore the plain V16.1 Shock.c.")

else:
    shock = once(
        shock,
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"\n',
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"\n'
        '#warning "PROJECT CITADEL HOME FRAME-GATE TEST 4: '
        'APT-first freeze wrapper is ACTIVE"\n',
        "Shock compile marker",
    )

    shock = once(
        shock,
        "static aptHookCookie citadel_3ds_audio_apt_cookie;\n"
        "static bool citadel_3ds_audio_apt_hook_registered = false;\n",
        "static aptHookCookie citadel_3ds_audio_apt_cookie;\n"
        "static bool citadel_3ds_audio_apt_hook_registered = false;\n\n"
        "/* PROJECT CITADEL HOME FRAME-GATE TEST 4 */\n"
        "volatile bool citadel_3ds_suspend_active = false;\n"
        "volatile bool citadel_3ds_suspend_seen = false;\n"
        "volatile bool citadel_3ds_restore_seen = false;\n",
        "Shock T4 lifecycle globals",
    )

    shock = once(
        shock,
        "static void citadel_3ds_audio_unregister_apt_hook(void);\n",
        "static void citadel_3ds_audio_unregister_apt_hook(void);\n"
        "void citadel_3ds_prepare_gpu_for_apt(void);\n"
        "bool citadel_3ds_apt_should_close(void);\n"
        "void citadel_3ds_home_gate_idle(void);\n",
        "Shock T4 prototypes",
    )

    replacements = (
        (
            "        case APTHOOK_ONSUSPEND:\n"
            '            v5_log("APT AUDIO HOOK event=ONSUSPEND begin");',
            "        case APTHOOK_ONSUSPEND:\n"
            "            citadel_3ds_suspend_active = true;\n"
            "            citadel_3ds_suspend_seen = true;\n"
            '            v5_log("APT AUDIO HOOK event=ONSUSPEND begin");',
            "Shock ONSUSPEND",
        ),
        (
            "        case APTHOOK_ONSLEEP:\n"
            '            v5_log("APT AUDIO HOOK event=ONSLEEP begin");',
            "        case APTHOOK_ONSLEEP:\n"
            "            citadel_3ds_suspend_active = true;\n"
            "            citadel_3ds_suspend_seen = true;\n"
            '            v5_log("APT AUDIO HOOK event=ONSLEEP begin");',
            "Shock ONSLEEP",
        ),
        (
            "        case APTHOOK_ONRESTORE:\n"
            '            v5_log("APT AUDIO HOOK event=ONRESTORE should_close=%d",',
            "        case APTHOOK_ONRESTORE:\n"
            "            citadel_3ds_restore_seen = true;\n"
            "            citadel_3ds_suspend_active = false;\n"
            '            v5_log("APT AUDIO HOOK event=ONRESTORE should_close=%d",',
            "Shock ONRESTORE",
        ),
        (
            "        case APTHOOK_ONWAKEUP:\n"
            '            v5_log("APT AUDIO HOOK event=ONWAKEUP should_close=%d",',
            "        case APTHOOK_ONWAKEUP:\n"
            "            citadel_3ds_restore_seen = true;\n"
            "            citadel_3ds_suspend_active = false;\n"
            '            v5_log("APT AUDIO HOOK event=ONWAKEUP should_close=%d",',
            "Shock ONWAKEUP",
        ),
        (
            "        case APTHOOK_ONEXIT:\n"
            '            v5_log("APT AUDIO HOOK event=ONEXIT");',
            "        case APTHOOK_ONEXIT:\n"
            "            citadel_3ds_suspend_active = true;\n"
            "            citadel_3ds_suspend_seen = true;\n"
            '            v5_log("APT AUDIO HOOK event=ONEXIT");',
            "Shock ONEXIT",
        ),
    )

    for old, new, label in replacements:
        shock = once(shock, old, new, label)

    helper_anchor = "static void citadel_3ds_audio_register_apt_hook(void)\n"

    helper_code = """/*
 * Complete previously submitted Citro3D work before SDL/libctru services
 * HOME/APT at the beginning of the next Shock frame.
 */
void citadel_3ds_prepare_gpu_for_apt(void)
{
    if (citadel_gpu_c3d_initialized)
        C3D_FrameSync();
}

bool citadel_3ds_apt_should_close(void)
{
    return aptShouldClose();
}

void citadel_3ds_home_gate_idle(void)
{
    svcSleepThread(1000000LL);
}

"""

    shock = once(
        shock,
        helper_anchor,
        helper_code + helper_anchor,
        "Shock T4 helper insertion",
    )

    SHOCK.write_text(shock, encoding="utf-8", newline="\n")
    print(f"Patched: {SHOCK}")

# ----------------------------------------------------------------------
# Reconstruct mainloop.c from the clean pre-T4 file, then apply T4.
# ----------------------------------------------------------------------

main = base

main = once(
    main,
    '#warning "PROJECT CITADEL V4: unique mainloop log is ACTIVE"\n',
    '#warning "PROJECT CITADEL V4: unique mainloop log is ACTIVE"\n'
    '#if defined(__3DS__) || defined(_3DS)\n'
    '#warning "PROJECT CITADEL HOME FRAME-GATE TEST 4: '
    'APT-first freeze wrapper is ACTIVE"\n'
    '#endif\n',
    "mainloop compile marker",
)

main = once(
    main,
    "extern void MousePollProc(void);\n"
    "void mainloop(int argc, char *argv[]) {\n"
    "    int log_this_frame;\n",
    "extern void MousePollProc(void);\n"
    "void mainloop(int argc, char *argv[]) {\n"
    "#if defined(__3DS__) || defined(_3DS)\n"
    "    extern bool citadel_3ds_system_close_requested;\n"
    "    extern volatile bool citadel_3ds_suspend_active;\n"
    "    extern volatile bool citadel_3ds_suspend_seen;\n"
    "    extern volatile bool citadel_3ds_restore_seen;\n"
    "    extern void citadel_3ds_prepare_gpu_for_apt(void);\n"
    "    extern bool citadel_3ds_apt_should_close(void);\n"
    "    extern void citadel_3ds_home_gate_idle(void);\n"
    "#endif\n"
    "    int log_this_frame;\n",
    "mainloop T4 extern declarations",
)

frame_anchor = """        if (log_this_frame)
            loopmark("FRAME START");

"""

frame_gate = """        if (log_this_frame)
            loopmark("FRAME START");

#if defined(__3DS__) || defined(_3DS)
        /*
         * PROJECT CITADEL HOME FRAME-GATE TEST 4
         *
         * Complete the previous GPU frame, then service SDL/APT before
         * timers, input, simulation, cursor updates, or rendering.
         */
        if (log_this_frame)
            loopmark("Before HOME gate GPU sync");
        citadel_3ds_prepare_gpu_for_apt();
        if (log_this_frame)
            loopmark("After HOME gate GPU sync");
#endif

        if (log_this_frame)
            loopmark("Before APT-FIRST pump_events");
        pump_events();
        if (log_this_frame)
            loopmark("After APT-FIRST pump_events");

#if defined(__3DS__) || defined(_3DS)
        if (!gPlayingGame || citadel_3ds_apt_should_close()) {
            loopmark("HOME gate: system close requested");
            citadel_3ds_system_close_requested = true;
            gPlayingGame = false;
            break;
        }

        if (citadel_3ds_suspend_active) {
            loopmark("HOME gate: suspend active; complete frame frozen");
            citadel_3ds_home_gate_idle();
            continue;
        }

        if (citadel_3ds_suspend_seen || citadel_3ds_restore_seen) {
            loopmark("HOME gate: suspend/restore transition completed");
            citadel_3ds_suspend_seen = false;
            citadel_3ds_restore_seen = false;
        }
#endif

"""

main = once(
    main,
    frame_anchor,
    frame_gate,
    "mainloop frame-gate insertion",
)

old_pump_block = """        // DG: at the beginning of each frame, get all the events from SDL
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

"""

main = once(
    main,
    old_pump_block,
    "",
    "removal of original middle-of-frame SDL pump",
)

for forbidden in (
    "citadel_3ds_newgame_home_t7_pre_frame",
    "citadel_3ds_newgame_home_t7_post_frame",
    "NEWGAME_HOME_T7",
):
    if forbidden in main:
        fail(f"Generated mainloop still contains T7 token: {forbidden}")

if main.count("pump_events();") != 1:
    fail(
        "Generated mainloop must contain exactly one pump_events() call; "
        f"found {main.count('pump_events();')}"
    )

pump_position = main.find("pump_events();")
tick_position = main.find('loopmark("Before TickCount")')

if pump_position < 0 or tick_position < 0 or pump_position >= tick_position:
    fail("APT-first pump_events() is not before TickCount.")

MAIN_ACTIVE.write_text(main, encoding="utf-8", newline="\n")
print(f"Installed repaired minimum-HOME mainloop: {MAIN_ACTIVE}")

print()
print("PASS: T4 Shock/mainloop pair installed.")
print("PASS: T7 hooks absent from mainloop.")
print("PASS: pump_events occurs exactly once and before TickCount.")
print("PASS: setup.c, wrapper.c, and gamewrap.c were not changed.")
