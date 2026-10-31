// SO'M Assembler - interaktiv jadval.
// Programma satrlari jadvalda tahrirlanadi; har o'zgarishdan keyin adres va ob'ekt kodlari
// Python dagi assembler orqali qayta hisoblanadi.
// Python bilan aloqa: alohida oynada window.pywebview.api, brauzer rejimida /api/<nom>.

const HTTP = new URLSearchParams(location.search).get("backend") === "http";
const REG_NAMES = { 0: "A", 1: "X", 2: "L", 3: "B", 4: "S", 5: "T", 6: "F", 8: "PC", 9: "SW" };
const EDITABLE = ["addr", "label", "opcode", "operand", "comment"];
const EMPTY_ROW = () => ({ label: "", opcode: "", operand: "", comment: "", addr: "" });

const $ = (sel) => document.querySelector(sel);
const ui = {
  grid: $("#grid tbody"), gridScroll: $("#gridScroll"), autoAddr: $("#autoAddr"),
  fileName: $("#fileName"), symtab: $("#symtabTable tbody"), errors: $("#errorsTable tbody"),
  noErrors: $("#noErrors"), objectBox: $("#objectBox"), bits: $("#bits"), explain: $("#explain"),
  errBadge: $("#errBadge"), statusDot: $("#statusDot"), statusText: $("#statusText"),
  statusRight: $("#statusRight"), toast: $("#toast"), examplesMenu: $("#examplesMenu"),
  filePicker: $("#filePicker"), mnemonics: $("#mnemonics"),
};

const state = {
  meta: null, mode: "auto", rows: [], result: null,
  sel: null,            // tanlangan qator kaliti: "m3" (jadval satri) yoki "l5_0" (literal)
  col: "opcode",        // tanlangan ustun
  editing: null,        // { i, col, input }
  undo: [], redo: [], saved: "[]", name: "nomsiz", wasDirty: false, view: [],
};

