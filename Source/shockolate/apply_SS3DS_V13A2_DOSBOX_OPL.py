#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path.cwd()
source = root / "src" / "MusicSrc" / "MusicDevice.c"
output = root / "src" / "MusicSrc" / "MusicDevice_3DS_V13A2.c"

if not source.is_file():
    print(
        "ERROR: src/MusicSrc/MusicDevice.c was not found. "
        "Run this from the Shockolate project root.",
        file=sys.stderr,
    )
    raise SystemExit(1)

text = source.read_text(encoding="utf-8")

if "PROJECT CITADEL MUSICDEVICE V13A2" in text:
    print("ERROR: MusicDevice.c already contains V13A2.", file=sys.stderr)
    raise SystemExit(1)

if "PROJECT CITADEL MUSICDEVICE V13A" not in text:
    print(
        "ERROR: V13A2 expects the current V13A MusicDevice.c.",
        file=sys.stderr,
    )
    raise SystemExit(1)

old_marker = (
    '#warning "PROJECT CITADEL MUSICDEVICE V13A: '
    'native OPL synthesis is ACTIVE"'
)
new_marker = (
    '#warning "PROJECT CITADEL MUSICDEVICE V13A2: '
    'lightweight DOSBox OPL core is ACTIVE"'
)

old_block = """    /* Keep Shockolate's already-proven ADLMIDI emulator for V13A. */
    adl_switchEmulator(adl, ADLMIDI_EMU_NUKED_174);

    adl_setNumChips(adl, 1);
"""

new_block = """    /*
     * The Nuked core is too expensive to synthesize inside the 3DS
     * real-time audio callback. Use libADLMIDI's lighter DOSBox core.
     */
    if (adl_switchEmulator(adl, ADLMIDI_EMU_DOSBOX) != 0)
    {
        adl_close(adl);
        return -1;
    }

    adl_setNumChips(adl, 1);
"""

if old_marker not in text:
    print("ERROR: V13A compiler marker was not found.", file=sys.stderr)
    raise SystemExit(1)

if old_block not in text:
    print("ERROR: V13A Nuked OPL block was not found.", file=sys.stderr)
    raise SystemExit(1)

text = text.replace(old_marker, new_marker, 1)
text = text.replace(old_block, new_block, 1)

output.write_text(text, encoding="utf-8", newline="\n")

print(f"Created: {output.relative_to(root)}")
print("Original MusicDevice.c was left unchanged.")
print("Install with:")
print(
    "  mv src/MusicSrc/MusicDevice_3DS_V13A2.c "
    "src/MusicSrc/MusicDevice.c"
)
