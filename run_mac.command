#!/bin/bash
# macOS: ikki marta bosib ishga tushirish. Birinchi marta pywebview o'rnatiladi.
cd "$(dirname "$0")" || exit 1
if [ ! -x .venv/bin/python ]; then
  echo "Birinchi ishga tushirish: virtual muhit yaratilmoqda va pywebview o'rnatilmoqda..."
  python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt || exit 1
fi
exec .venv/bin/python som_glass.py
