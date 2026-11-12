// W12 の採点用: 社内通知サービス（notify-api.md）の偽物。失敗を混ぜて、候補の外部呼び出しの堅牢さを動作で調べる。
// 使い方: node fake-notify.cjs <port> <token>
//   POST /v1/notifications  … 本物と同じ形。送り先ごとの「台本」（/__script）に従って応答する。台本が尽きたら 202。
//   POST /__script {recipient, actions:[...], replace?}  … 台本を足す（replace なら置き換える）。action: "ok" | {status:503} | {status:429, retryAfter:2}
//                                                | {status:400} | "hang"（応答しない） | "process_then_hang"（受け付けてから応答しない）
//   POST /__mode {all503: true|false}           … すべての要求に 503 を返す
//   GET  /__state                               … 受けた要求（requests）と、実際に届いたお知らせ（deliveries）
//   POST /__reset                               … 記録と台本を消す
// 届いたお知らせ: 202 を返した要求と process_then_hang の要求。Idempotency-Key が前に届いたものと同じなら、新しく届いたとは数えない。
// 応答しない要求は 90 秒で切る（候補がタイムアウトを持たないときに採点が止まらないように）。
"use strict";
const http = require("node:http");
const port = Number(process.argv[2]);
const token = process.argv[3];
let requests = [];
let deliveries = [];
let keys = new Map();
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

function deliver(rec) {
  if (rec.key && keys.has(rec.key)) return keys.get(rec.key);
  const id = `ntf_${++seq}`;
  deliveries.push({ id, t: Date.now(), recipient: rec.recipient, title: rec.title, body: rec.body, key: rec.key, category: rec.category });
  if (rec.key) keys.set(rec.key, id);
  return id;
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, "http://x");
  const raw = await readBody(req);
  if (url.pathname === "/__state") return send(res, 200, { requests, deliveries });
  if (url.pathname === "/__reset") {
    requests = []; deliveries = []; keys = new Map(); scripts = {}; all503 = false;
    return send(res, 200, {});
  }
  if (url.pathname === "/__script") {
    const b = JSON.parse(raw);
    if (b.replace) scripts[b.recipient] = [];
    (scripts[b.recipient] ??= []).push(...b.actions);
    return send(res, 200, {});
  }
  if (url.pathname === "/__mode") {
    all503 = !!JSON.parse(raw).all503;
    return send(res, 200, {});
  }
  if (req.method !== "POST" || url.pathname !== "/v1/notifications") return send(res, 404, { error: "not found" });
  const rec = {
    t: Date.now(), path: url.pathname, auth: req.headers["authorization"] ?? null,
    key: req.headers["idempotency-key"] ?? null, contentType: req.headers["content-type"] ?? null,
    raw: raw.slice(0, 3000), status: null, respondedAt: null, closedAt: null, action: null,
  };
  requests.push(rec);
  res.on("close", () => { rec.closedAt = Date.now(); });
  if (rec.auth !== `Bearer ${token}`) { rec.status = 401; rec.respondedAt = Date.now(); return send(res, 401, { error: "unauthorized" }); }
  let body;
  try { body = JSON.parse(raw); } catch { body = undefined; }
  if (!body || typeof body.recipient !== "string" || typeof body.title !== "string" || typeof body.body !== "string") {
    rec.status = 400; rec.respondedAt = Date.now();
    return send(res, 400, { error: "recipient, title, body are required" });
  }
  Object.assign(rec, { recipient: body.recipient, title: body.title, body: body.body, category: body.category ?? null });
  if (all503) { rec.status = 503; rec.respondedAt = Date.now(); return send(res, 503, { error: "maintenance" }); }
  const action = (scripts[body.recipient] ?? []).shift() ?? "ok";
  rec.action = action;
  if (action === "hang" || action === "process_then_hang") {
    if (action === "process_then_hang") rec.deliveredId = deliver(rec);
    setTimeout(() => {
      if (!res.writableEnded && !res.destroyed) { rec.status = 504; rec.respondedAt = Date.now(); send(res, 504, { error: "gateway timeout" }); }
    }, 90_000);
    return;
  }
  if (action !== "ok") {
    rec.status = action.status; rec.respondedAt = Date.now();
    const headers = action.retryAfter !== undefined ? { "retry-after": String(action.retryAfter) } : {};
    return send(res, action.status, { error: `status ${action.status}` }, headers);
  }
  const id = deliver(rec);
  rec.status = 202; rec.respondedAt = Date.now();
  send(res, 202, { id });
});
server.keepAliveTimeout = 1000;
server.listen(port, "127.0.0.1", () => console.log(`fake-notify listening ${port}`));
