#!/usr/bin/env python3
from pathlib import Path
import sys

root = Path.cwd()
source = root / "CMakeLists.txt"
output = root / "CMakeLists_V14X_GPU.txt"

if not source.is_file():
    print("ERROR: CMakeLists.txt not found. Run from the project root.", file=sys.stderr)
    raise SystemExit(1)

text = source.read_text(encoding="utf-8")

if "PROJECT CITADEL V14X GPU LIBRARIES" in text:
    print("ERROR: CMakeLists.txt already contains the V14X GPU link block.", file=sys.stderr)
    raise SystemExit(1)

include_anchor = ")\n\nif(NOT WIN32)\n"
include_block = """)

# PROJECT CITADEL V14X GPU LIBRARIES
if(NINTENDO_3DS)
    include_directories(
        "$ENV{DEVKITPRO}/portlibs/3ds/include"
        "$ENV{DEVKITPRO}/libctru/include"
    )
endif()

if(NOT WIN32)
"""

if include_anchor not in text:
    print("ERROR: Could not locate the global include_directories block.", file=sys.stderr)
    raise SystemExit(1)

text = text.replace(include_anchor, include_block, 1)

target_start = text.find("target_link_libraries(systemshock")
if target_start < 0:
    print("ERROR: target_link_libraries(systemshock ...) was not found.", file=sys.stderr)
    raise SystemExit(1)

target_end = text.find("\n)\n", target_start)
if target_end < 0:
    print("ERROR: Could not locate the end of the systemshock link block.", file=sys.stderr)
    raise SystemExit(1)

target_end += len("\n)\n")

gpu_link_block = """
# PROJECT CITADEL V14X GPU LIBRARIES
if(NINTENDO_3DS)
    target_link_libraries(systemshock
        citro2d
        citro3d
        ctru
        m
    )
endif()
"""

text = text[:target_end] + gpu_link_block + text[target_end:]
output.write_text(text, encoding="utf-8", newline="\n")

print(f"Created: {output.name}")
print("Original CMakeLists.txt was left unchanged.")
print("Install with:")
print("  mv CMakeLists_V14X_GPU.txt CMakeLists.txt")
