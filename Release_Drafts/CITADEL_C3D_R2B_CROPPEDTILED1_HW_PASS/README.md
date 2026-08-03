# Draft Citadel 3DS Citro3D Progress Update

> **DO NOT PUBLISH YET.** This local entry preserves the August 3, 2026 R2B
> milestone while additional Citro3D performance work continues.

## Cropped direct-tiled transport is hardware verified

`CITADEL-C3D-R2B-CROPPEDTILED1` stops generating the unused portions of the
software framebuffer texture. The 3DS now prepares only the top-screen image
regions and the composed lower-screen atlas required for the active layout.

Hardware validation recorded:

- Legacy-left validation: **PASS**
- Split-left validation: **PASS**
- Split-right validation: **PASS**
- Legacy-right validation: **pending; not exercised in this session**
- Pixel mismatches: **0**
- Cropped transport fallbacks: **0**
- Upload failures: **0**
- Draw failures: **0**
- Clean shutdown: **YES**

Compared with R2A, texture preparation changed from:

- Mono: **14.252 ms → 7.052 ms** (50.5% lower)
- Stereo: **28.212 ms → 13.288 ms** (52.9% lower)

Across the full R1-to-R2B progression, measured complete-frame rates changed
from approximately:

- Mono: **21.9 FPS → 29.1 FPS**
- Stereo: **10.6 FPS → 17.3 FPS**

That places mono gameplay just below 30 FPS in this hardware session and makes
stereo roughly 62.8% faster than
the original profiled transport build. Complete-frame results vary with scene
activity, while the isolated transport reductions are directly measured.

This remains an experimental Citro3D branch rather than a native world renderer.
The remaining stereo ceiling is now dominated by the CPU software-rendering
work performed before presentation.
