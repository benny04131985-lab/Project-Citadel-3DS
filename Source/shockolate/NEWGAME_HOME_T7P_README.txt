PROJECT CITADEL NEW GAME HOME T7P — PRESENTATION POLISH

Purpose
-------
T7 proved the HOME-safe New Game normalization. T7P preserves that exact
numbered-slot Save/Load lifecycle and changes only what the player sees:

1. Shock still creates and uploads every real Save/Load wrapper frame.
2. Citro2D covers those frames with the existing branded splash plus a six-step
   activity bar.
3. Initial menus remain Legacy.
4. During GAME_LOOP, SELECT alone toggles Legacy/Dual.
5. Pause/options/save/load no longer force Legacy or change the selected layout.

T7P intentionally does not move the normalizer ahead of the tutorial prompt.
The mask starts only when the hidden Save wrapper opens, preventing the tutorial
from being hidden before the player can dismiss it.

Install from the shockolate project root
----------------------------------------
Back up current T7 files:

  cp src/MacSrc/Shock.c src/MacSrc/Shock_BEFORE_T7P.c
  cp src/GameSrc/setup.c src/GameSrc/setup_BEFORE_T7P.c
  cp src/GameSrc/mainloop.c src/GameSrc/mainloop_BEFORE_T7P.c
  cp src/GameSrc/wrapper.c src/GameSrc/wrapper_BEFORE_T7P.c

Copy complete replacements:

  cp Shock_NEWGAME_HOME_T7P.c src/MacSrc/Shock.c
  cp setup_NEWGAME_HOME_T7P.c src/GameSrc/setup.c
  cp mainloop_NEWGAME_HOME_T7P.c src/GameSrc/mainloop.c
  cp wrapper_NEWGAME_HOME_T7P.c src/GameSrc/wrapper.c

Expected SHA-256
---------------
972c3abaef2e813ef0de99001ff4c2793f17301bfc1d891ccec22e753ebe22c8  src/MacSrc/Shock.c
236b2517ad37b87e88e4232bca712aaf8910f51205e130f13d0069cfe2f4ba82  src/GameSrc/setup.c
8fb3331b9e3e0fe1532417237d5adb8a8820508dc5f7e4f9d389870d31e9a369  src/GameSrc/mainloop.c
c28fa509d83b2b382d68044a6534918feb53c017f7c9963b3aeddd5e524e5f3e  src/GameSrc/wrapper.c

Build
-----
  rm -rf build

  cmake -S . -B build \
    -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DENABLE_OPENGL=OFF \
    -DENABLE_SOUND=OFF \
    -DENABLE_FLUIDSYNTH=OFF \
    -DENABLE_SDL2=ON

  cmake --build build --target project_citadel_3dsx -j"$(nproc)"

Test
----
1. Fresh launch -> New Game.
2. Dismiss the tutorial prompt normally.
3. The branded loading mask should cover the hidden Save/Load sequence.
4. When gameplay returns, press HOME and return.
5. Open pause/options and confirm the layout no longer changes.
6. Press SELECT to toggle Legacy/Dual; verify pause preserves that choice.

Expected logs
-------------
NEWGAME_HOME_T7.log should still end with T7 COMPLETE.
GPU_C2D_V16_1.log should include:
  GPU T7P MASK begin: internal numbered Save/Load hidden
  GPU T7P MASK complete: revealing normalized gameplay

Rollback
--------
  cp src/MacSrc/Shock_BEFORE_T7P.c src/MacSrc/Shock.c
  cp src/GameSrc/setup_BEFORE_T7P.c src/GameSrc/setup.c
  cp src/GameSrc/mainloop_BEFORE_T7P.c src/GameSrc/mainloop.c
  cp src/GameSrc/wrapper_BEFORE_T7P.c src/GameSrc/wrapper.c
