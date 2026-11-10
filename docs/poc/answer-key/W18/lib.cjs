// W18 のテストの共通部分（試行中は候補に見せない）。W12 の lib.cjs（重要度・通知）と W13 の lib.cjs（予約）を 1 つにまとめ、
// 設置場所・発注・履歴・副管理者の操作を足した。
// API の名前は系列ごと・回ごとに違うため、採点用の「アダプター」（環境変数 W18_ADAPTER の JSON。grading.md の「アダプター」）を通して操作する。
// 環境変数: W18_ADAPTER（JSON）、W18_NOTIFY・W18_AGENCY（偽の通知サービス・受付システムの URL）、W18_JOBS_TOKEN、POC_FAKE_NOW_FILE
const fs = require("node:fs");
const { request } = require("playwright");

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
/** 日本時間の日付（と時刻）を ISO にする。例: jst("2026-11-10") → 2026-11-09T22:30:00.000Z（日本時間 7:30） */
const jst = (date, time = "07:30") => new Date(`${date}T${time}:00+09:00`).toISOString();
/** YYYY-MM-DD に n 日足す */
const addDays = (d, n) => new Date(Date.parse(`${d}T00:00:00Z`) + n * 86_400_000).toISOString().slice(0, 10);
const is2xx = (s) => s >= 200 && s < 300;
const is4xx = (s) => s >= 400 && s < 500;
function assert(cond, msg) { if (!cond) throw new Error(msg); }
const show = (r) => `${r.status} ${JSON.stringify(r.json)?.slice(0, 200)}`;

function pick(obj, path) {
  if (path === undefined || path === null || path === "") return obj;
  return String(path).split(".").reduce((o, k) => (o == null ? undefined : o[k]), obj);
}

/** テンプレートを埋める。"{name:n}" は数値、"{name}" は文字列。 */
function fill(tpl, vars) {
  if (typeof tpl === "string") {
    const m = /^\{(\w+):n\}$/.exec(tpl);
    if (m) return Number(vars[m[1]]);
    const whole = /^\{(\w+)\}$/.exec(tpl);
    if (whole && vars[whole[1]] !== undefined && typeof vars[whole[1]] !== "string") return vars[whole[1]];
    return tpl.replace(/\{(\w+)\}/g, (_, k) => (vars[k] === undefined ? `{${k}}` : String(vars[k])));
  }
  if (Array.isArray(tpl)) return tpl.map((x) => fill(x, vars));
  if (tpl && typeof tpl === "object") return Object.fromEntries(Object.entries(tpl).map(([k, v]) => [k, fill(v, vars)]));
  return tpl;
}

