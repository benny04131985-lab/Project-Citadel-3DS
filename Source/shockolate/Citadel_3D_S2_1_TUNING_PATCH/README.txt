PROJECT CITADEL 3D — S2.1 TUNING
=================================

STARTING POINT
--------------
The successful S2 true dual-camera world-stereo build.

SCOPE
-----
S2.1 changes only:

  src/GameSrc/frsetup.c
  src/Libraries/INPUT/Source/sdl_events.c

DEPTH
-----
S2:
  slider curve = slider squared
  maximum convergence = 3 pixels

S2.1:
  centered signed-square curve
  maximum convergence = 5 pixels

The new curve keeps zero, midpoint, and maximum exact while putting the
broadest fine-adjustment region around the physical slider's middle.

C-NUB
-----
The existing VX1 native freelook values are per-frame velocities. S2 renders
the station world twice, so demanding stereo frames can lower main-loop
frequency and make the same per-frame velocity feel slower.

S2.1 measures elapsed milliseconds between input updates and scales ONLY
native freelook while the 3D slider is active:

  16 ms -> 1.00x
  20 ms -> 1.25x
  25 ms -> 1.56x
  33 ms -> 2.06x
  clamp -> 16 to 34 ms

Slider down:
  Exact VX1 C-stick calibration remains in effect.

INSTALL
-------
Extract this folder into the Shockolate project root, then:

  cd /c/Projects/Citadel_3D_DEV/Source/shockolate
  python Citadel_3D_S2_1_TUNING_PATCH/install_Citadel_3D_S2_1.py

BUILD
-----
  cmake --build build \
    --target project_citadel_3dsx \
    -j"$(nproc)" \
    2>&1 | tee S2_1_BUILD.log

TEST
----
1. Compare C-nub freelook with slider fully down and then raised.
2. Move the slider slowly through its center.
3. Check the full top setting for comfort and edge cleanliness.
4. Revisit the opening door/hallway scene.

REPORT
------
Depth middle: too flat / controllable / still too sensitive
Maximum depth: weak / ideal / excessive
C-nub match: slower / matched / faster
Edges: clean / minor artifacts / obvious splitting
