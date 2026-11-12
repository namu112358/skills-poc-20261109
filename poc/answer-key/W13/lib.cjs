// W13 のテストの共通部分（試行中は候補に見せない）。
// 予約の API は候補ごとに違うため、採点用の「アダプター」（環境変数 W13_ADAPTER の JSON。grading.md の「アダプター」）を通して操作する。
// 環境変数: W13_ADAPTER（JSON）、W13_PHASE（v1 / v2）、W13_JOBS_TOKEN、POC_FAKE_NOW_FILE（偽の時計のファイル）
const fs = require("node:fs");
const { request } = require("playwright");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
/** 日本時間の日付（と時刻）を ISO にする。例: jst("2026-11-10") → 2026-11-09T22:30:00.000Z（日本時間 7:30） */
const jst = (date, time = "07:30") => new Date(`${date}T${time}:00+09:00`).toISOString();
/** YYYY-MM-DD に n 日足す */
const addDays = (d, n) => new Date(Date.parse(`${d}T00:00:00Z`) + n * 86_400_000).toISOString().slice(0, 10);
const is2xx = (s) => s >= 200 && s < 300;
const is4xx = (s) => s >= 400 && s < 500;

function pick(obj, path) {
  if (!path) return obj;
  return String(path).split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

function fill(tpl, vars) {
  if (typeof tpl === "string") {
    const m = /^\{(\w+):n\}$/.exec(tpl);
    if (m) return Number(vars[m[1]]);
    return tpl.replace(/\{(\w+)\}/g, (_, k) => (vars[k] === undefined ? `{${k}}` : String(vars[k])));
  }
  if (Array.isArray(tpl)) return tpl.map((x) => fill(x, vars));
  if (tpl && typeof tpl === "object") return Object.fromEntries(Object.entries(tpl).map(([k, v]) => [k, fill(v, vars)]));
  return tpl;
}

function harness(base, prefix, adapterJson) {
  const adapter = adapterJson ?? JSON.parse(process.env.W13_ADAPTER || "{}");
  const phase = process.env.W13_PHASE || "v1";
  const results = [];
  const contexts = [];
  let seq = 0;
  async function ctx() {
    // API として呼ぶ: JSON を受け付ける旨を送り、リダイレクトは追わない（画面のフォーム送信と兼ねる実装で、
    // 失敗が 303 → 画面の 200 に見えないようにする。2026-11-10、試行前の確認の後の補正。判断の記録）
    const c = await request.newContext({ baseURL: base, timeout: 300_000, maxRedirects: 0,
      extraHTTPHeaders: { accept: "application/json" } });
    contexts.push(c);
    return c;
  }
  const users = new Map(); // context → 利用者 ID（時計を進めてセッションが切れたら入り直す）
  async function signIn(c, userId) {
    const res = await c.post("/api/login", { data: { userId, password: "password" } });
    if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
  }
  const sessions = {};
  /** 利用者ごとにログイン済みの context を返す（同じ利用者は使い回す） */
  async function as(userId) {
    if (sessions[userId]) return sessions[userId];
    const c = await ctx();
    await signIn(c, userId);
    users.set(c, userId);
    sessions[userId] = c;
    return c;
  }
  async function json(res) {
    try { return await res.json(); } catch { return undefined; }
  }
  async function call(c, method, path, body, headers) {
    // 本文の無い POST・PATCH・PUT・DELETE も JSON（{}）で送る（JSON の要求かどうかで応答を変える実装があるため）
    const data = body !== undefined ? body : method !== "GET" ? {} : undefined;
    const go = () => c.fetch(path, { method, ...(data !== undefined ? { data } : {}), ...(headers ? { headers } : {}), maxRedirects: 0 });
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
      results.push({ id, name, pass: false, detail: String(e.message ?? e).slice(0, 600) });
    }
  }
  function setNow(iso) {
    fs.writeFileSync(process.env.POC_FAKE_NOW_FILE, iso + "\n");
    return sleep(30);
  }
  /** 日付を候補の形にする（既定は YYYY-MM-DD のまま。adapter.dateFormat.start / end でテンプレートを指定できる） */
  function fmt(kind, d) {
    const t = adapter.dateFormat?.[kind];
    if (!t) return d;
    const v = t.replace("{d}", d).replace("{d+1}", addDays(d, 1));
    return /T/.test(v) && adapter.dateFormat?.iso ? new Date(v).toISOString() : v;
  }

  /** テスト用の計測器を作る（管理者・状態を指定できる）。 */
  async function instrument({ managerId = "kato", status = "in_use" } = {}) {
    const c = await as("sato");
    const no = `${prefix}-${String(++seq).padStart(4, "0")}`;
    const body = { managementNo: no, name: `検証用計測器 ${no}`, model: "T-1", location: "検証室", managerId, intervalMonths: 12, lastCalibratedOn: "2026-10-01" };
    const r = await call(c, "POST", "/api/instruments", body);
    if (r.status !== 201) throw new Error(`計測器を登録できない: ${r.status} ${JSON.stringify(r.json)?.slice(0, 200)}`);
    const id = r.json.instrument.id;
    if (status !== "in_use") {
      const p = await call(c, "PATCH", `/api/instruments/${id}`, { status });
      if (p.status !== 200) throw new Error(`状態を変えられない: ${p.status}`);
    }
    return { id, no, managerId };
  }

  /** 予約する。戻り値 { status, id, json } */
  async function reserve(userId, inst, start, end) {
    const a = adapter.create;
    if (!a) throw new Error("予約の API が見つからない（アダプター）");
    const vars = { instrumentId: inst.id, managementNo: inst.no, start: fmt("start", start), end: fmt("end", end), user: userId };
    const r = await call(await as(userId), a.method || "POST", fill(a.path, vars), a.body ? fill(a.body, vars) : undefined);
    return { status: r.status, id: is2xx(r.status) ? pick(r.json, a.id) : undefined, json: r.json };
  }
  /** 予約を必ず作る（作れなければテストを失敗にする） */
  async function mustReserve(userId, inst, start, end) {
    const r = await reserve(userId, inst, start, end);
    if (!is2xx(r.status) || r.id === undefined) throw new Error(`予約できない ${start}〜${end}: ${r.status} ${JSON.stringify(r.json)?.slice(0, 200)}`);
    return r.id;
  }
  /** 予約への操作（cancel / approve / reject）。アダプターに無い操作は 0 を返す */
  async function act(userId, action, inst, rid) {
    const a = adapter[action];
    if (!a) return 0;
    const vars = { instrumentId: inst.id, managementNo: inst.no, reservationId: rid, user: userId };
    const r = await call(await as(userId), a.method || "POST", fill(a.path, vars), a.body ? fill(a.body, vars) : undefined);
    return r.status;
  }
  /** 状態の値を、アダプターの対応表で共通の名前（active・pending・approved・rejected・cancelled・expired）にする */
  // 複数の項目を組み合わせた状態（'"active"|null|null'）では、項目ごとに "*"（何でもよい）・"@notnull"（null 以外）が使える
  function partMatch(p, r) {
    return p === "*" || (p === "@notnull" && r !== "null") || p === r;
  }
  function matches(v, raw) {
    if (JSON.stringify(v) === JSON.stringify(raw)) return true;
    // 1 項目だけの組み合わせ（fields.status が要素 1 つの配列）でも "*"・"@notnull" を使えるようにする（2026-11-10 補正）
    if (typeof v !== "string" || typeof raw !== "string" || !(v.includes("|") || v === "*" || v === "@notnull")) return false;
    const a = v.split("|"), b = raw.split("|");
    return a.length === b.length && a.every((p, i) => partMatch(p, b[i]));
  }
  function canon(raw) {
    for (const [name, values] of Object.entries(adapter.status || {})) {
      if ((Array.isArray(values) ? values : [values]).some((v) => matches(v, raw))) return name;
    }
    return `?${JSON.stringify(raw)}`;
  }
  function rawStatus(item) {
    const f = adapter.fields?.status;
    if (Array.isArray(f)) return f.map((k) => JSON.stringify(pick(item, k) ?? null)).join("|");
    return pick(item, f || "status");
  }
  /** 計測器の予約の一覧（共通の形 { id, status, start, end, user, raw }） */
  async function list(inst, viewer = "sato") {
    const a = adapter.list;
    if (!a) throw new Error("予約の一覧の API が見つからない（アダプター）");
    const vars = { instrumentId: inst.id, managementNo: inst.no };
    // 状態ごとに一覧が分かれている実装（compound-engineering-1）のため、paths で複数の一覧を足し合わせられる（ID で重複を除く）
    const items = [];
    const seen = new Set();
    for (const path of a.paths || [a.path]) {
      const r = await call(await as(viewer), a.method || "GET", fill(path, vars));
      if (!is2xx(r.status)) throw new Error(`一覧: ${r.status}`);
      for (const x of pick(r.json, a.items) || []) {
        const k = JSON.stringify(pick(x, adapter.fields?.id || "id"));
        if (!seen.has(k)) { seen.add(k); items.push(x); }
      }
    }
    const f = adapter.fields || {};
    return items
      .filter((x) => !a.filterInstrument || String(pick(x, a.filterInstrument)) === String(inst.id))
      .map((x) => ({ id: pick(x, f.id || "id"), raw: rawStatus(x), status: canon(rawStatus(x)),
        start: String(pick(x, f.start || "startOn") ?? "").slice(0, 10), end: String(pick(x, f.end || "endOn") ?? "").slice(0, 10),
        user: pick(x, f.user || "userId"), item: x }));
  }
  /** 予約の今の状態（一覧に無ければ "absent"） */
  async function statusOf(inst, rid) {
    const x = (await list(inst)).find((i) => String(i.id) === String(rid));
    return x ? x.status : "absent";
  }
  /** 有効な予約（v2 では管理者の承認まで済ませる）を作る */
  async function effective(userId, inst, start, end) {
    const id = await mustReserve(userId, inst, start, end);
    if (phase === "v2") {
      const s = await act(approverOf(inst), "approve", inst, id);
      if (!is2xx(s)) throw new Error(`承認できない: ${s}`);
    }
    return id;
  }
  const approverOf = (inst) => (inst.managerId === "inoue" ? "yamada" : inst.managerId);
  /** 貸し出す（既定はその計測器の管理者（無効なら代表者）が操作し、borrowerId に貸す）。戻り値は status と貸出 ID。
   *  貸出の操作者を管理者にするのは、貸出の登録を管理者に限る実装（gstack-1）で、予約と貸出の関係の項目（K04・K05・C10）が
   *  権限の違いだけで落ちないようにするため（2026-11-10 補正。既存の振る舞いの変化は P02 が sato の操作で見る） */
  async function lend(inst, borrowerId, dueOn, actor) {
    // W13_PREFIX=1: 補正 3 の前（貸出の操作者は sato）で採点する（判断の記録の比較用。点数には使わない）
    const who = actor || (process.env.W13_PREFIX === "1" ? "sato" : approverOf(inst));
    const r = await call(await as(who), "POST", `/api/instruments/${inst.id}/loans`, { borrowerId, dueOn });
    return { status: r.status, loanId: r.json?.loan?.id };
  }
  async function returnLoan(inst, loanId, actor) {
    const who = actor || (process.env.W13_PREFIX === "1" ? "sato" : approverOf(inst));
    return (await call(await as(who), "POST", `/api/instruments/${inst.id}/loans/${loanId}/return`)).status;
  }
  async function calibrate(inst, calibratedOn, result) {
    return call(await as("sato"), "POST", `/api/instruments/${inst.id}/calibrations`, { calibratedOn, result, agency: "検証用校正機関" });
  }
  /** 候補が作った定期実行のジョブ（期限切れの処理など）があれば呼ぶ */
  async function runJobs() {
    for (const j of adapter.jobs || []) {
      const c = await ctx();
      await c.fetch(j.path, { method: j.method || "POST", headers: { authorization: `Bearer ${process.env.W13_JOBS_TOKEN}` } });
    }
  }
  async function done() {
    for (const c of contexts) await c.dispose();
    console.log(JSON.stringify(results));
  }
  return { adapter, phase, results, as, call, check, setNow, instrument, reserve, mustReserve, act, list, statusOf, effective,
    approverOf, lend, returnLoan, calibrate, runJobs, done, ctx, canon };
}

function assert(cond, msg) { if (!cond) throw new Error(msg); }

module.exports = { harness, assert, jst, addDays, sleep, is2xx, is4xx, pick, fill };
