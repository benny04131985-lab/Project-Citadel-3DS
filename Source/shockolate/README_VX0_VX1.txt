PROJECT CITADEL VX0 / VX1 CONTROLLED RESTART TOOLKIT
====================================================

THE RULE
--------
VX0 never changes.

Every failed experiment is abandoned. VX1.1, VX1.2, and later versions must
start again from exact VX0, with a new marker, backup, diff, and runtime log.

VX0 CONTENT
-----------
Exact V17-SHIP four-file set:
  src/MacSrc/Shock.c
  src/GameSrc/setup.c
  src/GameSrc/mainloop.c
  src/GameSrc/wrapper.c

Plus original non-T2:
  src/GameSrc/gamewrap.c

PINNED VX0 SHA-256
------------------
05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724  src/MacSrc/Shock.c
236b2517ad37b87e88e4232bca712aaf8910f51205e130f13d0069cfe2f4ba82  src/GameSrc/setup.c
8fb3331b9e3e0fe1532417237d5adb8a8820508dc5f7e4f9d389870d31e9a369  src/GameSrc/mainloop.c
d027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2  src/GameSrc/wrapper.c
c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30  src/GameSrc/gamewrap.c

WORKFLOW
--------
1. Archive the current unknown-status project.
2. Create the new working copy.
3. Copy this toolkit into the new Shockolate repository root.
4. Assemble the five exact local files without touching active source:

     python citadel_vx_control.py prepare-vx0

5. Install VX0 with automatic backup and hash verification:

     python citadel_vx_control.py install-vx0

6. Verify at any time:

     python citadel_vx_control.py verify-vx0

7. Clean configure/build VX0 and complete VX_TEST_MATRIX.txt.
8. Archive the passing VX0 source and 3DSX.
9. Only then apply VX1.0:

     python citadel_vx_control.py apply-vx1

10. Clean configure/build VX1 and complete the VX1 matrix.
11. On any VX1 failure, archive the failed iteration and restore VX0:

     python citadel_vx_control.py rollback-vx1

WHY VX1 DOES NOT ADD ANOTHER RENDERER
-------------------------------------
V16.1 already loads Hack-i-Ben_Splash.t3x and draws it across the exact
400x240 top screen through C2D_DrawImageAt inside a real Citro3D frame. It
already is a texture on a screen-sized rectangle and appears flat.

VX1.0 changes only Shock.c. After eight successful splash frames it runs:

  C3D_FrameSync
  gspWaitForVBlank
  GSPGPU_SaveVramSysArea
  GSPGPU_ImportDisplayCaptureInfo
  GSPGPU_ReleaseRight
  GSPGPU_AcquireRight(0)
  GSPGPU_RestoreVramSysArea
  gspWaitForVBlank
  one later normal splash verification frame

It does not alter New Game, save/load, setup, mainloop, wrapper, or gamewrap.

DETERMINISTIC LOG
-----------------
VX1 creates this beside the normal 3DS prefs/log files:

  VX1_STARTUP_PRIMER.log

Required success lines:

  VX1.0 PRIMER RESULTS ... complete=1
  VX1.0 POST-PRIMER SPLASH FRAME COMPLETE ...

Historically successful GSP results were all 0x00000000.

BUILD
-----
Use the existing known command:

  rm -rf build

  cmake -S . -B build \
    -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
    -DENABLE_OPENGL=OFF \
    -DENABLE_SOUND=OFF \
    -DENABLE_FLUIDSYNTH=OFF \
    -DENABLE_SDL2=ON

  cmake --build build \
    --target project_citadel_3dsx \
    -j"$(nproc)"
