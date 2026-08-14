#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: citadel_embed_binary.py INPUT OUTPUT SYMBOL"
        )

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    symbol = sys.argv[3]
    data = input_path.read_bytes()

    output_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    for offset in range(0, len(data), 12):
        chunk = data[offset:offset + 12]
        rows.append(
            "    " + ", ".join(f"0x{value:02X}" for value in chunk) + ","
        )

    guard = f"{symbol.upper()}_H".replace(".", "_")
    text = (
        f"#ifndef {guard}\n"
        f"#define {guard}\n\n"
        "#include <stdint.h>\n\n"
        f"static const uint8_t {symbol}[] "
        "__attribute__((aligned(4))) = {\n"
        + "\n".join(rows)
        + "\n};\n\n"
        f"static const unsigned int {symbol}_size = "
        f"(unsigned int)sizeof({symbol});\n\n"
        f"#endif /* {guard} */\n"
    )

    output_path.write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
