"""Misol programmalar ob'ekt kodini darslikdagi natijalar bilan solishtirish.

Ishga tushirish:  python3 -m unittest discover tests
"""

import os
import unittest

from som import Assembler
from som.explain import explain

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def assemble(name, mode="auto"):
    with open(os.path.join(ROOT, "examples", name), encoding="utf-8") as f:
        return Assembler(f.read(), mode).assemble()


class ExampleProgramsTest(unittest.TestCase):
    def check(self, name, expected):
        asm = assemble(name)
        self.assertFalse(asm.has_errors, asm.listing())
        self.assertEqual(asm.object_program().strip(), expected.strip())

    def test_sic(self):
        self.check("copy_sic.asm", """
H^COPY  ^001000^00107A
T^001000^1E^141033^482039^001036^281030^301015^482061^3C1003^00102A^0C1039^00102D
T^00101E^15^0C1036^482061^081033^4C0000^454F46^000003^000000
T^002039^1E^041030^001030^E0205D^30203F^D8205D^281030^302057^549039^2C205E^38203F
T^002057^1C^101036^4C0000^F1^001000^041030^E02079^302064^509039^DC2079^2C1036
T^002073^07^382064^4C0000^05
E^001000
""")

    def test_xe(self):
        self.check("copy_xe.asm", """
H^COPY  ^000000^001077
T^000000^1D^17202D^69202D^4B101036^032026^290000^332007^4B10105D^3F2FEC^032010
T^00001D^13^0F2016^010003^0F200D^4B10105D^3E2003^454F46
T^001036^1D^B410^B400^B440^75101000^E32019^332FFA^DB2013^A004^332008^57C003^B850
T^001053^1D^3B2FEA^134000^4F0000^F1^B410^774000^E32011^332FFA^53C003^DF2008^B850
T^001070^07^3B2FEF^4F0000^05
M^000007^05
M^000014^05
M^000027^05
E^000000
""")

    def test_control_sections(self):
        self.check("copy_csect.asm", """
H^COPY  ^000000^001033
D^BUFFER^000033^BUFEND^001033^LENGTH^00002D
R^RDREC ^WRREC
T^000000^1D^172027^4B100000^032023^290000^332007^4B100000^3F2FEC^032016^0F2016
T^00001D^0D^010003^0F200A^4B100000^3E2000
T^000030^03^454F46
M^000004^05^+RDREC
M^000011^05^+WRREC
M^000024^05^+WRREC
E^000000

H^RDREC ^000000^00002B
R^BUFFER^LENGTH^BUFEND
T^000000^1D^B410^B400^B440^77201F^E3201B^332FFA^DB2015^A004^332009^57900000^B850
T^00001D^0E^3B2FE9^13100000^4F0000^F1^000000
M^000018^05^+BUFFER
M^000021^05^+LENGTH
M^000028^06^+BUFEND
M^000028^06^-BUFFER
E

H^WRREC ^000000^00001C
R^LENGTH^BUFFER
T^000000^1C^B410^77100000^E32012^332FFA^53900000^DF2008^B850^3B2FEE^4F0000^05
M^000003^05^+LENGTH
M^00000D^05^+BUFFER
E
""")

    def test_mode_detection(self):
        self.assertEqual(assemble("copy_sic.asm").mode, "sic")
        self.assertEqual(assemble("copy_xe.asm").mode, "xe")


class ExplainTest(unittest.TestCase):
    def explain_op(self, name, opcode):
        asm = assemble(name)
        line = next(l for l in asm.lines if l.opcode == opcode)
        return explain(line, asm.xe)

    def test_pc_relative(self):
        text = self.explain_op("copy_xe.asm", "STL")
        self.assertIn("TA = PC + disp = 0030", text)

    def test_base_relative(self):
        text = self.explain_op("copy_xe.asm", "STCH")
        self.assertIn("TA = (B) + disp = 0033 + 003 = 0036", text)

    def test_sic_format(self):
        text = self.explain_op("copy_sic.asm", "STCH")
        self.assertIn("indeksli", text)


class ErrorsTest(unittest.TestCase):
    def errors(self, source):
        asm = Assembler(source, mode="xe").assemble()
        return [e for line in asm.lines for e in line.errors]

    def test_undefined_symbol(self):
        errs = self.errors("P START 0\n LDA NOPE\n END\n")
        self.assertTrue(any("NOPE" in e for e in errs))

    def test_duplicate_label_keeps_locctr(self):
        asm = Assembler("P START 0\nA WORD 1\nA WORD 2\nB WORD 3\n END\n").assemble()
        self.assertEqual(asm.sections[0].symtab["B"].value, 6)
        self.assertTrue(asm.has_errors)

    def test_far_address_needs_format4(self):
        errs = self.errors("P START 0\n LDA FAR\n RESB 5000\nFAR WORD 1\n END\n")
        self.assertTrue(any("4-format" in e for e in errs))

    def test_xe_feature_in_sic_mode(self):
        asm = Assembler("P START 1000\n LDA #3\n END\n", mode="sic").assemble()
        self.assertTrue(asm.has_errors)


if __name__ == "__main__":
    unittest.main()
