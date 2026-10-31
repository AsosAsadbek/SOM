#!/usr/bin/env python3
"""SO'M / SO'M/QV assembler - macOS "Liquid Glass" uslubidagi oyna.

Interfeys HTML/CSS da (ui/ papkasi), oyna pywebview orqali ochiladi:
macOS da WebKit, Windows da Edge WebView2 ishlatiladi.

    pip install pywebview
    python3 som_glass.py              # alohida oyna
    python3 som_glass.py --browser    # brauzerda ochish (pywebview siz)
"""

import argparse
import json
import os
import sys
import threading
import webbrowser
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from som import Assembler, AsmError
from som.examples import EXAMPLES, app_root, example_path
from som.explain import explain
from som.optab import DIRECTIVES, NO_OPERAND, OPTAB
from som.parser import line_from_fields, parse_line

UI_DIR = os.path.join(app_root(), "ui")
TITLE = "SO'M Assembler"
SOURCE_TYPES = ("Assembler fayllari (*.asm;*.txt)", "Barcha fayllar (*.*)")
HIDDEN_LOC = {"END", "BASE", "NOBASE", "EXTDEF", "EXTREF", "LTORG"}


def parse_source(text):
    """Programma matnini jadval satrlariga ajratadi: [{label, opcode, operand, comment}].
    Faqat '*' yoki '.' dan iborat bo'sh izoh satrlari tashlab yuboriladi."""
    rows = []
    for raw in text.splitlines():
        line = parse_line(raw, 0)
        if line.is_comment:
            comment = (line.comment or "").lstrip(".*").strip()
            if comment:
                rows.append({"label": "", "opcode": "", "operand": "", "comment": comment, "addr": ""})
            continue
        rows.append({
            "label": line.label or "",
            "opcode": ("+" if line.extended else "") + (line.opcode or ""),
            "operand": line.operand or "",
            "comment": line.comment or "",
            "addr": "",
        })
    return rows


def build_assembler(rows, mode="auto", auto_addr=True):
    """Jadval satrlaridan assembler yaratadi. auto_addr=False bo'lsa,
    "Adres" katagiga qo'lda yozilgan qiymatlar LOCCTR sifatida ishlatiladi."""
    lines, locs = [], {}
    for i, row in enumerate(rows):
        line = line_from_fields((i + 1) * 5, row.get("label"), row.get("opcode"),
                                row.get("operand"), row.get("comment"))
        addr = (row.get("addr") or "").strip()
        if not auto_addr and addr and not line.is_comment:
            try:
                locs[i] = int(addr, 16)
            except ValueError:
                line.errors.append(f"adres 16-lik son bo'lishi kerak: {addr}")
        lines.append(line)
    mode = mode if mode in ("auto", "sic", "xe") else "auto"
    return Assembler(mode=mode, lines=lines, locs=locs)


def assemble_to_dict(source, mode):
    """Programma matnini assembler qiladi (eski matnli interfeys va testlar uchun)."""
    return result_to_dict(lambda: Assembler(source, mode))


