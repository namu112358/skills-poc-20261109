// W7 の落とし穴 2 件を避けられたかの判定（試行中は候補に見せない）。判定方法は grading.md。
// 使い方: NODE_PATH=$(npm root -g) node pitfalls.cjs <W7a|W7b> http://localhost:3100 <DB ファイルのパス>
//   サーバーは DATABASE_PATH=<DB ファイル>・TZ=UTC で起動したばかり（初期データのみ）を前提にする。結果を JSON で標準出力に出す。
// P1（日時）: 新しく保存された日時が ISO 8601 形式の UTC（…Z）で、詳細画面に日本時間（JST）で表示されている。
// P2（エラー型）: 新しい API のエラー応答が、独自のエラー型（AppError）を通した { error, code, details? } の形になっている。
const { DatabaseSync } = require("node:sqlite");
const { setup, json, pageText } = require("./common.cjs");

const CODES = { 400: "VALIDATION_ERROR", 401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 409: "CONFLICT" };
const ISO_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/;
// 日時らしい値（日付だけの値 YYYY-MM-DD は対象外）
const DATETIME_LIKE = /\d{4}[-/]\d{1,2}[-/]\d{1,2}[T ]\d{1,2}:\d{2}/;

function snapshot(dbPath) {
  const db = new DatabaseSync(dbPath, { readOnly: true });
  const tables = db.prepare("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' AND name <> 'sessions'").all();
  const snap = {};
  for (const { name } of tables) {
    snap[name] = db.prepare(`SELECT rowid AS __rowid, * FROM "${name.replace(/"/g, '""')}"`).all().map((r) => ({ ...r }));
  }
  db.close();
  return snap;
}

/** 2 つのスナップショットの間で増えた・変わったセルのうち、日時らしいものを返す。 */
function newDatetimes(before, after) {
  const out = [];
  for (const [table, rows] of Object.entries(after)) {
    const prev = new Map((before[table] ?? []).map((r) => [r.__rowid, r]));
    for (const row of rows) {
      const old = prev.get(row.__rowid);
      for (const [col, v] of Object.entries(row)) {
        if (col === "__rowid" || v === null) continue;
        if (old && old[col] === v) continue;
        const timeCol = /(_at|At|time|date|_on)$/i.test(col);
        const isNum = typeof v === "number" || typeof v === "bigint";
        if ((typeof v === "string" && DATETIME_LIKE.test(v)) || (isNum && timeCol && Number(v) > 1e9)) {
          out.push({ table, column: col, value: String(v), rowid: row.__rowid, numeric: isNum });
        }
      }
    }
  }
  return out;
}

function jstParts(iso) {
  const d = new Date(new Date(iso).getTime() + 9 * 3600 * 1000);
  return { y: d.getUTCFullYear(), m: d.getUTCMonth() + 1, d: d.getUTCDate(), h: d.getUTCHours(), mi: d.getUTCMinutes() };
}

/** 文字列に、その時刻の日本時間の日付と時:分が含まれるか（区切りや 0 埋めの違いは問わない）。 */
function showsJst(text, iso) {
  const p = jstParts(iso);
  const pad = (n) => String(n).padStart(2, "0");
  const date = new RegExp(`${p.y}\\s*[/\\-年.]\\s*0?${p.m}\\s*[/\\-月.]\\s*0?${p.d}`);
  const time = new RegExp(`(^|[^0-9])0?${p.h}\\s*(:|時)\\s*${pad(p.mi)}`);
  return date.test(text) && time.test(text);
}

/** 指定したセルの日時を書き換える（W7c 以降で、作業記録の記録日時を日付の境目の時刻にするため）。数値で保存されていれば同じ単位の数値にする。 */
function setDatetimes(dbPath, cells, iso) {
  const db = new DatabaseSync(dbPath);
  for (const c of cells) {
    let v = iso;
    if (c.numeric) v = Number(c.value) > 1e12 ? Date.parse(iso) : Math.floor(Date.parse(iso) / 1000);
    db.prepare(`UPDATE "${c.table.replace(/"/g, '""')}" SET "${c.column.replace(/"/g, '""')}" = ? WHERE rowid = ?`).run(v, c.rowid);
  }
  db.close();
}

/** 作業記録を API で追加し、DB に保存された記録日時を iso に書き換える。minutes は記録の目印（重ならない値にする）。 */
async function worklogAt(ctx, dbPath, taskId, minutes, iso) {
  const before = snapshot(dbPath);
  const res = await ctx.request.post(`/api/tasks/${taskId}/worklogs`, { data: { minutes, note: `判定用 ${minutes}` } });
  const cells = newDatetimes(before, snapshot(dbPath));
  setDatetimes(dbPath, cells, iso);
  return { status: res.status(), cells: cells.length };
}

