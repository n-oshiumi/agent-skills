#!/usr/bin/env node
// 記入済みの対策状況の表を、同梱のテンプレの版へ ID 単位で寄せる。記入済みのセルには触らない。
//
//   node sync.mjs <copy.md>            差分を出すだけ
//   node sync.mjs <copy.md> --write    新しい行の追加・ID の改名・版の書き換えを反映
//   node sync.mjs <copy.md> --adopt    ID 列の無い表に ID 列を足し、攻撃の種類の名前で ID を推定
//   node sync.mjs <copy.md> --init     テンプレをそのまま置く（既にあれば何もしない）
//
// 終了コード: 0 = 最新 / 2 = 反映すべき差分あり（dry-run）/ 1 = 誤り
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const TEMPLATE = join(HERE, "..", "template.md");
const CHANGES = join(HERE, "..", "CHANGES.md");

const splitRow = (line) => line.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((c) => c.trim());
const joinRow = (cells) => `| ${cells.join(" | ")} |`;
const idOf = (cell) => (cell ?? "").replace(/`/g, "").trim();
const isSep = (line) => /^\|[\s:|-]+\|$/.test((line ?? "").trim());
const VERSION_RE = /template-version:\s*(\d+)(?:\s*\(([^)]*)\))?/;
// 名前の括弧書き（例: 「（BFLA）」）はリポごとに書き換えられがちなので、推定では外して比べる。
const norm = (s) => s.replace(/（[^）]*）|\([^)]*\)/g, "").replace(/\s/g, "");

function parse(text) {
  const lines = text.split("\n");
  const tables = [];
  let section = "";
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].startsWith("## ")) section = lines[i].slice(3).trim();
    if (!lines[i].startsWith("|") || !isSep(lines[i + 1])) continue;
    const header = splitRow(lines[i]);
    const t = { section, header, headerLine: i, rows: [], col: (h) => header.indexOf(h) };
    let j = i + 2;
    for (; j < lines.length && lines[j].startsWith("|"); j++) t.rows.push({ line: j, cells: splitRow(lines[j]) });
    tables.push(t);
    i = j - 1;
  }
  return { lines, tables };
}

function templateRows() {
  const text = readFileSync(TEMPLATE, "utf8");
  const { tables } = parse(text);
  const rows = [];
  for (const t of tables) for (const r of t.rows) {
    rows.push({ id: idOf(r.cells[t.col("ID")]), section: t.section, header: t.header, cells: r.cells, name: r.cells[t.col("攻撃の種類")] });
  }
  return { text, rows, version: text.match(VERSION_RE) };
}

// CHANGES.md の「- rename: old.id -> new.id」を拾う。分類を見直して ID を変えたときに記入済みの値を引き継ぐため。
function renames() {
  if (!existsSync(CHANGES)) return new Map();
  return new Map([...readFileSync(CHANGES, "utf8").matchAll(/rename:\s*`?([\w.-]+)`?\s*->\s*`?([\w.-]+)`?/g)].map((m) => [m[1], m[2]]));
}

const prefixOf = (id) => id.split(".")[0];

function adopt(text, tpl) {
  const { lines, tables } = parse(text);
  const byName = new Map();
  for (const r of tpl.rows) byName.set(norm(r.name), byName.has(norm(r.name)) ? null : r.id);
  const unmatched = [];
  for (const t of tables) {
    if (t.col("ID") >= 0 || t.col("攻撃の種類") < 0) continue;
    lines[t.headerLine] = joinRow(["ID", ...t.header]);
    lines[t.headerLine + 1] = joinRow(["---", ...splitRow(lines[t.headerLine + 1])]);
    for (const r of t.rows) {
      const name = r.cells[t.col("攻撃の種類")];
      const id = byName.get(norm(name)) ?? "";
      if (!id) unmatched.push(`${t.section}: ${name}`);
      lines[r.line] = joinRow([id ? `\`${id}\`` : "", ...r.cells]);
    }
  }
  return { text: lines.join("\n"), unmatched };
}

