"""SO'M va SO'M/QV uchun ikki o'tishli assembler.

1-o'tish (pass1):
  * har bir satrga adres beriladi (LOCCTR - adreslar hisoblagichi);
  * nishonlar adreslari SYMTAB ga yoziladi;
  * direktivalar (START, BYTE, RESW, EQU, ...) bajariladi;
  * literallar (=C'EOF') LTORG/END da xotiraga joylashtiriladi.

2-o'tish (pass2):
  * buyruqlar mashina kodiga o'tkaziladi (OPTAB + SYMTAB yordamida);
  * BYTE/WORD qiymatlari hosil qilinadi;
  * ob'ekt programma (H, D, R, T, M, E yozuvlari) va listing yoziladi.
"""

from dataclasses import dataclass, field

from .expr import AsmError, Value, evaluate
from .optab import (DIRECTIVES, FORMAT2_OPERANDS, OPTAB, REGISTERS, SIC_OPS,
                    XE_DIRECTIVES)
from .parser import SourceLine, needs_operand, parse_line

MAX_TEXT_BYTES = 30         # bitta T yozuvidagi eng ko'p bayt soni (1E)


@dataclass
class Symbol:
    value: int
    relative: bool = True   # nishonlar nisbiy, EQU bilan berilgan son - absolyut


@dataclass
class Literal:
    name: str               # masalan: =C'EOF'
    hexval: str             # masalan: 454F46
    address: int = None


@dataclass
class Section:
    """Boshqaruv seksiyasi (BS). Oddiy programma - bitta seksiya."""
    name: str
    start: int = 0
    locctr: int = 0
    max_loc: int = 0
    length: int = 0
    symtab: dict = field(default_factory=dict)
    extdef: list = field(default_factory=list)
    extref: list = field(default_factory=list)
    literals: dict = field(default_factory=dict)    # nom -> Literal
    pending: list = field(default_factory=list)     # hali joylashtirilmagan literallar
    org_saved: int = None
    base: int = None
    first_exec: int = None
    mrecords: list = field(default_factory=list)    # (adres, yarim_baytlar, "+NOM" yoki "")

    def advance(self, size):
        self.locctr += size
        self.max_loc = max(self.max_loc, self.locctr)


def parse_byte_constant(operand):
    """C'EOF' -> '454F46', X'F1' -> 'F1'."""
    if len(operand) >= 3 and operand[1] == "'" and operand.endswith("'"):
        kind, body = operand[0].upper(), operand[2:-1]
        if kind == "C" and body:
            return "".join(f"{ord(c):02X}" for c in body)
        if kind == "X" and body:
            body = body.upper()
            if len(body) % 2 or any(c not in "0123456789ABCDEF" for c in body):
                raise AsmError(f"X'...' ichida juft sondagi 16-lik raqamlar bo'lishi kerak: {operand}")
            return body
    raise AsmError(f"noto'g'ri o'zgarmas: {operand}")


def parse_literal(name):
    """=C'EOF', =X'05' yoki =3 literalining qiymati (16-lik)."""
    body = name[1:]
    if body.isdigit():
        return f"{int(body) & 0xFFFFFF:06X}"
    return parse_byte_constant(body)


