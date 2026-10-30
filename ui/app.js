// SO'M Assembler - interfeys mantig'i.
// Python bilan aloqa: alohida oynada window.pywebview.api, brauzer rejimida /api/<nom>.

const HTTP = new URLSearchParams(location.search).get("backend") === "http";
const REG_NAMES = { 0: "A", 1: "X", 2: "L", 3: "B", 4: "S", 5: "T", 6: "F", 8: "PC", 9: "SW" };

const $ = (sel) => document.querySelector(sel);
const ui = {
  source: $("#source"), highlight: $("#highlight"), gutter: $("#gutter"),
  fileName: $("#fileName"), listing: $("#listingTable tbody"), listingScroll: $("#listingScroll"),
  symtab: $("#symtabTable tbody"), errors: $("#errorsTable tbody"), noErrors: $("#noErrors"),
  objectBox: $("#objectBox"), bits: $("#bits"), explain: $("#explain"),
  errBadge: $("#errBadge"), statusDot: $("#statusDot"), statusText: $("#statusText"),
  statusRight: $("#statusRight"), toast: $("#toast"), live: $("#liveToggle"),
  examplesMenu: $("#examplesMenu"), filePicker: $("#filePicker"),
};

const state = {
  meta: null, mode: "auto", result: null, selected: null, curRow: null,
  savedText: "", name: "nomsiz", errorRows: new Set(), wasDirty: false,
};

// ---------------------------------------------------------------- backend
function backendReady() {
  return new Promise((resolve) => {
    if (HTTP || (window.pywebview && window.pywebview.api && window.pywebview.api.assemble)) return resolve();
    window.addEventListener("pywebviewready", () => resolve(), { once: true });
  });
}

async function call(name, ...args) {
  if (HTTP) {
    const res = await fetch("/api/" + name, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(args),
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  }
  return window.pywebview.api[name](...args);
}

// ---------------------------------------------------------------- yordamchilar
const esc = (s) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const pad = (v, n) => v.toString(2).padStart(n, "0");

let toastTimer = null;
function toast(msg) {
  ui.toast.textContent = msg;
  ui.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (ui.toast.hidden = true), 2200);
}

function isMnemonic(word) {
  const w = (word || "").toUpperCase().replace(/^\+/, "");
  return state.meta.opcodeSet.has(w) || state.meta.directiveSet.has(w);
}

// ---------------------------------------------------------------- rangli matn
// Python dagi parser.py bilan bir xil qoidalar: nishon 1-ustunda, keyin buyruq, operand, izoh.
function readWord(text, pos) {
  while (pos < text.length && /\s/.test(text[pos])) pos++;
  const start = pos;
  while (pos < text.length && !/\s/.test(text[pos])) pos++;
  return [start, pos];
}

function readOperand(text, pos) {
  while (pos < text.length && /\s/.test(text[pos])) pos++;
  const start = pos;
  let last = "";
  while (pos < text.length) {
    const c = text[pos];
    if (c === "'") {
      let end = text.indexOf("'", pos + 1);
      if (end === -1) end = text.length - 1;
      last = "'";
      pos = end + 1;
      continue;
    }
    if (/\s/.test(c)) {
      let nxt = pos;
      while (nxt < text.length && /\s/.test(text[nxt])) nxt++;
      if (nxt < text.length && (",+-".includes(last) && last !== "" || ",+-".includes(text[nxt]))) {
        pos = nxt;
        continue;
      }
      break;
    }
    last = c;
    pos++;
  }
  return [start, pos];
}

function colorOperand(s) {
  let out = "";
  const re = /([CX]'[^']*'?)|(\d+)|([#@=])/gi;
  let i = 0, m;
  while ((m = re.exec(s))) {
    out += esc(s.slice(i, m.index));
    const cls = m[1] ? "tok-str" : m[2] ? "tok-num" : "tok-mod";
    out += `<span class="${cls}">${esc(m[0])}</span>`;
    i = re.lastIndex;
  }
  return out + esc(s.slice(i));
}