function harness(base, prefix) {
  const adapter = JSON.parse(process.env.W18_ADAPTER || "{}");
  const notify = process.env.W18_NOTIFY;
  const agency = process.env.W18_AGENCY;
  const results = [];
  const contexts = [];
  let seq = 0;
  async function ctx() {
    const c = await request.newContext({ baseURL: base, timeout: 300_000 });
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
  /** API を呼ぶ。c は context か利用者 ID */
  async function call(c, method, path, body, headers) {
    if (typeof c === "string") c = await as(c);
    const go = () => c.fetch(path, { method, ...(body !== undefined ? { data: body } : {}), ...(headers ? { headers } : {}) });
    let res = await go();
    if (res.status() === 401 && users.has(c)) {
      await signIn(c, users.get(c));
      res = await go();
    }
    return { status: res.status(), json: await json(res), text: res.status() >= 300 ? "" : undefined };
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
  /** アダプターの操作を呼ぶ（{method, path, body} のテンプレート）。無ければ undefined */
  async function op(spec, who, vars) {
    if (!spec) return undefined;
    return call(who, spec.method || "POST", fill(spec.path, vars), spec.body ? fill(spec.body, vars) : undefined);
  }

  // ---- 重要度（第 1 回）----
  const f1 = adapter.f1 || {};
  /** 重要度の値。"top"（最も高い）・"mid"・"low"、または値そのもの */
  function level(l) {
    const lv = f1.levels || [];
    if (l === "top") return lv[0];
    if (l === "mid") return lv.length >= 3 ? lv[1] : lv[lv.length - 1];
    if (l === "low") return lv[lv.length - 1];
    return l;
  }

  // ---- 設置場所（第 3 回）----
  const f3 = adapter.f3;
  const locCache = {};
  async function locations() {
    const r = await op(f3?.list ? { method: "GET", ...f3.list } : undefined, "sato", {});
    if (!r || !is2xx(r.status)) throw new Error(`場所の一覧: ${r ? show(r) : "アダプターに無い"}`);
    return (pick(r.json, f3.list.items) || []).map((x) => ({ id: pick(x, f3.fields?.id || "id"), name: pick(x, f3.fields?.name || "name"), item: x }));
  }
  /** 場所を作る（品質保証部の sato）。戻り値は呼び出しの結果と ID */
  async function createLocation(name, who = "sato") {
    const r = await op(f3?.create, who, { name });
    return { ...r, id: r && is2xx(r.status) ? pick(r.json, f3.create.id) : undefined };
  }
  /** 名前の場所の ID（無ければ作る）。テスト用の計測器の置き場所に使う */
  async function locationId(name) {
    if (locCache[name] !== undefined) return locCache[name];
    const found = (await locations()).find((l) => l.name === name);
    if (found) return (locCache[name] = found.id);
    const r = await createLocation(name);
    if (r.id === undefined) throw new Error(`場所を作れない: ${show(r)}`);
    return (locCache[name] = r.id);
  }
  /** 計測器の本文に入れる設置場所。第 3 回の後はアダプターの形（例 { locationId }）、それまでは名前の文字列 */
  async function locationBody(name) {
    if (!f3) return { location: name };
    return fill(f3.instrumentSet || { locationId: "{locationId:n}" }, { locationId: await locationId(name), name });
  }

  /** テスト用の計測器を作る（sato が登録）。status は in_use・calibrating・suspended・disposed（貸出中は lend で作る） */
  async function instrument({ managerId = "kato", interval = 12, last = "2026-10-01", status = "in_use", importance, location = "検証室", model = "T-1" } = {}) {
    const no = `${prefix}-${String(++seq).padStart(4, "0")}`;
    const body = { managementNo: no, name: `検証用計測器 ${no}`, model, managerId, intervalMonths: interval, lastCalibratedOn: last,
      ...(location === null ? {} : await locationBody(location)), ...(adapter.instrument?.createExtra || {}) };
    const value = importance === undefined ? undefined : level(importance);
    if (f1.set === "post" && value !== undefined) body[f1.key] = value;
    const r = await call("sato", "POST", "/api/instruments", body);
    if (r.status !== 201) throw new Error(`計測器を登録できない: ${show(r)}`);
    const id = pick(r.json, adapter.instrument?.id || "instrument.id");
    if (f1.set !== "post" && value !== undefined) {
      if (!f1.key) throw new Error("重要度の項目が見つからない（アダプター）");
      const p = await call("sato", "PATCH", `/api/instruments/${id}`, { [f1.key]: value });
      if (p.status !== 200) throw new Error(`重要度を設定できない: ${show(p)}`);
    }
    if (status !== "in_use") {
      const p = await call("sato", "PATCH", `/api/instruments/${id}`, { status });
      if (p.status !== 200) throw new Error(`状態を変えられない: ${show(p)}`);
    }
    return { id, no, managerId };
  }
  async function getInstrument(inst, who = "sato") {
    const r = await call(who, "GET", `/api/instruments/${inst.id}`);
    return { ...r, instrument: r.json?.instrument };
  }
  async function patch(inst, body, who = "sato") {
    return call(who, "PATCH", `/api/instruments/${inst.id}`, body);
  }
  /** 貸し出す（既定は sato が操作し、borrowerId に貸す） */
  async function lend(inst, borrowerId, dueOn = "2099-12-31", who = "sato") {
    const r = await call(who, "POST", `/api/instruments/${inst.id}/loans`, { borrowerId, dueOn });
    return { status: r.status, loanId: r.json?.loan?.id, json: r.json };
  }
  async function returnLoan(inst, loanId, who = "sato") {
    return (await call(who, "POST", `/api/instruments/${inst.id}/loans/${loanId}/return`)).status;
  }
  async function calibrate(inst, calibratedOn, result = "pass", who = "sato") {
    return call(who, "POST", `/api/instruments/${inst.id}/calibrations`, { calibratedOn, result, agency: "検証用校正機関" });
  }
  /** 定期実行のジョブを呼ぶ（JOBS_TOKEN の Bearer）。job は { method, path }。少し待って非同期の送信も拾う */
  async function runJob(job, settleMs = 1500) {
    if (!job?.path) throw new Error("ジョブの API が見つからない（アダプター）");
    const c = await ctx();
    const res = await c.fetch(job.path, { method: job.method || "POST", headers: { authorization: `Bearer ${process.env.W18_JOBS_TOKEN}` }, timeout: 300_000 });
    await sleep(settleMs);
    return res.status();
  }
  const runReminders = () => runJob(f1.job);

  // ---- 偽の通知サービス ----
  async function notifyState() { return (await fetch(`${notify}/__state`)).json(); }
  async function notifyScript(recipient, actions, replace = false) {
    await fetch(`${notify}/__script`, { method: "POST", body: JSON.stringify({ recipient, actions, replace }) });
  }
  const mentions = (d, no) => `${d.title ?? ""}\n${d.body ?? ""}`.includes(no);
  /** その計測器について届いたお知らせ（送り先で絞れる） */
  async function delivered(inst, recipient) {
    const s = await notifyState();
    return s.deliveries.filter((d) => mentions(d, inst.no) && (!recipient || d.recipient === recipient));
  }

  // ---- 予約（第 2 回）----
  const f2 = adapter.f2 || {};
  async function reserve(userId, inst, start, end) {
    if (!f2.create) throw new Error("予約の API が見つからない（アダプター）");
    const r = await op(f2.create, userId, { instrumentId: inst.id, managementNo: inst.no, start, end, user: userId });
    return { status: r.status, id: is2xx(r.status) ? pick(r.json, f2.create.id) : undefined, json: r.json };
  }
  async function mustReserve(userId, inst, start, end) {
    const r = await reserve(userId, inst, start, end);
    if (!is2xx(r.status) || r.id === undefined) throw new Error(`予約できない ${start}〜${end}: ${show(r)}`);
    return r.id;
  }
  async function cancelReservation(userId, inst, rid) {
    const r = await op(f2.cancel, userId, { instrumentId: inst.id, managementNo: inst.no, reservationId: rid, user: userId });
    return r ? r.status : 0;
  }
  function canon(raw) {
    for (const [name, values] of Object.entries(f2.status || {})) {
      if ((Array.isArray(values) ? values : [values]).some((v) => JSON.stringify(v) === JSON.stringify(raw))) return name;
    }
    return `?${JSON.stringify(raw)}`;
  }
  async function reservations(inst, viewer = "sato") {
    const r = await op(f2.list ? { method: "GET", ...f2.list } : undefined, viewer, { instrumentId: inst.id, managementNo: inst.no });
    if (!r || !is2xx(r.status)) throw new Error(`予約の一覧: ${r ? show(r) : "アダプターに無い"}`);
    const f = f2.fields || {};
    return (pick(r.json, f2.list.items) || [])
      .filter((x) => !f2.list.filterInstrument || String(pick(x, f2.list.filterInstrument)) === String(inst.id))
      .map((x) => ({ id: pick(x, f.id || "id"), status: canon(pick(x, f.status || "status")), start: String(pick(x, f.start || "startOn") ?? "").slice(0, 10),
        end: String(pick(x, f.end || "endOn") ?? "").slice(0, 10), user: pick(x, f.user || "userId"), item: x }));
  }
  async function reservationStatus(inst, rid) {
    const x = (await reservations(inst)).find((i) => String(i.id) === String(rid));
    return x ? x.status : "absent";
  }
  const gone = (s) => s === "cancelled" || s === "absent";

  // ---- 発注（第 4 回）----
  const f4 = adapter.f4 || {};
  async function order(inst, who = "sato") {
    if (!f4.create) throw new Error("発注の API が見つからない（アダプター）");
    const r = await op(f4.create, who, { instrumentId: inst.id, managementNo: inst.no, user: who });
    return { ...r, id: is2xx(r.status) ? pick(r.json, f4.create.id) : undefined };
  }
  function orderCanon(raw) {
    for (const [name, values] of Object.entries(f4.status || {})) {
      if ((Array.isArray(values) ? values : [values]).some((v) => JSON.stringify(v) === JSON.stringify(raw))) return name;
    }
    return `?${JSON.stringify(raw)}`;
  }
  /** 計測器の発注の一覧（共通の形 { id, status（pending・accepted・completed・failed）, externalId, returnOn, item }） */
  async function orders(inst, viewer = "sato") {
    const r = await op(f4.list ? { method: "GET", ...f4.list } : undefined, viewer, { instrumentId: inst.id, managementNo: inst.no });
    if (!r || !is2xx(r.status)) throw new Error(`発注の一覧: ${r ? show(r) : "アダプターに無い"}`);
    const f = f4.fields || {};
    return (pick(r.json, f4.list.items) || [])
      .filter((x) => !f4.list.filterInstrument || String(pick(x, f4.list.filterInstrument)) === String(inst.id))
      .map((x) => ({ id: pick(x, f.id || "id"), status: orderCanon(pick(x, f.status || "status")), externalId: pick(x, f.externalId),
        returnOn: pick(x, f.returnOn), item: x }));
  }
  const runOrderJob = () => runJob(f4.job);
  async function agencyState() { return (await fetch(`${agency}/__state`)).json(); }
  async function agencyScript(managementNo, actions, replace = false) {
    await fetch(`${agency}/__script`, { method: "POST", body: JSON.stringify({ managementNo, actions, replace }) });
  }
  async function agencyMode(all503) {
    await fetch(`${agency}/__mode`, { method: "POST", body: JSON.stringify({ all503 }) });
  }
  /** 受付システムが受け付けたその計測器の発注 */
  async function agencyOrders(inst) {
    return (await agencyState()).orders.filter((o) => o.item?.managementNo === inst.no);
  }

  // ---- 履歴（第 5 回）----
  const f5 = adapter.f5 || {};
  /** 計測器の履歴（新しい順かどうかは問わず、API が返す順のまま） */
  async function history(inst, viewer = "sato") {
    const r = await op(f5.list ? { method: "GET", ...f5.list } : undefined, viewer, { instrumentId: inst.id, managementNo: inst.no });
    if (!r || !is2xx(r.status)) throw new Error(`履歴: ${r ? show(r) : "アダプターに無い"}`);
    return (pick(r.json, f5.list.items) || []).filter((x) => !f5.list.filterInstrument || String(pick(x, f5.list.filterInstrument)) === String(inst.id));
  }
  const key = (x) => JSON.stringify(x);
  /** fn を実行し、その間に増えた履歴を返す */
  async function newHistory(inst, fn) {
    const before = new Set((await history(inst)).map(key));
    const out = await fn();
    const after = await history(inst);
    return { added: after.filter((x) => !before.has(key(x))), out, all: after };
  }

  // ---- 副管理者（引き継ぎ h1）----
  const h1 = adapter.h1 || {};
  async function setSubManager(inst, userId, who = "sato") {
    if (!h1.set) throw new Error("副管理者の設定のしかたが見つからない（アダプター）");
    return op(h1.set, who, { instrumentId: inst.id, managementNo: inst.no, subManager: userId === null ? null : userId });
  }

  async function done() {
    for (const c of contexts) await c.dispose();
    console.log(JSON.stringify(results));
  }
  return { adapter, results, as, call, check, setNow, op, level, instrument, getInstrument, patch, lend, returnLoan, calibrate,
    runJob, runReminders, notifyState, notifyScript, delivered, reserve, mustReserve, cancelReservation, reservations,
    reservationStatus, gone, locations, createLocation, locationId, locationBody, order, orders, runOrderJob, agencyState,
    agencyScript, agencyMode, agencyOrders, history, newHistory, setSubManager, done, ctx };
}

/** テストの本体を包む（例外が出たら X として 1 件だけ結果を出す） */
function main(name, fn) {
  fn().catch((e) => { console.log(JSON.stringify([{ id: "X", name: `${name} の実行`, pass: false, detail: String(e?.stack ?? e).slice(0, 800) }])); });
}

module.exports = { harness, main, assert, show, jst, addDays, sleep, is2xx, is4xx, pick, fill };
