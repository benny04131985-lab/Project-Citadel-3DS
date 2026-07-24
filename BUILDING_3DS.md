# Building Project Citadel 3D

## Requirements

- devkitPro with devkitARM and the Nintendo 3DS libraries.
- CMake.
- An MSYS2/devkitPro shell on Windows, or a compatible Unix-like shell.

## Configure

Always begin from an empty `build/` directory. Incremental CMake dependency
files proved unreliable in the Windows/MSYS development environment.

```bash
rm -rf build

cmake -S . -B build \
  -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake" \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_POLICY_VERSION_MINIMUM=3.5 \
  -DENABLE_OPENGL=OFF \
  -DENABLE_SOUND=OFF \
  -DENABLE_FLUIDSYNTH=OFF \
  -DENABLE_SDL2=ON
```

## Build

```bash
cmake --build build \
  --target project_citadel_3dsx \
  -j"$(nproc)"
```

Expected output:

```text
build/3D_Citadel_3DS.3dsx
```

The build must retain the runtime wall:

```text
sdmc:/3ds/SystemShock3D/
```

It must never be redirected to the mono-development folder
`sdmc:/3ds/SystemShock/`.
