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
          out.push({ table, column: col, value: String(v) });
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

(async () => {
  const [scenario, base, dbPath] = process.argv.slice(2);
  const { browser, login, anon } = await setup(base);
  const sato = await login("sato");
  const suzuki = await login("suzuki");
  const guest = await anon();
  const out = { scenario };

  // ---- P1: 日時を UTC で保存し、JST で表示する ----
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
