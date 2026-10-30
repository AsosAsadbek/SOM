"""Boshlang'ich matn satrini tahlil qilish (nishon, buyruq, operand, izoh).

Satr formati:
    [NISHON]  BUYRUQ  [OPERAND]  [izoh]

* 1-ustundan boshlangan so'z - nishon (label). Satr bo'sh joy bilan
  boshlansa, nishon yo'q.
* '.' yoki '*' bilan boshlangan satr - izoh.
* Operand ichidagi bo'sh joylarga ruxsat bor: "BUFFER, X", "BUFEND - BUFFER".
"""

from dataclasses import dataclass, field

from .optab import NO_OPERAND, OPTIONAL_OPERAND, is_mnemonic


@dataclass
class SourceLine:
    lineno: int                 # listingdagi satr nomeri (5, 10, 15, ...)
    text: str                   # asl matn
    label: str = None
    opcode: str = None          # '+' belgisisiz, katta harflarda
    extended: bool = False      # '+' bilan yozilgan (4-format)
    operand: str = None
    comment: str = None
    is_comment: bool = False
    # 1-o'tishda to'ldiriladi
    loc: int = None
    section: object = None
    literal: object = None      # operanddagi literal (=C'EOF')
    is_literal_pool: bool = False  # LTORG/END da hosil qilingan "* =C'EOF'" satri
    # 2-o'tishda to'ldiriladi
    obj: str = ""
    base: int = None            # buyruq o'girilgan paytdagi B registr qiymati
    errors: list = field(default_factory=list)


def _skip_spaces(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    return pos


def _read_word(text, pos):
    pos = _skip_spaces(text, pos)
    start = pos
    while pos < len(text) and not text[pos].isspace():
        pos += 1
    return text[start:pos], pos


def _read_operand(text, pos):
    """Operandni o'qiydi. Qo'shtirnoq ichidagi va ',', '+', '-' atrofidagi
    bo'sh joylar operandning bir qismi hisoblanadi."""
    pos = _skip_spaces(text, pos)
    buf = []
    n = len(text)
    while pos < n:
        c = text[pos]
        if c == "'":
            end = text.find("'", pos + 1)
            end = n - 1 if end == -1 else end
            buf.append(text[pos:end + 1])
            pos = end + 1
            continue
        if c.isspace():
            nxt = _skip_spaces(text, pos)
            last = buf[-1][-1] if buf else ""
            if nxt < n and (last in ",+-" or text[nxt] in ",+-"):
                pos = nxt
                continue
            break
        buf.append(c)
        pos += 1
    return "".join(buf), pos


def _normalize_operand(op):
    """Qo'shtirnoqdan tashqaridagi bo'sh joylarni olib tashlaydi va katta
    harfga o'tkazadi (C'...' ichidagi matn o'zgarmaydi)."""
    out = []
    parts = op.split("'")
    for i, part in enumerate(parts):
        if i % 2 == 0:
            out.append("".join(part.split()).upper())
        else:
            out.append(part)
    return "'".join(out)


def parse_line(text, lineno):
    line = SourceLine(lineno=lineno, text=text.rstrip("\r\n"))
    raw = line.text.rstrip()
    stripped = raw.strip()
    if not stripped or stripped[0] in ".*":
        line.is_comment = True
        line.comment = stripped
        return line

    has_label_col = not raw[0].isspace()
    first, pos = _read_word(raw, 0)
    if has_label_col:
        second, pos2 = _read_word(raw, pos)
        # 1-ustunda buyruq yozilgan bo'lsa (masalan "RSUB"), nishon yo'q deb olamiz
        if is_mnemonic(first) and not is_mnemonic(second):
            opcode = first
        else:
            line.label = first.upper()
            opcode, pos = second, pos2
    else:
        opcode = first

    line.extended = opcode.startswith("+")
    line.opcode = opcode.lstrip("+").upper() or None

    if line.opcode in NO_OPERAND:
        rest = raw[pos:].strip()
    else:
        operand, pos = _read_operand(raw, pos)
        if operand:
            line.operand = _normalize_operand(operand)
        rest = raw[pos:].strip()
    line.comment = rest or None
    return line


def needs_operand(opcode):
    return opcode not in NO_OPERAND and opcode not in OPTIONAL_OPERAND