// ---------------------------------------------------------------- backend
function backendReady() {
  return new Promise((resolve) => {
    if (HTTP || (window.pywebview && window.pywebview.api && window.pywebview.api.assemble_rows)) return resolve();
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
const esc = (s) => String(s ?? "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const pad = (v, n) => v.toString(2).padStart(n, "0");
const isBlank = (r) => !r.label && !r.opcode && !r.operand;
const isEnd = (r) => (r.opcode || "").trim().toUpperCase() === "END";
const endIndex = () => state.rows.findIndex(isEnd);

let toastTimer = null;
function toast(msg) {
  ui.toast.textContent = msg;
  ui.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (ui.toast.hidden = true), 2600);
}

// Qo'shtirnoqdan tashqarisini katta harfga o'tkazadi va bo'sh joylarni olib tashlaydi (C'...' o'zgarmaydi)
const normOperand = (v) => v.split("'").map((p, i) => (i % 2 ? p : p.replace(/\s+/g, "").toUpperCase())).join("'");

function colorOperand(s) {
  let out = "", i = 0, m;
  const re = /([CX]'[^']*'?)|(\d+)|([#@=])/gi;
  while ((m = re.exec(s))) {
    out += esc(s.slice(i, m.index));
    const cls = m[1] ? "tok-str" : m[2] ? "tok-num" : "tok-mod";
    out += `<span class="${cls}">${esc(m[0])}</span>`;
    i = re.lastIndex;
  }
  return out + esc(s.slice(i));
}

function colorOpcode(op) {
  const w = (op || "").toUpperCase().replace(/^\+/, "");
  if (!w) return "";
  const cls = state.meta.directiveSet.has(w) ? "tok-dir" : state.meta.opcodeSet.has(w) ? "tok-op" : "";
  return cls ? `<span class="${cls}">${esc(op)}</span>` : esc(op);
}

// ---------------------------------------------------------------- jadval ko'rinishi
// Jadval satrlari + assembler qo'shgan literal satrlari (* =C'EOF') bitta ro'yxatga yig'iladi.
function buildView() {
  const bySrc = new Map(), lits = new Map();
  const res = state.result;
  if (res && res.rows) {
    let last = 0;
    for (const r of res.rows) {
      if (r.srcRow) { bySrc.set(r.srcRow, r); last = r.srcRow; }
      else if (r.kind === "literal") {
        if (!lits.has(last)) lits.set(last, []);
        lits.get(last).push(r);
      }
    }
  }
  const view = [];
  (lits.get(0) || []).forEach((r, k) => view.push({ key: `l0_${k}`, model: null, res: r }));
  state.rows.forEach((row, i) => {
    view.push({ key: `m${i}`, model: i, res: bySrc.get(i + 1) || null });
    (lits.get(i + 1) || []).forEach((r, k) => view.push({ key: `l${i + 1}_${k}`, model: null, res: r }));
  });
  return view;
}

function cellText(entry, col) {
  const auto = ui.autoAddr.checked;
  if (entry.model == null) {
    const r = entry.res;
    return { num: "", addr: r.loc, label: "*", opcode: "", operand: r.operand, obj: r.obj, comment: "literal" }[col];
  }
  const row = state.rows[entry.model], r = entry.res;
  switch (col) {
    case "num": return String((entry.model + 1) * 5);
    case "addr": return !auto && row.addr ? row.addr.toUpperCase() : (r ? r.loc : "");
    case "obj": return r ? r.obj : "";
    default: return row[col] || "";
  }
}

function renderGrid() {
  const editing = state.editing && {
    i: state.editing.i, col: state.editing.col,
    value: state.editing.input.value, caret: state.editing.input.selectionStart,
  };
  state.rerendering = true;
  state.view = buildView();
  const auto = ui.autoAddr.checked;
  ui.grid.innerHTML = state.view.map((entry) => {
    const sel = entry.key === state.sel;
    const cls = [];
    let errTip = "";
    if (entry.model == null) cls.push("literal");
    else {
      const row = state.rows[entry.model];
      if (isBlank(row)) cls.push("comment");
      if (entry.res && entry.res.errors.length) {
        cls.push("error");
        errTip = `<span class="err-tip">⚠ ${esc(entry.res.errors[0])}</span>`;
      }
    }
    if (sel) cls.push("selected");
    const ed = entry.model != null;
    const td = (col, html, extra = "") => {
      const c = [col === "comment" ? "cmt" : col, extra];
      if (ed && EDITABLE.includes(col)) c.push("ed");
      if (sel && col === state.col) c.push("cur");
      return `<td data-col="${col}" class="${c.join(" ").trim()}">${html}</td>`;
    };
    const row = ed ? state.rows[entry.model] : null;
    const manual = ed && !auto && row.addr;
    return `<tr data-key="${entry.key}" class="${cls.join(" ")}">` +
      td("num", esc(cellText(entry, "num"))) +
      td("addr", esc(cellText(entry, "addr")), manual ? "manual" : "") +
      td("label", ed ? `<span class="tok-label">${esc(row.label)}</span>` : "*") +
      td("opcode", ed ? colorOpcode(row.opcode) : "") +
      td("operand", colorOperand(cellText(entry, "operand"))) +
      td("obj", esc(cellText(entry, "obj"))) +
      td("comment", esc(cellText(entry, "comment")) + errTip) +
      "</tr>";
  }).join("");
  state.rerendering = false;
  if (editing) {
    state.editing = null;           // eski input DOM dan olib tashlandi - qaytadan ochamiz
    startEdit(editing.i, editing.col, editing.value, editing.caret);
  }
}

function selectedEntry() {
  return state.view.find((e) => e.key === state.sel) || null;
}

function selectedModel() {
  const e = selectedEntry();
  return e ? e.model : null;
}

function select(key, { scroll = true } = {}) {
  state.sel = key;
  ui.grid.querySelectorAll("tr.selected").forEach((tr) => {
    tr.classList.remove("selected");
    tr.querySelectorAll("td.cur").forEach((td) => td.classList.remove("cur"));
  });
  const tr = ui.grid.querySelector(`tr[data-key="${key}"]`);
  if (tr) {
    tr.classList.add("selected");
    const td = tr.querySelector(`td[data-col="${state.col}"]`);
    if (td) td.classList.add("cur");
    if (scroll) tr.scrollIntoView({ block: "nearest" });
  }
  const entry = selectedEntry();
  showAnalysis(entry ? entry.res : null);
  updateToolButtons();
}

function updateToolButtons() {
  const i = selectedModel();
  $("#btnUp").disabled = i == null || i === 0;
  $("#btnDown").disabled = i == null || i >= state.rows.length - 1;
  $("#btnDelRow").disabled = i == null;
}

// ---------------------------------------------------------------- tahrirlash
function startEdit(i, col, initial, caret) {
  if (i == null || !EDITABLE.includes(col)) return;
  finishEdit(false);
  state.col = col;
  select(`m${i}`, { scroll: true });
  const td = ui.grid.querySelector(`tr[data-key="m${i}"] td[data-col="${col}"]`);
  if (!td) return;
  let value = initial;
  if (value == null) value = col === "addr" ? cellText({ model: i, res: entryRes(i) }, "addr") : state.rows[i][col] || "";
  td.classList.add("editing");
  td.innerHTML = `<input class="cell-input" spellcheck="false" autocomplete="off"${col === "opcode" ? ' list="mnemonics"' : ""}>`;
  const input = td.firstChild;
  input.value = value;
  state.editing = { i, col, input };
  input.focus();
  const pos = caret ?? value.length;
  input.setSelectionRange(pos, pos);
  input.addEventListener("keydown", onEditKey);
  input.addEventListener("blur", () => {
    if (!state.rerendering && state.editing && state.editing.input === input) finishEdit(true);
  });
}

function entryRes(i) {
  const e = state.view.find((x) => x.model === i);
  return e ? e.res : null;
}

function onEditKey(e) {
  const ed = state.editing;
  if (!ed) return;
  if (e.key === "Escape") {
    e.preventDefault();
    finishEdit(false);
  } else if (e.key === "Enter") {
    e.preventDefault();
    if (!finishEdit(true)) return;
    if (ed.i + 1 < state.rows.length) select(`m${ed.i + 1}`);
  } else if (e.key === "Tab") {
    e.preventDefault();
    if (!finishEdit(true)) return;
    let k = EDITABLE.indexOf(ed.col) + (e.shiftKey ? -1 : 1);
    let i = ed.i;
    if (k >= EDITABLE.length) { k = 1; i++; }       // keyingi satrning Nishon katagi
    if (k < 0) { k = EDITABLE.length - 1; i--; }
    if (i >= 0 && i < state.rows.length) startEdit(i, EDITABLE[k]);
  }
  e.stopPropagation();
}

// Tahrirni yakunlaydi. commit=false - bekor qilish. Noto'g'ri qiymatda false qaytaradi.
function finishEdit(commit) {
  const ed = state.editing;
  if (!ed) return true;
  let value = ed.input.value.trim();
  const row = state.rows[ed.i];
  if (commit && row) {
    if (ed.col === "addr") {
      value = value.toUpperCase();
      if (value && !/^[0-9A-F]{1,5}$/.test(value)) {
        toast("Adres 16-lik son bo'lishi kerak, masalan 1000 yoki 2039");
        ed.input.focus();
        return false;
      }
      const computed = cellText({ model: ed.i, res: entryRes(ed.i) }, "addr");
      if (ui.autoAddr.checked && (value === computed || !value)) value = row.addr;   // o'zgarmadi
      else if (ui.autoAddr.checked) {
        ui.autoAddr.checked = false;
        toast("Avtomatik adres o'chirildi: qo'lda yozilgan adres ishlatiladi");
      }
    } else if (ed.col === "operand") value = normOperand(value);
    else if (ed.col === "label" || ed.col === "opcode") value = value.toUpperCase();
  }
  state.editing = null;
  if (commit && row && value !== row[ed.col]) {
    pushUndo();
    row[ed.col] = value;
    if (ed.col === "opcode" && isEnd(row)) trimAfterEnd();
    changed();
  } else if (commit && ed.col === "addr" && !ui.autoAddr.checked) {
    changed();
  } else {
    renderGrid();
    select(state.sel, { scroll: false });
  }
  return true;
}

function trimAfterEnd() {
  const e = endIndex();
  if (e >= 0 && e < state.rows.length - 1) {
    const n = state.rows.length - 1 - e;
    state.rows.splice(e + 1);
    toast(`END dan keyingi ${n} ta satr o'chirildi (⌘Z - qaytarish)`);
  }
}

// ---------------------------------------------------------------- satr amallari
function snapshot() {
  return JSON.stringify({ rows: state.rows, auto: ui.autoAddr.checked });
}

function restore(snap) {
  const s = JSON.parse(snap);
  state.rows = s.rows;
  ui.autoAddr.checked = s.auto;
}

function pushUndo() {
  state.undo.push(snapshot());
  if (state.undo.length > 200) state.undo.shift();
  state.redo = [];
}

function undo() {
  if (!state.undo.length) return toast("Orqaga qaytariladigan amal yo'q");
  state.redo.push(snapshot());
  restore(state.undo.pop());
  changed();
}

function redo() {
  if (!state.redo.length) return;
  state.undo.push(snapshot());
  restore(state.redo.pop());
  changed();
}

function addRow() {
  finishEdit(true);
  const cur = selectedModel();
  let at = cur == null ? state.rows.length : cur + 1;
  const e = endIndex();
  if (e >= 0 && at > e) at = e;                     // END doim oxirgi satr bo'lib qoladi
  pushUndo();
  state.rows.splice(at, 0, EMPTY_ROW());
  changed();
  startEdit(at, "label");
}

function moveRow(delta) {
  finishEdit(true);
  const i = selectedModel();
  const j = i == null ? -1 : i + delta;
  if (i == null || j < 0 || j >= state.rows.length) return;
  if (isEnd(state.rows[i]) || isEnd(state.rows[j])) return toast("END oxirgi satr bo'lib qolishi kerak");
  pushUndo();
  [state.rows[i], state.rows[j]] = [state.rows[j], state.rows[i]];
  state.sel = `m${j}`;
  changed();
}

function deleteRow() {
  finishEdit(false);
  const i = selectedModel();
  if (i == null) return;
  pushUndo();
  state.rows.splice(i, 1);
  if (!state.rows.length) state.rows.push(EMPTY_ROW());
  state.sel = `m${Math.min(i, state.rows.length - 1)}`;
  changed();
  toast("Satr o'chirildi (⌘Z - qaytarish)");
}

function resetAddresses() {
  finishEdit(true);
  pushUndo();
  state.rows.forEach((r) => (r.addr = ""));
  ui.autoAddr.checked = true;
  changed();
  toast("Adreslar avtomatik hisoblandi");
}

// ---------------------------------------------------------------- assembler
let assembleSeq = 0;
async function assemble() {
  const seq = ++assembleSeq;
  const res = await call("assemble_rows", state.rows, state.mode, ui.autoAddr.checked);
  if (seq !== assembleSeq) return;                  // eskirgan javob
  state.result = res;
  renderAll();
}

function changed() {
  updateTitle();
  renderGrid();
  select(state.sel, { scroll: true });
  assemble();
}

function renderAll() {
  renderGrid();
  const r = state.result;
  if (r.fatal) {
    ui.symtab.innerHTML = ui.errors.innerHTML = "";
    ui.objectBox.textContent = "";
    setStatus(false, "XATO: " + r.fatal, "");
    select(state.sel, { scroll: false });
    return;
  }

  ui.symtab.innerHTML = r.symtab.map((s) =>
    `<tr><td>${esc(s.section)}</td><td>${esc(s.name)}</td><td class="obj">${s.value}</td>` +
    `<td class="msg">${esc(s.kind)}</td></tr>`).join("");

  if (r.object) {
    ui.objectBox.innerHTML = r.object.trimEnd().split("\n").map((line) => {
      if (!line) return "";
      const body = esc(line).replace(/\^/g, '<span class="sep">^</span>');
      return `<span class="rec-${line[0]}"><b>${body[0]}</b>${body.slice(1)}</span>`;
    }).join("\n");
  } else {
    ui.objectBox.textContent = "Programmada xatolar bor - ob'ekt programma yaratilmadi.\n\"Xatolar\" bo'limiga qarang.";
  }

  const errs = [];
  r.rows.forEach((row) => row.errors.forEach((e) => errs.push([row.srcRow, row.lineno, e])));
  ui.errors.innerHTML = errs.map(([src, n, e]) =>
    `<tr data-src="${src ?? ""}" class="error"><td class="num">${n ?? ""}</td><td class="msg">${esc(e)}</td></tr>`).join("");
  ui.noErrors.hidden = errs.length > 0;
  ui.errBadge.hidden = errs.length === 0;
  ui.errBadge.textContent = errs.length;

  const modeName = r.mode === "xe" ? "SO'M/QV (SIC/XE)" : "SO'M (SIC)";
  const lengths = r.sections.map((s) => `${s.name}: ${s.length}h bayt`).join("   ");
  const head = `Jami satrlar: ${state.rows.length}  |  Label'lar: ${r.symbolCount}  |  `;
  setStatus(errs.length === 0,
    head + (errs.length ? `${errs.length} ta xato — ob'ekt programma yaratilmadi`
                        : "Adres va obyekt kodlari qayta hisoblandi."),
    `${modeName}   ${lengths}`);
  select(state.sel, { scroll: false });
}

function setStatus(ok, text, right) {
  ui.statusDot.className = "dot " + (ok ? "ok" : "bad");
  ui.statusText.textContent = text;
  ui.statusRight.textContent = right;
}

// ---------------------------------------------------------------- buyruq tahlili
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
  let text = row ? row.explain : "Jadvaldagi satrni tanlang - buyruq bitlarga ajratib ko'rsatiladi.";
  if (chips) {
    // bitlar yuqorida "chip"lar bilan ko'rsatilgan - matndagi jadvalni olib tashlaymiz
    text = text.split("\n").filter((l) => !l.startsWith("|") && !l.startsWith("Standart SO'M formati")).join("\n")
      .replace(/\n{3,}/g, "\n\n");
  }
  ui.explain.textContent = text;
}

// ---------------------------------------------------------------- fayllar
function isDirty() { return JSON.stringify(state.rows) !== state.saved; }

function updateTitle() {
  const dirty = isDirty();
  ui.fileName.textContent = (dirty ? "● " : "") + state.name;
  document.title = `${dirty ? "• " : ""}${state.name} — SO'M Assembler`;
  if (dirty !== state.wasDirty) {
    state.wasDirty = dirty;
    if (!HTTP) call("set_dirty", dirty);
  }
}

function setRows(rows, name) {
  state.editing = null;
  state.rows = rows.length ? rows : [EMPTY_ROW()];
  state.saved = JSON.stringify(state.rows);
  state.name = name;
  state.undo = [];
  state.redo = [];
  state.sel = "m0";
  ui.autoAddr.checked = true;
  ui.gridScroll.scrollTop = 0;
  changed();
}

function rowsToText(rows) {
  return rows.map((r) => {
    if (isBlank(r)) return r.comment ? `*        ${r.comment}` : "";
    return `${(r.label || "").padEnd(8)} ${(r.opcode || "").padEnd(8)} ${(r.operand || "").padEnd(16)} ${r.comment || ""}`.trimEnd();
  }).join("\n") + "\n";
}

function tableToCsv() {
  const cols = ["num", "addr", "label", "opcode", "operand", "obj", "comment"];
  const q = (v) => (/[;"\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);
  const lines = ["Satr;Adres;Nishon;Buyruq;Operand;Ob'ekt kodi;Izoh"];
  for (const entry of state.view) lines.push(cols.map((c) => q(cellText(entry, c) || "")).join(";"));
  return lines.join("\r\n") + "\r\n";
}

async function confirmDiscard() {
  finishEdit(true);
  if (!isDirty()) return true;
  const msg = "Saqlanmagan o'zgarishlar yo'qoladi. Davom etilsinmi?";
  return HTTP ? window.confirm(msg) : call("confirm", msg);
}

function download(name, text) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

const baseName = () => state.name.replace(/\.[^.]*$/, "") || "programma";

async function newFile() {
  if (!(await confirmDiscard())) return;
  setRows([
    { label: "PROG", opcode: "START", operand: "1000", comment: "", addr: "" },
    { label: "FIRST", opcode: "RSUB", operand: "", comment: "", addr: "" },
    { label: "", opcode: "END", operand: "FIRST", comment: "", addr: "" },
  ], "nomsiz");
}

async function openFile() {
  if (!(await confirmDiscard())) return;
  if (HTTP) return ui.filePicker.click();
  const res = await call("open_file");
  if (res) setRows(res.rows, res.name);
}

async function saveFile() {
  finishEdit(true);
  const text = rowsToText(state.rows);
  const suggested = state.name === "nomsiz" ? "programma.asm" : state.name;
  if (HTTP) {
    download(suggested, text);
    state.name = suggested;
  } else {
    const res = await call("save_file", text, false, suggested);
    if (!res) return;
    state.name = res.name;
  }
  state.saved = JSON.stringify(state.rows);
  updateTitle();
  toast("Saqlandi: " + state.name);
}

async function saveCsv() {
  finishEdit(true);
  const csv = tableToCsv();
  if (HTTP) {
    download(baseName() + ".csv", "﻿" + csv);
    return toast("Jadval CSV ga saqlandi");
  }
  const res = await call("save_csv", csv, baseName() + ".csv");
  if (res) toast("Saqlandi: " + res.name);
}

async function exportResults() {
  finishEdit(true);
  const r = state.result;
  if (HTTP) {
    if (!r || r.fatal) return toast("Avval programmani hisoblang");
    download(baseName() + ".lst", r.listingText);
    if (r.object) download(baseName() + ".obj", r.object);
    return toast(r.object ? ".lst va .obj saqlandi" : ".lst saqlandi (xatolar bor - .obj yo'q)");
  }
  const res = await call("save_results", state.rows, state.mode, ui.autoAddr.checked, baseName());
  if (res) toast("Saqlandi: " + res.saved.join(", "));
}

// ---------------------------------------------------------------- hodisalar
ui.grid.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-key]");
  if (!tr || e.target.closest(".cell-input")) return;
  const td = e.target.closest("td[data-col]");
  if (td && EDITABLE.includes(td.dataset.col)) state.col = td.dataset.col;
  finishEdit(true);
  select(tr.dataset.key, { scroll: false });
});

ui.grid.addEventListener("dblclick", (e) => {
  const tr = e.target.closest("tr[data-key]");
  const td = e.target.closest("td[data-col]");
  if (!tr || !td || !tr.dataset.key.startsWith("m")) return;
  if (!EDITABLE.includes(td.dataset.col)) return toast("Bu katak avtomatik hisoblanadi");
  startEdit(+tr.dataset.key.slice(1), td.dataset.col);
});

ui.errors.addEventListener("click", (e) => {
  const tr = e.target.closest("tr[data-src]");
  if (!tr || !tr.dataset.src) return;
  showTab("analysis");
  select(`m${+tr.dataset.src - 1}`);
});

function showTab(name) {
  document.querySelectorAll("#tabSeg button").forEach((b) => b.classList.toggle("active", b.dataset.tab === name));
  document.querySelectorAll(".results-panel .view").forEach((v) => (v.hidden = v.dataset.view !== name));
}
document.querySelectorAll("#tabSeg button").forEach((b) => b.addEventListener("click", () => showTab(b.dataset.tab)));

document.querySelectorAll("#modeSeg button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll("#modeSeg button").forEach((x) => x.classList.toggle("active", x === b));
  state.mode = b.dataset.mode;
  assemble();
}));

