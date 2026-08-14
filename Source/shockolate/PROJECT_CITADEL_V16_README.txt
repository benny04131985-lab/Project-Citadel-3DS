PROJECT CITADEL 3DS — V16 RELEASE CANDIDATE
=============================================

V16 SCOPE
---------
V16 consolidates the proven non-stereoscopic port into one release-candidate
build before stereo rendering work begins.

Included:
  1. V15I SDL RGBA8 LCD-output fix.
  2. V15J 1024x512 texture with full-resolution source transport.
  3. Native 640x400 default on Nintendo 3DS.
  4. Explicit black bottom-screen scene during pause, options, save/load,
     menus, and SELECT legacy view.
  5. Physical A and R behavior swapped:
       A = toggle native freelook
       R = left mouse button / activate
  6. Hack-i-Ben pixel-art startup splash.
  7. Removal of the large V15G diagnostic texture allocations.
  8. Removal of the V15H control-asset requirement.

FILES MODIFIED
--------------
  src/MacSrc/Shock.c
  src/Libraries/INPUT/Source/sdl_events.c
  src/MacSrc/Prefs.c
  CMakeLists.txt

FILE ADDED
----------
  assets/v16/Hack-i-Ben_Splash.png

INSTALL
-------
Extract this package into a convenient folder.

Place apply_Project_Citadel_V16.py and the accompanying prepatched files
together, then run from the Shockolate project root:

  python <path-to-package>/apply_Project_Citadel_V16.py

Validation only; no changes are made.

Install:

  python <path-to-package>/apply_Project_Citadel_V16.py --install

Build:

  cmake --build build-3ds

The build invokes tex3ds v2.3.0 and creates:

  build-3ds/Hack-i-Ben_Splash.t3x

SD-CARD LAYOUT
--------------
Copy both generated files:

  build-3ds/systemshock.3dsx
  build-3ds/Hack-i-Ben_Splash.t3x

to:

  /3ds/SystemShock/

Recommended release layout:

  /3ds/SystemShock/
  ├── systemshock.3dsx
  ├── Hack-i-Ben_Splash.t3x
  ├── data/
  ├── res/
  │   └── sound/
  ├── prefs.txt
  └── keybinds.txt

NEW DEFAULT
-----------
When no prefs.txt exists on Nintendo 3DS, V16 selects video-mode index 2,
which is the proven 640x400 mode. Existing prefs files continue to take
precedence.

CONTROLS CHANGED
----------------
Previous:
  A = left click
  R = freelook toggle

V16:
  R = left click
  A = freelook toggle

No SDL2 library rebuild is required for this swap. Project Citadel reads
these two buttons directly in src/Libraries/INPUT/Source/sdl_events.c.

SPLASH
------
The Hack-i-Ben splash is generated as a 400x240 source and compiled through
tex3ds into Hack-i-Ben_Splash.t3x. It displays for approximately 2.2 seconds
on the upper screen while the lower screen remains black.

The game continues normally if the splash asset is missing, but release
packages should include it.

EXPECTED COMPILER MARKERS
-------------------------
PROJECT CITADEL V16: release candidate is ACTIVE
PROJECT CITADEL INPUT V16: A/R swap is ACTIVE

EXPECTED LOGS
-------------
GPU_C2D_V16.log
INPUT_3DS_V16.log

TEST CHECKLIST
--------------
1. Splash appears cleanly and then advances to Origin/System Shock.
2. New prefs default to 640x400.
3. R performs left-click/activation.
4. A toggles freelook during gameplay.
5. Pause and wrapper menus black the lower screen.
6. Split layout returns correctly after unpausing.
7. Music, effects, speech, saves, and touch input still work.
8. HOME/suspend behavior remains unchanged.
9. Shutdown log reports zero upload and draw failures.

WHAT TO SEND BACK
-----------------
1. GPU_C2D_V16.log
2. INPUT_3DS_V16.log
3. One short video covering splash, menu, gameplay, A/R behavior, and pause.
