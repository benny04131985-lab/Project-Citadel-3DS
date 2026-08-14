#!/usr/bin/env bash
set -euo pipefail

SHOCK_BASE="src/MacSrc/Shock_BEFORE_HOME_T4.c"
SETUP_BASE="src/GameSrc/setup_BEFORE_NEWGAME_HOME_T3.c"
MAINLOOP_BASE="src/GameSrc/mainloop_BEFORE_HOME_T4.c"
WRAPPER_BASE="wrapper_BASELINE_RECOVERED.c"
GAMEWRAP_T2="gamewrap_T2_SELFLOAD_PRESERVED.c"

for file in \
  "$SHOCK_BASE" \
  "$SETUP_BASE" \
  "$MAINLOOP_BASE" \
  "$WRAPPER_BASE" \
  "$GAMEWRAP_T2"
do
    if [[ ! -f "$file" ]]; then
        echo "ERROR: missing $file"
        exit 1
    fi
done

echo "===== VALIDATING CANDIDATES ====="

grep -q "PROJECT CITADEL V16.1" "$SHOCK_BASE" || {
    echo "ERROR: Shock baseline lacks V16.1 marker"
    exit 1
}

if grep -qE \
  'HOME FRAME-GATE TEST 4|NEWGAME_HOME_T7|T7P|V17-SHIP|V18-SHIP|V20-SHIP' \
  "$SHOCK_BASE"; then
    echo "ERROR: Shock baseline contains later experiment code"
    exit 1
fi

grep -q "PROJECT CITADEL KEYBOARD V3" "$SETUP_BASE" || {
    echo "ERROR: setup baseline lacks Keyboard V3 marker"
    exit 1
}

if grep -qE \
  'NEWGAME_HOME_T[3-9]|NEW GAME.*TEST [3-9]|T7|T7P' \
  "$SETUP_BASE"; then
    echo "ERROR: setup baseline contains later New Game code"
    exit 1
fi

grep -q "PROJECT CITADEL V4: unique mainloop" "$MAINLOOP_BASE" || {
    echo "ERROR: mainloop baseline lacks V4 marker"
    exit 1
}

if grep -qE \
  'HOME FRAME-GATE TEST 4|NEWGAME_HOME_T[4-9]|citadel_3ds_newgame_home_t7' \
  "$MAINLOOP_BASE"; then
    echo "ERROR: mainloop baseline contains T4/T7/later code"
    exit 1
fi

grep -q "PROJECT CITADEL SAVE KEYBOARD V2" "$WRAPPER_BASE" || {
    echo "ERROR: wrapper baseline lacks Save Keyboard V2 marker"
    exit 1
}

if grep -qE \
  'NEWGAME_HOME_T[5-9]|HOME NORMALIZER T6|PROJECT CITADEL T7|T7P' \
  "$WRAPPER_BASE"; then
    echo "ERROR: wrapper baseline contains later normalizer code"
    exit 1
fi

grep -q "PROJECT CITADEL NEW GAME HOME SELF-LOAD TEST 2" "$GAMEWRAP_T2" || {
    echo "ERROR: preserved gamewrap is not T2"
    exit 1
}

BACKUP="FAILED_EXACT_T7_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP"

cp src/MacSrc/Shock.c "$BACKUP/"
cp src/GameSrc/setup.c "$BACKUP/"
cp src/GameSrc/mainloop.c "$BACKUP/"
cp src/GameSrc/wrapper.c "$BACKUP/"
cp src/GameSrc/gamewrap.c "$BACKUP/"

cp "$SHOCK_BASE" src/MacSrc/Shock.c
cp "$SETUP_BASE" src/GameSrc/setup.c
cp "$MAINLOOP_BASE" src/GameSrc/mainloop.c
cp "$WRAPPER_BASE" src/GameSrc/wrapper.c
cp "$GAMEWRAP_T2" src/GameSrc/gamewrap.c

echo
echo "INSTALLED ACTUAL T2 HYBRID"
echo "Backup: $BACKUP"

sha256sum \
  src/MacSrc/Shock.c \
  src/GameSrc/setup.c \
  src/GameSrc/mainloop.c \
  src/GameSrc/wrapper.c \
  src/GameSrc/gamewrap.c
