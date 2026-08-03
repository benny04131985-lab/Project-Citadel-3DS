# CITADEL-C3D-R2C-PINGPONGTILED1 — Final Software Renderer Benchmark

Status: **HARDWARE PASS**  
Release role: **v1.0.2 final software renderer hotfix baseline**

## User-facing diagnostic average

- Session duration: **164.815 seconds**
- Measured frames: **3477**
- Mono frames: **1713**
- Mono average: **33.286 FPS / 30.043 ms**
- Stereo frames: **1764**
- Stereo average: **18.451 FPS / 54.196 ms**
- Combined average: **23.643 FPS / 42.297 ms**

## R1 transport profiler

- Presented frames: **3482**
- Mono profiler frames: **1809**
- Mono profiler cycle: **36.898 ms**
- Mono pre-present: **17.001 ms**
- Mono presentation: **19.897 ms**
- Mono FrameBegin: **12.222 ms**
- Mono cropped upload: **7.297 ms**
- Stereo profiler frames: **1672**
- Stereo profiler cycle: **56.119 ms**
- Stereo pre-present: **34.732 ms**
- Stereo presentation: **21.388 ms**
- Stereo FrameBegin: **7.718 ms**
- Stereo cropped upload: **13.289 ms**

The diagnostic average excludes gaps longer than one second and is the preferred
normal-gameplay FPS measurement. The transport profiler retains long-cycle
information useful for renderer analysis.

## Ping-pong proof

- Pre-frame uploads: **3481**
- In-frame uploads: **0**
- Pre-frame failures: **0**
- Texture switches: **3481**
- Set 0 draws: **1740**
- Set 1 draws: **1741**

## Safety proof

- Cropped mismatches: **0**
- Cropped fallbacks: **0**
- Direct-tiled fallbacks: **0**
- Upload failures: **0**
- Draw failures: **0**
- GPU profile clean shutdown: **YES**
