# Project Citadel 3DS v2.0.0

Frozen renderer: `CITADEL-C3D-R3D7C-CMDBUF512-SHIPRC1`

- one `fr_rend()` traversal per stereo frame;
- same native scene stream drives both eyes;
- right-only reciprocal-W depth warp;
- flat shared HUD/foreground;
- no right software residual/framebuffer reconstruction/legacy compositor;
- 512 KiB Citro3D command buffer.

Final hardware run `1786136661_000000A90E3ACF6E`:
- mono 30.832 FPS;
- stereo 23.836 FPS;
- 3,060 stereo scene traversals and 3,060 physical-right engine traversals skipped;
- 516,324 right-eye depth-warp vertices;
- 30.588% peak command-buffer use (~160,368 bytes);
- lowest sampled linear free memory 22,499,840 bytes;
- zero renderer failures;
- clean shutdown.

Renderer chapter closed. Future changes are issue-specific hotfixes only.
