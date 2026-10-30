"""OPTAB - buyruqlar kodlari jadvali.

Har bir mnemonik buyruq uchun: mashina kodi (opcode) va formati.
Format 1, 2 - faqat SO'M/QV da bor; format 3 yoki 4 ("3/4") buyruqlar
'+' belgisi bilan 4-formatda (kengaytirilgan) yozilishi mumkin.
"""

# mnemonik: (opcode, format)  format: 1, 2 yoki 3 (3 = "3/4")
OPTAB = {
    "ADD": (0x18, 3), "ADDF": (0x58, 3), "ADDR": (0x90, 2), "AND": (0x40, 3),
    "CLEAR": (0xB4, 2), "COMP": (0x28, 3), "COMPF": (0x88, 3), "COMPR": (0xA0, 2),
    "DIV": (0x24, 3), "DIVF": (0x64, 3), "DIVR": (0x9C, 2), "FIX": (0xC4, 1),
    "FLOAT": (0xC0, 1), "HIO": (0xF4, 1), "J": (0x3C, 3), "JEQ": (0x30, 3),
    "JGT": (0x34, 3), "JLT": (0x38, 3), "JSUB": (0x48, 3), "LDA": (0x00, 3),
    "LDB": (0x68, 3), "LDCH": (0x50, 3), "LDF": (0x70, 3), "LDL": (0x08, 3),
    "LDS": (0x6C, 3), "LDT": (0x74, 3), "LDX": (0x04, 3), "LPS": (0xD0, 3),
    "MUL": (0x20, 3), "MULF": (0x60, 3), "MULR": (0x98, 2), "NORM": (0xC8, 1),
    "OR": (0x44, 3), "RD": (0xD8, 3), "RMO": (0xAC, 2), "RSUB": (0x4C, 3),
    "SHIFTL": (0xA4, 2), "SHIFTR": (0xA8, 2), "SIO": (0xF0, 1), "SSK": (0xEC, 3),
    "STA": (0x0C, 3), "STB": (0x78, 3), "STCH": (0x54, 3), "STF": (0x80, 3),
    "STI": (0xD4, 3), "STL": (0x14, 3), "STS": (0x7C, 3), "STSW": (0xE8, 3),
    "STT": (0x84, 3), "STX": (0x10, 3), "SUB": (0x1C, 3), "SUBF": (0x5C, 3),
    "SUBR": (0x94, 2), "SVC": (0xB0, 2), "TD": (0xE0, 3), "TIO": (0xF8, 1),
    "TIX": (0x2C, 3), "TIXR": (0xB8, 2), "WD": (0xDC, 3),
}

# Standart SO'M (SIC) da mavjud buyruqlar. Qolganlari faqat SO'M/QV da.
SIC_OPS = {
    "ADD", "AND", "COMP", "DIV", "J", "JEQ", "JGT", "JLT", "JSUB", "LDA",
    "LDCH", "LDL", "LDX", "MUL", "OR", "RD", "RSUB", "STA", "STCH", "STL",
    "STSW", "STX", "SUB", "TD", "TIX", "WD",
}

# Registrlar: mnemonik nomi -> nomeri
REGISTERS = {"A": 0, "X": 1, "L": 2, "B": 3, "S": 4, "T": 5, "F": 6, "PC": 8, "SW": 9}

# 2-format buyruqlar operand turi:
#   "r1,r2" - ikki registr, "r1" - bitta registr,
#   "r1,n" - registr va son (siljish), "n" - faqat son (SVC)
FORMAT2_OPERANDS = {
    "ADDR": "r1,r2", "COMPR": "r1,r2", "DIVR": "r1,r2", "MULR": "r1,r2",
    "RMO": "r1,r2", "SUBR": "r1,r2", "CLEAR": "r1", "TIXR": "r1",
    "SHIFTL": "r1,n", "SHIFTR": "r1,n", "SVC": "n",
}

# Assembler direktivalari (mashina kodiga o'tmaydi, assemblerni boshqaradi)
DIRECTIVES = {
    "START", "END", "BYTE", "WORD", "RESB", "RESW",
    "EQU", "ORG", "LTORG", "BASE", "NOBASE", "CSECT", "EXTDEF", "EXTREF",
}

# Faqat SO'M/QV ga xos direktivalar
XE_DIRECTIVES = {"LTORG", "BASE", "NOBASE", "CSECT", "EXTDEF", "EXTREF"}

# Operandsiz yoziladigan buyruq/direktivalar
NO_OPERAND = {"RSUB", "LTORG", "NOBASE", "CSECT"} | {
    m for m, (_, fmt) in OPTAB.items() if fmt == 1
}

# Operandi ixtiyoriy bo'lganlar
OPTIONAL_OPERAND = {"END", "ORG"}


def is_mnemonic(word):
    """So'z buyruq yoki direktiva nomi bo'lsa True."""
    w = word.upper().lstrip("+")
    return w in OPTAB or w in DIRECTIVES