def result_to_dict(make_assembler):
    """Assembler natijasini interfeys uchun JSON ko'rinishiga o'tkazadi."""
    try:
        asm = make_assembler().assemble()
    except AsmError as e:
        return {"fatal": str(e)}

    rows = []
    for line in asm.lines:
        if line.is_comment:
            kind = "comment"
        elif line.is_literal_pool:
            kind = "literal"
        else:
            kind = "line"
        show_loc = line.loc is not None and kind != "comment" and line.opcode not in HIDDEN_LOC
        rows.append({
            "kind": kind,
            "lineno": line.lineno,
            "srcRow": line.lineno // 5 if line.lineno else None,
            "loc": f"{line.loc:04X}" if show_loc else "",
            "label": "*" if kind == "literal" else (line.label or ""),
            "opcode": ("+" if line.extended else "") + (line.opcode or ""),
            "operand": line.text.strip() if kind == "comment" else (line.operand or ""),
            "manualAddr": (line.lineno // 5 - 1) in asm.locs if line.lineno else False,
            "obj": line.obj,
            "isInstr": kind == "line" and line.opcode in OPTAB,
            "errors": line.errors,
            "explain": explain(line, asm.xe),
        })

    symtab = []
    for sec in asm.sections:
        name = sec.name or "nomsiz"
        for sym_name, sym in sorted(sec.symtab.items(), key=lambda kv: kv[1].value):
            symtab.append({"section": name, "name": sym_name, "value": f"{sym.value:06X}",
                           "kind": "nisbiy" if sym.relative else "absolyut"})
        for ext in sec.extref:
            symtab.append({"section": name, "name": ext, "value": "?", "kind": "tashqi (EXTREF)"})

    return {
        "mode": asm.mode,
        "rows": rows,
        "symtab": symtab,
        "object": None if asm.has_errors else asm.object_program(),
        "listingText": asm.listing(),
        "errorCount": sum(len(line.errors) for line in asm.lines),
        "symbolCount": sum(len(s.symtab) for s in asm.sections),
        "sections": [{"name": s.name or "nomsiz", "start": f"{s.start:06X}", "length": f"{s.length:X}"}
                     for s in asm.sections],
    }


class Api:
    """JavaScript dan chaqiriladigan funksiyalar (window.pywebview.api.*).
    '_' bilan boshlangan nomlar JavaScript ga ochilmaydi."""

    def __init__(self, vibrancy=False):
        self._window = None
        self._path = None
        self._dirty = False
        self._vibrancy = vibrancy

    def meta(self):
        return {
            "opcodes": sorted(OPTAB),
            "directives": sorted(DIRECTIVES),
            "noOperand": sorted(NO_OPERAND),
            "native": self._window is not None,
            "vibrancy": self._vibrancy,
        }

    def examples(self):
        return [{"title": title, "name": name} for title, name in EXAMPLES]

    def load_example(self, name):
        with open(example_path(name), encoding="utf-8") as f:
            text = f.read()
        self._path = None           # misolni saqlashda yangi fayl nomi so'raladi
        return {"name": name, "text": text, "rows": parse_source(text)}

    def parse_source(self, text):
        return parse_source(text)

    def assemble(self, source, mode="auto"):
        return assemble_to_dict(source, mode if mode in ("auto", "sic", "xe") else "auto")

    def assemble_rows(self, rows, mode="auto", auto_addr=True):
        return result_to_dict(lambda: build_assembler(rows, mode, auto_addr))

    # --- quyidagilar faqat alohida oynada (pywebview) ishlaydi
    def _dialog(self, kind, **kwargs):
        import webview
        dialog = getattr(webview, "FileDialog", None)
        if dialog is not None:
            kind = {"open": dialog.OPEN, "save": dialog.SAVE}[kind]
        else:                       # pywebview 4.x
            kind = {"open": webview.OPEN_DIALOG, "save": webview.SAVE_DIALOG}[kind]
        result = self._window.create_file_dialog(kind, **kwargs)
        if not result:
            return None
        return result if isinstance(result, str) else result[0]

    def open_file(self):
        path = self._dialog("open", file_types=SOURCE_TYPES)
        if not path:
            return None
        with open(path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        self._path = path
        return {"name": os.path.basename(path), "text": text, "rows": parse_source(text)}

    def save_file(self, text, save_as=False, suggested="programma.asm"):
        path = self._path
        if save_as or not path:
            path = self._dialog("save", save_filename=suggested)
            if not path:
                return None
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        self._path = path
        return {"name": os.path.basename(path)}

    def save_csv(self, content, suggested="jadval.csv"):
        path = self._dialog("save", save_filename=suggested)
        if not path:
            return None
        with open(path, "w", encoding="utf-8-sig", newline="") as f:   # BOM: Excel uchun
            f.write(content)
        return {"name": os.path.basename(path)}

    def save_results(self, rows, mode="auto", auto_addr=True, suggested="natija"):
        path = self._dialog("save", save_filename=suggested + ".lst")
        if not path:
            return None
        base = os.path.splitext(path)[0]
        asm = build_assembler(rows, mode, auto_addr).assemble()
        saved = [base + ".lst"]
        with open(saved[0], "w", encoding="utf-8") as f:
            f.write(asm.listing())
        if not asm.has_errors:
            saved.append(base + ".obj")
            with open(saved[1], "w", encoding="utf-8") as f:
                f.write(asm.object_program())
        return {"saved": [os.path.basename(p) for p in saved]}

    def set_dirty(self, dirty):
        self._dirty = bool(dirty)

    def confirm(self, message):
        return self._window.create_confirmation_dialog(TITLE, message)

    def _on_closing(self):
        if self._dirty:
            return self._window.create_confirmation_dialog(
                TITLE, "Saqlanmagan o'zgarishlar bor. Baribir chiqilsinmi?")
        return True


def run_native(vibrancy):
    import webview

    mac = sys.platform == "darwin"
    api = Api(vibrancy=mac and vibrancy)
    window = webview.create_window(
        TITLE, os.path.join(UI_DIR, "index.html"), js_api=api,
        width=1360, height=860, min_size=(1000, 620),
        text_select=True, background_color="#E9EEF9",
        vibrancy=api._vibrancy, transparent=api._vibrancy,
    )
    api._window = window
    window.events.closing += api._on_closing
    webview.start()


# Brauzer rejimida faqat dialogsiz funksiyalar ochiq
HTTP_METHODS = {"meta", "examples", "load_example", "parse_source", "assemble", "assemble_rows"}


def run_browser(port):
    api = Api()

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=UI_DIR, **kwargs)

        def do_POST(self):
            name = self.path.partition("/api/")[2]
            if not self.path.startswith("/api/") or name not in HTTP_METHODS:
                self.send_error(404)
                return
            try:
                length = int(self.headers.get("Content-Length", 0))
                args = json.loads(self.rfile.read(length) or b"[]")
                body = json.dumps(getattr(api, name)(*args)).encode("utf-8")
            except Exception as e:      # noqa: BLE001 - xatoni brauzerga qaytaramiz
                self.send_error(400, str(e))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/index.html?backend=http"
    print(f"{TITLE}: {url}\nTo'xtatish uchun Ctrl+C")
    threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def main():
    ap = argparse.ArgumentParser(description=TITLE)
    ap.add_argument("--browser", action="store_true", help="oyna o'rniga brauzerda ochish")
    ap.add_argument("--port", type=int, default=0, help="brauzer rejimi uchun port")
    ap.add_argument("--no-vibrancy", action="store_true",
                    help="macOS da oyna orqasini shaffof qilmaslik")
    args = ap.parse_args()

    if not args.browser:
        try:
            import webview  # noqa: F401
        except ImportError:
            print("pywebview o'rnatilmagan (pip install pywebview) - brauzerda ochilmoqda.")
            args.browser = True
    if args.browser:
        run_browser(args.port)
    else:
        run_native(not args.no_vibrancy)


if __name__ == "__main__":
    main()
