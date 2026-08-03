# Project Citadel 3D v1.0.2 — Final Software Renderer Hotfix

## Summary

This hotfix is the final optimized software-renderer release before native
Citro3D world rendering development begins. System Shock's original software
renderer still produces the game world, while the 3DS presentation path has
been replaced and optimized through direct Citro3D textured quads, fused
indexed-to-tiled conversion, output-sized cropped textures, and alternating
ping-pong texture sets.

The release uses the exact hardware-tested R2C binary. No behavior-changing
source edits were made after the successful hardware run.

## Hardware-measured result

Measured on New Nintendo 3DS hardware across **3477** normal
frames during a **164.8-second** session:

| Mode | v1.0.1 baseline | v1.0.2 R2C | Improvement |
|---|---:|---:|---:|
| Mono | 21.808 FPS | **33.286 FPS** | **+52.6%** |
| Stereo | 11.608 FPS | **18.451 FPS** | **+59.0%** |
| Mono frame time | 45.856 ms | **30.043 ms** | **34.5% shorter** |
| Stereo frame time | 86.146 ms | **54.196 ms** | **37.1% shorter** |

The mono result averages above the 30 FPS milestone. Performance remains
scene-dependent and stereo continues to render two complete software views.

## Renderer changes

- Replaced Citro2D screen-quad submission with direct Citro3D textured draws.
- Fused palette conversion and Morton-tiled texture writes into one pass.
- Removed the intermediate full-frame RGB565 staging/swizzle path during normal use.
- Generated only the top-screen and lower-screen regions actually displayed.
- Added two complete cropped texture sets for safe ping-pong submission.
- Kept the full R2A and R2B paths as automatic safety fallbacks.
- Preserved legacy and split-screen layouts, lower-screen controls, and true stereo.

## Hardware validation

- Legacy-left: **PASS**
- Split-left: **PASS**
- Split-right: **PASS**
- Legacy-right: **PENDING** (not failed; this exact combination was not exercised)
- Pixel mismatches: **0**
- Cropped fallbacks: **0**
- Direct-tiled safety fallbacks: **0**
- Ping-pong pre-frame failures: **0**
- Texture-set draws: **set 0 = 1740, set 1 = 1741**
- Upload failures: **0**
- Draw failures: **0**
- GPU profile clean shutdown: **YES**

## Diagnostic version label

The included hardware-tested binary still reports
`1.0.1-DIAG2-FPS-SPLIT` inside `citadel_diag.log`. That string identifies the
silent diagnostic schema inherited from v1.0.1; R2C's independent renderer and
profile markers identify the v1.0.2 hotfix implementation. The binary is left
unchanged to preserve exact hardware-test identity.

## Scope

This is the final software-world-renderer optimization milestone. The next
development branch replaces world rasterization itself with native Citro3D
geometry while keeping this R2C release as the stable fallback and comparison
baseline.

No copyrighted System Shock game data is included. A legally obtained original
copy of System Shock is required.
