#!/usr/bin/env python3

from pathlib import Path
import hashlib
import os
import sys

EXPECTED = "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724"
OUTPUT = Path("Shock_V17_SHIP_RECOVERED.c")

roots = [
    Path("."),
    Path("/c/Projects"),
    Path("/c/Users/benny/Desktop"),
]

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def replace_once(text: str, old: str, new: str, label: str):
    count = text.count(old)
    if count != 1:
        return None, f"{label}: expected 1 anchor, found {count}"
    return text.replace(old, new, 1), None

def try_build_v17(original: str):
    text = original

    # Reject files that are already later presentation experiments.
    if "PROJECT CITADEL V17-SHIP" in text:
        return text, None

    if "PROJECT CITADEL T7P:" in text:
        return None, "T7P Shock, not clean T7 baseline"

    if "GPU T7P MASK" in text or "citadel_3ds_draw_t7_mask" in text:
        return None, "contains T7P mask code"

    if "PROJECT CITADEL HOME FRAME-GATE TEST 4" in text:
        return None, "contains T4 frame-gate experiment"

    if "citadel_3ds_newgame_home_t7_pre_frame" in text:
        # Those hooks belong in mainloop/wrapper, not normally Shock.c.
        return None, "unexpected T7 state-machine hooks in Shock.c"

    text, error = replace_once(
        text,
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"\n',
        '#warning "PROJECT CITADEL AUDIO SUSPEND HOTFIX V2: '
        'NDSP close/deferred reopen hook is ACTIVE"\n'
        '#warning "PROJECT CITADEL V17-SHIP: T7 HOME fix + '
        'persistent gameplay layout are ACTIVE"\n',
        "V17 warning",
    )
    if error:
        return None, error

    text, error = replace_once(
        text,
        """/*
 * The in-game wrapper (save/load/options) remains in GAME_LOOP, so its own
 * visibility flag is also part of layout selection.
 */
extern uchar wrapper_panel_on;
""",
        """/*
 * The in-game wrapper (save/load/options) remains in GAME_LOOP. Its
 * visibility still gates gameplay controls, but V17-SHIP deliberately does
 * not change the player-selected Legacy/Dual presentation.
 */
extern uchar wrapper_panel_on;
""",
        "wrapper layout comment",
    )
    if error:
        return None, error

    text, error = replace_once(
        text,
        """static bool citadel_3ds_use_split_layout(void)
{
    return !citadel_legacy_view_override &&
           citadel_3ds_gameplay_controls_active();
}
""",
        """static bool citadel_3ds_use_split_layout(void)
{
    /*
     * V17-SHIP layout policy:
     *   - Initial setup/configuration/load-list screens remain Legacy.
     *   - GAME_LOOP begins in Dual unless SELECT has requested Legacy.
     *   - Pause/options/save/load wrappers preserve that selected layout.
     *
     * Wrapper visibility continues to disable gameplay controls through
     * citadel_3ds_gameplay_controls_active(); it no longer changes layout.
     */
    return !citadel_legacy_view_override &&
           _current_loop == GAME_LOOP;
}
""",
        "split-layout policy",
    )
    if error:
        return None, error

    text, error = replace_once(
        text,
        """        /*
         * Pause, options, save/load, menus, and SELECT legacy view must
         * actively submit a black bottom-screen scene. Clearing a target
         * without beginning that scene leaves the preceding gameplay frame
         * visible on the physical LCD.
         */
""",
        """        /*
         * Initial menus and SELECT Legacy view must actively submit a black
         * bottom-screen scene. GAME_LOOP wrappers preserve the player-selected
         * layout, so a genuine T7 Save/Load wrapper remains on the lower LCD.
         * Clearing a target without beginning that scene leaves the preceding
         * gameplay frame visible on the physical LCD.
         */
""",
        "bottom-scene comment",
    )
    if error:
        return None, error

    text, error = replace_once(
        text,
        """    /*
     * Never leave stale, disjointed interface fragments on the lower LCD
     * while menus or the SELECT legacy view are shown on top.
     */
""",
        """    /*
     * Never leave stale, disjointed interface fragments on the lower LCD
     * during initial menus or SELECT Legacy view. GAME_LOOP wrappers preserve
     * the selected layout and therefore remain confined to the lower LCD.
     */
""",
        "stale-bottom comment",
    )
    if error:
        return None, error

    return text, None

candidates = []
seen = set()

for root in roots:
    if not root.exists():
        continue

    for directory, subdirs, filenames in os.walk(root):
        subdirs[:] = [
            name for name in subdirs
            if name.lower() not in {
                "build", ".git", "cmakefiles",
                "node_modules", "ftp_deploy"
            }
        ]

        for filename in filenames:
            lower = filename.lower()

            if not lower.endswith(".c"):
                continue

            if "shock" not in lower:
                continue

            path = Path(directory) / filename

            try:
                resolved = path.resolve()
            except OSError:
                resolved = path

            if resolved in seen:
                continue

            seen.add(resolved)
            candidates.append(path)

print(f"Scanning {len(candidates)} Shock candidates...")
print()

results = []

for path in candidates:
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue

    rebuilt, error = try_build_v17(original)

    if rebuilt is None:
        results.append((path, error))
        continue

    data = rebuilt.encode("utf-8")
    digest = sha256(data)

    if digest == EXPECTED:
        OUTPUT.write_bytes(data)

        print("============================================================")
        print("EXACT V17 SHOCK RECOVERED")
        print(f"Baseline: {path}")
        print(f"Output:   {OUTPUT}")
        print(f"SHA256:   {digest}")
        print("============================================================")
        sys.exit(0)

    results.append((path, f"patched hash was {digest}"))

print("ERROR: No local candidate produced the exact V17 hash.")
print()
print("Most relevant candidates examined:")

shown = 0
for path, reason in results:
    if shown >= 30:
        break

    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue

    if (
        "PROJECT CITADEL V16.1" in text
        or "AUDIO SUSPEND HOTFIX V2" in text
        or "T7P" in text
    ):
        print(f"  {path}")
        print(f"    {reason}")
        shown += 1

sys.exit(1)
