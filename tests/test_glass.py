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
