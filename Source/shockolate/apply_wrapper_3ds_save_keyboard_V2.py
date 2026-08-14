#!/usr/bin/env python3
# Create a 3DS-native-save-keyboard version of Shockolate's wrapper.c.
#
# Usage from the Shockolate repository root:
#     python apply_wrapper_3ds_save_keyboard_V1.py
#
# Or provide wrapper.c explicitly:
#     python apply_wrapper_3ds_save_keyboard_V1.py src/GameSrc/wrapper.c
#
# The original file is not overwritten. The generated file is written beside
# it as wrapper_3DS_save_keyboard_V2.c.

from __future__ import annotations

import sys
from pathlib import Path


def fail(message: str) -> None:
    raise SystemExit(f"ERROR: {message}")


def main() -> None:
    source = (
        Path(sys.argv[1])
        if len(sys.argv) > 1
        else Path("src/GameSrc/wrapper.c")
    )

    if not source.is_file():
        fail(f"Could not find wrapper.c at: {source}")

    text = source.read_text(encoding="utf-8")

    marker = "PROJECT CITADEL SAVE KEYBOARD V2"
    if marker in text:
        fail("This wrapper.c already contains the V2 save-keyboard patch.")

    include_anchor = '#include "newmfd.h"\n'
    include_block = '''#if defined(__3DS__) || defined(_3DS)
#include <3ds/applets/swkbd.h>
#warning "PROJECT CITADEL SAVE KEYBOARD V2: native save titles are ACTIVE"
#endif

#include "newmfd.h"
'''

    if include_anchor not in text:
        fail('Could not find the include anchor: #include "newmfd.h"')
    text = text.replace(include_anchor, include_block, 1)

    handler_anchor = "uchar textlist_handler(uiEvent *ev, uchar butid) {\n"

    helper = r'''#if defined(__3DS__) || defined(_3DS)

static bool citadel_3ds_edit_save_title(opt_textlist_state *st,
                                        uchar butid,
                                        uchar line)
{
    SwkbdState keyboard;
    SwkbdButton button;
    char entered[SAVE_COMMENT_LEN];
    char filtered[SAVE_COMMENT_LEN];
    char *target;
    size_t source_index;
    size_t destination_index = 0;
    int max_length;

    if (st == NULL || line >= st->numblocks)
        return true;

    target = textlist_string(st, line);
    entered[0] = '\0';

    if ((st->initmask & (1U << line)) && target[0] != '\0') {
        strncpy(entered, target, sizeof(entered) - 1);
        entered[sizeof(entered) - 1] = '\0';
    }

    max_length = (int)st->blocksiz - 1;
    if (max_length <= 0 || max_length >= (int)sizeof(entered))
        max_length = (int)sizeof(entered) - 1;

    swkbdInit(&keyboard, SWKBD_TYPE_WESTERN, 2, max_length);
    swkbdSetHintText(&keyboard, "Enter save game name");
    swkbdSetInitialText(&keyboard, entered);
    swkbdSetValidation(&keyboard, SWKBD_NOTEMPTY_NOTBLANK, 0, 0);
    swkbdSetFeatures(&keyboard, SWKBD_DEFAULT_QWERTY);
    swkbdSetButton(&keyboard, SWKBD_BUTTON_LEFT, "Cancel", false);
    swkbdSetButton(&keyboard, SWKBD_BUTTON_RIGHT, "Save", true);

    button = swkbdInputText(&keyboard, entered, sizeof(entered));

    kb_flush();
    mouse_flush();

    if (button != SWKBD_BUTTON_CONFIRM)
        return true;

    for (source_index = 0;
         entered[source_index] != '\0' &&
         destination_index < (size_t)max_length;
         ++source_index) {
        unsigned char character = (unsigned char)entered[source_index];

        if (character >= 32 && character <= 126)
            filtered[destination_index++] = (char)character;
    }

    filtered[destination_index] = '\0';

    if (filtered[0] == '\0')
        return true;

    textlist_cleanup(st);

    st->currstring = (char)line;
    st->index = -1;
    st->modified = TRUE;
    st->initmask |= (1U << line);

    strncpy(target, filtered, (size_t)max_length);
    target[max_length] = '\0';

    /*
     * Redraw the edited line in Shock's software framebuffer. The normal
     * main-loop presentation immediately displays it; calling SDLDraw()
     * directly here would unnecessarily couple wrapper.c to Shock.c.
     */
    textlist_draw_line(st, line, butid);

    st->dealfunc(butid, line);
    return true;
}

#endif

'''

    if handler_anchor not in text:
        fail("Could not find textlist_handler().")
    text = text.replace(handler_anchor, helper + handler_anchor, 1)

    branch_anchor = '''        if (st->editable && (st->editmask & (1 << line))) {
'''
    branch_replacement = '''        if (st->editable && (st->editmask & (1 << line))) {
#if defined(__3DS__) || defined(_3DS)
            /*
             * On 3DS, clicking a save slot opens the native lower-screen
             * keyboard and saves immediately after confirmation.
             */
            if (ev->subtype & MOUSE_LEFT)
                return citadel_3ds_edit_save_title(st, butid, line);
#endif
'''

    if branch_anchor not in text:
        fail("Could not find the editable text-list mouse branch.")
    text = text.replace(branch_anchor, branch_replacement, 1)

    required = (
        marker,
        "citadel_3ds_edit_save_title",
        "swkbdInputText",
        "st->dealfunc(butid, line)",
    )
    missing = [item for item in required if item not in text]
    if missing:
        fail(f"Sanity check failed; missing: {missing}")

    output = source.with_name("wrapper_3DS_save_keyboard_V2.c")
    output.write_text(text, encoding="utf-8", newline="\n")

    print(f"Created: {output}")
    print("Original wrapper.c was left unchanged.")
    print("Rename the generated file to wrapper.c before compiling.")


if __name__ == "__main__":
    main()