function highlightLine(text) {
  const stripped = text.trim();
  if (!stripped) return esc(text);
  if (".*".includes(stripped[0])) return `<span class="tok-comment">${esc(text)}</span>`;

  const segs = [];      // [boshlanish, tugash, html]
  let [s1, e1] = readWord(text, 0);
  let opStart = s1, opEnd = e1;
  if (!/^\s/.test(text)) {
    const [s2, e2] = readWord(text, e1);
    const first = text.slice(s1, e1), second = text.slice(s2, e2);
    if (!(isMnemonic(first) && !isMnemonic(second))) {
      segs.push([s1, e1, `<span class="tok-label">${esc(first)}</span>`]);
      opStart = s2; opEnd = e2;
    }
  }
  const opWord = text.slice(opStart, opEnd);
  const op = opWord.toUpperCase().replace(/^\+/, "");
  if (opWord) {
    const cls = state.meta.directiveSet.has(op) ? "tok-dir" : isMnemonic(op) ? "tok-op" : "";
    segs.push([opStart, opEnd, cls ? `<span class="${cls}">${esc(opWord)}</span>` : esc(opWord)]);
  }
  let pos = opEnd;
  if (!state.meta.noOperandSet.has(op)) {
    const [os, oe] = readOperand(text, opEnd);
    if (oe > os) segs.push([os, oe, colorOperand(text.slice(os, oe))]);
    pos = oe;
  }
  const rest = text.slice(pos);
  if (rest.trim()) {
    const cs = pos + rest.search(/\S/);
    segs.push([cs, text.length, `<span class="tok-comment">${esc(text.slice(cs))}</span>`]);
  }
  let html = "", i = 0;
  for (const [s, e, h] of segs) {
    html += esc(text.slice(i, s)) + h;
    i = e;
  }
  return html + esc(text.slice(i));
}

function renderEditor() {
  const lines = ui.source.value.split("\n");
  let html = "", nums = "";
  lines.forEach((line, i) => {
    const row = i + 1;
    const cls = ["ln"];
    if (state.errorRows.has(row)) cls.push("err");
    if (state.curRow === row) cls.push("cur");
    html += `<span class="${cls.join(" ")}">${highlightLine(line) || " "}</span>`;
    const n = String(row * 5);
    nums += (state.errorRows.has(row) ? `<span class="err">${n}</span>` : n) + "\n";
  });
  ui.highlight.innerHTML = html;
  ui.gutter.innerHTML = nums;
  syncScroll();
}

function syncScroll() {
  ui.highlight.scrollTop = ui.source.scrollTop;
  ui.highlight.scrollLeft = ui.source.scrollLeft;
  ui.gutter.scrollTop = ui.source.scrollTop;
}

function revealSourceRow(row) {
  const lineH = 20, ta = ui.source;
  const top = (row - 1) * lineH;
  if (top < ta.scrollTop || top > ta.scrollTop + ta.clientHeight - 2 * lineH) {
    ta.scrollTop = Math.max(0, top - ta.clientHeight / 3);
  }
  syncScroll();
}

function currentSourceRow() {
  return ui.source.value.slice(0, ui.source.selectionStart).split("\n").length;
}

// ---------------------------------------------------------------- fayl holati
function isDirty() { return ui.source.value !== state.savedText; }

function updateTitle() {
  const dirty = isDirty();
  ui.fileName.textContent = (dirty ? "● " : "") + state.name;
  document.title = `${dirty ? "• " : ""}${state.name} — SO'M Assembler`;
  if (dirty !== state.wasDirty) {
    state.wasDirty = dirty;
    if (!HTTP) call("set_dirty", dirty);
  }
}

function setSource(text, name) {
  ui.source.value = text;
  state.savedText = text;
  state.name = name;
  state.curRow = null;
  state.selected = null;
  ui.source.scrollTop = 0;
  updateTitle();
  renderEditor();
  assemble();
}

async function confirmDiscard() {
  if (!isDirty()) return true;
  const msg = "Saqlanmagan o'zgarishlar yo'qoladi. Davom etilsinmi?";
  return HTTP ? window.confirm(msg) : call("confirm", msg);
}

function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

const baseName = () => state.name.replace(/\.[^.]*$/, "") || "programma";

async function newFile() {
  if (!(await confirmDiscard())) return;
  setSource("PROG     START   0\nFIRST    RSUB\n         END     FIRST\n", "nomsiz");
}

async function openFile() {
  if (!(await confirmDiscard())) return;
  if (HTTP) return ui.filePicker.click();
  const res = await call("open_file");
  if (res) setSource(res.text, res.name);
}

