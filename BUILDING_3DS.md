# Building v2.0.0

Requirements: devkitPro/devkitARM with 3DS libraries, CMake, and an MSYS2/devkitPro or compatible shell.

The exact qualified SDL2 headers/static libraries are included in `Libraries/SDL2`.

```bash
export DEVKITPRO=/opt/devkitpro
export DEVKITARM=/opt/devkitpro/devkitARM
cd Source/shockolate
rm -rf build
cmake -S . -B build   -DCMAKE_TOOLCHAIN_FILE="$DEVKITPRO/cmake/3DS.cmake"   -DCMAKE_BUILD_TYPE=Release   -DCMAKE_POLICY_VERSION_MINIMUM=3.5   -DENABLE_OPENGL=OFF   -DENABLE_SOUND=OFF   -DENABLE_FLUIDSYNTH=OFF   -DENABLE_SDL2=ON
cmake --build build --target project_citadel_3dsx -j"$(nproc)"
```

Qualified release executable: `Release/3D_Citadel_3DS.3dsx`.
