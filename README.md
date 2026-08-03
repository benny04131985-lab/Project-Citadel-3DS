# Project Citadel 3D

A native Nintendo 3DS port of **System Shock (1994)** based on the open-source
Shockolate codebase.

Project Citadel 3D provides:

- Native New Nintendo 3DS gameplay.
- True dual-camera stereoscopic station-world rendering.
- A flat, zero-parallax HUD and interface.
- Touchscreen and dual-screen presentation.
- C-stick freelook.
- Automatic flat presentation for cyberspace, 360-degree view, and full
  security-camera takeover.

## Current release

**v1.0.1 — Silent Diagnostics Hotfix**

The middle portion of the physical 3D slider is the recommended comfort sweet
spot. Maximum depth remains available, but comfort at the highest setting
depends on the player and session length.

## Original game data required

This repository and its releases do **not** include copyrighted System Shock
game data.

Users must provide legally obtained game files in:

```text
sdmc:/3ds/SystemShock3D/
```

See [INSTALLING.md](INSTALLING.md) for the expected layout.

## Build

See [BUILDING_3DS.md](BUILDING_3DS.md).

## Known issue

HOME/suspend behavior is not completely consistent and is reserved for a
separate future lifecycle hotfix. Saving, loading, in-game quit, ordinary
gameplay, and cyberspace transitions are functional in the S3 ship build.

## Licensing and attribution

The source is derived from Shockolate and remains distributed under the
included GPL-3.0 license terms. See [UPSTREAM_AND_LICENSE.md](UPSTREAM_AND_LICENSE.md),
`LICENSE`, and `COPYING.txt`.

System Shock and related names and assets belong to their respective owners.
Project Citadel 3D is an independent fan preservation/porting project and is
not affiliated with or endorsed by the rights holders.

## Support diagnostics

Version 1.0.1 silently creates:

`sdmc:/3ds/SystemShock3D/citadel_diag.log`

The file is overwritten at each successful startup and receives a completed
performance summary during normal shutdown. It records separate mono and stereo
frame statistics, frame-pacing information, hardware detection, memory samples,
Citro3D failure counters, and clean-shutdown status.

When reporting a performance or stability problem, reproduce the issue, exit
normally when possible, and attach the log or paste its contents into the
report.

The diagnostic system has no overlay or menu and performs no per-frame SD-card
writes.

## v1.0.2 — Final Software Renderer Hotfix

The R2C Citro3D transport path is the final optimized software-renderer
baseline. Hardware measurements on New Nintendo 3DS averaged
**33.286 FPS in mono** and
**18.451 FPS in true stereo**, with zero
transport mismatches, zero fallbacks, and zero GPU upload/draw failures.

The game world remains software rendered in this stable hotfix. Native Citro3D
world geometry is being developed separately and is not part of v1.0.2.
