"""Listingdagi satr ob'ekt kodini bitlarga ajratib tushuntirish.

Grafik oynadagi "Buyruq tahlili" paneli uchun ishlatiladi.
"""

from .optab import FORMAT2_OPERANDS, OPTAB, REGISTERS

REG_NAMES = {v: k for k, v in REGISTERS.items()}

DIRECTIVE_HELP = {
    "START": "Programma nomi va boshlang'ich adresi (16-lik). LOCCTR shu qiymatdan boshlanadi.",
    "END": "Programma oxiri. Operand - birinchi bajariladigan buyruq (E yozuviga yoziladi).",
    "BYTE": "Baytlar ketma-ketligi: C'...' - belgilar ASCII kodi, X'...' - 16-lik qiymat.",
    "WORD": "3 baytli (24 bit) butun son o'zgarmasi.",
    "RESB": "n bayt joy ajratadi: LOCCTR = LOCCTR + n. Ob'ekt kod hosil bo'lmaydi.",
    "RESW": "n so'z joy ajratadi: LOCCTR = LOCCTR + 3*n. Ob'ekt kod hosil bo'lmaydi.",
    "EQU": "Nishonga ifoda qiymatini beradi (adres emas). '*' - joriy LOCCTR.",
    "ORG": "LOCCTR ni berilgan qiymatga o'rnatadi; operandsiz - eski qiymatga qaytaradi.",
    "LTORG": "Shu joyga hali joylashtirilmagan literallarni (=C'EOF') joylaydi.",
    "BASE": "Assemblerga B registrda shu adres bo'lishini aytadi (bazaga nisbatan adreslash uchun).",
    "NOBASE": "Bazaga nisbatan adreslashni o'chiradi.",
    "CSECT": "Yangi boshqaruv seksiyasi. LOCCTR = 0, o'z SYMTAB i bo'ladi.",
    "EXTDEF": "Boshqa seksiyalar ishlata oladigan nomlar (D yozuvi).",
    "EXTREF": "Boshqa seksiyada aniqlangan nomlar (R yozuvi). Ular uchun M yozuvi yaratiladi.",
}


def _bits(value, width):
    return format(value, f"0{width}b")


