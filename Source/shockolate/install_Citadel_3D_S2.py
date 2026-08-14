#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import hashlib
import os
import shutil
import sys
import zipfile

ROOT = Path.cwd().resolve()
PACKAGE = Path(__file__).resolve().parent
PATCHED = PACKAGE / "PATCHED"
SAFE_ROOT = ROOT.parent.parent / "_PROTECTED_BASELINES"

FILES = {
    Path("src/GameSrc/render.c"): (
        "b76c3c1d27ea2b70e81fac100fd70297d13947a0fed64290985aa8d0a7527d80",
        "a7bfa101167707331bbe33bc0e5a366ef787cabebfb262d0c398fade5831aefd",
    ),
    Path("src/GameSrc/frmain.c"): (
        "b2900ea73c6ee360763fcdbd87da98a244d7d360c199bd61e95c6980882bc470",
        "e0aeb587cd0c62f86328316ac5cd12ca0d36455d4460ebf92102fac7a188def5",
    ),
    Path("src/GameSrc/frsetup.c"): (
        "39bd7b76cb0a80785271fcbba3aefec7fbdc9fecaba45dfae13d9ca7adc01edd",
        "4481cc5731f8b39fe10c52c1dd540bbec8aee4d4694d22e906253b65990269cf",
    ),
    Path("src/MacSrc/Shock.c"): (
        "9bac2edb2b9471a1e9b5f27186bc0d5247f23221da43e6031ab200be7d4500bc",
        "692c9c49e9d6d9963c452c66002cbd7bfce2bf17a067f687c301966579e95ed4",
    ),
}

GUARDS = {
    Path("CMakeLists.txt"):
        "bb688fe9c7041fb86e9f23d8fcd04979816267a73c1d7414199edabc4b62cec3",
    Path("src/GameSrc/setup.c"):
        "a7f04a76b0948b6774c81b4dcd384e2b24832578df1fb988def8f65d5edf4115",
}

S1 = "PROJECT CITADEL 3D S1: zero-parallax dual-eye transport is ACTIVE"
S2 = "PROJECT CITADEL 3D S2: true dual-camera world stereo is ACTIVE"


def die(message: str) -> None:
    print(f"\nERROR: {message}", file=sys.stderr)
    print("No project files were changed.", file=sys.stderr)
    raise SystemExit(1)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def section(text: str, start: str, end: str) -> str:
    i = text.find(start)
    j = text.find(end, i + len(start)) if i >= 0 else -1
    if i < 0 or j < 0:
        die("Could not isolate the existing APT/audio hook.")
    return text[i:j]


