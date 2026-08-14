PROJECT CITADEL 3DS — V16.1 LAUNCH POLISH CANDIDATE
====================================================

PURPOSE
-------
V16 passed a 30-minute Level 1 hardware play session without a reported bug,
error, or crash. V16.1 is the final comfort, lifecycle, and packaging pass
before the public mono release and stereoscopic development branch.

CHANGES
-------
1. HOME Menu close lifecycle
   - SDL_QUIT marks a true system-close request.
   - mainloop.c stops immediately after pump_events().
   - No additional game-loop or GPU frame is executed after aptMainLoop()
     requests shutdown.
   - Audio, Citro2D/Citro3D, and SDL shut down explicitly.
   - HOME "Close Software" finishes with svcExitProcess() after cleanup.

2. MFD crop correction
   - MFD source crop changes from Y=312/H=156 to Y=320/H=160.
   - Removes the moving-world strip above both MFDs.
   - Restores the previously clipped lower pixels.
   - Matching input/touch coordinate constants are updated.

3. Launch controls
   A = toggle native freelook
   R = left mouse / activate
   L = right mouse / fire
   B = leave freelook and center cursor on upper world view
   Touch = direct lower-screen interaction
   START = Escape/pause
   SELECT = legacy/full-frame view
   X/Y behavior is unchanged from the validated V16 build.

4. Stable external-data directory
   - Both 3DSX and CIA builds change working directory to:
       sdmc:/3ds/SystemShock
   - Preferences, keybinds, saves, logs, splash, data, and music therefore
     share one predictable location.

5. Homebrew metadata and CIA packaging
   - 48x48 Homebrew Menu icon.
   - HOME Menu banner.
   - Branded Project_Citadel_3DS.3dsx target.
   - Optional Project_Citadel_3DS.cia target.
   - The CIA contains no original System Shock data and no res folder.

INSTALL
-------
Extract the package. From the Shockolate project root:

  python <package>/apply_Project_Citadel_V16_1.py

This validates the expected files and mainloop patch anchor without changing
anything.

Install:

  python <package>/apply_Project_Citadel_V16_1.py --install

Build the branded 3DSX:

  cmake --build build-3ds

Build the optional CIA:

  cmake --build build-3ds --target project_citadel_cia

The CIA target requires bannertool and makerom in PATH. The branded 3DSX
target requires bannertool and 3dsxtool. A normal source build remains
available when the optional CIA tools are absent.

EXPECTED OUTPUTS
----------------
  build-3ds/Project_Citadel_3DS.3dsx
  build-3ds/Project_Citadel_3DS.cia
  build-3ds/Hack-i-Ben_Splash.t3x

SD LAYOUT
---------
  /3ds/SystemShock/
  ├── Project_Citadel_3DS.3dsx   (3DSX users)
  ├── Hack-i-Ben_Splash.t3x
  ├── data/
  ├── res/
  │   └── sound/
  ├── prefs.txt
  └── keybinds.txt

CIA users still need the same /3ds/SystemShock/data and res directories.
The installed title intentionally does not bundle copyrighted game data.

TEST CHECKLIST
--------------
1. Launch splash and main menu.
2. Close Software from the HOME Menu while sitting at the main menu.
3. Repeat Close Software during active gameplay.
4. Confirm no hard reboot is required.
5. Inspect both MFDs for a clean top edge and complete lower edge.
6. Confirm L fires/right-clicks.
7. Confirm R activates/left-clicks.
8. Move/touch the cursor to the lower screen, press B, then press A and fire.
9. Confirm pause and menus keep the lower screen black.
10. Confirm keyboard, saves, sound, music, suspend/resume, and 640x400 remain
    unchanged.
11. Send GPU_C2D_V16_1.log and INPUT_3DS_V16_1.log.

IMPORTANT
---------
The source transformations and package layout were validated here, but the
first actual devkitPro compile and hardware lifecycle test must occur on the
3DS build machine.