async function saveFile() {
  if (HTTP) {
    const name = state.name === "nomsiz" ? "programma.asm" : state.name;
    download(name, ui.source.value);
    state.name = name;
  } else {
    const suggested = state.name === "nomsiz" ? "programma.asm" : state.name;
    const res = await call("save_file", ui.source.value, false, suggested);
    if (!res) return;
    state.name = res.name;
  }
  state.savedText = ui.source.value;
  updateTitle();
  toast("Saqlandi: " + state.name);
}

async function exportResults() {
  const r = state.result;
  if (HTTP) {
    if (!r || r.fatal) return toast("Avval programmani assembler qiling");
    download(baseName() + ".lst", r.listingText);
    if (r.object) download(baseName() + ".obj", r.object);
    return toast(r.object ? ".lst va .obj saqlandi" : ".lst saqlandi (xatolar bor - .obj yo'q)");
  }
  const res = await call("save_results", ui.source.value, state.mode, baseName());
  if (res) toast("Saqlandi: " + res.saved.join(", "));
}

// ---------------------------------------------------------------- assembler
let assembleSeq = 0;
async function assemble() {
  const seq = ++assembleSeq;
  const res = await call("assemble", ui.source.value, state.mode);
  if (seq !== assembleSeq) return;         // eskirgan javob
  state.result = res;
  renderResults();
}

function renderResults() {
  const r = state.result;
  if (r.fatal) {
    state.errorRows = new Set();
    ui.listing.innerHTML = ui.symtab.innerHTML = ui.errors.innerHTML = "";
    ui.objectBox.textContent = "";
    setStatus(false, "XATO: " + r.fatal, "");
    renderEditor();
    return;
  }
  state.errorRows = new Set(r.rows.filter((x) => x.errors.length && x.srcRow).map((x) => x.srcRow));

  // Listing
  ui.listing.innerHTML = r.rows.map((row, i) => {
    const cls = [row.kind];
    if (row.errors.length) cls.push("error");
    const td = (v, c = "") => `<td${c ? ` class="${c}"` : ""}>${esc(String(v ?? ""))}</td>`;
    return `<tr data-idx="${i}" class="${cls.join(" ")}">` +
      td(row.lineno ?? "", "num") + td(row.loc) + td(row.label) + td(row.opcode, "op") +
      td(row.operand) + td(row.obj, "obj") + "</tr>";
  }).join("");

  // SYMTAB
  ui.symtab.innerHTML = r.symtab.map((s) =>
    `<tr><td>${esc(s.section)}</td><td>${esc(s.name)}</td><td class="obj">${s.value}</td>` +
    `<td class="msg">${esc(s.kind)}</td></tr>`).join("");

  // Ob'ekt programma
  if (r.object) {
    ui.objectBox.innerHTML = r.object.trimEnd().split("\n").map((line) => {
      if (!line) return "";
      const body = esc(line).replace(/\^/g, '<span class="sep">^</span>');
      return `<span class="rec-${line[0]}"><b>${body[0]}</b>${body.slice(1)}</span>`;
    }).join("\n");
  } else {
    ui.objectBox.textContent = "Programmada xatolar bor - ob'ekt programma yaratilmadi.\n\"Xatolar\" bo'limiga qarang.";
  }

  // Xatolar
  const errs = [];
  r.rows.forEach((row, i) => row.errors.forEach((e) => errs.push([i, row.lineno, e])));
  ui.errors.innerHTML = errs.map(([i, n, e]) =>
    `<tr data-idx="${i}" class="error"><td class="num">${n ?? ""}</td><td class="msg">${esc(e)}</td></tr>`).join("");
  ui.noErrors.hidden = errs.length > 0;
  ui.errBadge.hidden = errs.length === 0;
  ui.errBadge.textContent = errs.length;

  const modeName = r.mode === "xe" ? "SO'M/QV (SIC/XE)" : "SO'M (SIC)";
  const lengths = r.sections.map((s) => `${s.name}: ${s.length}h bayt`).join("   ");
  setStatus(errs.length === 0,
    errs.length ? `${modeName}  ·  ${errs.length} ta xato — ob'ekt programma yaratilmadi`
                : `${modeName}  ·  Xatolar yo'q`,
    lengths);

  // oldingi tanlovni saqlab qolish
  if (state.curRow != null) {
    const idx = r.rows.findIndex((x) => x.srcRow === state.curRow);
    if (idx >= 0) selectRow(idx, { scrollEditor: false });
  } else {
    showAnalysis(null);
  }
  renderEditor();
}

