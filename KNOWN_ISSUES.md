# Known issues

## HOME/suspend consistency

HOME/suspend behavior remains somewhat inconsistent. The S3 splash and final
lifecycle state improved consistency, but this issue is deferred to a separate
future hotfix.

The following are confirmed functional in the S3 ship build:

- Normal station gameplay.
- True stereoscopic world rendering.
- Save and load.
- In-game quit.
- Entering cyberspace.
- Exiting cyberspace.
- Automatic restoration of station stereo.
- C-stick freelook with stereo active.

Suspend hotfix work should not change the frozen S2.1 depth curve, C-stick
normalization, or S3 exceptional-view behavior.

## Performance reports

Performance may vary by scene, stereo state, installation, and hardware
environment. Version 1.0.1 adds a silent diagnostic report so performance
reports can be evaluated using measured frame timing rather than subjective
descriptions alone.

When reporting sluggish performance, attach:

`sdmc:/3ds/SystemShock3D/citadel_diag.log`

The current software-rendering pipeline remains in place in v1.0.1. A separate
experimental Citro3D renderer branch is under development and is not part of
this stable release.
