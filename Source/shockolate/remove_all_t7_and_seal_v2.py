#!/usr/bin/env python3
"""
Project Citadel: remove T7 completely from the current VX1-NATURAL baseline (V2).

Run from the Shockolate repository root:

    python remove_all_t7_and_seal.py

Required starting state:
  * Exact VX0 Shock.c, mainloop.c, wrapper.c, and gamewrap.c.
  * setup.c produced by make_vx1_natural_newgame.py:
      - VX1-NATURAL marker present
      - T7 arming call inactive
      - dormant T7 declaration/comment shell still present

What this script does:
  1. Verifies the exact current idle-T7 baseline.
  2. Stages precise reverse-T7 edits in memory.
  3. Refuses to write unless all expected edits match exactly.
  4. Checks all five staged files for T7 remnants.
  5. Saves the current five-file state as a timestamped rollback folder/ZIP.
  6. Atomically installs the no-T7 setup.c, mainloop.c, and wrapper.c.
  7. Verifies Shock.c and gamewrap.c remained byte-identical.
  8. Seals the resulting five-file no-T7 baseline in a second folder/ZIP.
  9. Writes SHA-256 manifests, provenance, and unified diffs.

No splash, GPU, APT, HOME, audio, input, layout, Save, Load, Continue, or
New Game behavior is added by this script. It only reverses the T7 diff.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import difflib
import hashlib
import os
import re
import shutil
import stat
import sys
import zipfile


SAFE_ROOT = Path("/c/Projects/Citadel-Baselines")

SHOCK = Path("src/MacSrc/Shock.c")
SETUP = Path("src/GameSrc/setup.c")
MAINLOOP = Path("src/GameSrc/mainloop.c")
WRAPPER = Path("src/GameSrc/wrapper.c")
GAMEWRAP = Path("src/GameSrc/gamewrap.c")

FILES = [SHOCK, SETUP, MAINLOOP, WRAPPER, GAMEWRAP]

EXPECTED_CURRENT_HASHES = {
    SHOCK:
        "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724",
    MAINLOOP:
        "8fb3331b9e3e0fe1532417237d5adb8a8820508dc5f7e4f9d389870d31e9a369",
    WRAPPER:
        "d027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2",
    GAMEWRAP:
        "c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30",
}

NATURAL_MARKER = (
    "PROJECT CITADEL VX1-NATURAL: use the original New Game path."
)
ACTIVE_ARM_CALL = "citadel_3ds_arm_newgame_home_t7();"

T7_CODE_PATTERNS = [
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

    if "\r\n" in text:
        newline = "\r\n"
    else:
        newline = "\n"

    return text, newline


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
            f"{label}: expected exactly one matching block, found {count}"
        )

    return text.replace(old, new, 1)


def remove_setup_t7(text: str, nl: str) -> str:
    declaration = adapt(
        """#if defined(__3DS__) || defined(_3DS)
void citadel_3ds_arm_newgame_home_t7(void);
#endif

""",
        nl,
    )

    natural_t7_shell = adapt(
        """#if defined(__3DS__) || defined(_3DS)
    /*
     * PROJECT CITADEL T7:
     * Arm only after the original New Game path has finished every normal
     * quest-variable, version, HUD, and setup-state assignment. Continue and
     * every user-selected Load path remain completely untouched.
     */
    /* PROJECT CITADEL VX1-NATURAL: use the original New Game path. */
#endif
""",
        nl,
    )

    text = replace_once(
        text,
        declaration,
        "",
        "setup.c T7 declaration",
    )
    text = replace_once(
        text,
        natural_t7_shell,
        "",
        "setup.c dormant T7 arming shell",
    )

    return text


def remove_mainloop_t7(text: str, nl: str) -> str:
    declarations = adapt(
        """#if defined(__3DS__) || defined(_3DS)
void citadel_3ds_newgame_home_t7_pre_frame(void);
void citadel_3ds_newgame_home_t7_post_frame(void);
#endif

""",
        nl,
    )

    warning = adapt(
        '#warning "PROJECT CITADEL T7: exact numbered-slot UI lifecycle hook is ACTIVE"\n',
        nl,
    )

    local_variable = adapt(
        "    short loop_at_frame_start;\n",
        nl,
    )

    loop_capture = adapt(
        "        loop_at_frame_start = _current_loop;\n",
        nl,
    )

    pre_frame = adapt(
        """