ui.autoAddr.addEventListener("change", () => {
  pushUndo();
  changed();
  toast(ui.autoAddr.checked ? "Adreslar avtomatik hisoblanadi"
    : "Avtomatik adres o'chiq: Adres katagini ikki marta bosib o'zgartiring");
});

$("#btnRun").addEventListener("click", () => {
  finishEdit(true);
  assemble().then(() => toast("Adres va obyekt kodlari qayta hisoblandi"));
});
$("#btnNew").addEventListener("click", newFile);
$("#btnOpen").addEventListener("click", openFile);
$("#btnSave").addEventListener("click", saveFile);
$("#btnExport").addEventListener("click", exportResults);
$("#btnAddRow").addEventListener("click", addRow);
$("#btnUp").addEventListener("click", () => moveRow(-1));
$("#btnDown").addEventListener("click", () => moveRow(1));
$("#btnDelRow").addEventListener("click", deleteRow);
$("#btnResetAddr").addEventListener("click", resetAddresses);
$("#btnCsv").addEventListener("click", saveCsv);
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
  if (file) setRows(await call("parse_source", await file.text()), file.name);
  ui.filePicker.value = "";
});

function moveSelection(delta) {
  const idx = state.view.findIndex((e) => e.key === state.sel);
  const next = state.view[Math.max(0, Math.min(state.view.length - 1, (idx < 0 ? 0 : idx) + delta))];
  if (next) select(next.key);
}

