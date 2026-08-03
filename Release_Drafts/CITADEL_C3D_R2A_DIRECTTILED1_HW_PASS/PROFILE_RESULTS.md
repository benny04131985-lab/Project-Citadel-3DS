# CITADEL-C3D-R2A-DIRECTTILED1 — Hardware Results

Status: **PASS**  
Publication status: **LOCAL DRAFT — DO NOT PUBLISH YET**

## Validation

- Direct-tiled enabled at shutdown: **YES**
- Byte-for-byte validation: **PASS, 0 mismatches**
- Direct-tiled fallbacks: **0**
- Left-eye passes: **3254**
- Right-eye passes: **1450**
- Presented frames: **3255**
- Upload failures: **0**
- Draw failures: **0**
- Clean shutdown: **YES**

## R1 transport baseline versus R2A

| Measurement | R1 baseline | R2A DIRECTTILED1 | Change |
|---|---:|---:|---:|
| Mono texture transport | 22.418 ms | 14.252 ms | **36.4% lower** |
| Stereo texture transport | 45.008 ms | 28.212 ms | **37.3% lower** |
| Mono full frame | 45.631 ms | 41.106 ms | **9.9% shorter** |
| Stereo full frame | 94.288 ms | 71.890 ms | **23.8% shorter** |
| Approximate mono rate | 21.9 FPS | 24.3 FPS | session comparison |
| Approximate stereo rate | 10.6 FPS | 13.9 FPS | session comparison |

The isolated transport measurements are the strongest apples-to-apples result.
Full-frame rates also depend on the gameplay activity represented in each run.

## Implementation

R2A fuses indexed-color palette conversion and Morton-tiled RGB565 output into
one pass per eye. It removes the separate linear RGB565 staging pass, separate
Morton swizzle pass, unnecessary full-texture padding clear, and repeated
per-pixel scaling divisions. The old transport remains available as a safety
fallback, but this hardware run used it **zero times**.

## Remaining bottlenecks

The fused direct-tiled pass still costs approximately
**14.222 ms per mono eye** and
**14.116/14.066 ms per stereo eye**.
The next practical target is reducing the number of pixels processed before a
larger native-world-renderer conversion.
