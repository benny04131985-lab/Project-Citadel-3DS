#!/usr/bin/env python3
'''
Project Citadel 3D S2.1 — depth response + stereo freelook normalization

Changes only:
  src/GameSrc/frsetup.c
  src/Libraries/INPUT/Source/sdl_events.c
'''

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import difflib
import hashlib
import os
import sys
import zipfile


ROOT = Path.cwd().resolve()
PROJECT_ROOT = ROOT.parent.parent
SAFE_ROOT = PROJECT_ROOT / "_PROTECTED_BASELINES"

FRSETUP = Path("src/GameSrc/frsetup.c")
INPUT = Path("src/Libraries/INPUT/Source/sdl_events.c")
SHOCK = Path("src/MacSrc/Shock.c")

EXPECTED_FRSETUP_SHA256 = (
    "4481cc5731f8b39fe10c52c1dd540bbec8aee4d4694d22e906253b65990269cf"
)
EXPECTED_INPUT_SHA256 = (
    "11339aa19e1d00df595e7017e219a92b2cb9bc7e0bf45493f3affaa62c808d62"
)

FRSETUP_MARKER = (
    "PROJECT CITADEL 3D S2.1: centered depth curve and 5px ceiling are ACTIVE"
)
INPUT_MARKER = (
    "PROJECT CITADEL 3D S2.1 INPUT: frame-time freelook normalization is ACTIVE"
)


def fail(message: str) -> None:
    print()
    print(f"ERROR: {message}", file=sys.stderr)
    print("No source files were installed.", file=sys.stderr)
    raise SystemExit(1)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_text(path: Path) -> tuple[bytes, str, str]:
    raw = path.read_bytes()
    text = raw.decode("utf-8")
    newline = "\r\n" if "\r\n" in text else "\n"
    return raw, text.replace("\r\n", "\n"), newline