#if defined(__3DS__) || defined(_3DS)
        /*
         * A real wrapper selection is handled before the active game frame is
         * rendered. T7 performs its queued Save/Load selection here, after the
         * wrapper has already remained open and visible for a complete frame.
         */
        if (loop_at_frame_start == GAME_LOOP && gPlayingGame)
            citadel_3ds_newgame_home_t7_pre_frame();
#endif
""",
        nl,
    )

    post_frame = adapt(
        """
#if defined(__3DS__) || defined(_3DS)
        /*
         * Advance T7 only after a frame that both began and ended in GAME_LOOP.
         * This guarantees that each real Save/Load wrapper is presented for a
         * complete frame before its genuine selection callback is invoked.
         */
        if (loop_at_frame_start == GAME_LOOP &&
            _current_loop == GAME_LOOP &&
            gPlayingGame) {
            citadel_3ds_newgame_home_t7_post_frame();
        }
#endif
""",
        nl,
    )

    replacements = [
        (declarations, "", "mainloop.c T7 declarations"),
        (warning, "", "mainloop.c T7 warning"),
        (local_variable, "", "mainloop.c T7 local variable"),
        (loop_capture, "", "mainloop.c T7 frame-start capture"),
        (pre_frame, "", "mainloop.c T7 pre-frame hook"),
        (post_frame, "", "mainloop.c T7 post-frame hook"),
    ]

    for old, new, label in replacements:
        text = replace_once(text, old, new, label)

    return text


def remove_wrapper_t7(text: str, nl: str) -> str:
    stdio_include = adapt("#include <stdio.h>\n", nl)

    extra_prototypes = adapt(
        """void wrapper_start(void (*init)(void));
void load_dealfunc(uchar butid, uchar index);
void save_dealfunc(uchar butid, uchar index);
""",
        nl,
    )

    load_result_state = adapt(
        """