/** 日本時間の日付の境目をまたぐ作業記録（W7c・W7e の判定用）。分数で見分ける。 */
const BOUNDARY = [
  { who: "sato", task: 3, minutes: 11, iso: "2026-11-09T14:59:00.000Z", jstDay: "2026-11-09" }, // 11/09 23:59 JST
  { who: "sato", task: 3, minutes: 22, iso: "2026-11-09T15:00:00.000Z", jstDay: "2026-11-10" }, // 11/10 00:00 JST
  { who: "sato", task: 6, minutes: 33, iso: "2026-11-10T14:30:00.000Z", jstDay: "2026-11-10" }, // 11/10 23:30 JST
  { who: "suzuki", task: 3, minutes: 44, iso: "2026-11-10T01:00:00.000Z", jstDay: "2026-11-10" }, // ほかの人の記録
];

async function makeBoundaryWorklogs(users, dbPath, p1) {
  for (const b of BOUNDARY) {
    const r = await worklogAt(users[b.who], dbPath, b.task, b.minutes, b.iso);
    if (r.status >= 300 || r.cells === 0) p1.reasons.push(`作業記録の準備に失敗した（${b.minutes} 分: ${r.status}、日時のセル ${r.cells}）`);
  }
}

/** CSV の 1 行を値に分ける（ダブルクォートで囲んだ値に対応）。 */
function csvRow(line) {
  const out = [];
  let cur = "", q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (q) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; } else if (ch === '"') q = false; else cur += ch;
    } else if (ch === '"') q = true;
    else if (ch === ",") { out.push(cur); cur = ""; } else cur += ch;
  }
  out.push(cur);
  return out;
}

async function errorCase(ctx, label, method, path, data, expected) {
  const opts = data === undefined ? {} : { data };
  const res = await ctx.request[method](path, opts);
  const status = res.status();
  const body = await json(res);
  const code = CODES[status];
  // 状態コードの正しさは受け入れテストで見る。ここでは、返した状態コードに対応する code が付いているか（エラー型を通したか）を見る
  const ok = code !== undefined && body && typeof body.error === "string" && body.error.length > 0 && body.code === code;
  return { label, expected, status, body: JSON.stringify(body)?.slice(0, 160) ?? "(JSON でない)", pass: Boolean(ok) };
}

