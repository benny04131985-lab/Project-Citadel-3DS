# CITADEL-C3D-R2B-CROPPEDTILED1 — Hardware Results

Status: **HARDWARE PASS**  
Publication status: **LOCAL DRAFT — DO NOT PUBLISH YET**

## Validation coverage

- Legacy left: **PASS**
- Split left: **PASS**
- Legacy right: **PENDING — this exact stereo/legacy combination was not exercised**
- Split right: **PASS**
- Pixel mismatches: **0**
- Cropped-path fallbacks: **0**
- R2A safety-path fallbacks: **0**
- Upload failures: **0**
- Draw failures: **0**
- Clean shutdown: **YES**


The milestone is valid for every path exercised during the run. `legacy_right`
remains recorded as **PENDING** rather
than being silently promoted to PASS.

## Preserved hardware workload

- Presented frames: **2993**
- Mono frames: **2244**
- Stereo frames: **748**
- Top-left cropped passes: **2992**
- Top-right cropped passes: **748**
- Bottom-atlas passes: **2194**
- Cropped pixels processed: **512,217,600**

## Performance progression

| Measurement | R1 full transport | R2A direct-tiled | R2B cropped-tiled |
|---|---:|---:|---:|
| Mono texture transport | 22.418 ms | 14.252 ms | **7.052 ms** |
| Stereo texture transport | 45.008 ms | 28.212 ms | **13.288 ms** |
| Mono complete frame | 45.631 ms | 41.106 ms | **34.381 ms** |
| Stereo complete frame | 94.288 ms | 71.890 ms | **57.901 ms** |
| Approximate mono rate | 21.9 FPS | 24.3 FPS | **29.1 FPS** |
| Approximate stereo rate | 10.6 FPS | 13.9 FPS | **17.3 FPS** |

## R2A to R2B change

- Mono transport: **50.5% lower**
- Stereo transport: **52.9% lower**
- Mono complete-frame time: **16.4% shorter**
- Stereo complete-frame time: **19.5% shorter**
- Mono measured rate: **19.6% higher**
- Stereo measured rate: **24.2% higher**

## R1 to R2B measured result

- Mono: **21.9 → 29.1 FPS** (32.7% higher)
- Stereo: **10.6 → 17.3 FPS** (62.8% higher)

The isolated transport measurements are the strongest apples-to-apples result.
Complete-frame rates also depend on the gameplay activity represented by each
hardware session.

## R2B timing detail

- Mono cropped transport: **7.023 ms**
- Stereo left cropped transport: **8.546 ms**
- Stereo right cropped transport: **4.705 ms**
- Mono pre-present engine work: **15.183 ms**
- Stereo pre-present engine work: **36.717 ms**
- Mono presentation: **19.198 ms**
- Stereo presentation: **21.183 ms**

## Implementation

R2B keeps the R2A direct indexed-to-Morton conversion but generates only the
output-sized regions consumed by the top and bottom 3DS displays. It uses
separate cropped top-left, cropped top-right, and bottom-atlas textures while
retaining the complete R2A transport as a frame-safe fallback.

This hardware run recorded zero cropped-path fallbacks and zero fallback-swizzle
time. The remaining major stereo cost is software rendering before presentation,
not texture submission.
