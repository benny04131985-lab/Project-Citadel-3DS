# Draft Citadel 3DS Citro3D Progress Update

> **DO NOT PUBLISH YET.** This local entry preserves the August 3, 2026 R2A
> milestone while additional performance work continues.

## Direct-tiled framebuffer transport is hardware verified

The experimental Citro3D branch has reached its first substantial measured
performance gain. `CITADEL-C3D-R2A-DIRECTTILED1` replaces the previous
linear-RGB565-plus-Morton-swizzle pipeline with a fused pass that converts the
8-bit software framebuffer directly into the final tiled Citro3D texture.

Hardware validation completed with:

- **0 visual-data mismatches** during byte-for-byte validation
- **0 fallback transport passes**
- **0 upload failures**
- **0 draw failures**
- **clean shutdown**

Measured texture-transport cost changed from:

- Mono: **22.418 ms → 14.252 ms** (36.4% lower)
- Stereo: **45.008 ms → 28.212 ms** (37.3% lower)

During these hardware sessions, approximate complete-frame rates changed from:

- Mono: **21.9 FPS → 24.3 FPS** (11.0% higher)
- Stereo: **10.6 FPS → 13.9 FPS** (31.2% higher)

The isolated transport figures are directly comparable. Complete-frame rates
vary somewhat with gameplay activity, but the stereo improvement was also
clearly noticeable during hardware testing.

This is not yet a fully native world renderer: System Shock still rasterizes
its world in software. The current branch now has a verified native Citro3D
presenter and a substantially faster framebuffer transport layer, giving us a
stronger base for the next optimization pass.
