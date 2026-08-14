#!/usr/bin/env python3
'''
Project Citadel VX1.1-SPLASH-SYNTH-A

Apply:
    python apply_vx1_1_splash_synth_a.py

Rollback:
    python apply_vx1_1_splash_synth_a.py rollback

Starting point:
    A protected VX1-NATURAL-NO-T7 baseline created by
    remove_all_t7_and_seal_v3.py.

Only src/MacSrc/Shock.c is modified. The existing Hack-i-Ben full-screen
Citro2D textured rectangle remains intact. After eight completed splash frames,
the patch performs one synchronized VRAM/GPU-right release and reacquire
sequence, then verifies a later normal splash frame.

The script creates protected pre-patch and post-patch five-file folders/ZIPs
under C:/Projects/Citadel-Baselines.
'''

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import difflib
import hashlib
import os
import re
import shutil
import sys
import zipfile


SAFE_ROOT = Path("/c/Projects/Citadel-Baselines")

SHOCK = Path("src/MacSrc/Shock.c")
SETUP = Path("src/GameSrc/setup.c")
MAINLOOP = Path("src/GameSrc/mainloop.c")
WRAPPER = Path("src/GameSrc/wrapper.c")
GAMEWRAP = Path("src/GameSrc/gamewrap.c")
FILES = [SHOCK, SETUP, MAINLOOP, WRAPPER, GAMEWRAP]

EXPECTED_SHOCK = (
    "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724"
)
EXPECTED_GAMEWRAP = (
    "c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30"
)

MARKER = (
    "PROJECT CITADEL VX1.1-SPLASH-SYNTH-A: "
    "startup GPU ownership round trip is ACTIVE"
)
LOG_NAME = "VX1_1_SPLASH_SYNTH_A.log"

LOCAL_BACKUP = Path(
    "BEFORE_VX1_1_SPLASH_SYNTH_A/src/MacSrc/Shock.c"
)
DIFF_PATH = Path("VX1_1_SPLASH_SYNTH_A.diff")
INSTALL_RECORD = Path("VX1_1_SPLASH_SYNTH_A_INSTALLED.txt")

T7_PATTERNS = [
    re.compile(r"(?i)\bcitadel_3ds_[A-Za-z0-9_]*t7[A-Za-z0-9_]*\b"),
    re.compile(r"(?i)\bCITADEL_T7[A-Za-z0-9_]*\b"),
    re.compile(r"(?i)\bNEWGAME_HOME_T7[A-Za-z0-9_.-]*\b"),
    re.compile(r"(?i)\bT7\b"),
]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


def read_source(path: Path) -> tuple[str, str]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        text = handle.read()

    return text, "\r\n" if "\r\n" in text else "\n"


