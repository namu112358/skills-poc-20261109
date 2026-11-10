// W18 の採点用: 校正機関の受付システム（agency-api.md）の偽物。失敗を混ぜて、発注の送り方を動作で調べる。
// 使い方: node fake-agency.cjs <port> <api-key>
//   POST /v1/orders  … 本物と同じ形。管理番号ごとの「台本」（/__script）に従って応答する。台本が尽きたら 201。
//   POST /__script {managementNo, actions:[...], replace?} … action: "ok" | {status:503} | {status:429, retryAfter:1} | {status:400}
//                                                     | "hang"（応答しない） | "process_then_hang"（受け付けてから応答しない）
//   POST /__mode {all503: true|false} … すべての発注に 503 を返す（止まっている）
//   GET  /__state … 受けた要求（requests）と、受け付けた発注（orders）
// 受け付けた発注: 201 を返した要求と process_then_hang の要求。Idempotency-Key か clientReference が前のものと同じなら、
// 新しい発注として数えない（Idempotency-Key は最初の結果を返し、clientReference だけが同じなら 409 duplicate を返す）。
// 応答しない要求は 90 秒で切る。返却予定日は、要求を受けた日（日本時間）の 14 日後。
"use strict";
const http = require("node:http");
const port = Number(process.argv[2]);
const apiKey = process.argv[3];
let requests = [];
let orders = [];
const byKey = new Map();
const byRef = new Map();
let scripts = {};
let all503 = false;
let seq = 0;

function send(res, status, body, headers = {}) {
  res.writeHead(status, { "content-type": "application/json", ...headers });
  res.end(JSON.stringify(body));
}
function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => resolve(data));
  });
}
function returnOn() {
  const jst = new Date(Date.now() + 9 * 3600_000 + 14 * 86_400_000);
  return jst.toISOString().slice(0, 10);
}
function accept(rec, body) {
  const order = { orderId: `AG-${String(++seq).padStart(5, "0")}`, status: "accepted", estimatedReturnOn: returnOn() };
  orders.push({ ...order, t: Date.now(), clientReference: body.clientReference, item: body.item, requestedBy: body.requestedBy, key: rec.key });
  if (rec.key) byKey.set(rec.key, order);
  byRef.set(body.clientReference, order);
  return order;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const raw = await readBody(req);
  if (url.pathname === "/__state") return send(res, 200, { requests, orders });
  if (url.pathname === "/__script") {
    const b = JSON.parse(raw);
    if (b.replace) scripts[b.managementNo] = [];
    (scripts[b.managementNo] ??= []).push(...b.actions);
    return send(res, 200, {});
  }
  if (url.pathname === "/__mode") {
    all503 = !!JSON.parse(raw).all503;
    return send(res, 200, {});
  }
  if (req.method !== "POST" || url.pathname !== "/v1/orders") return send(res, 404, { error: "not found" });
  const rec = { t: Date.now(), apiKey: req.headers["x-api-key"] ?? null, key: req.headers["idempotency-key"] ?? null,
    raw: raw.slice(0, 3000), status: null, action: null };
  requests.push(rec);
  if (rec.apiKey !== apiKey) { rec.status = 401; return send(res, 401, { error: "unauthorized" }); }
  let body;
  try { body = JSON.parse(raw); } catch { body = undefined; }
  const no = body?.item?.managementNo;
  if (!body || typeof body.clientReference !== "string" || !body.clientReference || typeof no !== "string") {
    rec.status = 400;
    return send(res, 400, { error: "clientReference and item.managementNo are required" });
  }
  Object.assign(rec, { managementNo: no, clientReference: body.clientReference, requestedBy: body.requestedBy ?? null });
  if (all503) { rec.status = 503; return send(res, 503, { error: "maintenance" }); }
  if (rec.key && byKey.has(rec.key)) { rec.status = 201; rec.action = "replay"; return send(res, 201, byKey.get(rec.key)); }
  if (byRef.has(body.clientReference)) {
    rec.status = 409; rec.action = "duplicate";
    return send(res, 409, { error: "duplicate", orderId: byRef.get(body.clientReference).orderId });
  }
  const action = (scripts[no] ?? []).shift() ?? "ok";
  rec.action = action;
  if (action === "hang" || action === "process_then_hang") {
    if (action === "process_then_hang") accept(rec, body);
    setTimeout(() => {
      if (!res.writableEnded && !res.destroyed) { rec.status = 504; send(res, 504, { error: "gateway timeout" }); }
    }, 90_000);
    return;
  }
  if (action !== "ok") {
    rec.status = action.status;
    const headers = action.retryAfter !== undefined ? { "retry-after": String(action.retryAfter) } : {};
    return send(res, action.status, { error: `status ${action.status}` }, headers);
  }
  rec.status = 201;
  send(res, 201, accept(rec, body));
});
server.keepAliveTimeout = 1000;
server.listen(port, "127.0.0.1", () => console.log(`fake-agency listening ${port}`));