function setStatus(ok, text, right) {
  ui.statusDot.className = "dot " + (ok ? "ok" : "bad");
  ui.statusText.textContent = text;
  ui.statusRight.textContent = right;
}

// ---------------------------------------------------------------- tanlash va tahlil
function selectRow(idx, { scrollEditor = true, scrollTable = true } = {}) {
  const r = state.result;
  if (!r || !r.rows || !r.rows[idx]) return;
  ui.listing.querySelectorAll("tr.selected").forEach((tr) => tr.classList.remove("selected"));
  const tr = ui.listing.querySelector(`tr[data-idx="${idx}"]`);
  if (tr) {
    tr.classList.add("selected");
    if (scrollTable) tr.scrollIntoView({ block: "nearest" });
  }
  state.selected = idx;
  const row = r.rows[idx];
  showAnalysis(row);
  if (row.srcRow) {
    state.curRow = row.srcRow;
    renderEditor();
    if (scrollEditor) revealSourceRow(row.srcRow);
  }
}

function field(name, value, cls, sub) {
  return `<div class="bit-field ${cls}"><span class="bit-name">${name}</span>` +
    `<span class="bit-val">${value}</span>${sub ? `<span class="bit-sub">${sub}</span>` : ""}</div>`;
}

function bitFields(row) {
  if (!row || !row.isInstr || !row.obj) return "";
  const v = parseInt(row.obj, 16) >>> 0;
  const fmt = row.obj.length / 2;
  const hex = (x, n) => x.toString(16).toUpperCase().padStart(n, "0");
  if (fmt === 1) return field("opcode", pad(v, 8), "opcode", hex(v, 2));
  if (fmt === 2) {
    const op = v >>> 8, r1 = (v >>> 4) & 15, r2 = v & 15;
    return field("opcode", pad(op, 8), "opcode", hex(op, 2)) +
      field("r1", pad(r1, 4), "reg", REG_NAMES[r1] || r1) + field("r2", pad(r2, 4), "reg", REG_NAMES[r2] || r2);
  }
  if (state.result.mode !== "xe") {
    const op = v >>> 16, x = (v >>> 15) & 1, addr = v & 0x7fff;
    return field("opcode", pad(op, 8), "opcode", hex(op, 2)) +
      field("x", x, "flag" + (x ? " on" : "")) + field("adres", pad(addr, 15), "addr", hex(addr, 4));
  }
  const shift = fmt === 4 ? 20 : 12;
  const first = v >>> (shift + 4);
  const flags = (v >>> shift) & 15;
  const disp = fmt === 4 ? v & 0xfffff : v & 0xfff;
  const bits = { n: (first >>> 1) & 1, i: first & 1, x: flags >>> 3, b: (flags >>> 2) & 1, p: (flags >>> 1) & 1, e: flags & 1 };
  let html = field("opcode", pad(first >>> 2, 6), "opcode", hex(first & 0xfc, 2));
  for (const [k, b] of Object.entries(bits)) html += field(k, b, "flag" + (b ? " on" : ""));
  return html + field(fmt === 4 ? "adres" : "disp", pad(disp, fmt === 4 ? 20 : 12), "addr",
    hex(disp, fmt === 4 ? 5 : 3));
}

function showAnalysis(row) {
  const chips = bitFields(row);
  ui.bits.innerHTML = chips;
  let text = row ? row.explain : "Listingdagi satrni tanlang - buyruq bitlarga ajratib ko'rsatiladi.";
  if (chips) {
    // bitlar yuqorida "chip"lar bilan ko'rsatilgan - matndagi jadvalni olib tashlaymiz
    text = text.split("\n").filter((l) => !l.startsWith("|") && !l.startsWith("Standart SO'M formati")).join("\n")
      .replace(/\n{3,}/g, "\n\n");
  }
  ui.explain.textContent = text;
}

