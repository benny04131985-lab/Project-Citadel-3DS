PROJECT CITADEL 3D — S2 TRUE WORLD PATCH
=========================================

Starting point:
  Known-good S1 tree at C:/Projects/Citadel_3D_DEV/Source/shockolate

What S2 does:
  - Renders the ordinary station world twice from parallel left/right cameras.
  - Uses the physical 3D slider for activation and a squared strength curve.
  - Keeps HUD, weapon, cursor, text, borders, screen effects, menus and wrappers flat.
  - Sends the right composite through a second RGB565 Citro3D texture.
  - Keeps slider-zero and unavailable-capture frames on the known-good S1 path.
  - Intentionally leaves cyberspace flat in S2.

Files replaced by installer:
  src/GameSrc/render.c
  src/GameSrc/frmain.c
  src/GameSrc/frsetup.c
  src/MacSrc/Shock.c

Explicitly not changed:
  CMakeLists.txt, setup.c, mainloop.c, wrapper.c, gamewrap.c, SDLSound.c,
  HOME/APT logic, audio, input, save/load, layout policy or SD paths.

Install:
  1. Extract this package into the shockolate project root.
  2. Run: python install_Citadel_3D_S2.py
  3. Build: cmake --build build --target project_citadel_3dsx --clean-first -j"$(nproc)"

The installer requires exact hashes from the S1 bundle supplied for this patch.
It creates protected pre/post snapshots under Citadel_3D_DEV/_PROTECTED_BASELINES.
