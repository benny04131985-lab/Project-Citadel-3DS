#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path.cwd()
source = root / "src" / "GameSrc" / "audiolog.c"
output = root / "src" / "GameSrc" / "audiolog_3DS_V12F.c"

if not source.is_file():
    print(
        "ERROR: src/GameSrc/audiolog.c was not found. "
        "Run this script from the Shockolate project root.",
        file=sys.stderr,
    )
    raise SystemExit(1)

text = source.read_text(encoding="utf-8")

if "PROJECT CITADEL AUDIOLOG V12F" in text:
    print("ERROR: audiolog.c already contains V12F.", file=sys.stderr)
    raise SystemExit(1)

if "PROJECT CITADEL AUDIOLOG V12E" not in text:
    print(
        "ERROR: V12F expects the working V12E audiolog.c.",
        file=sys.stderr,
    )
    raise SystemExit(1)

text = text.replace(
    '#warning "PROJECT CITADEL AUDIOLOG V12E: Afile speech streaming is ACTIVE"',
    '#warning "PROJECT CITADEL AUDIOLOG V12F: speech stream and device resume are ACTIVE"',
    1,
)

stop_start = text.find("void audiolog_stop(")
if stop_start < 0:
    print("ERROR: audiolog_stop() was not found.", file=sys.stderr)
    raise SystemExit(1)

stop_end = text.find("\nerrtype ", stop_start)
if stop_end < 0:
    stop_end = text.find("\nvoid ", stop_start + 1)
if stop_end < 0:
    stop_end = len(text)

stop_function = text[stop_start:stop_end]

if "SDL_PauseAudioDevice(device, 1);" not in stop_function:
    print(
        "ERROR: audiolog_stop() does not contain the expected pause call.",
        file=sys.stderr,
    )
    raise SystemExit(1)

if "VOICE DEVICE RESUME" in stop_function:
    print("ERROR: resume hotfix is already present.", file=sys.stderr)
    raise SystemExit(1)

anchor = "    curr_alog = -1;\n"
if anchor not in stop_function:
    print(
        "ERROR: Could not locate the end of audiolog_stop().",
        file=sys.stderr,
    )
    raise SystemExit(1)

resume_block = (
    "#if defined(__3DS__) || defined(_3DS)\n"
    "    /* Resume the one shared SDL device after freeing speech. */\n"
    "    SDL_PauseAudioDevice(device, 0);\n"
    "\n"
    "    citadel_v12e_voice_log(\n"
    "        \"VOICE DEVICE RESUME\",\n"
    "        citadel_v12e_voice_email,\n"
    "        SDL_GetAudioDeviceStatus(device),\n"
    "        0);\n"
    "#endif\n"
    "\n"
)

stop_function = stop_function.replace(
    anchor,
    resume_block + anchor,
    1,
)

text = text[:stop_start] + stop_function + text[stop_end:]
output.write_text(text, encoding="utf-8", newline="\n")

print(f"Created: {output.relative_to(root)}")
print("Original V12E audiolog.c was left unchanged.")
print("Install with:")
print(
    "  mv src/GameSrc/audiolog_3DS_V12F.c "
    "src/GameSrc/audiolog.c"
)
