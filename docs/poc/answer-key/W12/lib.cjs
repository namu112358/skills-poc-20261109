// W12 の受け入れテスト・隠しテスト・堅牢さのテストの共通部分（試行中は候補に見せない）。
// 候補ごとに違う部分（重要度の項目名と値、ジョブの API）は、adapt.cjs が作る「アダプター」（環境変数 W12_ADAPTER の JSON）で吸収する。
// 環境変数: W12_ADAPTER（JSON）、W12_NOTIFY（偽の通知サービスの URL）、W12_JOBS_TOKEN、POC_FAKE_NOW_FILE（偽の時計のファイル）
const fs = require("node:fs");
const { request } = require("playwright");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
/** 日本時間の日付（と時刻）を ISO にする。例: jst("2027-01-01") → 2026-12-31T22:30:00.000Z（日本時間 7:30） */
const jst = (date, time = "07:30") => new Date(`${date}T${time}:00+09:00`).toISOString();

function harness(base, prefix) {
  const adapter = JSON.parse(process.env.W12_ADAPTER || "{}");
  const notify = process.env.W12_NOTIFY;
  const results = [];
  const contexts = [];
  let seq = 0;
  async function ctx() {
    const c = await request.newContext({ baseURL: base, timeout: 300_000 });
    contexts.push(c);
    return c;
  }
  const users = new Map(); // ログインした context → 利用者 ID（時計を進めてセッションが切れたら入り直す）
  async function signIn(c, userId) {
    const res = await c.post("/api/login", { data: { userId, password: "password" } });
    if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
  }
  async function login(userId) {
    const c = await ctx();
    await signIn(c, userId);
    users.set(c, userId);
    return c;
  }
  async function json(res) {
    try { return await res.json(); } catch { return undefined; }
  }
  async function call(c, method, path, body, headers) {
    const go = () => c.fetch(path, { method, ...(body !== undefined ? { data: body } : {}), ...(headers ? { headers } : {}) });
    let res = await go();
    if (res.status() === 401 && users.has(c)) {
      await signIn(c, users.get(c));
      res = await go();
    }
    return { status: res.status(), json: await json(res) };
  }
  async function check(id, name, fn) {
    try {
      const detail = await fn();
      results.push({ id, name, pass: true, detail: detail ?? "" });
    } catch (e) {
      results.push({ id, name, pass: false, detail: String(e.message ?? e).slice(0, 500) });
    }
  }
  function setNow(iso) {
    fs.writeFileSync(process.env.POC_FAKE_NOW_FILE, iso + "\n");
    return sleep(30);
  }
  /** 重要度の値。level は "top"（最も高い）・"mid"・"low"、または値そのもの */
  function level(l) {
    const lv = adapter.levels || [];
    if (l === "top") return lv[0];
    if (l === "mid") return lv.length >= 3 ? lv[1] : lv[lv.length - 1];
    if (l === "low") return lv[lv.length - 1];
    return l;
  }
  /** テスト用の計測器を作る。status は in_use・calibrating・suspended・disposed（貸出中は lend で作る） */
  async function instrument(c, { managerId = "sato", interval = 12, last, status = "in_use", importance = "top" }) {
    const no = `${prefix}-${String(++seq).padStart(4, "0")}`;
    const body = { managementNo: no, name: `検証用計測器 ${no}`, model: "T-1", location: "検証室", managerId, intervalMonths: interval, lastCalibratedOn: last };
    const value = importance === undefined ? undefined : level(importance);
    if (adapter.set === "post" && value !== undefined) body[adapter.key] = value;
    const r = await call(c, "POST", "/api/instruments", body);
    if (r.status !== 201) throw new Error(`計測器を登録できない: ${r.status} ${JSON.stringify(r.json)?.slice(0, 200)}`);
    const id = r.json.instrument.id;
    if (adapter.set !== "post" && value !== undefined) {
      const p = await call(c, "PATCH", `/api/instruments/${id}`, { [adapter.key]: value });
      if (p.status !== 200) throw new Error(`重要度を設定できない: ${p.status} ${JSON.stringify(p.json)?.slice(0, 200)}`);
    }
    if (status !== "in_use") {
      const p = await call(c, "PATCH", `/api/instruments/${id}`, { status });
      if (p.status !== 200) throw new Error(`状態を変えられない: ${p.status}`);
    }
    return { id, no };
  }
  async function lend(c, inst, borrowerId, dueOn = "2099-12-31") {
    const r = await call(c, "POST", `/api/instruments/${inst.id}/loans`, { borrowerId, dueOn });
    if (r.status !== 201) throw new Error(`貸し出せない: ${r.status} ${JSON.stringify(r.json)}`);
  }
  async function calibrate(c, inst, calibratedOn, result = "pass") {
    const r = await call(c, "POST", `/api/instruments/${inst.id}/calibrations`, { calibratedOn, result, agency: "検証用校正機関" });
    if (r.status !== 201) throw new Error(`校正記録を登録できない: ${r.status} ${JSON.stringify(r.json)}`);
  }
  /** ジョブを呼ぶ（アダプターの method・path、JOBS_TOKEN の Bearer）。完了を待ち、少し待って非同期の送信も拾う */
  async function runJob() {
    if (!adapter.job?.path) throw new Error("ジョブの API が見つからない");
    const c = await ctx();
    const t0 = Date.now();
    const res = await c.fetch(adapter.job.path, {
      method: adapter.job.method || "POST",
      headers: { authorization: `Bearer ${process.env.W12_JOBS_TOKEN}`, ...(adapter.job.headers || {}) },
      timeout: 300_000,
    });
    await sleep(adapter.job.settleMs ?? 1500);
    return { status: res.status(), ms: Date.now() - t0 };
  }
  async function state() {
    const r = await fetch(`${notify}/__state`);
    return r.json();
  }
  async function script(recipient, actions, replace = false) {
    await fetch(`${notify}/__script`, { method: "POST", body: JSON.stringify({ recipient, actions, replace }) });
  }
  async function mode(all503) {
    await fetch(`${notify}/__mode`, { method: "POST", body: JSON.stringify({ all503 }) });
  }
  const mentions = (d, no) => `${d.title ?? ""}\n${d.body ?? ""}`.includes(no);
  /** その計測器について届いたお知らせ（送り先で絞れる） */
  async function delivered(inst, recipient) {
    const s = await state();
    return s.deliveries.filter((d) => mentions(d, inst.no) && (!recipient || d.recipient === recipient));
  }
  /** その計測器について届いた要求（失敗した応答を含む） */
  async function requested(inst, recipient) {
    const s = await state();
    return s.requests.filter((d) => d.raw.includes(inst.no) && (!recipient || d.recipient === recipient));
  }
  async function done() {
    for (const c of contexts) await c.dispose();
    console.log(JSON.stringify(results));
  }
  return { adapter, results, login, call, check, setNow, level, instrument, lend, calibrate, runJob, state, script, mode,
    delivered, requested, done, ctx };
}

function assert(cond, msg) { if (!cond) throw new Error(msg); }
const show = (r) => `${r.status} ${JSON.stringify(r.json)?.slice(0, 200)}`;

module.exports = { harness, assert, show, jst, sleep };
