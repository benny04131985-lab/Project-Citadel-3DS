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

**v1.0.0 — S3 Ship**

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