// ---------------------------------------------------------------- hodisalar
let liveTimer = null;
ui.source.addEventListener("input", () => {
  updateTitle();
  renderEditor();
  if (ui.live.checked) {
    clearTimeout(liveTimer);
    liveTimer = setTimeout(assemble, 350);
  }
});
ui.source.addEventListener("scroll", syncScroll);
ui.source.addEventListener("keydown", (e) => {
  if (e.key === "Tab" && !e.metaKey && !e.ctrlKey) {
    e.preventDefault();
    document.execCommand("insertText", false, "\t");
  }
});
function editorCursorMoved() {
  const row = currentSourceRow();
  if (!state.result || !state.result.rows) return;
  const idx = state.result.rows.findIndex((x) => x.srcRow === row);
  if (idx >= 0) selectRow(idx, { scrollEditor: false });
}
ui.source.addEventListener("click", editorCursorMoved);
ui.source.addEventListener("keyup", (e) => {
  if (["ArrowUp", "ArrowDown", "PageUp", "PageDown"].includes(e.key)) editorCursorMoved();
});

ui.listing.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  if (tr) selectRow(+tr.dataset.idx);
});
ui.listingScroll.addEventListener("keydown", (e) => {
  if (state.selected == null || !["ArrowUp", "ArrowDown"].includes(e.key)) return;
  e.preventDefault();
  selectRow(state.selected + (e.key === "ArrowDown" ? 1 : -1));
});
ui.listingScroll.tabIndex = 0;

ui.errors.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-idx]");
  if (!tr) return;
  showTab("listing");
  selectRow(+tr.dataset.idx);
});

function showTab(name) {
  document.querySelectorAll("#tabSeg button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".view").forEach((v) => (v.hidden = v.dataset.view !== name));
}
document.querySelectorAll("#tabSeg button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

document.querySelectorAll("#modeSeg button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#modeSeg button").forEach((x) => x.classList.toggle("active", x === b));
  state.mode = b.dataset.mode;
  assemble();
}));

$("#btnRun").addEventListener("click", () => assemble().then(() => toast("Assembler jarayoni tugadi")));
$("#btnNew").addEventListener("click", newFile);
$("#btnOpen").addEventListener("click", openFile);
$("#btnSave").addEventListener("click", saveFile);
$("#btnExport").addEventListener("click", exportResults);
$("#btnExamples").addEventListener("click", (e) => {
  e.stopPropagation();
  const r = e.currentTarget.getBoundingClientRect();
  ui.examplesMenu.style.left = r.left + "px";
  ui.examplesMenu.style.top = r.bottom + 8 + "px";
  ui.examplesMenu.hidden = !ui.examplesMenu.hidden;
});
document.addEventListener("click", () => (ui.examplesMenu.hidden = true));

ui.filePicker.addEventListener("change", async () => {
  const file = ui.filePicker.files[0];
  if (file) setSource(await file.text(), file.name);
  ui.filePicker.value = "";
});

document.addEventListener("keydown", (e) => {
  const cmd = e.metaKey || e.ctrlKey;
  const key = e.key.toLowerCase();
  if (e.key === "F5" || (cmd && key === "r") || (cmd && key === "b")) { e.preventDefault(); assemble(); }
  else if (cmd && key === "s") { e.preventDefault(); saveFile(); }
  else if (cmd && key === "o") { e.preventDefault(); openFile(); }
  else if (cmd && key === "n") { e.preventDefault(); newFile(); }
  else if (e.key === "Escape") ui.examplesMenu.hidden = true;
});

window.addEventListener("beforeunload", (e) => {
  if (HTTP && isDirty()) { e.preventDefault(); e.returnValue = ""; }
});

// ---------------------------------------------------------------- ishga tushirish
async function init() {
  await backendReady();
  const meta = await call("meta");
  meta.opcodeSet = new Set(meta.opcodes);
  meta.directiveSet = new Set(meta.directives);
  meta.noOperandSet = new Set(meta.noOperand);
  state.meta = meta;
  if (meta.vibrancy) document.body.classList.add("vibrant");

  const examples = await call("examples");
  ui.examplesMenu.innerHTML = examples.map((x) =>
    `<button data-name="${esc(x.name)}">${esc(x.title)}</button>`).join("");
  ui.examplesMenu.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
    ui.examplesMenu.hidden = true;
    if (!(await confirmDiscard())) return;
    const res = await call("load_example", b.dataset.name);
    setSource(res.text, res.name);
  }));

  const first = await call("load_example", "copy_xe.asm");
  setSource(first.text, first.name);
  ui.source.focus();
}

init().catch((err) => setStatus(false, "Xato: " + err.message, ""));
