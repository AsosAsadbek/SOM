"""Liquid Glass oynasining Python qismi (pywebview siz tekshiriladi)."""

import unittest

from som_glass import Api, assemble_to_dict


class GlassApiTest(unittest.TestCase):
    def test_assemble_result_shape(self):
        api = Api()
        res = api.assemble(api.load_example("copy_xe.asm")["text"], "auto")
        self.assertEqual(res["mode"], "xe")
        self.assertEqual(res["errorCount"], 0)
        stl = next(r for r in res["rows"] if r["opcode"] == "STL")
        self.assertEqual((stl["loc"], stl["obj"], stl["srcRow"]), ("0000", "17202D", 2))
        self.assertTrue(stl["isInstr"])
        self.assertTrue(res["object"].startswith("H^COPY"))

    def test_errors_and_no_object(self):
        res = assemble_to_dict("P START 0\n FOO 1\n END\n", "xe")
        self.assertEqual(res["errorCount"], 1)
        self.assertIsNone(res["object"])

    def test_unknown_example_rejected(self):
        with self.assertRaises(ValueError):
            Api().load_example("../som_glass.py")


if __name__ == "__main__":
    unittest.main()


class TableModeTest(unittest.TestCase):
    """Interaktiv jadval: satrlar alohida kataklardan, adreslar qo'lda berilishi mumkin."""

    def rows(self):
        return Api().load_example("copy_sic.asm")["rows"]

    def test_rows_give_same_object_program_as_text(self):
        api = Api()
        text = api.load_example("copy_sic.asm")["text"]
        self.assertEqual(api.assemble_rows(self.rows())["object"], api.assemble(text)["object"])

    def test_symbol_count_matches_original_table(self):
        self.assertEqual(Api().assemble_rows(self.rows())["symbolCount"], 17)

    def test_manual_address_moves_following_rows(self):
        rows = self.rows()
        rows[2]["addr"] = "2000"                    # CLOOP JSUB RDREC
        res = Api().assemble_rows(rows, "auto", False)
        by_line = {r["lineno"]: r for r in res["rows"]}
        self.assertEqual((by_line[15]["loc"], by_line[15]["manualAddr"]), ("2000", True))
        self.assertEqual(by_line[20]["loc"], "2003")
        self.assertEqual(by_line[10]["obj"], "142030")   # RETADR ham 1000h ga surildi

    def test_manual_address_ignored_when_auto(self):
        rows = self.rows()
        rows[2]["addr"] = "2000"
        res = Api().assemble_rows(rows, "auto", True)
        self.assertEqual(res["rows"][2]["loc"], "1003")

    def test_bad_manual_address_is_an_error(self):
        rows = self.rows()
        rows[2]["addr"] = "XYZ"
        self.assertEqual(Api().assemble_rows(rows, "auto", False)["errorCount"], 1)

    def test_operand_on_rsub_is_an_error(self):
        rows = [{"label": "P", "opcode": "START", "operand": "0"},
                {"opcode": "RSUB", "operand": "X"}, {"opcode": "END"}]
        self.assertEqual(Api().assemble_rows(rows, "xe")["errorCount"], 1)