def make_snapshot(folder: Path, sources: dict[Path, Path], note: str) -> None:
    folder.mkdir(parents=True, exist_ok=False)
    sums = []
    for rel, source in sources.items():
        target = folder / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        sums.append(f"{sha(target)}  {rel.as_posix()}")
    (folder / "SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    (folder / "BASELINE_INFO.txt").write_text(note.rstrip() + "\n", encoding="utf-8")


def zip_folder(folder: Path) -> Path:
    out = folder.with_suffix(".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(folder.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(folder.parent))
    return out


def main() -> int:
    if not ROOT.as_posix().lower().endswith("citadel_3d_dev/source/shockolate"):
        die(f"Run from C:/Projects/Citadel_3D_DEV/Source/shockolate\nCurrent: {ROOT}")

    for rel in list(FILES) + list(GUARDS):
        if not (ROOT / rel).is_file():
            die(f"Missing active file: {rel}")

    for rel in FILES:
        if not (PATCHED / rel).is_file():
            die(f"Patch package is incomplete: PATCHED/{rel}")

    current = {rel: sha(ROOT / rel) for rel in FILES}
    if all(current[rel] == FILES[rel][1] for rel in FILES):
        print("Citadel 3D S2 is already installed exactly; nothing changed.")
        return 0

    bad = [rel for rel in FILES if current[rel] != FILES[rel][0]]
    if bad:
        print("The following files do not match the exact known-good S1 bundle:")
        for rel in bad:
            print(f"  {rel}: {current[rel]}")
        die("Refusing to merge into an unknown source state.")

    for rel, expected in GUARDS.items():
        actual = sha(ROOT / rel)
        if actual != expected:
            die(f"Protected guard differs from supplied S1 source: {rel}\n{actual}")

    shock_before = (ROOT / "src/MacSrc/Shock.c").read_text(encoding="utf-8")
    shock_after = (PATCHED / "src/MacSrc/Shock.c").read_text(encoding="utf-8")
    if S1 not in shock_before or S2 in shock_before:
        die("Shock.c is not the expected S1 starting point.")
    if S1 not in shock_after or S2 not in shock_after:
        die("Packaged Shock.c is missing its S1/S2 identity markers.")
    if "sdmc:/3ds/SystemShock/" in shock_after or "sdmc:/3ds/systemshock/" in shock_after:
        die("Packaged Shock.c violates the mono SD wall.")

    hook_start = "static void citadel_3ds_audio_apt_hook(\n"
    hook_end = "static void citadel_3ds_audio_register_apt_hook(void)\n"
    if section(shock_before, hook_start, hook_end) != section(shock_after, hook_start, hook_end):
        die("Packaged S2 unexpectedly changes the existing APT/audio hook.")

    for rel, (_before, expected_after) in FILES.items():
        actual = sha(PATCHED / rel)
        if actual != expected_after:
            die(f"Packaged patched-file hash failed: {rel}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pre = SAFE_ROOT / f"S2_PRE_TRUE_WORLD_{stamp}"
    post = SAFE_ROOT / f"S2_TRUE_WORLD_CANDIDATE_{stamp}"
    SAFE_ROOT.mkdir(parents=True, exist_ok=True)

    snapshot_sources = {rel: ROOT / rel for rel in FILES}
    snapshot_sources.update({rel: ROOT / rel for rel in GUARDS})
    make_snapshot(
        pre,
        snapshot_sources,
        "PROJECT CITADEL 3D — exact known-good S1 files before S2 true world stereo.\n"
        "HOME/APT and audio are outside the scope of this patch.",
    )
    pre_zip = zip_folder(pre)

    temps = []
    try:
        for rel in FILES:
            target = ROOT / rel
            temp = target.with_name(target.name + ".S2_TEMP")
            shutil.copy2(PATCHED / rel, temp)
            temps.append(temp)
        for rel in FILES:
            target = ROOT / rel
            os.replace(target.with_name(target.name + ".S2_TEMP"), target)
    except Exception as error:
        for temp in temps:
            temp.unlink(missing_ok=True)
        die(f"Atomic install failed: {error}\nRestore from {pre}")

    for rel, (_before, expected_after) in FILES.items():
        if sha(ROOT / rel) != expected_after:
            die(f"Installed hash failed: {rel}\nRestore from {pre}")
    for rel, expected in GUARDS.items():
        if sha(ROOT / rel) != expected:
            die(f"Protected guard changed: {rel}\nRestore from {pre}")

    post_sources = {rel: ROOT / rel for rel in FILES}
    post_sources.update({rel: ROOT / rel for rel in GUARDS})
    make_snapshot(
        post,
        post_sources,
        "PROJECT CITADEL 3D — S2 true dual-camera world candidate.\n"
        "HUD/interface flat mask active; cyberspace intentionally remains S1-flat.",
    )
    post_zip = zip_folder(post)

    print("\n============================================================")
    print("PROJECT CITADEL 3D S2 TRUE WORLD INSTALLED")
    print("============================================================")
    print("PASS: two station-world camera passes installed")
    print("PASS: slider-driven eye separation installed")
    print("PASS: automatic flat HUD/interface mask installed")
    print("PASS: independent right-eye RGB565 transport installed")
    print("PASS: S1 fallback retained for slider zero and non-gameplay")
    print("PASS: APT/audio hook unchanged")
    print("PASS: CMakeLists.txt and setup.c unchanged")
    print(f"PRE-S2: {pre}")
    print(f"PRE-S2 ZIP: {pre_zip}")
    print(f"S2: {post}")
    print(f"S2 ZIP: {post_zip}")
    print("============================================================")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