def write_source(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def adapt(block: str, newline: str) -> str:
    return block.replace("\n", newline)


def replace_once(
    text: str,
    old: str,
    new: str,
    label: str,
) -> str:
    count = text.count(old)

    if count != 1:
        raise RuntimeError(
            f"{label}: expected exactly one anchor, found {count}"
        )

    return text.replace(old, new, 1)


def verify_root() -> None:
    if not Path("src/MacSrc").is_dir() or not Path("src/GameSrc").is_dir():
        raise RuntimeError(
            "Run this from the Shockolate repository root."
        )

    for path in FILES:
        if not path.is_file():
            raise RuntimeError(f"Missing required source file: {path}")


def strip_comments(text: str) -> str:
    result: list[str] = []
    index = 0
    state = "code"

    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""

        if state == "code":
            if current == "/" and following == "/":
                result.extend((" ", " "))
                index += 2
                state = "line_comment"
                continue

            if current == "/" and following == "*":
                result.extend((" ", " "))
                index += 2
                state = "block_comment"
                continue

            result.append(current)

            if current == '"':
                state = "string"
            elif current == "'":
                state = "char"

            index += 1
            continue

        if state == "line_comment":
            if current == "\n":
                result.append("\n")
                state = "code"
            else:
                result.append(" ")

            index += 1
            continue

        if state == "block_comment":
            if current == "*" and following == "/":
                result.extend((" ", " "))
                index += 2
                state = "code"
                continue

            result.append("\n" if current == "\n" else " ")
            index += 1
            continue

        result.append(current)

        if current == "\\" and index + 1 < len(text):
            result.append(text[index + 1])
            index += 2
            continue

        if state == "string" and current == '"':
            state = "code"
        elif state == "char" and current == "'":
            state = "code"

        index += 1

    return "".join(result)


def find_t7_remnants() -> list[str]:
    findings: list[str] = []

    for path in (SETUP, MAINLOOP, WRAPPER):
        text, _newline = read_source(path)
        searchable = strip_comments(text)
        original_lines = text.splitlines()

        for line_number, line in enumerate(
            searchable.splitlines(),
            start=1,
        ):
            for pattern in T7_PATTERNS:
                match = pattern.search(line)

                if match is None:
                    continue

                original = (
                    original_lines[line_number - 1].strip()
                    if line_number <= len(original_lines)
                    else line.strip()
                )
                findings.append(
                    f"{path}:{line_number}: "
                    f"{match.group(0)!r}: {original}"
                )
                break

    return findings


def parse_manifest(path: Path) -> dict[Path, str]:
    manifest: dict[Path, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line:
            continue

        parts = line.split(None, 1)

        if len(parts) != 2:
            raise RuntimeError(f"Malformed manifest line: {raw_line}")

        digest, relative = parts
        manifest[Path(relative.strip())] = digest.lower()

    return manifest


def active_hashes() -> dict[Path, str]:
    return {path: sha256_file(path) for path in FILES}


def find_matching_baseline(
    hashes: dict[Path, str],
) -> Path | None:
    if not SAFE_ROOT.is_dir():
        return None

    candidates = sorted(
        (
            path
            for path in SAFE_ROOT.glob(
                "VX1-NATURAL-NO-T7_BASELINE_*"
            )
            if path.is_dir()
        ),
        reverse=True,
    )

    for candidate in candidates:
        manifest_path = candidate / "SHA256SUMS.txt"

        if not manifest_path.is_file():
            continue

        try:
            manifest = parse_manifest(manifest_path)
        except Exception:
            continue

        if all(
            manifest.get(path, "") == hashes[path]
            for path in FILES
        ):
            return candidate

    return None


def copy_files(
    destination_root: Path,
    contents: dict[Path, bytes],
) -> None:
    for path in FILES:
        destination = destination_root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contents[path])

        if sha256_file(destination) != sha256_bytes(contents[path]):
            raise RuntimeError(
                f"copy verification failed for {destination}"
            )


def write_manifest(
    destination_root: Path,
    contents: dict[Path, bytes],
) -> None:
    lines = [
        f"{sha256_bytes(contents[path])}  {path.as_posix()}"
        for path in FILES
    ]
    (destination_root / "SHA256SUMS.txt").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def make_zip(folder: Path) -> tuple[Path, str]:
    archive_path = folder.parent / f"{folder.name}.zip"

    with zipfile.ZipFile(
        archive_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
    ) as archive:
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                archive.write(
                    path,
                    Path(folder.name) / path.relative_to(folder),
                )

    archive_hash = sha256_file(archive_path)
    (folder.parent / f"{folder.name}.zip.sha256.txt").write_text(
        f"{archive_hash}  {archive_path.name}\n",
        encoding="utf-8",
    )

    return archive_path, archive_hash


def patch_shock(original: str, newline: str) -> str:
    warning_anchor = adapt(
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"\n',
        newline,
    )
    warning_new = warning_anchor + adapt(
        '#warning "PROJECT CITADEL VX1.1-SPLASH-SYNTH-A: '
        'startup GPU ownership round trip is ACTIVE"\n',
        newline,
    )

    state_anchor = adapt(
        "static Uint32 citadel_v16_splash_until = 0;\n",
        newline,
    )
    state_new = state_anchor + adapt(
        '''
/*
 * VX1.1-SPLASH-SYNTH-A:
 * the existing Hack-i-Ben image already fills a real 400x240 Citro2D
 * textured rectangle. After eight completed splash frames, perform one
 * controlled GPU ownership and VRAM save/restore round trip.
 */
#define CITADEL_VX1_1_SYNTH_FRAME 8u

static unsigned int citadel_vx1_1_splash_frames = 0;
static bool citadel_vx1_1_synth_attempted = false;
static bool citadel_vx1_1_synth_complete = false;
static bool citadel_vx1_1_post_frame_complete = false;
''',
        newline,
    )

    prototype_anchor = adapt(
        "static bool citadel_v16_present_splash(void);\n",
        newline,
    )
    prototype_new = prototype_anchor + adapt(
        '''static void citadel_vx1_1_log(const char *fmt, ...);
static bool citadel_vx1_1_run_splash_synth(void);
''',
        newline,
    )

    function_anchor = adapt(
        "static bool citadel_v16_present_splash(void)\n{",
        newline,
    )

    helper_code = adapt(
        r'''static void citadel_vx1_1_log(const char *fmt, ...)
{
    FILE *file;
    va_list args;

    file = fopen("VX1_1_SPLASH_SYNTH_A.log", "a");
    if (file == NULL)
        return;

    va_start(args, fmt);
    vfprintf(file, fmt, args);
    va_end(args);

    fputc('\n', file);
    fflush(file);
    fclose(file);
}

static bool citadel_vx1_1_run_splash_synth(void)
{
    GSPGPU_CaptureInfo capture_info;
    Result save_result = (Result)-1;
    Result capture_result = (Result)-1;
    Result release_result = (Result)-1;
    Result acquire_result = (Result)-1;
    Result restore_result = (Result)-1;
    bool owned_before;
    bool owned_after;
    u16 top_width = 0;
    u16 top_height = 0;
    u16 bottom_width = 0;
    u16 bottom_height = 0;
    u8 *top_left;
    u8 *top_right;
    u8 *bottom;

    if (citadel_vx1_1_synth_attempted)
        return citadel_vx1_1_synth_complete;

    citadel_vx1_1_synth_attempted = true;

    /*
     * The calling splash frame has already ended. Fully drain it and cross
     * one VBlank before touching GPU ownership.
     */
    C3D_FrameSync();
    gspWaitForVBlank();

    owned_before = gspHasGpuRight();

    top_left =
        gfxGetFramebuffer(
            GFX_TOP,
            GFX_LEFT,
            &top_width,
            &top_height);
    top_right =
        gfxGetFramebuffer(
            GFX_TOP,
            GFX_RIGHT,
            NULL,
            NULL);
    bottom =
        gfxGetFramebuffer(
            GFX_BOTTOM,
            GFX_LEFT,
            &bottom_width,
            &bottom_height);

    citadel_vx1_1_log(
        "VX1.1 SYNTH BEGIN build=%s %s splash_frames=%u "
        "gpu_right_before=%d top=%ux%u bottom=%ux%u "
        "topL=%p topR=%p bottom=%p",
        __DATE__,
        __TIME__,
        citadel_vx1_1_splash_frames,
        owned_before ? 1 : 0,
        (unsigned int)top_width,
        (unsigned int)top_height,
        (unsigned int)bottom_width,
        (unsigned int)bottom_height,
        (void *)top_left,
        (void *)top_right,
        (void *)bottom);

    v5_log(
        "VX1.1 SYNTH BEGIN splash_frames=%u gpu_right_before=%d",
        citadel_vx1_1_splash_frames,
        owned_before ? 1 : 0);

    if (!owned_before) {
        citadel_vx1_1_log(
            "VX1.1 SYNTH ABORT reason=no-GPU-right");
        v5_log(
            "VX1.1 SYNTH ABORT reason=no-GPU-right");
        return false;
    }

    memset(&capture_info, 0, sizeof(capture_info));

    save_result = GSPGPU_SaveVramSysArea();
    capture_result =
        GSPGPU_ImportDisplayCaptureInfo(&capture_info);

    if (R_SUCCEEDED(save_result) &&
        R_SUCCEEDED(capture_result)) {
        release_result = GSPGPU_ReleaseRight();

        if (R_SUCCEEDED(release_result)) {
            acquire_result = GSPGPU_AcquireRight(0);

            if (R_SUCCEEDED(acquire_result))
                restore_result = GSPGPU_RestoreVramSysArea();
        }
    }

    gspWaitForVBlank();
    owned_after = gspHasGpuRight();

    citadel_vx1_1_synth_complete =
        R_SUCCEEDED(save_result) &&
        R_SUCCEEDED(capture_result) &&
        R_SUCCEEDED(release_result) &&
        R_SUCCEEDED(acquire_result) &&
        R_SUCCEEDED(restore_result) &&
        owned_after;

    citadel_vx1_1_log(
        "VX1.1 SYNTH RESULTS save=0x%08lX capture=0x%08lX "
        "release=0x%08lX acquire=0x%08lX restore=0x%08lX "
        "gpu_right_after=%d complete=%d",
        (unsigned long)save_result,
        (unsigned long)capture_result,
        (unsigned long)release_result,
        (unsigned long)acquire_result,
        (unsigned long)restore_result,
        owned_after ? 1 : 0,
        citadel_vx1_1_synth_complete ? 1 : 0);

    v5_log(
        "VX1.1 SYNTH RESULTS save=0x%08lX capture=0x%08lX "
        "release=0x%08lX acquire=0x%08lX restore=0x%08lX "
        "gpu_right_after=%d complete=%d",
        (unsigned long)save_result,
        (unsigned long)capture_result,
        (unsigned long)release_result,
        (unsigned long)acquire_result,
        (unsigned long)restore_result,
        owned_after ? 1 : 0,
        citadel_vx1_1_synth_complete ? 1 : 0);

    return citadel_vx1_1_synth_complete;
}

''',
        newline,
    ) + function_anchor

    frame_anchor = adapt(
        '''    C3D_FrameEnd(0);
    ++citadel_gpu_presented_frames;

    if (!draw_ok)
        ++citadel_gpu_draw_failures;
''',
        newline,
    )

    frame_new = adapt(
        '''    C3D_FrameEnd(0);
    ++citadel_gpu_presented_frames;
    ++citadel_vx1_1_splash_frames;

    if (citadel_vx1_1_splash_frames == 1u) {
        remove("VX1_1_SPLASH_SYNTH_A.log");
        citadel_vx1_1_log(
            "PROJECT CITADEL VX1.1-SPLASH-SYNTH-A START "
            "build=%s %s",
            __DATE__,
            __TIME__);
    }

    if (!citadel_vx1_1_synth_attempted &&
        citadel_vx1_1_splash_frames >=
            CITADEL_VX1_1_SYNTH_FRAME) {
        (void)citadel_vx1_1_run_splash_synth();
    } else if (citadel_vx1_1_synth_complete &&
               !citadel_vx1_1_post_frame_complete &&
               citadel_vx1_1_splash_frames >
                   CITADEL_VX1_1_SYNTH_FRAME) {
        /*
         * This is a later ordinary SYNCDRAW splash frame submitted after
         * GPU reacquisition. Fully synchronize it before declaring success.
         */
        C3D_FrameSync();
        gspWaitForVBlank();

        citadel_vx1_1_post_frame_complete = true;

        citadel_vx1_1_log(
            "VX1.1 POST-SYNTH SPLASH FRAME COMPLETE "
            "frame=%u gpu_right=%d",
            citadel_vx1_1_splash_frames,
            gspHasGpuRight() ? 1 : 0);

        v5_log(
            "VX1.1 POST-SYNTH SPLASH FRAME COMPLETE "
            "frame=%u gpu_right=%d",
            citadel_vx1_1_splash_frames,
            gspHasGpuRight() ? 1 : 0);
    }

    if (!draw_ok)
        ++citadel_gpu_draw_failures;
''',
        newline,
    )

    patched = replace_once(
        original,
        warning_anchor,
        warning_new,
        "compile marker",
    )
    patched = replace_once(
        patched,
        state_anchor,
        state_new,
        "synth state",
    )
    patched = replace_once(
        patched,
        prototype_anchor,
        prototype_new,
        "synth prototypes",
    )
    patched = replace_once(
        patched,
        function_anchor,
        helper_code,
        "synth helper",
    )
    patched = replace_once(
        patched,
        frame_anchor,
        frame_new,
        "splash frame hook",
    )

    if patched.count(MARKER) != 1:
        raise RuntimeError(
            "staged Shock.c does not contain exactly one VX1.1 marker"
        )

    return patched


def apply_patch() -> int:
    verify_root()

    print("============================================================")
    print("PROJECT CITADEL VX1.1-SPLASH-SYNTH-A")
    print("============================================================")
    print()
    print("Verifying protected no-T7 starting point...")

    hashes = active_hashes()

    for path in FILES:
        print(f"{hashes[path]}  {path}")

    if hashes[SHOCK] != EXPECTED_SHOCK:
        print()
        print("ERROR: Shock.c is not the exact no-synth baseline.")
        print("Nothing changed.")
        return 1

    if hashes[GAMEWRAP] != EXPECTED_GAMEWRAP:
        print()
        print("ERROR: gamewrap.c is not the expected baseline.")
        print("Nothing changed.")
        return 1

    baseline = find_matching_baseline(hashes)

    if baseline is None:
        print()
        print(
            "ERROR: The current five files do not match any protected "
            "VX1-NATURAL-NO-T7 baseline manifest."
        )
        print("Nothing changed.")
        return 1

    print(f"OK    protected baseline match: {baseline}")

    remnants = find_t7_remnants()

    if remnants:
        print()
        print("ERROR: Executable T7 remnants remain:")
        for finding in remnants:
            print(f"  {finding}")
        print("Nothing changed.")
        return 1

    print("OK    executable T7 scan is clean")

    original_text, newline = read_source(SHOCK)

    if MARKER in original_text:
        print("ERROR: VX1.1-SPLASH-SYNTH-A is already installed.")
        return 1

    required = (
        '#warning "PROJECT CITADEL V16.1: launch polish candidate is ACTIVE"',
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"',
        "static Uint32 citadel_v16_splash_until = 0;",
        "static bool citadel_v16_present_splash(void);",
        "static bool citadel_v16_present_splash(void)",
        "C3D_FrameBegin(C3D_FRAME_SYNCDRAW)",
        "C2D_DrawImageAt(citadel_v16_splash_image",
        "C3D_FrameEnd(0);",
    )

    missing = [token for token in required if token not in original_text]

    if missing:
        print()
        print("ERROR: Required splash anchors are missing:")
        for token in missing:
            print(f"  {token}")
        print("Nothing changed.")
        return 1

    try:
        patched_text = patch_shock(original_text, newline)
    except RuntimeError as error:
        print(f"ERROR: {error}")
        print("Nothing changed.")
        return 1

    original_bytes = {path: path.read_bytes() for path in FILES}
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rollback_root = SAFE_ROOT / (
        f"VX1-NATURAL-NO-T7_PRE-SPLASH_ROLLBACK_{timestamp}"
    )
    candidate_root = SAFE_ROOT / (
        f"VX1_1_SPLASH_SYNTH_A_CANDIDATE_{timestamp}"
    )

    SAFE_ROOT.mkdir(parents=True, exist_ok=True)
    rollback_root.mkdir(parents=True, exist_ok=False)

    try:
        copy_files(rollback_root, original_bytes)
        write_manifest(rollback_root, original_bytes)
        (rollback_root / "BASELINE_INFO.txt").write_text(
            "PROJECT CITADEL NO-T7 PRE-SPLASH ROLLBACK\n"
            "===========================================\n\n"
            "Exact five-file state immediately before "
            "VX1.1-SPLASH-SYNTH-A.\n\n"
            f"Protected input baseline: {baseline}\n"
            f"Saved: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Repository: {Path.cwd()}\n",
            encoding="utf-8",
        )
        rollback_zip, rollback_zip_hash = make_zip(rollback_root)
    except Exception as error:
        print(f"ERROR: Could not create protected rollback: {error}")
        print("Active source was not changed.")
        return 1

    print()
    print(f"ROLLBACK FOLDER: {rollback_root}")
    print(f"ROLLBACK ZIP:    {rollback_zip}")
    print(f"ROLLBACK SHA256: {rollback_zip_hash}")

    LOCAL_BACKUP.parent.mkdir(parents=True, exist_ok=True)

    if LOCAL_BACKUP.exists():
        if sha256_file(LOCAL_BACKUP) != EXPECTED_SHOCK:
            print(
                "ERROR: Existing local Shock.c backup is not the exact "
                f"baseline: {LOCAL_BACKUP}"
            )
            return 1
    else:
        LOCAL_BACKUP.write_bytes(original_bytes[SHOCK])

    diff = "".join(
        difflib.unified_diff(
            original_text.splitlines(keepends=True),
            patched_text.splitlines(keepends=True),
            fromfile="src/MacSrc/Shock.c (no-T7 baseline)",
            tofile="src/MacSrc/Shock.c (VX1.1 splash synth A)",
        )
    )

    temporary = SHOCK.with_name(
        SHOCK.name + ".VX1_1_SPLASH_SYNTH_A_TEMP"
    )

    try:
        write_source(temporary, patched_text)

        if MARKER not in read_source(temporary)[0]:
            raise RuntimeError(
                "temporary Shock.c marker verification failed"
            )

        os.replace(temporary, SHOCK)
    except Exception as error:
        temporary.unlink(missing_ok=True)
        print(f"ERROR: Could not install patched Shock.c: {error}")
        return 1

    for path in (SETUP, MAINLOOP, WRAPPER, GAMEWRAP):
        if sha256_file(path) != hashes[path]:
            print(
                "ERROR: A source file other than Shock.c changed. "
                f"Restore from {rollback_root}"
            )
            return 1

    installed_text, _newline = read_source(SHOCK)

    if installed_text.count(MARKER) != 1:
        print(
            "ERROR: Installed marker verification failed. "
            f"Restore from {rollback_root}"
        )
        return 1

    DIFF_PATH.write_text(diff, encoding="utf-8")
    candidate_bytes = {path: path.read_bytes() for path in FILES}
    candidate_root.mkdir(parents=True, exist_ok=False)

    try:
        copy_files(candidate_root, candidate_bytes)
        write_manifest(candidate_root, candidate_bytes)

        diff_dir = candidate_root / "DIFFS"
        diff_dir.mkdir(parents=True, exist_ok=True)
        (diff_dir / DIFF_PATH.name).write_text(
            diff,
            encoding="utf-8",
        )

        (candidate_root / "BASELINE_INFO.txt").write_text(
            "PROJECT CITADEL VX1.1-SPLASH-SYNTH-A\n"
            "======================================\n\n"
            "Only src/MacSrc/Shock.c changed.\n"
            "setup.c, mainloop.c, wrapper.c, and gamewrap.c remain "
            "byte-identical to the protected no-T7 baseline.\n\n"
            "Dedicated SD log:\n"
            f"  {LOG_NAME}\n\n"
            f"Protected input baseline: {baseline}\n"
            f"Sealed: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Repository: {Path.cwd()}\n",
            encoding="utf-8",
        )

        candidate_zip, candidate_zip_hash = make_zip(candidate_root)
    except Exception as error:
        print(
            "ERROR: Patch is installed, but candidate sealing failed: "
            f"{error}"
        )
        print(f"Rollback remains at: {rollback_root}")
        return 1

    INSTALL_RECORD.write_text(
        "PROJECT CITADEL VX1.1-SPLASH-SYNTH-A\n"
        f"Installed: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Input baseline: {baseline}\n"
        f"Rollback folder: {rollback_root}\n"
        f"Candidate folder: {candidate_root}\n"
        f"Baseline Shock SHA256: {EXPECTED_SHOCK}\n"
        f"Candidate Shock SHA256: {sha256_file(SHOCK)}\n"
        "Only Shock.c was modified.\n",
        encoding="utf-8",
    )

    print()
    print("============================================================")
    print("VX1.1-SPLASH-SYNTH-A INSTALLED AND SEALED")
    print(f"MODIFIED ONLY:    {SHOCK}")
    print(f"NEW SHOCK SHA256: {sha256_file(SHOCK)}")
    print(f"ROLLBACK FOLDER:  {rollback_root}")
    print(f"ROLLBACK ZIP:     {rollback_zip}")
    print(f"CANDIDATE FOLDER: {candidate_root}")
    print(f"CANDIDATE ZIP:    {candidate_zip}")
    print(f"CANDIDATE SHA256: {candidate_zip_hash}")
    print(f"DIFF:             {DIFF_PATH}")
    print(f"3DS LOG:          {LOG_NAME}")
    print("============================================================")
    return 0


def rollback_patch() -> int:
    verify_root()

    if not LOCAL_BACKUP.is_file():
        print(f"ERROR: Missing local rollback source: {LOCAL_BACKUP}")
        return 1

    if sha256_file(LOCAL_BACKUP) != EXPECTED_SHOCK:
        print("ERROR: Local rollback Shock.c is not exact baseline.")
        return 1

    temporary = SHOCK.with_name(SHOCK.name + ".ROLLBACK_TEMP")
    shutil.copyfile(LOCAL_BACKUP, temporary)

    if sha256_file(temporary) != EXPECTED_SHOCK:
        temporary.unlink(missing_ok=True)
        print("ERROR: Temporary rollback verification failed.")
        return 1

    os.replace(temporary, SHOCK)

    print("============================================================")
    print("VX1.1-SPLASH-SYNTH-A ROLLED BACK")
    print(f"RESTORED: {SHOCK}")
    print(f"SHA256:   {sha256_file(SHOCK)}")
    print("The other four source files were never modified.")
    print("============================================================")
    return 0


def main() -> int:
    try:
        if len(sys.argv) == 1:
            return apply_patch()

        if len(sys.argv) == 2 and sys.argv[1].lower() == "rollback":
            return rollback_patch()

        print(
            "Usage:\n"
            "  python apply_vx1_1_splash_synth_a.py\n"
            "  python apply_vx1_1_splash_synth_a.py rollback"
        )
        return 2

    except RuntimeError as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
