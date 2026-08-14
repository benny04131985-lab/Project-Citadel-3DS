# Project Citadel 3DS

A native Nintendo 3DS port of **System Shock (1994)** based on Shockolate.

## v2.0.0 — shipped

The v2 renderer uses native Citro3D world rendering plus the AvP-style
single-stream stereo architecture: one engine scene traversal per stereo
frame, the same native scene sent to both physical eyes, a right-eye
reciprocal-depth warp for real station-world depth, and a flat zero-parallax
HUD/interface.

Final representative New Nintendo 3DS qualification:
- **30.832 FPS mono** over 3,837 measured frames;
- **23.836 FPS true stereo** over 3,182 measured frames;
- 512 KiB command buffer, **30.588%** peak usage;
- zero capture overflow, draw-budget, upload, presentation, or GPU failures;
- clean shutdown.

Lighter stereo workloads during development reached roughly 28–32 FPS.

## Original game data required

Copyrighted System Shock game data is **not included**. Provide legally obtained
game data in `sdmc:/3ds/SystemShock3D/`. See `INSTALLING.md`.

## Project status

Renderer development is frozen at v2.0.0. Future work is limited to focused
hotfixes for reproducible user-facing issues.

System Shock and related names/assets belong to their respective owners.
Project Citadel 3DS is an independent fan preservation/porting project.
