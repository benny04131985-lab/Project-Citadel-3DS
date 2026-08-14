#!/usr/bin/env python3
# Project Citadel controlled VX0/VX1 restart utility.
# Run from the Shockolate repository root.

from pathlib import Path
from datetime import datetime
import difflib
import hashlib
import os
import shutil
import sys
import zipfile

EXPECTED = {
    Path('src/MacSrc/Shock.c'): '05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724',
    Path('src/GameSrc/setup.c'): '236b2517ad37b87e88e4232bca712aaf8910f51205e130f13d0069cfe2f4ba82',
    Path('src/GameSrc/mainloop.c'): '8fb3331b9e3e0fe1532417237d5adb8a8820508dc5f7e4f9d389870d31e9a369',
    Path('src/GameSrc/wrapper.c'): 'd027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2',
    Path('src/GameSrc/gamewrap.c'): 'c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30',
}

TOKENS = {
    Path('src/MacSrc/Shock.c'): ('shock',),
    Path('src/GameSrc/setup.c'): ('setup',),
    Path('src/GameSrc/mainloop.c'): ('mainloop',),
    Path('src/GameSrc/wrapper.c'): ('wrapper',),
    Path('src/GameSrc/gamewrap.c'): ('gamewrap',),
}

ROOTS = [
    Path('.'),
    Path('/c/Projects/Citadel-Recovery-PROBFUCKED'),
    Path('/c/Projects'),
    Path('/c/Users/benny/Downloads'),
    Path('/c/Users/benny/Desktop'),
    Path('/c/$Recycle.Bin'),
]

PACKAGE = Path('VX0_BASELINE_SOURCE')
PACKAGE_ZIP = Path('PROJECT_CITADEL_VX0_BASELINE_SOURCE.zip')
VX1_MARKER = 'PROJECT CITADEL VX1.0: startup synthetic HOME primer is ACTIVE'
SKIP = {'.git', 'build', 'node_modules', '__pycache__', 'vx0_baseline_source'}


