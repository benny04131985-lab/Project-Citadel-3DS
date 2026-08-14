#!/usr/bin/env bash

ROOTS=(
  "."
  "/c/Projects/Citadel-Recovery-PROBFUCKED"
  "/c/Users/benny/Desktop"
  "/c/Users/benny/Downloads"
)

locate() {
    LABEL="$1"
    EXPECTED="$2"
    PATTERN="$3"

    echo
    echo "============================================================"
    echo "$LABEL"
    echo "EXPECTED: $EXPECTED"
    echo "============================================================"

    FOUND=0

    while IFS= read -r -d '' FILE; do
        ACTUAL=$(sha256sum "$FILE" 2>/dev/null | awk '{print $1}')

        if [ "$ACTUAL" = "$EXPECTED" ]; then
            echo "MATCH: $FILE"
            FOUND=1
        fi
    done < <(
        find "${ROOTS[@]}" \
          -type f \
          -iname "$PATTERN" \
          -not -path '*/build/*' \
          -not -path '*/Citadel-Recovery-PROBFUCKED/LIVE_AND_RECYCLE_FILES/c/Projects/Citadel-Recovery-PROBFUCKED/*' \
          -print0 2>/dev/null
    )

    if [ "$FOUND" -eq 0 ]; then
        echo "NO MATCH FOUND"
    fi
}

locate \
  "SHOCK" \
  "05a84b8e8a9c1fc8e0105f1fe1f15324bf05a42f44a7e2e07cdfe76416b0a724" \
  "Shock*.c"

locate \
  "SETUP" \
  "236b2517ad37b87e88e4232bca712aaf8910f51205e130f13d0069cfe2f4ba82" \
  "setup*.c"

locate \
  "WRAPPER" \
  "d027061772d92a50c5d06bc890b9c56c07f93ccf80b3adfbbabd6bd801b8b9c2" \
  "wrapper*.c"

locate \
  "GAMEWRAP" \
  "c764f1a1f5c16bbafd44acbe06df88e2cbf2ddcf9c82945d5041509c9f0c9e30" \
  "gamewrap*.c"
