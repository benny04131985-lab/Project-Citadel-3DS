#!/usr/bin/env bash

OUT="SURVIVING_BUILD_CANDIDATES.txt"
: > "$OUT"

find \
  /c/Projects \
  /c/Users/benny/Desktop \
  -type f \
  \( \
    -iname '*.3dsx' -o \
    -iname '*.elf' -o \
    -iname 'gamewrap.o' -o \
    -iname 'mainloop.o' -o \
    -iname 'wrapper.o' -o \
    -iname 'setup.o' -o \
    -iname 'Shock.o' -o \
    -iname 'libGAME_LIB.a' \
  \) \
  2>/dev/null |
while IFS= read -r f; do
    echo "============================================================" | tee -a "$OUT"
    echo "FILE: $f" | tee -a "$OUT"
    stat -c 'TIME: %y  SIZE: %s' "$f" 2>/dev/null | tee -a "$OUT"
    sha256sum "$f" 2>/dev/null | tee -a "$OUT"

    echo "MARKERS:" | tee -a "$OUT"

    strings "$f" 2>/dev/null |
      grep -Ei \
      'PROJECT CITADEL|V16\.1|V21A|V21E|SELF-LOAD TEST 2|NEWGAME_HOME_T2|NEWGAME_HOME_T7|HOME FRAME-GATE|unique mainloop|SAVE KEYBOARD|KEYBOARD V3|build=Jul 23 2026|mainloop build' |
      head -80 |
      tee -a "$OUT"

    echo | tee -a "$OUT"
done

echo
echo "Results written to: $OUT"