def sha256_file(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def ensure_root():
    if not Path('src/MacSrc').is_dir() or not Path('src/GameSrc').is_dir():
        raise RuntimeError('Run this from the Shockolate repository root.')


def candidate_name(name, tokens):
    low = Path(name).name.lower()
    return low.endswith('.c') and any(token in low for token in tokens)


def preference(label):
    low = label.replace('\\', '/').lower()
    if 'project_citadel_v17_ship.zip' in low:
        rank = 0
    elif 'from_zip_archives' in low:
        rank = 1
    elif 'before_exact_v17_recovery' in low:
        rank = 2
    elif 'citadel-recovery-probfucked' in low:
        rank = 3
    elif '/downloads/' in low:
        rank = 4
    else:
        rank = 5
    return rank, len(low), low


def filesystem_matches(expected_hash, tokens):
    matches = []
    seen = set()
    for root in ROOTS:
        if not root.exists():
            continue
        for directory, subdirs, filenames in os.walk(root):
            directory_path = Path(directory)
            subdirs[:] = [
                name for name in subdirs
                if name.lower() not in SKIP
                and not (directory_path / name).is_symlink()
            ]
            for filename in filenames:
                if not candidate_name(filename, tokens):
                    continue
                path = directory_path / filename
                try:
                    resolved = str(path.resolve())
                    if resolved in seen or not path.is_file():
                        continue
                    seen.add(resolved)
                    if sha256_file(path) == expected_hash:
                        matches.append((str(path), path.read_bytes()))
                except (OSError, PermissionError):
                    pass
    return matches


def zip_matches(expected_hash, tokens):
    matches = []
    archives = [
        Path('/c/Users/benny/Downloads/PROJECT_CITADEL_V17_SHIP.zip'),
        Path('/c/Projects/Citadel-Recovery-PROBFUCKED/LIVE_AND_RECYCLE_FILES/c/Users/benny/Downloads/PROJECT_CITADEL_V17_SHIP.zip'),
    ]
    for archive in archives:
        if not archive.is_file():
            continue
        try:
            with zipfile.ZipFile(archive, 'r') as zf:
                for info in zf.infolist():
                    if info.is_dir() or info.file_size > 2 * 1024 * 1024:
                        continue
                    if not candidate_name(info.filename, tokens):
                        continue
                    data = zf.read(info)
                    if sha256_bytes(data) == expected_hash:
                        matches.append((f'{archive}::{info.filename}', data))
        except (OSError, PermissionError, zipfile.BadZipFile):
            pass
    return matches


def verify_paths(paths, prefix=None):
    okay = True
    for target, expected_hash in paths.items():
        path = target if prefix is None else prefix / target
        if not path.is_file():
            print(f'MISSING {path}')
            okay = False
            continue
        actual = sha256_file(path)
        status = 'OK' if actual == expected_hash else 'WRONG'
        print(f'{status:5} {actual}  {path}')
        okay = okay and actual == expected_hash
    return okay


def prepare_vx0():
    ensure_root()
    selected = {}
    print('============================================================')
    print('PROJECT CITADEL VX0 BASELINE ASSEMBLER')
    print('============================================================')

    for target, expected_hash in EXPECTED.items():
        print(f'\nLocating exact {target.name}\nSHA256: {expected_hash}')
        candidates = filesystem_matches(expected_hash, TOKENS[target])
        candidates.extend(zip_matches(expected_hash, TOKENS[target]))
        candidates.sort(key=lambda item: preference(item[0]))
        if not candidates:
            print(f'ERROR: No exact match found for {target}.')
            return 1
        selected[target] = candidates[0]
        print(f'Exact matches found: {len(candidates)}')
        print(f'Selected: {candidates[0][0]}')

    if PACKAGE.exists():
        shutil.rmtree(PACKAGE)

    manifest = []
    provenance = ['PROJECT CITADEL VX0 BASELINE PROVENANCE', '']
    for target, expected_hash in EXPECTED.items():
        destination = PACKAGE / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        label, data = selected[target]
        destination.write_bytes(data)
        if sha256_file(destination) != expected_hash:
            print(f'ERROR: Output verification failed: {destination}')
            return 1
        manifest.append(f'{expected_hash}  {target.as_posix()}')
        provenance += [target.as_posix(), f'  SHA256: {expected_hash}', f'  FROM: {label}', '']

    (PACKAGE / 'SHA256SUMS.txt').write_text('\n'.join(manifest) + '\n', encoding='utf-8')
    (PACKAGE / 'PROVENANCE.txt').write_text('\n'.join(provenance), encoding='utf-8')

    if PACKAGE_ZIP.exists():
        PACKAGE_ZIP.unlink()
    with zipfile.ZipFile(PACKAGE_ZIP, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in PACKAGE.rglob('*'):
            if path.is_file():
                zf.write(path, path.relative_to(PACKAGE.parent))

    print('\n============================================================')
    print('VX0 BASELINE SOURCE ASSEMBLED')
    print(f'FOLDER:  {PACKAGE.resolve()}')
    print(f'ARCHIVE: {PACKAGE_ZIP.resolve()}')
    print('ACTIVE SOURCE TREE WAS NOT MODIFIED')
    print('============================================================')
    return 0


def install_vx0():
    ensure_root()
    print('===== VERIFYING PACKAGED VX0 =====')
    if not verify_paths(EXPECTED, PACKAGE):
        print('ERROR: Run prepare-vx0 first. Nothing changed.')
        return 1
    for target in EXPECTED:
        if not target.is_file():
            print(f'ERROR: Active target missing: {target}')
            return 1

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = Path(f'BEFORE_VX0_INSTALL_{stamp}')
    for target in EXPECTED:
        destination = backup / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(target, destination)
    with (backup / 'SHA256SUMS_BEFORE.txt').open('w', encoding='utf-8') as f:
        for target in EXPECTED:
            f.write(f'{sha256_file(target)}  {target.as_posix()}\n')

    for target, expected_hash in EXPECTED.items():
        source = PACKAGE / target
        temporary = target.with_name(target.name + '.VX0_TEMP')
        shutil.copy2(source, temporary)
        if sha256_file(temporary) != expected_hash:
            temporary.unlink(missing_ok=True)
            print(f'ERROR: Temporary verification failed: {target}')
            return 1
        os.replace(temporary, target)
        print(f'INSTALLED {target}')

    print('\n===== FINAL VX0 VERIFICATION =====')
    if not verify_paths(EXPECTED):
        print(f'ERROR: Final verification failed. Backup: {backup}')
        return 1

    Path('VX0_INSTALLED_SHA256SUMS.txt').write_text(
        ''.join(f'{digest}  {target.as_posix()}\n' for target, digest in EXPECTED.items()),
        encoding='utf-8')
    Path('VX0_BASELINE_ID.txt').write_text(
        'PROJECT CITADEL VX0\nExact V17-SHIP four-file set plus original non-T2 gamewrap.c\n'
        f"Installed: {datetime.now().isoformat(timespec='seconds')}\n",
        encoding='utf-8')

    print('\n============================================================')
    print('PROJECT CITADEL VX0 INSTALLED AND SEALED')
    print(f'ROLLBACK BACKUP: {backup}')
    print('============================================================')
    return 0


def replace_once(text, old, new, label):
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected one anchor, found {count}')
    return text.replace(old, new, 1)


def apply_vx1():
    ensure_root()
    print('===== VERIFYING IMMUTABLE VX0 BASE =====')
    if not verify_paths(EXPECTED):
        print('ERROR: VX1.0 applies only to pristine VX0. Nothing changed.')
        return 1

    shock = Path('src/MacSrc/Shock.c')
    original = shock.read_text(encoding='utf-8')
    if VX1_MARKER in original:
        print('ERROR: VX1.0 is already present.')
        return 1

    warning_anchor = '#warning "PROJECT CITADEL V16.1: launch polish candidate is ACTIVE"\n'
    warning_new = warning_anchor + '#warning "PROJECT CITADEL VX1.0: startup synthetic HOME primer is ACTIVE"\n'

    state_anchor = 'static Uint32 citadel_v16_splash_until = 0;\n'
    state_new = state_anchor + '''

/* VX1.0: one startup synthetic GPU ownership round trip. */
#define CITADEL_VX1_PRIMER_MIN_SPLASH_FRAMES 8
static unsigned int citadel_vx1_splash_frames = 0;
static bool citadel_vx1_primer_attempted = false;
static bool citadel_vx1_primer_complete = false;
static bool citadel_vx1_post_primer_frame_seen = false;
'''

    proto_anchor = 'static bool citadel_v16_present_splash(void);\n'
    proto_new = proto_anchor + '''static void citadel_vx1_log(const char *fmt, ...);
static bool citadel_vx1_run_startup_primer(void);
'''

    helper_anchor = 'static bool citadel_v16_present_splash(void)\n{'
    helper = r'''static void citadel_vx1_log(const char *fmt, ...)
{
    FILE *file;
    va_list args;

    file = fopen("VX1_STARTUP_PRIMER.log", "a");
    if (file == NULL)
        return;

    va_start(args, fmt);
    vfprintf(file, fmt, args);
    va_end(args);
    fputc('\n', file);
    fflush(file);
    fclose(file);
}

static bool citadel_vx1_run_startup_primer(void)
{
    GSPGPU_CaptureInfo capture_info;
    Result save_result;
    Result capture_result;
    Result release_result;
    Result acquire_result;
    Result restore_result;
    bool owned_before;
    bool owned_after;
    u16 top_width = 0;
    u16 top_height = 0;
    u16 bottom_width = 0;
    u16 bottom_height = 0;
    u8 *top_left;
    u8 *top_right;
    u8 *bottom;

    if (citadel_vx1_primer_attempted)
        return citadel_vx1_primer_complete;

    citadel_vx1_primer_attempted = true;

    /* The calling splash frame has ended. Fully drain it first. */
    C3D_FrameSync();
    gspWaitForVBlank();

    owned_before = gspHasGpuRight();
    top_left = gfxGetFramebuffer(GFX_TOP, GFX_LEFT, &top_width, &top_height);
    top_right = gfxGetFramebuffer(GFX_TOP, GFX_RIGHT, NULL, NULL);
    bottom = gfxGetFramebuffer(GFX_BOTTOM, GFX_LEFT, &bottom_width, &bottom_height);

    citadel_vx1_log(
        "VX1.0 PRIMER BEGIN build=%s %s splash_frames=%u gpu_right=%d "
        "top=%ux%u bottom=%ux%u topL=%p topR=%p bottom=%p",
        __DATE__, __TIME__, citadel_vx1_splash_frames,
        owned_before ? 1 : 0,
        (unsigned int)top_width, (unsigned int)top_height,
        (unsigned int)bottom_width, (unsigned int)bottom_height,
        (void *)top_left, (void *)top_right, (void *)bottom);

    v5_log("VX1.0 PRIMER BEGIN splash_frames=%u gpu_right=%d",
           citadel_vx1_splash_frames, owned_before ? 1 : 0);

    if (!owned_before) {
        citadel_vx1_log("VX1.0 PRIMER ABORTED: application does not own GPU right");
        v5_log("VX1.0 PRIMER ABORTED: application does not own GPU right");
        return false;
    }

    memset(&capture_info, 0, sizeof(capture_info));
    save_result = GSPGPU_SaveVramSysArea();
    capture_result = GSPGPU_ImportDisplayCaptureInfo(&capture_info);
    release_result = GSPGPU_ReleaseRight();
    acquire_result = GSPGPU_AcquireRight(0);
    restore_result = GSPGPU_RestoreVramSysArea();

    gspWaitForVBlank();
    owned_after = gspHasGpuRight();

    citadel_vx1_primer_complete =
        R_SUCCEEDED(save_result) &&
        R_SUCCEEDED(capture_result) &&
        R_SUCCEEDED(release_result) &&
        R_SUCCEEDED(acquire_result) &&
        R_SUCCEEDED(restore_result) &&
        owned_after;

    citadel_vx1_log(
        "VX1.0 PRIMER RESULTS save=0x%08lX capture=0x%08lX "
        "release=0x%08lX acquire=0x%08lX restore=0x%08lX "
        "gpu_right_after=%d complete=%d",
        (unsigned long)save_result, (unsigned long)capture_result,
        (unsigned long)release_result, (unsigned long)acquire_result,
        (unsigned long)restore_result,
        owned_after ? 1 : 0, citadel_vx1_primer_complete ? 1 : 0);

    v5_log(
        "VX1.0 PRIMER RESULTS save=0x%08lX capture=0x%08lX "
        "release=0x%08lX acquire=0x%08lX restore=0x%08lX complete=%d",
        (unsigned long)save_result, (unsigned long)capture_result,
        (unsigned long)release_result, (unsigned long)acquire_result,
        (unsigned long)restore_result,
        citadel_vx1_primer_complete ? 1 : 0);

    return citadel_vx1_primer_complete;
}

''' + helper_anchor

    frame_anchor = '''    C3D_FrameEnd(0);
    ++citadel_gpu_presented_frames;

    if (!draw_ok)
        ++citadel_gpu_draw_failures;
'''
    frame_new = '''    C3D_FrameEnd(0);
    ++citadel_gpu_presented_frames;
    ++citadel_vx1_splash_frames;

    if (citadel_vx1_splash_frames == 1) {
        remove("VX1_STARTUP_PRIMER.log");
        citadel_vx1_log("PROJECT CITADEL VX1.0 START build=%s %s",
                        __DATE__, __TIME__);
    }

    if (!citadel_vx1_primer_attempted &&
        citadel_vx1_splash_frames >= CITADEL_VX1_PRIMER_MIN_SPLASH_FRAMES) {
        (void)citadel_vx1_run_startup_primer();
    } else if (citadel_vx1_primer_complete &&
               !citadel_vx1_post_primer_frame_seen &&
               citadel_vx1_splash_frames > CITADEL_VX1_PRIMER_MIN_SPLASH_FRAMES) {
        citadel_vx1_post_primer_frame_seen = true;
        citadel_vx1_log(
            "VX1.0 POST-PRIMER SPLASH FRAME COMPLETE frame=%u gpu_right=%d",
            citadel_vx1_splash_frames, gspHasGpuRight() ? 1 : 0);
        v5_log("VX1.0 POST-PRIMER SPLASH FRAME COMPLETE frame=%u",
               citadel_vx1_splash_frames);
    }

    if (!draw_ok)
        ++citadel_gpu_draw_failures;
'''

    try:
        patched = replace_once(original, warning_anchor, warning_new, 'compiler marker')
        patched = replace_once(patched, state_anchor, state_new, 'VX1 state')
        patched = replace_once(patched, proto_anchor, proto_new, 'VX1 prototypes')
        patched = replace_once(patched, helper_anchor, helper, 'VX1 helper')
        patched = replace_once(patched, frame_anchor, frame_new, 'splash post-frame hook')
    except RuntimeError as exc:
        print(f'ERROR: {exc}')
        return 1

    if patched.count(VX1_MARKER) != 1:
        print('ERROR: VX1 marker verification failed.')
        return 1

    backup = Path('BEFORE_VX1_0/src/MacSrc/Shock.c')
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists() and sha256_file(backup) != EXPECTED[shock]:
        print(f'ERROR: Existing VX1 backup is not pristine VX0: {backup}')
        return 1
    if not backup.exists():
        shutil.copy2(shock, backup)

    diff = ''.join(difflib.unified_diff(
        original.splitlines(keepends=True),
        patched.splitlines(keepends=True),
        fromfile='src/MacSrc/Shock.c (VX0)',
        tofile='src/MacSrc/Shock.c (VX1.0)'))

    temporary = shock.with_name(shock.name + '.VX1_TEMP')
    temporary.write_text(patched, encoding='utf-8')
    if VX1_MARKER not in temporary.read_text(encoding='utf-8'):
        temporary.unlink(missing_ok=True)
        print('ERROR: Temporary VX1 verification failed.')
        return 1
    os.replace(temporary, shock)

    Path('VX1_0_STARTUP_PRIMER.diff').write_text(diff, encoding='utf-8')
    new_hash = sha256_file(shock)
    Path('VX1_0_INSTALLED.txt').write_text(
        'PROJECT CITADEL VX1.0 STARTUP PRIMER\n'
        f"Installed: {datetime.now().isoformat(timespec='seconds')}\n"
        f'VX0 Shock SHA256: {EXPECTED[shock]}\n'
        f'VX1 Shock SHA256: {new_hash}\n'
        'Other four active source files remain exact VX0.\n',
        encoding='utf-8')

    print('\n============================================================')
    print('PROJECT CITADEL VX1.0 STARTUP PRIMER INSTALLED')
    print(f'MODIFIED ONLY: {shock}')
    print(f'VX1 SHA256:    {new_hash}')
    print(f'VX0 BACKUP:    {backup}')
    print('DIFF:          VX1_0_STARTUP_PRIMER.diff')
    print('3DS LOG:       VX1_STARTUP_PRIMER.log')
    print('============================================================')
    return 0


def rollback_vx1():
    ensure_root()
    shock = Path('src/MacSrc/Shock.c')
    backup = Path('BEFORE_VX1_0/src/MacSrc/Shock.c')
    expected = EXPECTED[shock]
    if not backup.is_file() or sha256_file(backup) != expected:
        print('ERROR: Exact VX0 rollback backup is unavailable.')
        return 1
    temporary = shock.with_name(shock.name + '.VX0_RESTORE_TEMP')
    shutil.copy2(backup, temporary)
    if sha256_file(temporary) != expected:
        temporary.unlink(missing_ok=True)
        print('ERROR: Rollback verification failed.')
        return 1
    os.replace(temporary, shock)
    print(f'RESTORED EXACT VX0: {shock}')
    print(f'SHA256: {sha256_file(shock)}')
    return 0


def usage():
    print('Usage: python citadel_vx_control.py COMMAND')
    print('Commands: prepare-vx0 install-vx0 verify-vx0 apply-vx1 rollback-vx1')
    return 2


def main():
    if len(sys.argv) != 2:
        return usage()
    actions = {
        'prepare-vx0': prepare_vx0,
        'install-vx0': install_vx0,
        'verify-vx0': lambda: 0 if verify_paths(EXPECTED) else 1,
        'apply-vx1': apply_vx1,
        'rollback-vx1': rollback_vx1,
    }
    action = actions.get(sys.argv[1].lower())
    if action is None:
        return usage()
    try:
        return action()
    except RuntimeError as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