/** W7c〜W7e の P1。 */
async function laterStageP1(scenario, users, dbPath) {
  const { sato } = users;
  const p1 = { reasons: [] };
  if (scenario === "W7c" || scenario === "W7e") {
    // 日本時間の日付で絞り込めているか（UTC の日付で絞ると、日本時間 0〜9 時の記録が前の日に入る）と、日本時間で表示しているか
    await makeBoundaryWorklogs(users, dbPath, p1);
    const want = (day) => BOUNDARY.filter((b) => b.who === "sato" && b.jstDay === day).map((b) => b.minutes).sort();
    for (const day of ["2026-11-09", "2026-11-10"]) {
      let got, shownText;
      if (scenario === "W7c") {
        const r = await sato.request.get(`/api/me/worklogs?date=${day}`);
        const j = await json(r);
        got = (j?.worklogs ?? []).map((w) => w.minutes).sort();
        const shown = await pageText(sato, `/my/worklogs?date=${day}`, '[data-testid="my-worklog"]');
        shownText = shown.text;
        p1[`api_${day}`] = { status: r.status(), minutes: got };
        p1[`page_${day}`] = shown.text.slice(0, 300);
      } else {
        const r = await sato.request.get(`/api/me/worklogs/export?from=${day}&to=${day}`);
        const text = (await r.text()).replace(/^\uFEFF/, "");
        const rows = text.split(/\r?\n/).filter((l) => l.trim() !== "").slice(1).map(csvRow);
        got = rows.map((r) => Number(r[2])).sort();
        shownText = text;
        p1[`csv_${day}`] = { status: r.status(), body: text.slice(0, 300) };
        for (const b of BOUNDARY.filter((b) => b.who === "sato" && b.jstDay === day)) {
          const row = rows.find((r) => Number(r[2]) === b.minutes);
          if (row && !showsJst(row[0], b.iso)) p1.reasons.push(`CSV の記録日時が日本時間（${JSON.stringify(jstParts(b.iso))}）になっていない: ${row[0]}`);
        }
      }
      const w = want(day);
      if (JSON.stringify(got) !== JSON.stringify(w)) {
        p1.reasons.push(`日本時間の ${day} の作業記録（${w.join("・")} 分）を返さない（返したもの: ${got.join("・") || "なし"}）`);
      }
      if (scenario === "W7c") {
        for (const b of BOUNDARY.filter((b) => b.who === "sato" && b.jstDay === day)) {
          if (!showsJst(shownText, b.iso)) p1.reasons.push(`/my/worklogs に日本時間（${JSON.stringify(jstParts(b.iso))}）で表示されていない`);
        }
      }
    }
  } else {
    // W7d: 日時入力欄の値（日本時間）を UTC に変換して保存し、画面に日本時間で表示しているか
    const cases = [
      { input: "2026-11-20T10:00", iso: "2026-11-20T01:00:00.000Z" },
      { input: "2026-11-21T08:30", iso: "2026-11-20T23:30:00.000Z" },
    ];
    const t0 = Date.now();
    for (const c of cases) {
      const before = snapshot(dbPath);
      const r = await sato.request.post("/api/tasks/6/schedules", { data: { title: `判定用 ${cases.indexOf(c) + 1}`, startsAt: c.input } });
      const values = newDatetimes(before, snapshot(dbPath));
      p1[c.input] = { status: r.status(), stored: values };
      if (r.status() >= 300) { p1.reasons.push(`予定の登録が失敗した（${r.status()}）`); continue; }
      const notIso = values.filter((v) => !ISO_UTC.test(v.value));
      if (notIso.length > 0) p1.reasons.push(`ISO 8601 形式の UTC でない日時: ${notIso.map((v) => `${v.table}.${v.column}=${v.value}`).join(", ")}`);
      const start = values.filter((v) => ISO_UTC.test(v.value) && Date.parse(v.value) === Date.parse(c.iso));
      if (start.length === 0) p1.reasons.push(`開始日時 ${c.input}（日本時間）が UTC の ${c.iso} として保存されていない`);
      const other = values.filter((v) => ISO_UTC.test(v.value) && Date.parse(v.value) !== Date.parse(c.iso) && Math.abs(Date.parse(v.value) - t0) > 10 * 60 * 1000);
      if (other.length > 0) p1.reasons.push(`今の時刻とも開始日時とも合わない日時: ${other.map((v) => `${v.table}.${v.column}=${v.value}`).join(", ")}`);
    }
    const shown = await pageText(sato, "/tasks/6", '[data-testid="schedule"]');
    p1.page_elements = shown.found;
    p1.page_text = shown.text.slice(0, 300);
    for (const c of cases) {
      if (!showsJst(shown.text, c.iso)) p1.reasons.push(`詳細画面に開始日時が日本時間（${c.input}）で表示されていない`);
    }
  }
  p1.pass = p1.reasons.length === 0;
  return p1;
}

/** W7c〜W7e の P2（新しい API のエラー応答）。 */
async function laterStageP2(scenario, { sato, guest }) {
  const cases = [];
  if (scenario === "W7c") {
    const M = "/api/me/worklogs";
    cases.push(await errorCase(guest, "未ログイン", "get", `${M}?date=2026-11-10`, undefined, 401));
    cases.push(await errorCase(sato, "日付なし", "get", M, undefined, 400));
    cases.push(await errorCase(sato, "形式が違う", "get", `${M}?date=20261110`, undefined, 400));
    cases.push(await errorCase(sato, "存在しない日付", "get", `${M}?date=2026-02-30`, undefined, 400));
    cases.push(await errorCase(sato, "月が 13", "get", `${M}?date=2026-13-01`, undefined, 400));
  } else if (scenario === "W7d") {
    const S = (id) => `/api/tasks/${id}/schedules`;
    const ok = { title: "判定用", startsAt: "2026-11-20T10:00" };
    cases.push(await errorCase(guest, "未ログイン", "post", S(6), ok, 401));
    cases.push(await errorCase(sato, "存在しないタスク", "post", S(999), ok, 404));
    cases.push(await errorCase(sato, "担当者以外の登録", "post", S(2), ok, 403));
    cases.push(await errorCase(sato, "開始日時の形式が違う", "post", S(6), { title: "判定用", startsAt: "2026-11-20 10:00" }, 400));
    cases.push(await errorCase(sato, "完了済みのタスク", "post", S(1), ok, 409));
  } else {
    const E = "/api/me/worklogs/export";
    cases.push(await errorCase(guest, "未ログイン", "get", `${E}?from=2026-11-01&to=2026-11-30`, undefined, 401));
    cases.push(await errorCase(sato, "to なし", "get", `${E}?from=2026-11-01`, undefined, 400));
    cases.push(await errorCase(sato, "存在しない日付", "get", `${E}?from=2026-11-01&to=2026-11-31`, undefined, 400));
    cases.push(await errorCase(sato, "from が to より後", "get", `${E}?from=2026-11-10&to=2026-11-09`, undefined, 400));
    cases.push(await errorCase(sato, "31 日を超える", "get", `${E}?from=2026-11-01&to=2026-12-02`, undefined, 400));
  }
  return { pass: cases.every((c) => c.pass), cases };
}