document.addEventListener("keydown", (e) => {
  const cmd = e.metaKey || e.ctrlKey;
  const key = e.key.toLowerCase();
  if (e.key === "F5" || (cmd && key === "r")) { e.preventDefault(); $("#btnRun").click(); return; }
  if (cmd && key === "s") { e.preventDefault(); saveFile(); return; }
  if (cmd && key === "o") { e.preventDefault(); openFile(); return; }
  if (cmd && key === "n") { e.preventDefault(); newFile(); return; }
  if (e.key === "Escape") { ui.examplesMenu.hidden = true; return; }
  if (state.editing || e.target.matches("input, textarea")) return;

  // jadval bilan ishlash (katak tahrirlanmayotganda)
  if (cmd && key === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); return; }
  if (cmd && e.key === "ArrowUp") { e.preventDefault(); moveRow(-1); return; }
  if (cmd && e.key === "ArrowDown") { e.preventDefault(); moveRow(1); return; }
  if (cmd && e.key === "Backspace") { e.preventDefault(); deleteRow(); return; }
  if (cmd && e.key === "Enter") { e.preventDefault(); addRow(); return; }
  if (cmd || e.altKey) return;

  const i = selectedModel();
  if (e.key === "ArrowDown" || e.key === "ArrowUp") {
    e.preventDefault();
    moveSelection(e.key === "ArrowDown" ? 1 : -1);
  } else if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
    e.preventDefault();
    const k = EDITABLE.indexOf(state.col) + (e.key === "ArrowRight" ? 1 : -1);
    state.col = EDITABLE[Math.max(0, Math.min(EDITABLE.length - 1, k))];
    select(state.sel, { scroll: false });
  } else if ((e.key === "Enter" || e.key === "F2") && i != null) {
    e.preventDefault();
    startEdit(i, state.col);
  } else if ((e.key === "Backspace" || e.key === "Delete") && i != null && state.rows[i][state.col]) {
    e.preventDefault();
    pushUndo();
    state.rows[i][state.col] = "";
    changed();
  } else if (e.key.length === 1 && i != null) {
    e.preventDefault();
    startEdit(i, state.col, e.key);                 // yozishni boshlash - katak tahrirga o'tadi
  }
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
  state.meta = meta;
  if (meta.vibrancy) document.body.classList.add("vibrant");
  ui.mnemonics.innerHTML = [...meta.opcodes, ...meta.directives].map((m) => `<option value="${m}">`).join("");

  const examples = await call("examples");
  ui.examplesMenu.innerHTML = examples.map((x) =>
    `<button data-name="${esc(x.name)}">${esc(x.title)}</button>`).join("");
  ui.examplesMenu.querySelectorAll("button").forEach((b) => b.addEventListener("click", async () => {
    ui.examplesMenu.hidden = true;
    if (!(await confirmDiscard())) return;
    const res = await call("load_example", b.dataset.name);
    setRows(res.rows, res.name);
  }));

  const first = await call("load_example", "copy_sic.asm");
  setRows(first.rows, first.name);
  ui.gridScroll.focus();
}

init().catch((err) => setStatus(false, "Xato: " + err.message, ""));
