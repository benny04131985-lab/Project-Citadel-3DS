#!/usr/bin/env python3
"""
Patch the R2C finalizer so intentional untracked GitHub Release_Drafts/ entries
are permitted, while every tracked modification and every other untracked path
still blocks the handoff.

Run from:
    C:/Projects/Citadel_Citro3D_DEV/Source/shockolate
"""
from __future__ import annotations

import py_compile
import shutil
from pathlib import Path

TARGET = Path("finalize_Project_Citadel_R2C_HOTFIX_and_FORK_NATIVE.py")
BACKUP = Path("finalize_Project_Citadel_R2C_HOTFIX_and_FORK_NATIVE.PRE_ALLOW_RELEASE_DRAFTS.py")

OLD_DOC = "  - The GitHub repo must be clean before this script changes it."
NEW_DOC = (
    "  - The GitHub repo must have no tracked changes and no untracked paths "
    "outside intentional Release_Drafts/."
)

OLD_FUNCTION = '''def git_clean(repo: Path) -> bool:\n    result = run(["git", "-C", str(repo), "status", "--porcelain"], check=False)\n    return result.returncode == 0 and not result.stdout.strip()\n'''

NEW_FUNCTION = '''ALLOWED_UNTRACKED_GITHUB_PREFIXES = ("Release_Drafts/",)\n\n\ndef git_blocking_status(repo: Path) -> list[str]:\n    \"\"\"Return status lines that make the repository unsafe to modify.\n\n    Existing local milestone entries under Release_Drafts/ are intentionally\n    unpublished and may remain untracked. Tracked edits anywhere—including\n    inside Release_Drafts—and all other untracked paths remain blocking.\n    \"\"\"\n    result = run(\n        [\n            "git",\n            "-C",\n            str(repo),\n            "status",\n            "--porcelain=v1",\n            "--untracked-files=all",\n        ],\n        check=False,\n    )\n    if result.returncode != 0:\n        return [f"git status failed with exit code {result.returncode}"]\n\n    blocking: list[str] = []\n    for raw_line in result.stdout.splitlines():\n        line = raw_line.rstrip("\\r\\n")\n        if not line:\n            continue\n        if len(line) < 4:\n            blocking.append(line)\n            continue\n\n        status = line[:2]\n        path = line[3:]\n        allowed_untracked = status == "??" and any(\n            path.startswith(prefix) for prefix in ALLOWED_UNTRACKED_GITHUB_PREFIXES\n        )\n        if not allowed_untracked:\n            blocking.append(line)\n    return blocking\n\n\ndef git_clean(repo: Path) -> bool:\n    return not git_blocking_status(repo)\n'''

OLD_UPDATE_ERROR = '''    if not git_clean(GITHUB_ROOT):\n        status = run(["git", "-C", str(GITHUB_ROOT), "status", "--short", "--branch"], check=False)\n        raise FinalizeError(\n            "Citadel_3D_GITHUB has uncommitted changes. Commit or preserve them before running this script.\\n"\n            + status.stdout.strip()\n        )\n'''

NEW_UPDATE_ERROR = '''    blocking = git_blocking_status(GITHUB_ROOT)\n    if blocking:\n        raise FinalizeError(\n            "Citadel_3D_GITHUB has blocking changes. Intentional untracked "\n            "Release_Drafts/ entries are allowed; the following paths are not:\\n"\n            + "\\n".join(blocking)\n        )\n'''

OLD_MAIN_ERROR = '''        if not git_clean(GITHUB_ROOT):\n            status = run(["git", "-C", str(GITHUB_ROOT), "status", "--short", "--branch"], check=False)\n            raise FinalizeError("GitHub repository is not clean:\\n" + status.stdout.strip())\n'''

NEW_MAIN_ERROR = '''        blocking = git_blocking_status(GITHUB_ROOT)\n        if blocking:\n            raise FinalizeError(\n                "GitHub repository has blocking changes. Intentional untracked "\n                "Release_Drafts/ entries are allowed; the following paths are not:\\n"\n                + "\\n".join(blocking)\n            )\n'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"ERROR: expected exactly one {label} anchor, found {count}.")
    return text.replace(old, new, 1)


def main() -> None:
    if not TARGET.is_file():
        raise SystemExit(f"ERROR: missing target: {TARGET.resolve()}")
    if BACKUP.exists():
        raise SystemExit(f"ERROR: backup already exists; refusing to overwrite: {BACKUP.resolve()}")

    original = TARGET.read_text(encoding="utf-8")
    if "ALLOWED_UNTRACKED_GITHUB_PREFIXES" in original:
        raise SystemExit("ERROR: ALLOW_RELEASE_DRAFTS patch already appears installed.")

    patched = original
    patched = replace_once(patched, OLD_DOC, NEW_DOC, "safety-doc")
    patched = replace_once(patched, OLD_FUNCTION, NEW_FUNCTION, "git-clean function")
    patched = replace_once(patched, OLD_UPDATE_ERROR, NEW_UPDATE_ERROR, "update_github cleanliness check")
    patched = replace_once(patched, OLD_MAIN_ERROR, NEW_MAIN_ERROR, "main cleanliness check")

    shutil.copy2(TARGET, BACKUP)
    TARGET.write_text(patched, encoding="utf-8", newline="\n")

    try:
        py_compile.compile(str(TARGET), doraise=True)
    except Exception:
        shutil.copy2(BACKUP, TARGET)
        raise

    reread = TARGET.read_text(encoding="utf-8")
    required = (
        'ALLOWED_UNTRACKED_GITHUB_PREFIXES = ("Release_Drafts/",)',
        "def git_blocking_status(repo: Path) -> list[str]:",
        "Release_Drafts/ entries are allowed",
    )
    missing = [marker for marker in required if marker not in reread]
    if missing:
        shutil.copy2(BACKUP, TARGET)
        raise SystemExit("ERROR: post-write verification failed: " + ", ".join(missing))

    print("============================================================")
    print("R2C FINALIZER ALLOW_RELEASE_DRAFTS PATCH: SUCCESS")
    print("============================================================")
    print(f"Patched: {TARGET.resolve()}")
    print(f"Backup:  {BACKUP.resolve()}")
    print("Allowed: untracked Release_Drafts/... files only")
    print("Blocked: all tracked changes and all other untracked paths")
    print("No checkpoint, release candidate, commit, tag, branch, or push was created.")


if __name__ == "__main__":
    main()