#if defined(__3DS__) || defined(_3DS)
static errtype citadel_3ds_t7_last_load_result = ERR_NOEFFECT;
#endif
""",
        nl,
    )

    t7_load_dealfunc = adapt(
        """void load_dealfunc(uchar butid, uchar index) {
    errtype load_result;

    begin_wait();
    Poke_SaveName(index);
    // Spew(DSRC_EDITOR_Save,("attempting to load from %s\\n",save_game_name));

    load_result = load_game(save_game_name);
#if defined(__3DS__) || defined(_3DS)
    citadel_3ds_t7_last_load_result = load_result;
#endif
    if (load_result != OK) {
""",
        nl,
    )

    original_load_dealfunc = adapt(
        """void load_dealfunc(uchar butid, uchar index) {
    begin_wait();
    Poke_SaveName(index);
    // Spew(DSRC_EDITOR_Save,("attempting to load from %s\\n",save_game_name));

    if (load_game(save_game_name) != OK) {
""",
        nl,
    )

    text = replace_once(
        text,
        stdio_include,
        "",
        "wrapper.c T7 stdio include",
    )
    text = replace_once(
        text,
        extra_prototypes,
        "",
        "wrapper.c T7 callback prototypes",
    )
    text = replace_once(
        text,
        load_result_state,
        "",
        "wrapper.c T7 load-result state",
    )
    text = replace_once(
        text,
        t7_load_dealfunc,
        original_load_dealfunc,
        "wrapper.c T7 load_dealfunc instrumentation",
    )

    block_start = adapt(
        """

#if defined(__3DS__) || defined(_3DS)

#warning "PROJECT CITADEL NEW GAME HOME NORMALIZER T7 is ACTIVE"
""",
        nl,
    )

    block_end = adapt(
        """
#endif

#define NEEDED_DISKSPACE 630000
""",
        nl,
    )

    start_index = text.find(block_start)

    if start_index < 0:
        raise RuntimeError(
            "wrapper.c T7 implementation: start marker was not found"
        )

    end_index = text.find(block_end, start_index)

    if end_index < 0:
        raise RuntimeError(
            "wrapper.c T7 implementation: end marker was not found"
        )

    if text.find(block_start, start_index + 1) >= 0:
        raise RuntimeError(
            "wrapper.c T7 implementation: multiple start markers found"
        )

    replacement = adapt(
        """

#define NEEDED_DISKSPACE 630000
""",
        nl,
    )

    text = (
        text[:start_index]
        + replacement
        + text[end_index + len(block_end):]
    )

    return text


def strip_c_comments_preserve_lines(text: str) -> str:
    """
    Remove // and /* */ comments while preserving strings, character
    literals, newlines, and line numbering.

    This prevents harmless historical prose comments from being mistaken for
    executable T7 code while still scanning #warning text, log strings,
    identifiers, macros, and filenames.
    """
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

        if state in ("string", "char"):
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
            continue

    return "".join(result)


def find_remnants(
    staged: dict[Path, str],
) -> list[str]:
    findings: list[str] = []

    for path, text in staged.items():
        searchable = strip_c_comments_preserve_lines(text)
        original_lines = text.splitlines()

        for line_number, line in enumerate(
            searchable.splitlines(),
            start=1,
        ):
            for pattern in T7_CODE_PATTERNS:
                match = pattern.search(line)

                if match is None:
                    continue

                original_line = (
                    original_lines[line_number - 1].strip()
                    if line_number <= len(original_lines)
                    else line.strip()
                )

                findings.append(
                    f"{path}:{line_number}: matched "
                    f"{match.group(0)!r}: {original_line}"
                )
                break

    return findings


def copy_tree_files(
    destination_root: Path,
    contents: dict[Path, bytes],
) -> None:
    for relative_path, data in contents.items():
        destination = destination_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

        if sha256_file(destination) != sha256_bytes(data):
            raise RuntimeError(
                f"copy verification failed for {destination}"
            )


def write_manifest(
    root: Path,
    contents: dict[Path, bytes],
) -> None:
    lines = [
        f"{sha256_bytes(contents[path])}  {path.as_posix()}"
        for path in FILES
    ]

    (root / "SHA256SUMS.txt").write_text(
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


def main() -> int:
    if not Path("src/MacSrc").is_dir() or not Path("src/GameSrc").is_dir():
        print("ERROR: Run this from the Shockolate repository root.")
        return 1

    print("============================================================")
    print("PROJECT CITADEL VX1-NATURAL: REMOVE ALL T7 — V2")
    print("============================================================")
    print()
    print("Verifying current idle-T7 baseline...")

    for path in FILES:
        if not path.is_file():
            print(f"ERROR: Missing required file: {path}")
            return 1

    for path, expected_hash in EXPECTED_CURRENT_HASHES.items():
        actual_hash = sha256_file(path)
        status = "OK" if actual_hash == expected_hash else "WRONG"
        print(f"{status:5} {actual_hash}  {path}")

        if actual_hash != expected_hash:
            print()
            print(
                "ERROR: Current tree does not match the sealed starting "
                "baseline. Nothing changed."
            )
            return 1

    original_text: dict[Path, str] = {}
    newline_style: dict[Path, str] = {}
    original_bytes: dict[Path, bytes] = {}

    for path in FILES:
        original_bytes[path] = path.read_bytes()
        text, newline = read_source(path)
        original_text[path] = text
        newline_style[path] = newline

    setup_text = original_text[SETUP]

    if NATURAL_MARKER not in setup_text:
        print("ERROR: VX1-NATURAL marker is missing from setup.c.")
        print("Nothing changed.")
        return 1

    active_arm_lines = [
        number
        for number, line in enumerate(setup_text.splitlines(), start=1)
        if ACTIVE_ARM_CALL in line
        and not line.lstrip().startswith(("//", "/*", "*"))
    ]

    if active_arm_lines:
        print(
            "ERROR: T7 arming call is active at setup.c line(s): "
            f"{active_arm_lines}"
        )
        print("Nothing changed.")
        return 1

    print(f"CHECK {sha256_file(SETUP)}  {SETUP}")
    print("OK    VX1-NATURAL marker present")
    print("OK    T7 arming call is inactive")

    try:
        staged_text = dict(original_text)
        staged_text[SETUP] = remove_setup_t7(
            staged_text[SETUP],
            newline_style[SETUP],
        )
        staged_text[MAINLOOP] = remove_mainloop_t7(
            staged_text[MAINLOOP],
            newline_style[MAINLOOP],
        )
        staged_text[WRAPPER] = remove_wrapper_t7(
            staged_text[WRAPPER],
            newline_style[WRAPPER],
        )
    except RuntimeError as error:
        print()
        print(f"ERROR: {error}")
        print("Nothing changed.")
        return 1

    if staged_text[SHOCK] != original_text[SHOCK]:
        print("ERROR: Shock.c changed during staging.")
        return 1

    if staged_text[GAMEWRAP] != original_text[GAMEWRAP]:
        print("ERROR: gamewrap.c changed during staging.")
        return 1

    remnants = find_remnants(staged_text)

    if remnants:
        print()
        print("ERROR: T7 remnants remain in staged source:")
        for finding in remnants:
            print(f"  {finding}")
        print("Nothing changed.")
        return 1

    changed_files = [
        path
        for path in FILES
        if staged_text[path] != original_text[path]
    ]

    expected_changed = [SETUP, MAINLOOP, WRAPPER]

    if changed_files != expected_changed:
        print()
        print("ERROR: Unexpected changed-file set:")
        for path in changed_files:
            print(f"  {path}")
        print("Nothing changed.")
        return 1

    staged_bytes = {
        path: staged_text[path].encode("utf-8")
        for path in FILES
    }

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    rollback_name = (
        f"VX1-NATURAL-IDLE-T7_ROLLBACK_{timestamp}"
    )
    rollback_root = SAFE_ROOT / rollback_name

    no_t7_name = (
        f"VX1-NATURAL-NO-T7_BASELINE_{timestamp}"
    )
    no_t7_root = SAFE_ROOT / no_t7_name

    if rollback_root.exists() or no_t7_root.exists():
        print("ERROR: Timestamped baseline destination already exists.")
        return 1

    SAFE_ROOT.mkdir(parents=True, exist_ok=True)
    rollback_root.mkdir(parents=True, exist_ok=False)

    try:
        copy_tree_files(rollback_root, original_bytes)
        write_manifest(rollback_root, original_bytes)

        (rollback_root / "BASELINE_INFO.txt").write_text(
            "PROJECT CITADEL VX1-NATURAL IDLE-T7 ROLLBACK\n"
            "============================================\n\n"
            "This is the exact five-file state immediately before all "
            "remaining dormant T7 code was removed.\n\n"
            f"Saved: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Source repository: {Path.cwd()}\n",
            encoding="utf-8",
        )

        rollback_zip, rollback_zip_hash = make_zip(rollback_root)
    except Exception as error:
        print()
        print(f"ERROR: Could not create rollback baseline: {error}")
        print("Active source was not changed.")
        return 1

    print()
    print(f"ROLLBACK SEALED: {rollback_root}")
    print(f"ROLLBACK ZIP:    {rollback_zip}")
    print(f"ROLLBACK SHA256: {rollback_zip_hash}")

    diffs: dict[Path, str] = {}

    for path in expected_changed:
        diffs[path] = "".join(
            difflib.unified_diff(
                original_text[path].splitlines(keepends=True),
                staged_text[path].splitlines(keepends=True),
                fromfile=f"{path.as_posix()} (idle T7)",
                tofile=f"{path.as_posix()} (no T7)",
            )
        )

    temporary_files: dict[Path, Path] = {}

    try:
        for path in expected_changed:
            temporary = path.with_name(path.name + ".NO_T7_TEMP")
            write_source(temporary, staged_text[path])
            temporary_files[path] = temporary

            if temporary.read_bytes() != staged_bytes[path]:
                raise RuntimeError(
                    f"temporary byte verification failed for {path}"
                )

        for path in expected_changed:
            os.replace(temporary_files[path], path)

    except Exception as error:
        for temporary in temporary_files.values():
            temporary.unlink(missing_ok=True)

        print()
        print(f"ERROR while installing no-T7 sources: {error}")
        print("Attempting automatic rollback...")

        rollback_failed = False

        for path in expected_changed:
            source = rollback_root / path
            try:
                shutil.copyfile(source, path)
            except Exception as rollback_error:
                rollback_failed = True
                print(
                    f"ROLLBACK ERROR {path}: {rollback_error}"
                )

        if rollback_failed:
            print(
                "CRITICAL: Automatic rollback was incomplete. "
                f"Use the sealed folder: {rollback_root}"
            )
        else:
            print("Automatic rollback completed.")

        return 1

    print()
    print("===== ACTIVE NO-T7 VERIFICATION =====")

    active_text: dict[Path, str] = {}
    active_bytes: dict[Path, bytes] = {}

    for path in FILES:
        active_bytes[path] = path.read_bytes()
        text, _newline = read_source(path)
        active_text[path] = text
        print(f"{sha256_file(path)}  {path}")

    active_remnants = find_remnants(active_text)

    if active_remnants:
        print()
        print("ERROR: T7 remnants found after installation:")
        for finding in active_remnants:
            print(f"  {finding}")
        print(f"Restore from: {rollback_root}")
        return 1

    if sha256_file(SHOCK) != EXPECTED_CURRENT_HASHES[SHOCK]:
        print("ERROR: Shock.c no longer matches the starting baseline.")
        return 1

    if sha256_file(GAMEWRAP) != EXPECTED_CURRENT_HASHES[GAMEWRAP]:
        print("ERROR: gamewrap.c no longer matches the starting baseline.")
        return 1

    no_t7_root.mkdir(parents=True, exist_ok=False)

    try:
        copy_tree_files(no_t7_root, active_bytes)
        write_manifest(no_t7_root, active_bytes)

        diff_root = no_t7_root / "DIFFS"
        diff_root.mkdir(parents=True, exist_ok=True)

        for path, diff in diffs.items():
            diff_name = path.as_posix().replace("/", "__") + ".diff"
            (diff_root / diff_name).write_text(
                diff,
                encoding="utf-8",
            )

        (no_t7_root / "BASELINE_INFO.txt").write_text(
            "PROJECT CITADEL VX1-NATURAL NO-T7 BASELINE\n"
            "===========================================\n\n"
            "Starting point:\n"
            "  Sealed VX1-NATURAL baseline with T7 permanently IDLE.\n\n"
            "Only changes:\n"
            "  setup.c: removed dormant T7 declaration and arming shell.\n"
            "  mainloop.c: removed T7 declarations, warning, state capture, "
            "and pre/post-frame hooks.\n"
            "  wrapper.c: removed T7-only include/prototypes/load-result "
            "instrumentation and complete T7 state machine.\n\n"
            "Unchanged:\n"
            "  Shock.c and gamewrap.c are byte-identical to the input "
            "baseline.\n"
            "  No splash, GPU, HOME, APT, audio, input, layout, Save, Load, "
            "Continue, or New Game fix was added.\n\n"
            f"Sealed: {datetime.now().isoformat(timespec='seconds')}\n"
            f"Source repository: {Path.cwd()}\n\n"
            "Iteration rule:\n"
            "  Run the full four-path cold-boot matrix. If behavior is worse "
            "or less consistent, restore the five files from the rollback "
            "folder/ZIP and reassess.\n",
            encoding="utf-8",
        )

        no_t7_zip, no_t7_zip_hash = make_zip(no_t7_root)

    except Exception as error:
        print()
        print(f"ERROR: Active source is no-T7, but sealing failed: {error}")
        print(
            "The active no-T7 files remain installed. "
            f"Rollback is available at: {rollback_root}"
        )
        return 1

    Path("VX1_NATURAL_NO_T7_INSTALLED.txt").write_text(
        "PROJECT CITADEL VX1-NATURAL NO-T7\n"
        f"Installed: {datetime.now().isoformat(timespec='seconds')}\n"
        f"Rollback: {rollback_root}\n"
        f"Baseline: {no_t7_root}\n"
        "Full four-path cold-boot matrix required.\n",
        encoding="utf-8",
    )

    print()
    print("============================================================")
    print("VX1-NATURAL NO-T7 INSTALLED AND SEALED")
    print(f"ROLLBACK FOLDER: {rollback_root}")
    print(f"ROLLBACK ZIP:    {rollback_zip}")
    print(f"NO-T7 FOLDER:    {no_t7_root}")
    print(f"NO-T7 ZIP:       {no_t7_zip}")
    print(f"NO-T7 ZIP SHA:   {no_t7_zip_hash}")
    print()
    print("T7 REMNANT SCAN: CLEAN")
    print("CHANGED FILES: setup.c, mainloop.c, wrapper.c")
    print("UNCHANGED: Shock.c, gamewrap.c")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
