#!/usr/bin/env python3
"""SO'M / SO'M/QV ikki o'tishli assembler - grafik muhit (tkinter).

Ishga tushirish:  python som_gui.py
"""

import os
import sys
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from som import Assembler, AsmError
from som.examples import EXAMPLES, example_path
from som.explain import explain
from som.optab import DIRECTIVES, OPTAB, is_mnemonic

APP_TITLE = "SO'M / SO'M/QV assembler"
MODES = {"Avtomatik": "auto", "SO'M (SIC)": "sic", "SO'M/QV (SIC/XE)": "xe"}

HELP_TEXT = """\
Programma satri formati:
    NISHON   BUYRUQ   OPERAND   izoh

  * Nishon 1-ustundan yoziladi; nishonsiz satr bo'sh joy bilan boshlanadi.
  * '.' yoki '*' bilan boshlangan satr - izoh.
  * +JSUB - 4-format, #3 - bevosita, @RETADR - vositali, BUFFER,X - indeksli.

Ishlash tartibi:
  1. Programmani yozing yoki "Misollar" menyusidan tanlang.
  2. "Assembler qilish" tugmasini (F5) bosing.
  3. Natijalar o'ng tomonda: Listing, SYMTAB, Ob'ekt programma, Xatolar.
  4. Listingdagi satrni tanlasangiz, pastda buyruq bitlarga ajratib
     tushuntiriladi va chapda mos satr belgilanadi.
  5. "Fayl > Natijani saqlash" - .lst va .obj fayllarini yozadi.
"""