def encode_text(text: str, newline: str) -> bytes:
    if newline == "\r\n":
        text = text.replace("\n", "\r\n")
    return text.encode("utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        fail(f"{label}: expected exactly one anchor, found {count}.")
    return text.replace(old, new, 1)


def zip_dir(directory: Path) -> Path:
    archive = directory.with_suffix(".zip")
    with zipfile.ZipFile(
        archive,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as handle:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                handle.write(path, path.relative_to(directory.parent))
    return archive


def save_snapshot(
    destination: Path,
    files: dict[Path, bytes],
    note: str,
) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    manifest = []

    for relative, data in files.items():
        output = destination / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(data)
        manifest.append(f"{sha256_bytes(data)}  {relative.as_posix()}")

    (destination / "SHA256SUMS.txt").write_text(
        "\n".join(sorted(manifest)) + "\n",
        encoding="utf-8",
    )
    (destination / "BASELINE_INFO.txt").write_text(
        note.rstrip() + "\n",
        encoding="utf-8",
    )


def patch_frsetup(text: str) -> str:
    text = replace_once(
        text,
        "#if defined(__3DS__) || defined(_3DS)\n"
        "/* -------------------------------------------------------------------------\n"
        " * PROJECT CITADEL 3D S2: true software-rendered world stereo.",
        "#if defined(__3DS__) || defined(_3DS)\n"
        '#warning "PROJECT CITADEL 3D S2.1: centered depth curve and 5px ceiling are ACTIVE"\n'
        "/* -------------------------------------------------------------------------\n"
        " * PROJECT CITADEL 3D S2: true software-rendered world stereo.",
        "S2.1 renderer marker",
    )

    text = replace_once(
        text,
        "#define CITADEL_3DS_STEREO_MAX_CONVERGENCE_PIXELS 3",
        "#define CITADEL_3DS_STEREO_MAX_CONVERGENCE_PIXELS 5",
        "5-pixel convergence ceiling",
    )

    helper = '''/*
 * S2.1 slider response:
 *
 * S2 used slider^2, which concentrated almost all fine control near the
 * physical slider's bottom. This signed-square curve keeps 0 -> 0, 0.5 -> 0.5
 * and 1 -> 1, but deliberately flattens the response around the center.
 */
static float citadel_3ds_stereo_centered_slider_curve(float slider)
{
    float normalized;
    float centered;

    if (slider <= CITADEL_3DS_STEREO_SLIDER_MIN)
        return 0.0f;

    normalized =
        (slider - CITADEL_3DS_STEREO_SLIDER_MIN) /
        (1.0f - CITADEL_3DS_STEREO_SLIDER_MIN);

    if (normalized < 0.0f) normalized = 0.0f;
    if (normalized > 1.0f) normalized = 1.0f;

    centered = (normalized * 2.0f) - 1.0f;

    if (centered < 0.0f)
        return 0.5f - (0.5f * centered * centered);

    return 0.5f + (0.5f * centered * centered);
}

'''

    text = replace_once(
        text,
        "void citadel_3ds_stereo_begin_frame(float slider)\n{",
        helper + "void citadel_3ds_stereo_begin_frame(float slider)\n{",
        "centered slider helper",
    )

    text = replace_once(
        text,
        "    citadel_3ds_stereo_slider_curve = slider * slider;",
        "    citadel_3ds_stereo_slider_curve =\n"
        "        citadel_3ds_stereo_centered_slider_curve(slider);",
        "slider response assignment",
    )

    return text


def patch_input(text: str) -> str:
    warning_prefix = '#warning "PROJECT CITADEL INPUT V16.1'
    start = text.find(warning_prefix)
    if start < 0:
        fail("Input marker: PROJECT CITADEL INPUT V16.1 warning not found.")
    line_end = text.find("\n", start)
    if line_end < 0:
        fail("Input marker line is malformed.")
    if text.find(warning_prefix, line_end + 1) >= 0:
        fail("Input marker is not unique.")

    text = (
        text[:line_end + 1]
        + '#warning "PROJECT CITADEL 3D S2.1 INPUT: frame-time freelook normalization is ACTIVE"\n'
        + text[line_end + 1:]
    )

    text = replace_once(
        text,
        "static int citadel_freelook_velocity_x = 0;\n"
        "static int citadel_freelook_velocity_y = 0;",
        "static int citadel_freelook_velocity_x = 0;\n"
        "static int citadel_freelook_velocity_y = 0;\n"
        "static u64 citadel_3ds_freelook_last_update_ms = 0;",
        "freelook frame timestamp",
    )

    helper = '''/*
 * S2.1 keeps the established mono C-stick calibration intact.
 *
 * The C-stick produces a per-main-loop velocity. True stereo adds a second
 * software world render, reducing loop frequency on demanding frames. Scale
 * only freelook by elapsed frame time while the physical 3D slider is active.
 * A 16-34 ms clamp preserves 60 Hz behavior and caps compensation near 30 Hz.
 */
static int citadel_3ds_stereo_freelook_frame_scale(void)
{
    const u64 target_ms = 16;
    const u64 maximum_ms = 34;
    u64 now = osGetTime();
    u64 elapsed = target_ms;

    if (citadel_3ds_freelook_last_update_ms != 0 &&
        now >= citadel_3ds_freelook_last_update_ms)
        elapsed = now - citadel_3ds_freelook_last_update_ms;

    citadel_3ds_freelook_last_update_ms = now;

    if (osGet3DSliderState() < 0.015f)
        return (int)target_ms;

    if (elapsed < target_ms) elapsed = target_ms;
    if (elapsed > maximum_ms) elapsed = maximum_ms;

    return (int)elapsed;
}

static int citadel_3ds_scale_signed_round(int value,
                                          int numerator,
                                          int denominator)
{
    if (value > 0)
        return (value * numerator + denominator / 2) / denominator;
    if (value < 0)
        return -(((-value) * numerator + denominator / 2) / denominator);
    return 0;
}

'''

    signature = (
        "static void citadel_update_cstick(const circlePosition *cstick, "
        "bool gameplay_active, bool split_layout, bool touch_held)\n"
        "{"
    )
    text = replace_once(
        text,
        signature,
        helper + signature,
        "freelook timing helper",
    )

    text = replace_once(
        text,
        "    int sx,sy,lx,ly;\n"
        "    citadel_freelook_velocity_x=0; citadel_freelook_velocity_y=0;",
        "    int sx,sy,lx,ly;\n"
        "    int stereo_frame_scale =\n"
        "        citadel_3ds_stereo_freelook_frame_scale();\n"
        "    citadel_freelook_velocity_x=0; citadel_freelook_velocity_y=0;",
        "freelook per-frame scale sample",
    )

    old_speed = (
        "        citadel_freelook_velocity_x="
        "(citadel_freelook_velocity_x*CITADEL_CSTICK_SPEED_NUMERATOR)"
        "/CITADEL_CSTICK_SPEED_DENOMINATOR;\n"
        "        citadel_freelook_velocity_y="
        "(citadel_freelook_velocity_y*CITADEL_CSTICK_SPEED_NUMERATOR)"
        "/CITADEL_CSTICK_SPEED_DENOMINATOR;\n"
        "        return;"
    )

    new_speed = (
        "        citadel_freelook_velocity_x="
        "(citadel_freelook_velocity_x*CITADEL_CSTICK_SPEED_NUMERATOR)"
        "/CITADEL_CSTICK_SPEED_DENOMINATOR;\n"
        "        citadel_freelook_velocity_y="
        "(citadel_freelook_velocity_y*CITADEL_CSTICK_SPEED_NUMERATOR)"
        "/CITADEL_CSTICK_SPEED_DENOMINATOR;\n"
        "        citadel_freelook_velocity_x =\n"
        "            citadel_3ds_scale_signed_round(\n"
        "                citadel_freelook_velocity_x,\n"
        "                stereo_frame_scale,\n"
        "                16);\n"
        "        citadel_freelook_velocity_y =\n"
        "            citadel_3ds_scale_signed_round(\n"
        "                citadel_freelook_velocity_y,\n"
        "                stereo_frame_scale,\n"
        "                16);\n"
        "        return;"
    )

    text = replace_once(
        text,
        old_speed,
        new_speed,
        "stereo freelook normalization",
    )

    return text


def main() -> int:
    expected_suffix = "citadel_3d_dev/source/shockolate"
    if not ROOT.as_posix().lower().endswith(expected_suffix):
        fail(
            "Run this only from:\n"
            "  C:/Projects/Citadel_3D_DEV/Source/shockolate\n"
            f"Current: {ROOT}"
        )

    for path in (FRSETUP, INPUT, SHOCK):
        if not path.is_file():
            fail(f"Missing required active file: {path}")

    shock_text = SHOCK.read_text(encoding="utf-8", errors="replace")
    if "PROJECT CITADEL 3D S2: true dual-camera world stereo is ACTIVE" not in shock_text:
        fail("The active tree is not the proven S2 true-world build.")

    _, frsetup_text, frsetup_newline = read_text(FRSETUP)
    _, input_text, input_newline = read_text(INPUT)

    if FRSETUP_MARKER in frsetup_text or INPUT_MARKER in input_text:
        print("Citadel 3D S2.1 is already installed; nothing changed.")
        return 0

    actual_frsetup_hash = sha256_file(FRSETUP)
    actual_input_hash = sha256_file(INPUT)

    if actual_frsetup_hash != EXPECTED_FRSETUP_SHA256:
        fail(
            "frsetup.c is not the exact successful S2 source.\n"
            f"Expected: {EXPECTED_FRSETUP_SHA256}\n"
            f"Actual:   {actual_frsetup_hash}"
        )

    if actual_input_hash != EXPECTED_INPUT_SHA256:
        fail(
            "sdl_events.c is not the sealed VX1 input source.\n"
            f"Expected: {EXPECTED_INPUT_SHA256}\n"
            f"Actual:   {actual_input_hash}"
        )

    original = {
        FRSETUP: FRSETUP.read_bytes(),
        INPUT: INPUT.read_bytes(),
    }

    patched_frsetup = patch_frsetup(frsetup_text)
    patched_input = patch_input(input_text)

    for token in (
        FRSETUP_MARKER,
        "CITADEL_3DS_STEREO_MAX_CONVERGENCE_PIXELS 5",
        "citadel_3ds_stereo_centered_slider_curve",
    ):
        if token not in patched_frsetup:
            fail(f"Prepared frsetup.c is missing: {token}")

    for token in (
        INPUT_MARKER,
        "citadel_3ds_stereo_freelook_frame_scale",
        "citadel_3ds_scale_signed_round",
        "osGet3DSliderState() < 0.015f",
    ):
        if token not in patched_input:
            fail(f"Prepared sdl_events.c is missing: {token}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre = SAFE_ROOT / f"S2_1_PRE_TUNING_{timestamp}"
    post = SAFE_ROOT / f"S2_1_CENTERED_5PX_TIME_NORMALIZED_{timestamp}"
    SAFE_ROOT.mkdir(parents=True, exist_ok=True)

    save_snapshot(
        pre,
        original,
        (
            "PROJECT CITADEL 3D — PRE-S2.1\n"
            "Successful S2 true-world source immediately before depth/input tuning.\n"
            "Only frsetup.c and sdl_events.c may change."
        ),
    )
    pre_zip = zip_dir(pre)

    temp_frsetup = FRSETUP.with_name(FRSETUP.name + ".S2_1_TEMP")
    temp_input = INPUT.with_name(INPUT.name + ".S2_1_TEMP")

    try:
        temp_frsetup.write_bytes(encode_text(patched_frsetup, frsetup_newline))
        temp_input.write_bytes(encode_text(patched_input, input_newline))
        os.replace(temp_frsetup, FRSETUP)
        os.replace(temp_input, INPUT)
    except Exception as error:
        temp_frsetup.unlink(missing_ok=True)
        temp_input.unlink(missing_ok=True)
        fail(f"Atomic install failed: {error}")

    installed_frsetup = read_text(FRSETUP)[1]
    installed_input = read_text(INPUT)[1]

    if FRSETUP_MARKER not in installed_frsetup:
        fail(f"Installed frsetup marker missing. Restore from {pre}")
    if INPUT_MARKER not in installed_input:
        fail(f"Installed input marker missing. Restore from {pre}")

    active = {
        FRSETUP: FRSETUP.read_bytes(),
        INPUT: INPUT.read_bytes(),
    }
    save_snapshot(
        post,
        active,
        (
            "PROJECT CITADEL 3D — S2.1 CANDIDATE\n"
            "Centered signed-square slider response.\n"
            "5-pixel maximum convergence.\n"
            "Stereo-only frame-time C-stick freelook normalization.\n"
            "Mono input calibration remains unchanged."
        ),
    )

    diff_dir = post / "DIFFS"
    diff_dir.mkdir(parents=True, exist_ok=True)

    (diff_dir / "frsetup.c.diff").write_text(
        "".join(
            difflib.unified_diff(
                frsetup_text.splitlines(keepends=True),
                installed_frsetup.splitlines(keepends=True),
                fromfile="src/GameSrc/frsetup.c (S2)",
                tofile="src/GameSrc/frsetup.c (S2.1)",
            )
        ),
        encoding="utf-8",
    )
    (diff_dir / "sdl_events.c.diff").write_text(
        "".join(
            difflib.unified_diff(
                input_text.splitlines(keepends=True),
                installed_input.splitlines(keepends=True),
                fromfile="src/Libraries/INPUT/Source/sdl_events.c (VX1)",
                tofile="src/Libraries/INPUT/Source/sdl_events.c (S2.1)",
            )
        ),
        encoding="utf-8",
    )
    post_zip = zip_dir(post)

    print()
    print("============================================================")
    print("PROJECT CITADEL 3D S2.1 INSTALLED")
    print("============================================================")
    print("PASS: Slider response fine-control moved to the center.")
    print("PASS: Maximum convergence raised from 3px to 5px.")
    print("PASS: Mono C-stick calibration remains unchanged.")
    print("PASS: Stereo freelook is normalized to measured frame time.")
    print("PASS: Only frsetup.c and sdl_events.c changed.")
    print()
    print(f"PRE-S2.1:  {pre}")
    print(f"PRE ZIP:   {pre_zip}")
    print(f"S2.1:      {post}")
    print(f"S2.1 ZIP:  {post_zip}")
    print()
    print("Build:")
    print('  cmake --build build --target project_citadel_3dsx -j"$(nproc)"')
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
