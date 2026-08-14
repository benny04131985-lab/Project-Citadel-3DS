PROJECT CITADEL 3D — S3 SHIP POLISH
====================================

STARTING POINT
--------------
Successful S2.1:
  * true dual-camera station-world stereo
  * centered 5-pixel slider tuning
  * frame-time-normalized C-nub freelook

S3 CHANGES
----------
Only these active files change:

  src/GameSrc/render.c
  src/MacSrc/Shock.c

Stereo depth math and C-nub tuning remain byte-for-byte unchanged.

EXCEPTIONAL VIEWS
-----------------
True stereo remains active during ordinary station gameplay.

These modes deliberately use identical-eye flat transport:

  * cyberspace
  * 360-degree view
  * full security-camera takeover

LOGGING
-------
Retained:
  * one startup stereo identity record
  * one first-presentation record
  * one first true-world-frame record
  * errors and shutdown summary

Removed:
  * recurring stereo state log every 600 frames

INSTALL
-------
Extract this folder into:

  C:\Projects\Citadel_3D_DEV\Source\shockolate

Then:

  cd /c/Projects/Citadel_3D_DEV/Source/shockolate
  python Citadel_3D_S3_SHIP_POLISH_PATCH/install_Citadel_3D_S3.py

BUILD RULE
----------
Always rebuild from an empty build directory:

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
    -j"$(nproc)" \
    2>&1 | tee S3_SHIP_BUILD.log