class AssemblerApp:
    def __init__(self, root):
        self.root = root
        self.path = None
        self.asm = None
        self.row_lines = {}         # listing qatori id -> SourceLine
        self.src_rows = {}          # boshlang'ich matn satri (1, 2, ...) -> listing qatori id
        self._highlight_job = None
        self._syncing = False
        self.saved_text = ""        # oxirgi saqlangan/ochilgan matn

        self.mono = tkfont.nametofont("TkFixedFont").copy()
        self.mono.configure(size=11)
        self.mono_bold = self.mono.copy()
        self.mono_bold.configure(weight="bold")

        self._build_menu()
        self._build_toolbar()
        self._build_statusbar()     # body dan oldin: pastki qator joyini saqlab qolish uchun
        self._build_body()
        self._bind_keys()

        root.protocol("WM_DELETE_WINDOW", self.on_exit)
        self.load_example("copy_xe.asm")

    # ------------------------------------------------------------------
    # Oyna tuzilishi
    # ------------------------------------------------------------------
    def _build_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=False)
        file_menu.add_command(label="Yangi", accelerator="Ctrl+N", command=self.new_file)
        file_menu.add_command(label="Ochish...", accelerator="Ctrl+O", command=self.open_file)
        file_menu.add_command(label="Saqlash", accelerator="Ctrl+S", command=self.save_file)
        file_menu.add_command(label="Boshqacha saqlash...", command=self.save_file_as)
        file_menu.add_separator()
        file_menu.add_command(label="Natijani saqlash (.lst, .obj)...", command=self.save_results)
        file_menu.add_separator()
        file_menu.add_command(label="Chiqish", command=self.on_exit)
        menubar.add_cascade(label="Fayl", menu=file_menu)

        ex_menu = tk.Menu(menubar, tearoff=False)
        for title, name in EXAMPLES:
            ex_menu.add_command(label=title, command=lambda n=name: self.load_example(n))
        menubar.add_cascade(label="Misollar", menu=ex_menu)

        help_menu = tk.Menu(menubar, tearoff=False)
        help_menu.add_command(label="Qo'llanma", accelerator="F1", command=self.show_help)
        help_menu.add_command(label="Buyruqlar jadvali (OPTAB)", command=self.show_optab)
        help_menu.add_command(label="Dastur haqida", command=self.show_about)
        menubar.add_cascade(label="Yordam", menu=help_menu)
        self.root.config(menu=menubar)

    def _build_toolbar(self):
        bar = ttk.Frame(self.root, padding=(6, 4))
        bar.pack(side=tk.TOP, fill=tk.X)
        ttk.Button(bar, text="Ochish", command=self.open_file).pack(side=tk.LEFT)
        ttk.Button(bar, text="Saqlash", command=self.save_file).pack(side=tk.LEFT, padx=(4, 0))
        ttk.Separator(bar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(bar, text="Rejim:").pack(side=tk.LEFT)
        self.mode_var = tk.StringVar(value="Avtomatik")
        ttk.Combobox(bar, textvariable=self.mode_var, values=list(MODES), state="readonly",
                     width=18).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="▶  Assembler qilish (F5)", command=self.run_assembler).pack(
            side=tk.LEFT, padx=(8, 0))

    def _build_body(self):
        paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 4))

        # --- chap: boshlang'ich programma muharriri
        left = ttk.LabelFrame(paned, text="Boshlang'ich programma", padding=4)
        paned.add(left, weight=1)
        self.gutter = tk.Text(left, width=5, padx=4, takefocus=0, bd=0, state=tk.DISABLED,
                              font=self.mono, background="#eeeeee", foreground="#888888")
        self.gutter.pack(side=tk.LEFT, fill=tk.Y)
        self.editor = tk.Text(left, wrap=tk.NONE, undo=True, font=self.mono, width=60)
        ys = ttk.Scrollbar(left, orient=tk.VERTICAL, command=self._scroll_both)
        xs = ttk.Scrollbar(left, orient=tk.HORIZONTAL, command=self.editor.xview)
        self.editor.configure(yscrollcommand=lambda *a: (ys.set(*a), self._sync_gutter()),
                              xscrollcommand=xs.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        xs.pack(side=tk.BOTTOM, fill=tk.X)
        self.editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.editor.tag_configure("comment", foreground="#7a7a7a", font=self.mono)
        self.editor.tag_configure("label", foreground="#0b5cad")
        self.editor.tag_configure("opcode", foreground="#8a1c9e", font=self.mono_bold)
        self.editor.tag_configure("directive", foreground="#b35c00", font=self.mono_bold)
        self.editor.tag_configure("string", foreground="#2e7d32")
        self.editor.tag_configure("error", background="#ffd6d6")
        self.editor.tag_configure("current", background="#fff3b0")
        self.editor.tag_raise("current")
        self.editor.bind("<<Modified>>", self._on_modified)
        self.editor.bind("<ButtonRelease-1>", self._on_editor_click)
        self.editor.bind("<KeyRelease>", self._on_editor_key)

        # --- o'ng: natijalar
        right = ttk.Notebook(paned)
        paned.add(right, weight=1)
        self.notebook = right

        # Listing + buyruq tahlili
        lst_tab = ttk.PanedWindow(right, orient=tk.VERTICAL)
        right.add(lst_tab, text="Listing")
        cols = ("satr", "adres", "nishon", "buyruq", "operand", "kod")
        heads = ("Satr", "Adres", "Nishon", "Buyruq", "Operand", "Ob'ekt kodi")
        widths = (50, 60, 80, 80, 160, 100)
        self.listing = self._make_tree(lst_tab, cols, heads, widths)
        lst_tab.add(self.listing.master, weight=3)
        self.listing.tag_configure("error", background="#ffd6d6")
        self.listing.tag_configure("comment", foreground="#888888")
        self.listing.tag_configure("literal", foreground="#2e7d32")
        self.listing.bind("<<TreeviewSelect>>", self._on_listing_select)

        info = ttk.LabelFrame(lst_tab, text="Buyruq tahlili", padding=4)
        lst_tab.add(info, weight=2)
        self.explain_box = tk.Text(info, height=12, wrap=tk.NONE, font=self.mono,
                                   state=tk.DISABLED, background="#fbfbf5")
        self.explain_box.pack(fill=tk.BOTH, expand=True)

        # SYMTAB
        sym_frame = ttk.Frame(right)
        right.add(sym_frame, text="SYMTAB")
        self.symtab = self._make_tree(sym_frame, ("sek", "nom", "qiymat", "tur"),
                                      ("Seksiya", "Nom", "Qiymat (16-lik)", "Turi"),
                                      (100, 100, 120, 100))
        self.symtab.master.pack(fill=tk.BOTH, expand=True)

        # Ob'ekt programma
        obj_frame = ttk.Frame(right, padding=4)
        right.add(obj_frame, text="Ob'ekt programma")
        self.obj_box = tk.Text(obj_frame, wrap=tk.NONE, font=self.mono, state=tk.DISABLED)
        oxs = ttk.Scrollbar(obj_frame, orient=tk.HORIZONTAL, command=self.obj_box.xview)
        oys = ttk.Scrollbar(obj_frame, orient=tk.VERTICAL, command=self.obj_box.yview)
        self.obj_box.configure(xscrollcommand=oxs.set, yscrollcommand=oys.set)
        oys.pack(side=tk.RIGHT, fill=tk.Y)
        oxs.pack(side=tk.BOTTOM, fill=tk.X)
        self.obj_box.pack(fill=tk.BOTH, expand=True)
        for tag, color in (("H", "#0b5cad"), ("T", "#222222"), ("M", "#b35c00"),
                           ("E", "#8a1c9e"), ("D", "#2e7d32"), ("R", "#2e7d32")):
            self.obj_box.tag_configure(tag, foreground=color)

        # Xatolar
        err_frame = ttk.Frame(right)
        right.add(err_frame, text="Xatolar")
        self.errors = self._make_tree(err_frame, ("satr", "xato"), ("Satr", "Xato"), (60, 500))
        self.errors.master.pack(fill=tk.BOTH, expand=True)
        self.errors.bind("<<TreeviewSelect>>", self._on_error_select)

    def _make_tree(self, parent, cols, heads, widths):
        frame = ttk.Frame(parent)
        tree = ttk.Treeview(frame, columns=cols, show="headings", selectmode="browse")
        for col, head, width in zip(cols, heads, widths):
            tree.heading(col, text=head, anchor=tk.W)
            tree.column(col, width=width, anchor=tk.W, stretch=(col in ("operand", "xato")))
        ys = ttk.Scrollbar(frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=ys.set)
        ys.pack(side=tk.RIGHT, fill=tk.Y)
        tree.pack(fill=tk.BOTH, expand=True)
        return tree

    def _build_statusbar(self):
        self.status = tk.StringVar(value="Tayyor")
        ttk.Label(self.root, textvariable=self.status, anchor=tk.W, relief=tk.SUNKEN,
                  padding=(6, 2)).pack(side=tk.BOTTOM, fill=tk.X)

    def _bind_keys(self):
        self.root.bind("<F5>", lambda e: self.run_assembler())
        self.root.bind("<F1>", lambda e: self.show_help())
        self.root.bind("<Control-n>", lambda e: self.new_file())
        self.root.bind("<Control-o>", lambda e: self.open_file())
        self.root.bind("<Control-s>", lambda e: (self.save_file(), "break")[1])

    # ------------------------------------------------------------------
    # Muharrir: satr nomerlari va rang berish
    # ------------------------------------------------------------------
    def _scroll_both(self, *args):
        self.editor.yview(*args)
        self._sync_gutter()

    def _sync_gutter(self):
        self.gutter.yview_moveto(self.editor.yview()[0])

    def _update_gutter(self):
        count = int(self.editor.index("end-1c").split(".")[0])
        # listingdagi kabi satrlar 5, 10, 15, ... deb nomerlanadi
        numbers = "\n".join(str(i * 5) for i in range(1, count + 1))
        self.gutter.configure(state=tk.NORMAL)
        self.gutter.delete("1.0", tk.END)
        self.gutter.insert("1.0", numbers)
        self.gutter.configure(state=tk.DISABLED)
        self._sync_gutter()

    def _on_modified(self, _event=None):
        # <<Modified>> faqat bayroq o'zgarganda keladi, shuning uchun uni qaytadan tushiramiz
        if not self.editor.edit_modified():
            return
        self.editor.edit_modified(False)
        self._set_title()
        if self._highlight_job:
            self.root.after_cancel(self._highlight_job)
        self._highlight_job = self.root.after(150, self._refresh_editor)

    def _refresh_editor(self):
        self._highlight_job = None
        self._update_gutter()
        self.highlight_syntax()

    def highlight_syntax(self):
        ed = self.editor
        for tag in ("comment", "label", "opcode", "directive", "string"):
            ed.tag_remove(tag, "1.0", tk.END)
        lines = ed.get("1.0", "end-1c").split("\n")
        for row, text in enumerate(lines, start=1):
            stripped = text.strip()
            if not stripped:
                continue
            if stripped[0] in ".*":
                ed.tag_add("comment", f"{row}.0", f"{row}.end")
                continue
            words = []          # (boshlanish, tugash, so'z) - birinchi 3 ta so'z
            col = 0
            while col < len(text) and len(words) < 3:
                while col < len(text) and text[col].isspace():
                    col += 1
                start = col
                while col < len(text) and not text[col].isspace():
                    col += 1
                if start < col:
                    words.append((start, col, text[start:col]))
            for start, end, word in words[:2]:
                if is_mnemonic(word):
                    tag = "directive" if word.upper() in DIRECTIVES else "opcode"
                    ed.tag_add(tag, f"{row}.{start}", f"{row}.{end}")
                    break
                if start == 0:
                    ed.tag_add("label", f"{row}.{start}", f"{row}.{end}")
            pos = text.find("'")
            while pos != -1:
                end = text.find("'", pos + 1)
                if end == -1:
                    break
                ed.tag_add("string", f"{row}.{max(pos - 1, 0)}", f"{row}.{end + 1}")
                pos = text.find("'", end + 1)

    # ------------------------------------------------------------------
    # Fayllar
    # ------------------------------------------------------------------
    @property
    def dirty(self):
        """Saqlanmagan o'zgarishlar bormi."""
        return self.editor.get("1.0", "end-1c") != self.saved_text

    def _set_title(self):
        name = os.path.basename(self.path) if self.path else "nomsiz"
        mark = "*" if self.dirty else ""
        self.root.title(f"{mark}{name} - {APP_TITLE}")

    def _set_source(self, text, path):
        self.editor.delete("1.0", tk.END)
        self.editor.insert("1.0", text)
        self.editor.edit_reset()
        self.path = path
        self.saved_text = self.editor.get("1.0", "end-1c")
        self._refresh_editor()
        self._set_title()

    def _confirm_discard(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(APP_TITLE, "O'zgarishlar saqlansinmi?")
        if answer is None:
            return False
        return self.save_file() if answer else True

    def new_file(self):
        if self._confirm_discard():
            self._set_source("PROG     START   0\nFIRST    RSUB\n         END     FIRST\n", None)
            self._clear_results()

    def open_file(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Programmani ochish",
            filetypes=[("Assembler fayllari", "*.asm *.txt"), ("Barcha fayllar", "*.*")])
        if path:
            with open(path, encoding="utf-8", errors="replace") as f:
                self._set_source(f.read(), path)
            self.run_assembler()

    def load_example(self, name):
        if not self._confirm_discard():
            return
        path = example_path(name)
        with open(path, encoding="utf-8") as f:
            self._set_source(f.read(), path)
        self.run_assembler()

    def save_file(self):
        if not self.path:
            return self.save_file_as()
        with open(self.path, "w", encoding="utf-8") as f:
            self.saved_text = self.editor.get("1.0", "end-1c")
            f.write(self.saved_text)
        self._set_title()
        self.status.set(f"Saqlandi: {self.path}")
        return True

    def save_file_as(self):
        path = filedialog.asksaveasfilename(
            title="Programmani saqlash", defaultextension=".asm",
            filetypes=[("Assembler fayllari", "*.asm"), ("Barcha fayllar", "*.*")])
        if not path:
            return False
        self.path = path
        return self.save_file()

    def save_results(self):
        if not self.asm:
            self.run_assembler()
        if not self.asm:
            return
        initial = os.path.splitext(os.path.basename(self.path))[0] if self.path else "natija"
        path = filedialog.asksaveasfilename(
            title="Natija fayllari nomi (kengaytmasiz)", initialfile=initial,
            filetypes=[("Barcha fayllar", "*.*")])
        if not path:
            return
        base = os.path.splitext(path)[0]
        with open(base + ".lst", "w", encoding="utf-8") as f:
            f.write(self.asm.listing())
        saved = [base + ".lst"]
        if not self.asm.has_errors:
            with open(base + ".obj", "w", encoding="utf-8") as f:
                f.write(self.asm.object_program())
            saved.append(base + ".obj")
        messagebox.showinfo(APP_TITLE, "Saqlandi:\n" + "\n".join(saved))

    def on_exit(self):
        if self._confirm_discard():
            self.root.destroy()

    # ------------------------------------------------------------------
    # Assembler
    # ------------------------------------------------------------------
    def _clear_results(self):
        self.asm = None
        self.row_lines.clear()
        self.src_rows.clear()
        for tree in (self.listing, self.symtab, self.errors):
            tree.delete(*tree.get_children())
        for box in (self.obj_box, self.explain_box):
            self._set_text(box, "")
        self.editor.tag_remove("error", "1.0", tk.END)
        self.editor.tag_remove("current", "1.0", tk.END)

    @staticmethod
    def _set_text(box, text):
        box.configure(state=tk.NORMAL)
        box.delete("1.0", tk.END)
        box.insert("1.0", text)
        box.configure(state=tk.DISABLED)

    def run_assembler(self):
        self._clear_results()
        source = self.editor.get("1.0", "end-1c")
        try:
            asm = Assembler(source, MODES[self.mode_var.get()]).assemble()
        except AsmError as e:
            self.status.set(f"XATO: {e}")
            return
        self.asm = asm
        self._fill_listing(asm)
        self._fill_symtab(asm)
        self._fill_object(asm)
        n_err = self._fill_errors(asm)

        mode = "SO'M/QV (SIC/XE)" if asm.xe else "SO'M (SIC)"
        sections = ", ".join(f"{s.name or 'nomsiz'} = {s.length:X}h bayt" for s in asm.sections)
        if n_err:
            self.status.set(f"Rejim: {mode}   |   Xatolar: {n_err} - ob'ekt programma yaratilmadi")
            self.notebook.select(3)
        else:
            self.status.set(f"Rejim: {mode}   |   Xatolar yo'q   |   Uzunlik: {sections}")

    def _fill_listing(self, asm):
        for line in asm.lines:
            if line.is_comment:
                values = (line.lineno, "", "", "", line.text.strip(), "")
                tags = ("comment",)
            elif line.is_literal_pool:
                values = ("", f"{line.loc:04X}", "*", "", line.operand, line.obj)
                tags = ("literal",)
            else:
                hide_loc = line.opcode in ("END", "BASE", "NOBASE", "EXTDEF", "EXTREF", "LTORG")
                loc = "" if line.loc is None or hide_loc else f"{line.loc:04X}"
                opcode = ("+" if line.extended else "") + (line.opcode or "")
                values = (line.lineno, loc, line.label or "", opcode, line.operand or "", line.obj)
                tags = ("error",) if line.errors else ()
            iid = self.listing.insert("", tk.END, values=values, tags=tags)
            self.row_lines[iid] = line
            if line.lineno:
                self.src_rows[line.lineno // 5] = iid
                if line.errors:
                    row = line.lineno // 5
                    self.editor.tag_add("error", f"{row}.0", f"{row}.end+1c")

    def _fill_symtab(self, asm):
        for sec in asm.sections:
            name = sec.name or "nomsiz"
            for sym_name, sym in sorted(sec.symtab.items(), key=lambda kv: kv[1].value):
                kind = "nisbiy" if sym.relative else "absolyut"
                self.symtab.insert("", tk.END, values=(name, sym_name, f"{sym.value:06X}", kind))
            for ext in sec.extref:
                self.symtab.insert("", tk.END, values=(name, ext, "?", "tashqi (EXTREF)"))

    def _fill_object(self, asm):
        box = self.obj_box
        box.configure(state=tk.NORMAL)
        box.delete("1.0", tk.END)
        if asm.has_errors:
            box.insert("1.0", "Programmada xatolar bor - ob'ekt programma yaratilmadi.\n"
                              "\"Xatolar\" bo'limiga qarang.")
        else:
            for rec in asm.object_program().splitlines(keepends=True):
                box.insert(tk.END, rec, (rec[:1],))
            box.insert(tk.END, "\n" + RECORD_HELP)
        box.configure(state=tk.DISABLED)

    def _fill_errors(self, asm):
        count = 0
        for iid, line in self.row_lines.items():
            for err in line.errors:
                self.errors.insert("", tk.END, iid=f"err{count}", values=(line.lineno or "", err))
                count += 1
        return count

    # ------------------------------------------------------------------
    # Tanlash: listing <-> muharrir
    # ------------------------------------------------------------------
    def _mark_source_row(self, row):
        self.editor.tag_remove("current", "1.0", tk.END)
        self.editor.tag_add("current", f"{row}.0", f"{row}.end+1c")
        self.editor.see(f"{row}.0")

    def _on_listing_select(self, _event=None):
        sel = self.listing.selection()
        if not sel or self.asm is None:
            return
        line = self.row_lines.get(sel[0])
        if line is None:
            return
        self._set_text(self.explain_box, explain(line, self.asm.xe))
        if line.lineno and not self._syncing:
            self._mark_source_row(line.lineno // 5)

    def _on_error_select(self, _event=None):
        sel = self.errors.selection()
        if not sel:
            return
        lineno = self.errors.item(sel[0], "values")[0]
        if lineno:
            row = int(lineno) // 5
            self._mark_source_row(row)
            iid = self.src_rows.get(row)
            if iid:
                self._select_listing(iid)

    def _select_listing(self, iid):
        self._syncing = True
        self.listing.selection_set(iid)
        self.listing.see(iid)
        self._on_listing_select()
        self._syncing = False

    def _on_editor_click(self, _event=None):
        row = int(self.editor.index(tk.INSERT).split(".")[0])
        iid = self.src_rows.get(row)
        if iid:
            self.editor.tag_remove("current", "1.0", tk.END)
            self._select_listing(iid)

    def _on_editor_key(self, event):
        if event.keysym in ("Up", "Down", "Prior", "Next"):
            self._on_editor_click()

    # ------------------------------------------------------------------
    # Yordam oynalari
    # ------------------------------------------------------------------
    def _text_window(self, title, text, width=70, height=24):
        win = tk.Toplevel(self.root)
        win.title(title)
        box = tk.Text(win, wrap=tk.WORD, font=self.mono, width=width, height=height, padx=8, pady=8)
        box.insert("1.0", text)
        box.configure(state=tk.DISABLED)
        box.pack(fill=tk.BOTH, expand=True)
        ttk.Button(win, text="Yopish", command=win.destroy).pack(pady=6)

    def show_help(self):
        self._text_window("Qo'llanma", HELP_TEXT)

    def show_optab(self):
        rows = [f"{'Buyruq':<8}{'Kod':<6}Format", "-" * 22]
        for name, (code, fmt) in sorted(OPTAB.items()):
            rows.append(f"{name:<8}{code:02X}    {'3/4' if fmt == 3 else fmt}")
        self._text_window("OPTAB", "\n".join(rows), width=30, height=30)

    def show_about(self):
        messagebox.showinfo(APP_TITLE,
                            "Soddalashtirilgan o'quv mashinasi (SO'M) va SO'M/QV uchun\n"
                            "ikki o'tishli assembler.\n\n"
                            "1-o'tish: adreslar (LOCCTR) va SYMTAB.\n"
                            "2-o'tish: mashina kodi va ob'ekt programma.")


RECORD_HELP = """\
--------------------------------------------------------------
H - bosh qism: nomi, boshlang'ich adresi, uzunligi
D - EXTDEF: boshqa seksiyalarga ochiq nomlar va adreslari
R - EXTREF: tashqi nomlar
T - tana: boshlang'ich adres, uzunlik (<= 1E bayt), kodlar
M - modifikatsiya: adres, yarim baytlar soni, [+/-nom]
E - tugallash: birinchi bajariladigan buyruq adresi
"""


def main():
    if sys.platform == "win32":
        try:                                    # Windows da xira shriftni oldini olish
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    root.geometry("1280x760")
    root.minsize(900, 500)
    style = ttk.Style(root)
    if "vista" in style.theme_names():
        style.theme_use("vista")
    elif "clam" in style.theme_names():
        style.theme_use("clam")
    AssemblerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
