# Project Citadel 3D v1.0.1 — Silent Diagnostics Hotfix

## Purpose

Version 1.0.1 adds an automatic background diagnostic report to improve support
for performance, stability, and hardware-specific reports.

The diagnostic system has no interface, overlay, menu option, or console output.
It runs silently and does not change normal controls or presentation behavior.

## Changes

- Added automatic creation of:
  `sdmc:/3ds/SystemShock3D/citadel_diag.log`
- The log is overwritten each time Project Citadel 3D starts successfully.
- Performance counters remain in memory during play.
- The completed report is written during normal shutdown.
- Added an explicit New Nintendo 3DS speedup request during startup.
- Added separate mono and stereo frame statistics.
- Added combined frame-pacing statistics.
- Added clean-shutdown detection.
- Added Citro3D upload and draw failure counters.
- Added sampled linear-memory reporting.

## Diagnostic information

The generated report includes:

- Build version and timestamp.
- New or Old Nintendo 3DS hardware detection.
- New Nintendo 3DS speedup request status.
- Initial and last sampled 3D-slider positions.
- Mono average FPS and frame time.
- Stereo average FPS and frame time.
- Best and worst frame times for each mode.
- Combined average FPS.
- Median, P95, and P99 frame times.
- Frames exceeding 16.67, 33.33, 50, and 100 milliseconds.
- Long stalls excluded from normal FPS calculation.
- Initial and lowest sampled linear memory.
- Citro3D presentation, upload-failure, and draw-failure counts.
- Clean or incomplete shutdown status.

## Support reports

When reporting a performance or stability problem:

1. Launch Project Citadel 3D v1.0.1.
2. Reproduce the issue.
3. Exit normally when possible.
4. Locate `citadel_diag.log` beside the 3DSX.
5. Attach the file or paste its contents into the report.

The log contains technical runtime statistics and does not contain copyrighted
game data.

## Scope

This release does not claim a renderer performance improvement. Its purpose is
to provide consistent evidence for investigating reports across different New
Nintendo 3DS systems, SD cards, installations, and gameplay situations.

The established v1.0 gameplay, controls, stereoscopic presentation, dual-screen
layout, save/load behavior, and asset requirements remain unchanged.

## Game data

No copyrighted System Shock game data is included. A legally obtained original
copy of System Shock is required.