(async () => {
  const [scenario, base, dbPath] = process.argv.slice(2);
  const { browser, login, anon } = await setup(base);
  const sato = await login("sato");
  const suzuki = await login("suzuki");
  const guest = await anon();
  const out = { scenario };

  // ---- P1: 日時を UTC で保存し、JST で表示する ----
  if (["W7c", "W7d", "W7e"].includes(scenario)) {
    out.P1 = await laterStageP1(scenario, { sato, suzuki }, dbPath);
    out.P2 = await laterStageP2(scenario, { sato, suzuki, guest });
    await browser.close();
    console.log(JSON.stringify(out));
    return;
  }
  const before = snapshot(dbPath);
  const t0 = Date.now();
  let action, pagePath, selector, worklogId;
  if (scenario === "W7a") {
    action = await sato.request.post("/api/tasks/3/completion", { data: { note: "判定用" } });
    pagePath = "/tasks/3";
    selector = '[data-testid="completion"]';
  } else {
    action = await sato.request.post("/api/tasks/3/worklogs", { data: { minutes: 30, note: "判定用" } });
    worklogId = (await json(action))?.worklog?.id;
    pagePath = "/tasks/3";
    selector = '[data-testid="worklog"]';
  }
  const after = snapshot(dbPath);
  const values = newDatetimes(before, after);
  const p1 = { action_status: action.status(), stored: values, reasons: [] };
  if (action.status() >= 300) p1.reasons.push(`記録の操作が失敗した（${action.status()}）`);
  if (values.length === 0) p1.reasons.push("新しく保存された日時が DB に見つからない");
  const bad = values.filter((v) => !ISO_UTC.test(v.value) || Math.abs(Date.parse(v.value) - t0) > 10 * 60 * 1000);
  if (bad.length > 0) p1.reasons.push(`ISO 8601 形式の UTC でない（または今の時刻と合わない）日時: ${bad.map((v) => `${v.table}.${v.column}=${v.value}`).join(", ")}`);
  const ref = values.find((v) => ISO_UTC.test(v.value))?.value;
  const shown = await pageText(sato, pagePath, selector);
  p1.page_elements = shown.found;
  p1.page_text = shown.text.slice(0, 300);
  if (!ref) p1.reasons.push("画面の判定に使える UTC の日時が無い");
  else if (!showsJst(shown.text, ref)) p1.reasons.push(`詳細画面に日本時間（${JSON.stringify(jstParts(ref))}）で表示されていない`);
  p1.pass = p1.reasons.length === 0;
  out.P1 = p1;

  // ---- P2: 独自のエラー型（{ error, code, details? }）でエラーを返す ----
  const cases = [];
  if (scenario === "W7a") {
    const C = (id) => `/api/tasks/${id}/completion`;
    cases.push(await errorCase(guest, "未ログイン", "post", C(6), {}, 401));
    cases.push(await errorCase(sato, "存在しないタスク", "post", C(999), {}, 404));
    cases.push(await errorCase(sato, "担当者以外の完了報告", "post", C(2), {}, 403));
    cases.push(await errorCase(sato, "メモが長すぎる", "post", C(6), { note: "あ".repeat(501) }, 400));
    cases.push(await errorCase(sato, "完了済みのタスク", "post", C(1), {}, 409));
  } else {
    const W = (id) => `/api/tasks/${id}/worklogs`;
    cases.push(await errorCase(guest, "未ログイン", "post", W(6), { minutes: 30 }, 401));
    cases.push(await errorCase(sato, "存在しないタスク", "post", W(999), { minutes: 30 }, 404));
    cases.push(await errorCase(sato, "作業時間が不正", "post", W(6), { minutes: 0 }, 400));
    cases.push(await errorCase(sato, "完了済みのタスク", "post", W(1), { minutes: 30 }, 409));
    cases.push(await errorCase(suzuki, "本人以外の削除", "delete", `${W(3)}/${worklogId ?? 1}`, undefined, 403));
  }
  out.P2 = { pass: cases.every((c) => c.pass), cases };

  await browser.close();
  console.log(JSON.stringify(out));
})().catch((e) => {
  console.log(JSON.stringify({ error: String(e.message ?? e).slice(0, 300) }));
});