def explain(line, xe):
    """Satr uchun tushuntirish matnini qaytaradi."""
    if line.is_comment:
        return "Izoh satri - assembler uni e'tiborsiz qoldiradi."
    if line.errors:
        return "Bu satrda xato bor:\n  " + "\n  ".join(line.errors)
    if line.is_literal_pool:
        return (f"Literal {line.operand} shu adresga joylashtirildi: {line.loc:04X}\n"
                f"Qiymati: {line.obj}\n"
                "Literalga murojaat qilgan buyruqlar shu adresni ishlatadi.")
    op = line.opcode
    head = f"{(line.label or '')} {'+' if line.extended else ''}{op} {line.operand or ''}".strip()
    if op not in OPTAB:
        text = f"{head}\n\nDirektiva: {DIRECTIVE_HELP.get(op, '')}"
        if op == "BYTE" and line.obj:
            text += "\n\nBaytlar: " + " ".join(line.obj[k:k + 2] for k in range(0, len(line.obj), 2))
            if line.operand.upper().startswith("C'"):
                chars = line.operand[2:-1]
                text += "\nASCII:   " + "  ".join(f"{c}={ord(c):02X}" for c in chars)
        elif op == "WORD" and line.obj:
            text += f"\n\nQiymat: {int(line.obj, 16)} = {line.obj} (24 bit)"
        return text
    if not line.obj:
        return head

    code = int(line.obj, 16)
    fmt = len(line.obj) // 2
    out = [head, f"Adres: {line.loc:04X}    Ob'ekt kodi: {line.obj}    Format: {fmt}", ""]

    if fmt == 1:
        out.append(f"opcode = {line.obj} ({op}) - 1 baytli buyruq, operand yo'q.")
    elif fmt == 2:
        r1, r2 = (code >> 4) & 0xF, code & 0xF
        out += [
            "| opcode (8) | r1 (4) | r2 (4) |",
            f"| {_bits(code >> 8, 8)}   | {_bits(r1, 4)}   | {_bits(r2, 4)}   |",
            "",
            f"opcode = {code >> 8:02X} ({op})",
        ]
        kind = FORMAT2_OPERANDS[op]
        if kind == "r1,r2":
            out.append(f"r1 = {r1} ({REG_NAMES.get(r1, '-')}),  r2 = {r2} ({REG_NAMES.get(r2, '-')})")
        elif kind == "r1":
            out.append(f"r1 = {r1} ({REG_NAMES.get(r1, '-')}),  r2 = 0 (ishlatilmaydi)")
        elif kind == "r1,n":
            out.append(f"r1 = {r1} ({REG_NAMES.get(r1, '-')}),  r2 = n-1 = {r2} (siljish n = {r2 + 1})")
        else:
            out.append(f"n = {r1} (supervizor chaqiruv raqami)")
    elif not xe:
        opcode, x, addr = code >> 16, (code >> 15) & 1, code & 0x7FFF
        out += [
            "Standart SO'M formati:",
            "| opcode (8) | x | adres (15)      |",
            f"| {_bits(opcode, 8)}   | {x} | {_bits(addr, 15)} |",
            "",
            f"opcode = {opcode:02X} ({op})",
            f"x = {x} -> " + ("indeksli: TA = adres + (X)" if x else "to'g'ridan-to'g'ri: TA = adres"),
            f"adres = {addr:04X}",
        ]
    else:
        shift = 20 if fmt == 4 else 12
        first = code >> (shift + 4)
        flags = (code >> shift) & 0xF
        disp = code & ((1 << shift) - 1)
        n, i = (first >> 1) & 1, first & 1
        x, b, p, e = flags >> 3, (flags >> 2) & 1, (flags >> 1) & 1, flags & 1
        width = 20 if fmt == 4 else 12
        name = "adres (20)" if fmt == 4 else "disp (12)"
        out += [
            f"| opcode (6) | n | i | x | b | p | e | {name}",
            f"| {_bits(first >> 2, 6)}     | {n} | {i} | {x} | {b} | {p} | {e} | {_bits(disp, width)}",
            "",
            f"opcode = {_bits(first >> 2, 6)}00 = {first & 0xFC:02X} ({op})",
        ]
        if n and i:
            out.append("n=1 i=1 -> oddiy adreslash: operand = xotiradagi (TA) qiymat")
        elif i:
            out.append("n=0 i=1 -> bevosita adreslash (#): operand = TA ning o'zi")
        elif n:
            out.append("n=1 i=0 -> vositali adreslash (@): TA dagi so'z - operand adresi")
        out.append(f"x={x} -> " + ("indeksli: TA ga (X) qo'shiladi" if x else "indekssiz"))
        if e:
            out.append(f"e=1 -> 4-format, to'liq adres = {disp:05X}")
            if disp == 0 and line.operand:
                out.append("(adres 0 - uni yuklagich M yozuvi orqali to'ldiradi)")
        elif p:
            sdisp = disp - 0x1000 if disp & 0x800 else disp
            pc = line.loc + 3
            out.append(f"b=0 p=1 -> PC ga nisbatan: PC = {line.loc:04X} + 3 = {pc:04X}")
            out.append(f"   disp = {disp:03X} ({sdisp:+d})  ->  TA = PC + disp = {pc + sdisp:04X}")
        elif b:
            out.append(f"b=1 p=0 -> bazaga nisbatan: TA = (B) + disp = "
                       f"{line.base or 0:04X} + {disp:03X} = {(line.base or 0) + disp:04X}")
        else:
            out.append(f"b=0 p=0 -> to'g'ridan-to'g'ri: TA = disp = {disp:03X}")
    return "\n".join(out)