class Assembler:
    def __init__(self, source, mode="auto"):
        self.source_lines = [parse_line(t, (i + 1) * 5)
                             for i, t in enumerate(source.splitlines())]
        self.mode = mode if mode != "auto" else self._detect_mode()
        self.lines = []         # oraliq fayl: 1-o'tish natijasi
        self.sections = []

    @property
    def xe(self):
        return self.mode == "xe"

    @property
    def has_errors(self):
        return any(line.errors for line in self.lines)

    def _detect_mode(self):
        """Programmada SO'M/QV imkoniyatlari ishlatilgan bo'lsa - 'xe'."""
        for line in self.source_lines:
            if line.is_comment or not line.opcode:
                continue
            op = line.operand or ""
            if (line.extended or op[:1] in ("#", "@", "=")
                    or line.opcode in XE_DIRECTIVES
                    or (line.opcode in OPTAB and line.opcode not in SIC_OPS)):
                return "xe"
        return "sic"

    def assemble(self):
        self.pass1()
        self.pass2()
        return self

    # ------------------------------------------------------------------
    # 1-O'TISH
    # ------------------------------------------------------------------
    def pass1(self):
        sec = None
        ended = False
        for line in self.source_lines:
            if line.is_comment:
                self.lines.append(line)
                continue
            if ended:
                line.errors.append("END dan keyin satr bo'lmasligi kerak")
                self.lines.append(line)
                continue
            op = line.opcode

            if sec is None:
                sec = self._new_section((line.label or "") if op == "START" else "", 0)
                if op == "START":
                    try:
                        sec.start = sec.locctr = sec.max_loc = int(line.operand or "0", 16)
                    except ValueError:
                        line.errors.append("START operandi 16-lik son bo'lishi kerak")
                    line.loc, line.section = sec.locctr, sec
                    self.lines.append(line)
                    continue

            if op == "CSECT":
                self._flush_literals(sec)
                self._close_section(sec)
                sec = self._new_section(line.label or "", 0)
                if not line.label:
                    line.errors.append("CSECT uchun nom (nishon) kerak")

            line.loc, line.section = sec.locctr, sec
            self.lines.append(line)
            try:
                self._pass1_line(line, sec)
            except AsmError as e:
                line.errors.append(str(e))

            if op == "LTORG":
                self._flush_literals(sec)
            elif op == "END":
                self._flush_literals(sec)
                ended = True

        if sec is None:
            raise AsmError("programma bo'sh")
        if not ended:
            self.lines[-1].errors.append("END direktivasi topilmadi")
            self._flush_literals(sec)
        self._close_section(sec)

    def _new_section(self, name, start):
        sec = Section(name=name, start=start, locctr=start, max_loc=start)
        self.sections.append(sec)
        return sec

    def _close_section(self, sec):
        sec.length = sec.max_loc - sec.start
        for name in sec.extdef:
            if name not in sec.symtab:
                self.lines[-1].errors.append(f"EXTDEF dagi {name} nomi bu seksiyada aniqlanmagan")

    def _define(self, sec, name, value, relative=True):
        if name in sec.symtab:
            raise AsmError(f"{name} nishoni ikki marta e'lon qilingan")
        if name in sec.extref:
            raise AsmError(f"{name} EXTREF da e'lon qilingan, uni bu yerda aniqlab bo'lmaydi")
        sec.symtab[name] = Symbol(value, relative)

    def _flush_literals(self, sec):
        """Joylashtirilmagan literallarni xotiraga joylaydi (literal pul)."""
        for lit in sec.pending:
            lit.address = sec.locctr
            pool = SourceLine(lineno=None, text=f"*  {lit.name}", label="*",
                              operand=lit.name, loc=sec.locctr, section=sec,
                              literal=lit, is_literal_pool=True)
            self.lines.append(pool)
            sec.advance(len(lit.hexval) // 2)
        sec.pending = []

    def _pass1_line(self, line, sec):
        op = line.opcode
        if op not in OPTAB and op not in DIRECTIVES:
            raise AsmError(f"noma'lum buyruq: {op}")
        if needs_operand(op) and not line.operand:
            raise AsmError(f"{op} uchun operand kerak")
        if not self.xe:
            self._check_sic(line)

        # nishonni SYMTAB ga yozish (EQU da qiymat alohida hisoblanadi)
        if line.label and op not in ("EQU", "CSECT", "START"):
            try:
                self._define(sec, line.label, sec.locctr)
            except AsmError as e:       # xato bo'lsa ham LOCCTR to'g'ri oshishi kerak
                line.errors.append(str(e))

        if op in OPTAB:
            fmt = OPTAB[op][1]
            if line.extended and fmt != 3:
                raise AsmError(f"{op} buyrug'ini 4-formatda yozib bo'lmaydi")
            size = 4 if line.extended else fmt
            if line.operand and line.operand.startswith("="):
                line.literal = self._register_literal(sec, line.operand)
            sec.advance(size)
        elif op == "WORD":
            sec.advance(3)
        elif op == "BYTE":
            sec.advance(len(parse_byte_constant(line.operand)) // 2)
        elif op in ("RESW", "RESB"):
            count = self._absolute(line.operand, sec)
            sec.advance(count * (3 if op == "RESW" else 1))
        elif op == "EQU":
            if not line.label:
                raise AsmError("EQU uchun nishon kerak")
            val = evaluate(line.operand, sec, sec.locctr)
            if val.ext:
                raise AsmError("EQU da tashqi nomlarni ishlatib bo'lmaydi")
            self._define(sec, line.label, val.value, val.rel == 1)
            line.loc = val.value
        elif op == "ORG":
            if line.operand:
                val = evaluate(line.operand, sec, sec.locctr)
                sec.org_saved = sec.locctr
                sec.locctr = val.value
                line.loc = val.value
            elif sec.org_saved is not None:
                sec.locctr, sec.org_saved = sec.org_saved, None
                line.loc = sec.locctr
        elif op == "EXTDEF":
            sec.extdef.extend(self._name_list(line.operand))
        elif op == "EXTREF":
            sec.extref.extend(self._name_list(line.operand))
        elif op == "START":
            raise AsmError("START faqat programma boshida bo'lishi mumkin")
        # BASE, NOBASE, LTORG, END, CSECT - 1-o'tishda alohida ish talab qilmaydi

    def _check_sic(self, line):
        op = line.opcode
        if (line.extended or op in XE_DIRECTIVES
                or (op in OPTAB and op not in SIC_OPS)
                or (line.operand or "")[:1] in ("#", "@", "=")):
            raise AsmError(f"'{line.text.strip()}' - bu imkoniyat faqat SO'M/QV da bor")

    def _register_literal(self, sec, name):
        lit = sec.literals.get(name)
        if lit is None:
            lit = Literal(name, parse_literal(name))
            sec.literals[name] = lit
            sec.pending.append(lit)
        return lit

    @staticmethod
    def _name_list(operand):
        names = [n for n in operand.split(",") if n]
        for n in names:
            if not (n[0].isalpha() and n.isalnum()):
                raise AsmError(f"noto'g'ri nom: {n}")
        return names

    @staticmethod
    def _absolute(operand, sec):
        val = evaluate(operand, sec, sec.locctr)
        if not val.is_absolute or val.value < 0:
            raise AsmError(f"musbat absolyut qiymat kerak: {operand}")
        return val.value

    # ------------------------------------------------------------------
    # 2-O'TISH
    # ------------------------------------------------------------------
    def pass2(self):
        for line in self.lines:
            if line.is_comment or line.errors:
                continue
            try:
                self._pass2_line(line, line.section)
            except AsmError as e:
                line.errors.append(str(e))

    def _pass2_line(self, line, sec):
        if line.is_literal_pool:
            line.obj = line.literal.hexval
            return
        op = line.opcode
        if op in OPTAB:
            fmt = OPTAB[op][1]
            if fmt == 1:
                line.obj = f"{OPTAB[op][0]:02X}"
            elif fmt == 2:
                line.obj = self._encode_format2(line)
            elif self.xe:
                line.base = sec.base
                line.obj = self._encode_format34(line, sec)
            else:
                line.obj = self._encode_sic(line, sec)
        elif op == "BYTE":
            line.obj = parse_byte_constant(line.operand)
        elif op == "WORD":
            val = evaluate(line.operand, sec, line.loc)
            self._add_mrecords(sec, line.loc, 6, val)
            line.obj = f"{val.value & 0xFFFFFF:06X}"
        elif op == "BASE":
            sec.base = evaluate(line.operand, sec, line.loc).value
        elif op == "NOBASE":
            sec.base = None
        elif op == "END" and line.operand:
            self.sections[0].first_exec = evaluate(line.operand, self.sections[0], line.loc).value

    def _relocatable(self, sec):
        # START 0 bilan boshlangan SO'M/QV programmasi qayta joylashtiriluvchi
        return self.xe and sec.start == 0

    def _add_mrecords(self, sec, address, halfbytes, val):
        if val.rel == 1 and self._relocatable(sec):
            sec.mrecords.append((address, halfbytes, ""))
        for sign, name in val.ext:
            sec.mrecords.append((address, halfbytes, ("+" if sign > 0 else "-") + name))

    def _encode_format2(self, line):
        op = line.opcode
        kind = FORMAT2_OPERANDS[op]
        parts = (line.operand or "").split(",")

        def reg(name):
            if name not in REGISTERS:
                raise AsmError(f"noma'lum registr: {name}")
            return REGISTERS[name]

        def num(text, lo, hi):
            if not text.isdigit() or not lo <= int(text) <= hi:
                raise AsmError(f"{lo}..{hi} oralig'idagi son kerak: {text}")
            return int(text)

        expected = kind.count(",") + 1
        if len(parts) != expected:
            raise AsmError(f"{op} uchun operand formati: {kind}")
        if kind == "r1,r2":
            r1, r2 = reg(parts[0]), reg(parts[1])
        elif kind == "r1":
            r1, r2 = reg(parts[0]), 0
        elif kind == "r1,n":
            r1, r2 = reg(parts[0]), num(parts[1], 1, 16) - 1
        else:
            r1, r2 = num(parts[0], 0, 15), 0
        return f"{OPTAB[op][0]:02X}{r1:X}{r2:X}"

    def _target(self, line, sec, operand):
        """Operand bo'yicha maqsad adresni (TA) hisoblaydi."""
        if operand.startswith("="):
            return Value(line.literal.address, 1)
        return evaluate(operand, sec, line.loc)

    @staticmethod
    def _split_index(operand):
        if operand.endswith(",X"):
            return operand[:-2], 1
        return operand, 0

    def _encode_sic(self, line, sec):
        """Standart SO'M: | opcode 8 | x 1 | adres 15 |"""
        opcode = OPTAB[line.opcode][0]
        if not line.operand:
            return f"{opcode:02X}0000"
        operand, x = self._split_index(line.operand)
        ta = self._target(line, sec, operand).value
        if not 0 <= ta <= 0x7FFF:
            raise AsmError(f"adres 15 razryadga sig'maydi: {ta:X}")
        return f"{(opcode << 16) | (x << 15) | ta:06X}"

    def _encode_format34(self, line, sec):
        """SO'M/QV 3-format: | op 6 | n i x b p e | disp 12 |
                   4-format: | op 6 | n i x b p e | addr 20 |"""
        opcode = OPTAB[line.opcode][0]
        n = i = 1
        x = b = p = 0
        e = 1 if line.extended else 0
        operand = line.operand or ""

        if not operand:                         # RSUB
            disp = 0
        else:
            if operand[0] == "#":               # bevosita adreslash
                n, i, operand = 0, 1, operand[1:]
            elif operand[0] == "@":             # vositali adreslash
                n, i, operand = 1, 0, operand[1:]
            operand, x = self._split_index(operand)
            if x and not (n and i):
                raise AsmError("indeksli adreslashni # yoki @ bilan birga ishlatib bo'lmaydi")
            val = self._target(line, sec, operand)

            if e:                               # 4-format: to'liq 20 razryadli adres
                if not -(1 << 19) <= val.value < (1 << 20):
                    raise AsmError("adres 20 razryadga sig'maydi")
                self._add_mrecords(sec, line.loc + 1, 5, val)
                disp = val.value & 0xFFFFF
            elif val.ext:
                raise AsmError(f"tashqi nomga faqat 4-formatda murojaat qilish mumkin (+{line.opcode})")
            elif val.rel == 0:                  # absolyut qiymat: to'g'ridan-to'g'ri
                if not 0 <= val.value <= 4095:
                    raise AsmError(f"qiymat 12 razryadga sig'maydi ({val.value}), 4-formatdan foydalaning")
                disp = val.value
            else:                               # nisbiy adres: avval Pc, keyin B ga nisbatan
                pc = line.loc + 3
                if -2048 <= val.value - pc <= 2047:
                    p, disp = 1, (val.value - pc) & 0xFFF
                elif sec.base is not None and 0 <= val.value - sec.base <= 4095:
                    b, disp = 1, val.value - sec.base
                else:
                    raise AsmError("adres juda uzoq: 4-format (+) yoki BASE dan foydalaning")

        first = (opcode & 0xFC) | (n << 1) | i
        flags = (x << 3) | (b << 2) | (p << 1) | e
        if e:
            return f"{first:02X}{flags:X}{disp:05X}"
        return f"{first:02X}{flags:X}{disp:03X}"

    # ------------------------------------------------------------------
    # OB'EKT PROGRAMMA
    # ------------------------------------------------------------------
    def object_program(self, sep="^"):
        out = []
        for idx, sec in enumerate(self.sections):
            recs = [["H", sec.name.ljust(6)[:6], f"{sec.start:06X}", f"{sec.length:06X}"]]
            for k in range(0, len(sec.extdef), 6):
                rec = ["D"]
                for name in sec.extdef[k:k + 6]:
                    sym = sec.symtab.get(name)
                    rec += [name.ljust(6)[:6], f"{sym.value if sym else 0:06X}"]
                recs.append(rec)
            for k in range(0, len(sec.extref), 12):
                recs.append(["R"] + [name.ljust(6)[:6] for name in sec.extref[k:k + 12]])
            recs += self._text_records(sec)
            for addr, half, name in sec.mrecords:
                recs.append(["M", f"{addr:06X}", f"{half:02X}"] + ([name] if name else []))
            if idx == 0 and sec.first_exec is not None:
                recs.append(["E", f"{sec.first_exec:06X}"])
            else:
                recs.append(["E"])
            out.append("\n".join(sep.join(r).rstrip() for r in recs))
        return "\n\n".join(out) + "\n"

    def _text_records(self, sec):
        recs, start, buf = [], None, ""

        def flush():
            nonlocal start, buf
            if buf:
                recs.append(["T", f"{start:06X}", f"{len(buf) // 2:02X}", *chunks])
            start, buf = None, ""
            chunks.clear()

        chunks = []
        for line in self.lines:
            if line.section is not sec or line.is_comment:
                continue
            if line.opcode in ("RESW", "RESB", "ORG"):
                flush()
                continue
            if not line.obj:
                continue
            nbytes = len(line.obj) // 2
            if buf and (line.loc != start + len(buf) // 2
                        or len(buf) // 2 + nbytes > MAX_TEXT_BYTES):
                flush()
            if not buf:
                start = line.loc
            buf += line.obj
            chunks.append(line.obj)
        flush()
        return recs

    # ------------------------------------------------------------------
    # LISTING
    # ------------------------------------------------------------------
    def listing(self):
        out = [f"Rejim: {'SO`M/QV (SIC/XE)' if self.xe else 'SO`M (SIC)'}", ""]
        out.append(f"{'Satr':>5}  {'Adres':<6}{'Nishon':<9}{'Buyruq':<9}{'Operand':<20}Ob'ekt kodi")
        out.append("-" * 70)
        for line in self.lines:
            num = f"{line.lineno:>5}" if line.lineno else " " * 5
            if line.is_comment:
                out.append(f"{num}  {'':<6}{line.text.strip()}")
                continue
            loc = f"{line.loc:04X}" if line.loc is not None and line.opcode not in (
                "END", "BASE", "NOBASE", "EXTDEF", "EXTREF", "LTORG") else ""
            if line.is_literal_pool:
                out.append(f"{num}  {loc:<6}{'*':<9}{line.operand:<29}{line.obj}")
                continue
            opcode = ("+" if line.extended else "") + (line.opcode or "")
            out.append(f"{num}  {loc:<6}{line.label or '':<9}{opcode:<9}"
                       f"{line.operand or '':<20}{line.obj}")
            for err in line.errors:
                out.append(f"{'':7}*** XATO: {err}")

        for sec in self.sections:
            out.append("")
            out.append(f"SYMTAB ({sec.name or 'nomsiz'}), uzunligi {sec.length:06X}:")
            for name, sym in sorted(sec.symtab.items(), key=lambda kv: kv[1].value):
                kind = "nisbiy" if sym.relative else "absolyut"
                out.append(f"    {name:<8} {sym.value:06X}  {kind}")
            if sec.extref:
                out.append(f"    EXTREF: {', '.join(sec.extref)}")
        errors = sum(len(line.errors) for line in self.lines)
        out.append("")
        out.append(f"Xatolar soni: {errors}")
        return "\n".join(out) + "\n"
