// W7e（作業記録の CSV 出力）の受け入れテスト（試行中は候補に見せない）。課題は docs/poc/tasks/wf-W7e.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance-W7e.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかりを前提にする。作業記録は W7b の API で「今」作る。
// 落とし穴（日本時間の期間での絞り込み・記録日時の表示、エラー型）はここでは判定しない（pitfalls.cjs）。
// そのため、日本時間の今日と UTC の今日のどちらの日付で返しても合格にし、記録日時の列の形は見ない。
const { setup, assert, json } = require("./common.cjs");

function ymd(d) {
  return d.toISOString().slice(0, 10);
}
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

(async () => {
  const base = process.argv[2];
  const { browser, results, login, anon, check } = await setup(base);
  const sato = await login("sato");
  const suzuki = await login("suzuki");
  const guest = await anon();
  const E = (from, to) => `/api/me/worklogs/export?from=${from}&to=${to}`;
  const now = new Date();
  const days = [...new Set([ymd(new Date(now.getTime() + 9 * 3600 * 1000)), ymd(now)])];

  await check("未ログインでは 401", async () => {
    const r = await guest.request.get(E(days[0], days[0]));
    assert(r.status() === 401, `got ${r.status()}`);
  });
  await check("記録の無い期間は見出しの行だけ（200、CSV の Content-Type と添付のファイル名）", async () => {
    const r = await sato.request.get(E("2001-01-01", "2001-01-31"));
    const text = await r.text();
    const h = r.headers();
    assert(r.status() === 200, `got ${r.status()}`);
    assert(/^text\/csv/i.test(h["content-type"] ?? "") && /charset=utf-8/i.test(h["content-type"] ?? ""), `content-type: ${h["content-type"]}`);
    assert(/attachment/i.test(h["content-disposition"] ?? "") && (h["content-disposition"] ?? "").includes("worklogs-2001-01-01-2001-01-31.csv"),
      `content-disposition: ${h["content-disposition"]}`);
    assert(text.replace(/^﻿/, "") === "記録日時,タスク,作業時間（分）,メモ\r\n" || text.replace(/^﻿/, "") === "記録日時,タスク,作業時間（分）,メモ",
      `body: ${JSON.stringify(text).slice(0, 120)}`);
  });
  await sato.request.post("/api/tasks/3/worklogs", { data: { minutes: 30, note: '設計, "見直し"' } });
  await sato.request.post("/api/tasks/6/worklogs", { data: { minutes: 45, note: "1 行目\n2 行目" } });
  await suzuki.request.post("/api/tasks/3/worklogs", { data: { minutes: 60, note: "鈴木の記録" } });
  let rows, raw;
  await check("自分の作業記録だけが古い順に 1 行ずつ出る（タスクの名前・作業時間・メモ）", async () => {
    for (const d of days) {
      const t = (await (await sato.request.get(E(d, d))).text()).replace(/^﻿/, "");
      if (t.includes("API 設計")) { raw = t; break; }
    }
    assert(raw, `今日（${days.join(" / ")}）の記録が出ない`);
    // メモの改行を含むので、ダブルクォートの外の CRLF で分ける
    const lines = [];
    let cur = "", q = false;
    for (let i = 0; i < raw.length; i++) {
      const ch = raw[i];
      if (ch === '"') q = !q;
      if (!q && ch === "\r" && raw[i + 1] === "\n") { lines.push(cur); cur = ""; i++; continue; }
      cur += ch;
    }
    if (cur) lines.push(cur);
    assert(lines[0] === "記録日時,タスク,作業時間（分）,メモ", `見出し: ${lines[0]}`);
    rows = lines.slice(1).map(csvRow);
    assert(rows.length === 2, `行数 ${rows.length}: ${JSON.stringify(raw).slice(0, 200)}`);
    assert(rows[0][1] === "API 設計" && rows[0][2] === "30" && rows[0][3] === '設計, "見直し"', JSON.stringify(rows[0]));
    assert(rows[1][1] === "E2E テストの追加" && rows[1][2] === "45" && rows[1][3] === "1 行目\n2 行目", JSON.stringify(rows[1]));
    assert(rows.every((r) => r[0].length > 0), "記録日時が空");
  });
  await check("改行は CRLF", async () => {
    assert(raw && raw.startsWith("記録日時,タスク,作業時間（分）,メモ\r\n"), "見出しの行の改行が CRLF でない");
  });
  await check("ほかの人の CSV には自分の記録だけが出る", async () => {
    let t = "";
    for (const d of days) {
      t = (await (await suzuki.request.get(E(d, d))).text()).replace(/^﻿/, "");
      if (t.includes("鈴木の記録")) break;
    }
    assert(t.includes("鈴木の記録") && !t.includes("API 設計,30"), JSON.stringify(t).slice(0, 160));
  });
  await check("from・to が無い・形式が違う・存在しない日付・from が to より後・31 日を超えるときは 400（CSV を返さない）", async () => {
    const qs = ["", "?from=2026-11-01", "?to=2026-11-30", "?from=2026-11-01&to=20261130", "?from=2026-11-01&to=2026-11-31",
      "?from=2026-11-10&to=2026-11-09", "?from=2026-11-01&to=2026-12-02", "?from=abc&to=2026-11-01"];
    const s = [];
    for (const q of qs) {
      const r = await sato.request.get(`/api/me/worklogs/export${q}`);
      s.push(`${r.status()}${/csv/i.test(r.headers()["content-type"] ?? "") ? "csv" : ""}`);
    }
    assert(s.every((x) => x === "400"), `got ${s}`);
  });
  await check("期間の境界（ちょうど 31 日、from と to が同じ日）は受け付ける", async () => {
    const s = [(await sato.request.get(E("2026-11-01", "2026-12-01"))).status(), (await sato.request.get(E("2026-11-01", "2026-11-01"))).status()];
    assert(s.every((x) => x === 200), `got ${s}`);
  });
  await check("[既存] タスクの作業記録の API は今までどおり使える", async () => {
    const j = await json(await sato.request.get("/api/tasks/3/worklogs"));
    assert(j?.worklogs?.length === 2 && j.totalMinutes === 90, JSON.stringify(j)?.slice(0, 160));
  });

  await browser.close();
  console.log(JSON.stringify(results));
})().catch((e) => {
  console.log(JSON.stringify([{ name: "E2E 実行", pass: false, detail: String(e.message ?? e).slice(0, 300) }]));
});
