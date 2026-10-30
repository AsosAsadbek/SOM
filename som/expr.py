"""Operanddagi ifodalarni hisoblash: BUFEND-BUFFER, *, LENGTH+3, ...

Har bir ifoda natijasi uchta narsadan iborat:
  value - son qiymati
  rel   - nisbiy (relative) hadlar soni: nishonlar programma joylashgan
          joyga bog'liq (nisbiy), sonlar esa absolyut. To'g'ri ifodada
          rel = 0 (absolyut) yoki rel = 1 (nisbiy) bo'ladi.
  ext   - tashqi nomlar (EXTREF) ro'yxati: [(+1, 'BUFEND'), (-1, 'BUFFER')].
          Ularning qiymati assemblerga noma'lum, shuning uchun 0 olinadi va
          yuklagich uchun M (modifikatsiya) yozuvi yaratiladi.
"""

import re
from dataclasses import dataclass, field


class AsmError(Exception):
    pass


@dataclass
class Value:
    value: int
    rel: int = 0
    ext: list = field(default_factory=list)

    def __neg__(self):
        return Value(-self.value, -self.rel, [(-s, n) for s, n in self.ext])

    def __add__(self, other):
        return Value(self.value + other.value, self.rel + other.rel, self.ext + other.ext)

    def __sub__(self, other):
        return self + (-other)

    @property
    def is_absolute(self):
        return self.rel == 0 and not self.ext


_TOKEN = re.compile(r"[A-Z_][A-Z0-9_]*|\d+|[-+*/()]")


def evaluate(text, section, locctr):
    """Ifodani hisoblaydi. Aniqlanmagan nom bo'lsa AsmError chiqaradi."""
    tokens = _TOKEN.findall(text)
    if "".join(tokens) != text:
        raise AsmError(f"noto'g'ri ifoda: {text}")
    parser = _ExprParser(tokens, section, locctr)
    result = parser.expr()
    if parser.pos != len(tokens):
        raise AsmError(f"noto'g'ri ifoda: {text}")
    if result.rel not in (0, 1):
        raise AsmError(f"ifoda na absolyut, na nisbiy: {text}")
    return result


class _ExprParser:
    """expr := term (('+'|'-') term)* ; term := factor (('*'|'/') factor)*"""

    def __init__(self, tokens, section, locctr):
        self.tokens = tokens
        self.pos = 0
        self.section = section
        self.locctr = locctr

    def _peek(self):
        return self.tokens[self.pos] if self.pos < len(self.tokens) else None

    def _next(self):
        tok = self._peek()
        if tok is None:
            raise AsmError("ifoda to'liq emas")
        self.pos += 1
        return tok

    def expr(self):
        result = self.term()
        while self._peek() in ("+", "-"):
            op = self._next()
            rhs = self.term()
            result = result + rhs if op == "+" else result - rhs
        return result

    def term(self):
        result = self.factor()
        while self._peek() in ("*", "/"):
            op = self._next()
            rhs = self.factor()
            if not (result.is_absolute and rhs.is_absolute):
                raise AsmError("'*' va '/' faqat absolyut qiymatlar bilan ishlatiladi")
            if op == "/":
                if rhs.value == 0:
                    raise AsmError("nolga bo'lish")
                result = Value(int(result.value / rhs.value))
            else:
                result = Value(result.value * rhs.value)
        return result

    def factor(self):
        tok = self._next()
        if tok == "-":
            return -self.factor()
        if tok == "*":                      # joriy adres (LOCCTR)
            return Value(self.locctr, 1)
        if tok == "(":
            result = self.expr()
            if self._next() != ")":
                raise AsmError("')' yetishmayapti")
            return result
        if tok.isdigit():
            return Value(int(tok))
        if tok[0].isalpha() or tok[0] == "_":
            sym = self.section.symtab.get(tok)
            if sym is not None:
                return Value(sym.value, 1 if sym.relative else 0)
            if tok in self.section.extref:
                return Value(0, 0, [(1, tok)])
            raise AsmError(f"aniqlanmagan nom: {tok}")
        raise AsmError(f"kutilmagan belgi: {tok}")
