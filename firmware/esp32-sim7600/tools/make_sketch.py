#!/usr/bin/env python3
"""Bitta faylli Arduino sketch yasash (Cirkit Designer / Arduino IDE uchun).

src/main.cpp + include/*.h (+ config.h) -> <out>/SmartAgroLTE/SmartAgroLTE.ino
Lokal #include "..." lar bir marta joylashtiriladi (#pragma once kabi), tashqi kutubxonalar
(<TinyGsmClient.h> va h.k.) o'z holicha qoladi.

    python3 tools/make_sketch.py --sim              # SIMULATION_MODE=1 (Cirkit Designer)
    python3 tools/make_sketch.py --config include/config.h --out dist

Natijada config qiymatlari (token ham!) bo'ladi — dist/ .gitignore'da, hech qayerga commit qilmang.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INCLUDE_RE = re.compile(r'^\s*#\s*include\s+"([^"]+)"\s*$')


def inline(path: Path, config: Path, seen: set[str]) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "#pragma once":
            continue
        m = INCLUDE_RE.match(line)
        if m:
            name = m.group(1)
            if name in seen:
                continue
            seen.add(name)
            src = config if name == "config.h" else ROOT / "include" / name
            if not src.exists():
                sys.exit(f"topilmadi: {src}")
            out.append(f"// ===== {name} =====")
            out.extend(inline(src, config, seen))
            out.append(f"// ===== /{name} =====")
            continue
        out.append(line.replace('__has_include("config.h")', "1"))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", type=Path, help="config fayli (default: include/config.h, bo'lmasa config.example.h)")
    ap.add_argument("--sim", action="store_true", help="SIMULATION_MODE=1 qilib yasash")
    ap.add_argument("--out", type=Path, default=ROOT / "dist", help="chiqish katalogi")
    a = ap.parse_args()
    config = a.config or (ROOT / "include" / "config.h")
    if not config.exists():
        config = ROOT / "include" / "config.example.h"
    lines = [
        "// Avtomatik yasalgan: firmware/esp32-sim7600/tools/make_sketch.py — tahrirlamang, manbani o'zgartiring.",
        f"// config: {config.name}",
    ]
    if a.sim:
        lines.append("#define SIMULATION_MODE 1")
    lines += inline(ROOT / "src" / "main.cpp", config, set())
    dst = a.out / "SmartAgroLTE" / "SmartAgroLTE.ino"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mode = "1" if a.sim else "config bo'yicha"
    print(f"{dst} ({len(lines)} qator, SIMULATION_MODE={mode})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
