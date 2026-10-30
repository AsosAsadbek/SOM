"""Darslikdagi misol programmalar ro'yxati (grafik oynalar uchun)."""

import os
import sys


def app_root():
    """Dastur fayllari (ui/, examples/) joylashgan papka.
    Mac ilovasi (PyInstaller) ichida ular sys._MEIPASS papkasida bo'ladi."""
    return getattr(sys, "_MEIPASS", None) or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


EXAMPLES_DIR = os.path.join(app_root(), "examples")

EXAMPLES = [
    ("SO'M - COPY programmasi", "copy_sic.asm"),
    ("SO'M/QV - COPY programmasi", "copy_xe.asm"),
    ("SO'M/QV - boshqaruv seksiyalari", "copy_csect.asm"),
]


def example_path(name):
    """Misol fayli yo'li; ro'yxatda bo'lmagan nom uchun ValueError."""
    if name not in {n for _, n in EXAMPLES}:
        raise ValueError(f"noma'lum misol: {name}")
    return os.path.join(EXAMPLES_DIR, name)
