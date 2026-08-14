# Citadel Citro3D Native Branch Handoff

Branch base: **CITADEL-C3D-R2C-PINGPONGTILED1**  
Frozen software baseline: **v1.0.2 Final Software Renderer Hotfix**  
Hardware-tested binary SHA-256: `331d46f0a939b7332b479db87c2167a251269bf6c4b376c5107b731ee96d5318`

## Proven baseline

- Mono: **33.286 FPS**
- Stereo: **18.451 FPS**
- Pixel mismatches: **0**
- Transport fallbacks: **0**
- GPU upload/draw failures: **0**

Do not weaken or delete the R2C path while native coverage is incomplete. It is
the fallback, comparison renderer, menu/UI presenter, and rollback point.

## First native milestone

`CITADEL-C3D-R3A-WORLDPROOF1`

Goal: render one genuine live System Shock room through native Citro3D geometry
while simulation, visibility, camera state, unsupported objects, menus, HUD, and
fallback presentation remain owned by the established engine paths.

### Recommended sequence

1. Instrument the software world renderer immediately before span/pixel rasterization.
2. Identify live opaque world polygons and their camera-space vertices.
3. Capture walls first; add floor and ceiling once the coordinate transform is proven.
4. Submit flat diagnostic colors through a dedicated native vertex buffer.
5. Use a real depth buffer and perspective projection.
6. Suppress only geometry positively confirmed as natively replayed.
7. Preserve the R2C software image for unsupported geometry and emergency fallback.
8. Prove walking, turning, looking, doors, and room transitions on hardware.
9. Only after geometry is stable, add texture/material translation and native stereo.

## Success condition

A genuine current Citadel room—rather than a test triangle or reconstructed
mock-up—tracks the player's live camera and renders walls, floor, and ceiling on
PICA200 without corrupting the existing lower-screen interface.
