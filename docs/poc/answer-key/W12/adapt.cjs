// W12 の採点用: 候補の実装から「アダプター」（重要度の項目名・値・設定のしかた・絞り込み・ジョブの API）を見つけ、JSON で出す。
// 候補は項目名や値（A/B/C、high/medium/low など）を自分で決めるため、テストはこのアダプターを通して操作する。
// 自動で決められないとき（値が数値で順序が分からない、自由入力など）は needs_review を true にし、採点者が確かめる
//（docs/poc/answer-key/W12/grading.md の「アダプター」）。
// 使い方: W12_ROUTES='[{"path":"/api/jobs/x","methods":["POST"]}]' W12_JOBS_TOKEN=... node adapt.cjs <base>
const { request } = require("playwright");

const BASE_KEYS = ["id", "managementNo", "name", "model", "location", "managerId", "intervalMonths", "lastCalibratedOn", "status", "note"];
const VALUE_SETS = [
  ["A", "B", "C"], ["high", "medium", "low"], ["HIGH", "MEDIUM", "LOW"], ["高", "中", "低"], ["high", "normal", "low"],
  ["critical", "normal", "low"], ["critical", "high", "normal"], ["高", "通常", "低"], ["a", "b", "c"], ["high", "normal"],
  ["important", "normal"], ["高", "通常"], [true, false], [3, 2, 1], [1, 2, 3],
];
const NAME_HINT = /importan|priority|critical|重要|rank|grade|level|class|tier/i;

(async () => {
  const base = process.argv[2];
  const notes = [];
  const out = { key: null, levels: [], default: null, set: "patch", filter: { api: false, page: false, param: null },
    job: { method: null, path: null, unauthStatus: null }, needs_review: false, notes };
  const c = await request.newContext({ baseURL: base, timeout: 300_000 });
  const login = await c.post("/api/login", { data: { userId: "sato", password: "password" } });
  if (login.status() !== 200) throw new Error("login failed");
  const j = async (res) => { try { return await res.json(); } catch { return undefined; } };
  const get = async (id) => (await j(await c.get(`/api/instruments/${id}`)))?.instrument;
  const list = (await j(await c.get("/api/instruments")))?.instruments ?? [];
  const seed = list.find((i) => i.managementNo === "MI-0001") ?? list[0];
  const detail = seed ? await get(seed.id) : undefined;
  const keys = [...new Set([...Object.keys(seed ?? {}), ...Object.keys(detail ?? {})])].filter((k) => !BASE_KEYS.includes(k));
  keys.sort((a, b) => (NAME_HINT.test(b) ? 1 : 0) - (NAME_HINT.test(a) ? 1 : 0));
  notes.push(`新しい項目: ${keys.join(", ") || "なし"}`);
  const probeBody = (no) => ({ managementNo: no, name: "アダプター確認用", managerId: "sato", intervalMonths: 120, lastCalibratedOn: "2026-01-05" });
  const created = await j(await c.post("/api/instruments", { data: probeBody("AD-0001") }));
  const probe = created?.instrument;
  if (!probe) notes.push("確認用の計測器を登録できない");
  let best = null;
  if (probe) {
    for (const key of keys) {
      const v0 = (detail ?? seed)[key];
      if (v0 !== null && typeof v0 === "object") continue;
      for (const set of VALUE_SETS) {
        const accepted = [];
        for (const v of set) {
          const r = await c.patch(`/api/instruments/${probe.id}`, { data: { [key]: v } });
          if (r.status() === 200 && (await get(probe.id))?.[key] === v) accepted.push(v);
        }
        if (accepted.length >= 2 && (!best || accepted.length > best.levels.length)) best = { key, levels: accepted, set };
      }
      if (best) {
        const bogus = await c.patch(`/api/instruments/${probe.id}`, { data: { [key]: "zz-unknown" } });
        if (bogus.status() === 200) { out.needs_review = true; notes.push(`${key} は任意の値を受け付ける`); }
        break;
      }
    }
  }
  if (best) {
    out.key = best.key;
    out.levels = best.levels;
    if (typeof best.levels[0] === "number") { out.needs_review = true; notes.push("値が数値で、どれが高いかを自動で決められない（仮に大きい方を高いとした）"); }
    // 既存の計測器の重要度: 初期データの計測器でいちばん多い値（初期データの一部を見本として A にした候補もいるため。2026-11-10 補正）
    const counts = new Map();
    for (const i of list) counts.set(JSON.stringify(i[best.key] ?? null), (counts.get(JSON.stringify(i[best.key] ?? null)) ?? 0) + 1);
    out.default = JSON.parse([...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? "null");
    // 登録のときに重要度を受け付けるか
    const r = await j(await c.post("/api/instruments", { data: { ...probeBody("AD-0002"), [best.key]: best.levels[0] } }));
    out.set = r?.instrument && (await get(r.instrument.id))?.[best.key] === best.levels[0] ? "post" : "patch";
    // 一覧の絞り込み（API と画面）
    await c.patch(`/api/instruments/${probe.id}`, { data: { [best.key]: best.levels[0] } });
    const snake = best.key.replace(/[A-Z]/g, (m) => "_" + m.toLowerCase());
    for (const param of [...new Set([best.key, snake, "importance", "priority", "level"])]) {
      const q = encodeURIComponent(String(best.levels[0]));
      const l = (await j(await c.get(`/api/instruments?${param}=${q}`)))?.instruments;
      if (Array.isArray(l) && l.some((i) => i.id === probe.id) && l.every((i) => i[best.key] === best.levels[0]) && l.length < list.length) {
        out.filter.api = true; out.filter.param = param;
      }
      const page = await c.get(`/instruments?${param}=${q}`);
      const html = page.status() === 200 ? await page.text() : "";
      if (html.includes("AD-0001") && !html.includes("MI-0001")) { out.filter.page = true; out.filter.param ??= param; }
      if (out.filter.api || out.filter.page) break;
    }
  } else {
    out.needs_review = true;
    notes.push("重要度の項目を自動で見つけられない");
  }
  // ジョブの API（候補が足した Route のうち、JOBS_TOKEN で 2xx を返すもの。/api/jobs/ を優先）
  const routes = JSON.parse(process.env.W12_ROUTES || "[]")
    .filter((r) => !r.path.includes("["))
    .sort((a, b) => (b.path.startsWith("/api/jobs/") ? 1 : 0) - (a.path.startsWith("/api/jobs/") ? 1 : 0));
  const anon = await request.newContext({ baseURL: base, timeout: 300_000 });
  for (const r of routes) {
    for (const method of ["POST", "GET", "PUT"].filter((m) => r.methods.includes(m))) {
      const res = await anon.fetch(r.path, { method, headers: { authorization: `Bearer ${process.env.W12_JOBS_TOKEN}` } });
      if (res.status() >= 200 && res.status() < 300) {
        const no = await anon.fetch(r.path, { method });
        out.job = { method, path: r.path, unauthStatus: no.status() };
        break;
      }
      notes.push(`${method} ${r.path} -> ${res.status()}`);
    }
    if (out.job.path) break;
  }
  if (!out.job.path) { out.needs_review = true; notes.push("ジョブの API を自動で見つけられない"); }
  await c.dispose(); await anon.dispose();
  console.log(JSON.stringify(out));
})().catch((e) => { console.log(JSON.stringify({ error: String(e), needs_review: true })); });
