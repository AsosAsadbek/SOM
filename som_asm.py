#!/usr/bin/env python3
"""Ikki o'tishli assembler - buyruqlar satri interfeysi.

Ishlatish:
    python3 som_asm.py examples/copy_sic.asm
    python3 som_asm.py examples/copy_xe.asm --mode xe -o natija

Natija: <nom>.lst (listing) va <nom>.obj (ob'ekt programma) fayllari.
"""

import argparse
import os
import sys

from som import Assembler, AsmError


def main():
    ap = argparse.ArgumentParser(description="SO'M / SO'M/QV ikki o'tishli assembler")
    ap.add_argument("source", help="assembler tilidagi programma fayli (.asm)")
    ap.add_argument("-o", "--output", help="natija fayllari nomi (kengaytmasiz)")
    ap.add_argument("--mode", choices=["auto", "sic", "xe"], default="auto",
                    help="sic - standart SO'M, xe - SO'M/QV, auto - avtomatik aniqlash")
    ap.add_argument("--sep", default="^",
                    help="ob'ekt programma maydonlari orasidagi ajratuvchi (default: ^)")
    ap.add_argument("-q", "--quiet", action="store_true", help="ekranga chiqarmaslik")
    args = ap.parse_args()

    with open(args.source, encoding="utf-8") as f:
        source = f.read()

    try:
        asm = Assembler(source, args.mode).assemble()
    except AsmError as e:
        print(f"XATO: {e}", file=sys.stderr)
        return 1

    base = args.output or os.path.splitext(args.source)[0]
    listing = asm.listing()
    with open(base + ".lst", "w", encoding="utf-8") as f:
        f.write(listing)
    if not asm.has_errors:
        obj = asm.object_program(args.sep)
        with open(base + ".obj", "w", encoding="utf-8") as f:
            f.write(obj)

    if not args.quiet:
        print(listing)
        if not asm.has_errors:
            print("Ob'ekt programma:")
            print(obj)
    if asm.has_errors:
        print("Programmada xatolar bor - ob'ekt programma yaratilmadi.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