function sync(text, tpl) {
  const ren = renames();
  const { lines, tables } = parse(text);
  const report = { renamed: [], added: [], appendedSections: [], deprecated: [], local: [], blank: [], noIdTables: [] };
  const present = new Map();
  for (const t of tables) {
    const c = t.col("ID");
    if (c < 0) { if (t.col("攻撃の種類") >= 0) report.noIdTables.push(t.section); continue; }
    for (const r of t.rows) {
      let id = idOf(r.cells[c]);
      if (!id) { report.blank.push(`${t.section}: ${r.cells[t.col("攻撃の種類")] ?? ""}`); continue; }
      if (ren.has(id)) {
        report.renamed.push(`${id} → ${ren.get(id)}`);
        id = ren.get(id);
        r.cells[c] = `\`${id}\``;
        lines[r.line] = joinRow(r.cells);
      }
      if (!present.has(id)) present.set(id, { t, r });
    }
  }
  // ID の無い行があると、同じ攻撃を別 ID で二重に足してしまうので、埋まるまで追加しない。
  if (report.noIdTables.length || report.blank.length) return { text: lines.join("\n"), report, blocked: true };

  const tplIds = new Set(tpl.rows.map((r) => r.id));
  for (const [id, { t, r }] of present) {
    if (id.startsWith("local.")) report.local.push(`${id}: ${r.cells[t.col("攻撃の種類")] ?? ""}`);
    else if (!tplIds.has(id)) report.deprecated.push(`${id}: ${r.cells[t.col("攻撃の種類")] ?? ""}`);
  }

  const insertAfter = new Map();
  const newSections = new Map();
  tpl.rows.forEach((tr, i) => {
    if (present.has(tr.id)) return;
    const prefix = prefixOf(tr.id);
    const host = tables.find((t) => t.col("ID") >= 0 && t.rows.some((r) => prefixOf(idOf(r.cells[t.col("ID")])) === prefix));
    if (!host) {
      if (!newSections.has(tr.section)) newSections.set(tr.section, { header: tr.header, rows: [] });
      newSections.get(tr.section).rows.push(tr.cells);
      return;
    }
    let after = host.headerLine + 1;
    for (let k = i - 1; k >= 0 && prefixOf(tpl.rows[k].id) === prefix; k--) {
      const hit = host.rows.find((r) => idOf(r.cells[host.col("ID")]) === tpl.rows[k].id);
      if (hit) { after = hit.line; break; }
    }
    // 層ごと「対象外」にした表は、増えた行も対象外のまま揃える。
    const allNa = host.rows.length && host.rows.every((r) => r.cells[host.col("状態")] === "対象外");
    const cells = host.header.map((h) => {
      if (h === "ID") return `\`${tr.id}\``;
      if (h === "状態") return allNa ? "対象外" : "―";
      const j = tr.header.indexOf(h);
      return j >= 0 && h !== "守っている仕組み" && h !== "残っている弱点" ? tr.cells[j] : "";
    });
    if (!insertAfter.has(after)) insertAfter.set(after, []);
    insertAfter.get(after).push(joinRow(cells));
    report.added.push(`${tr.id}（${host.section} へ）`);
  });

  const out = [];
  lines.forEach((l, i) => { out.push(l); for (const row of insertAfter.get(i) ?? []) out.push(row); });
  for (const [section, s] of newSections) {
    while (out.length && out[out.length - 1] === "") out.pop();
    out.push("", `## ${section}`, "", joinRow(s.header), joinRow(s.header.map(() => "---")), ...s.rows.map(joinRow), "");
    report.appendedSections.push(`${section}（${s.rows.length} 行）`);
  }
  return { text: out.join("\n"), report, blocked: false };
}

function setVersion(text, tpl) {
  const line = tpl.text.split("\n")[0];
  return VERSION_RE.test(text.split("\n")[0]) ? [line, ...text.split("\n").slice(1)].join("\n") : `${line}\n${text}`;
}

const args = process.argv.slice(2);
const file = args.find((a) => !a.startsWith("--"));
if (!file) { console.error("usage: sync.mjs <copy.md> [--write|--adopt|--init]"); process.exit(1); }
const tpl = templateRows();
const latest = Number(tpl.version?.[1]);

if (args.includes("--init")) {
  if (existsSync(file)) { console.log(`既にある: ${file}（同期は --init なしで）`); process.exit(0); }
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, tpl.text);
  console.log(`テンプレ v${latest} を置いた: ${file}`);
  process.exit(0);
}

if (!existsSync(file)) { console.error(`無い: ${file}（新規は --init）`); process.exit(1); }
const before = readFileSync(file, "utf8");
const current = Number(before.match(VERSION_RE)?.[1] ?? 0);

if (args.includes("--adopt")) {
  const { text, unmatched } = adopt(before, tpl);
  if (text === before) { console.log("ID 列の無い表は無い"); process.exit(0); }
  writeFileSync(file, text);
  console.log("ID 列を足した。");
  if (unmatched.length) console.log(`ID を推定できなかった行（テンプレの ID か local.<名前> を手で入れる）:\n${unmatched.map((u) => `- ${u}`).join("\n")}`);
  process.exit(0);
}

const { text, report, blocked } = sync(before, tpl);
const list = (title, a) => a.length && console.log(`${title}:\n${a.map((x) => `- ${x}`).join("\n")}`);
console.log(`版: v${current || "?"} → テンプレ v${latest}`);
list("ID 列の無い表（--adopt で足す）", report.noIdTables);
list("ID が空の行（テンプレの ID か local.<名前> を入れる）", report.blank);
if (blocked) process.exit(1);
list("ID の改名", report.renamed);
list("追加する行", report.added);
list("追加する節", report.appendedSections);
list("テンプレから消えた行（消さずに残す。不要なら手で消す）", report.deprecated);
list("テンプレへの昇格候補（local.）", report.local);

const next = setVersion(text, tpl);
if (next === before) { console.log("最新。変更なし"); process.exit(0); }
if (!args.includes("--write")) { console.log("（dry-run。反映は --write）"); process.exit(2); }
writeFileSync(file, next);
console.log(`反映した: ${file}`);
