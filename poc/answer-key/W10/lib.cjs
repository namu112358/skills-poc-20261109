// W10 の受け入れテスト・隠しテストの共通部分（試行中は候補に見せない）。
const { request } = require("playwright");

function harness(base) {
  const results = [];
  const contexts = [];
  async function login(userId) {
    const ctx = await request.newContext({ baseURL: base });
    contexts.push(ctx);
    const res = await ctx.post("/api/login", { data: { userId, password: "password" } });
    if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
    return ctx;
  }
  async function anon() {
    const ctx = await request.newContext({ baseURL: base });
    contexts.push(ctx);
    return ctx;
  }
  async function check(id, name, fn) {
    try {
      const detail = await fn();
      results.push({ id, name, pass: true, detail: detail ?? "" });
    } catch (e) {
      results.push({ id, name, pass: false, detail: String(e.message ?? e).slice(0, 400) });
    }
  }
  async function json(res) {
    try { return await res.json(); } catch { return undefined; }
  }
  async function call(ctx, method, path, body, raw) {
    const opts = {};
    if (raw !== undefined) opts.data = raw, opts.headers = { "content-type": "application/json" };
    else if (body !== undefined) opts.data = body;
    const res = await ctx.fetch(path, { method, ...opts });
    return { status: res.status(), json: await json(res) };
  }
  // 担当者 assignee・期限 dueDate のタスクを作り、ID を返す（作成は既存の API）
  async function newTask(ctx, dueDate, assignee = "sato") {
    const r = await call(ctx, "POST", "/api/tasks", { title: `W10 検証 ${Math.random().toString(36).slice(2, 8)}`, status: "todo", assignee, dueDate });
    if (r.status !== 201) throw new Error(`タスクを作成できない: ${r.status} ${JSON.stringify(r.json)}`);
    return r.json.task.id;
  }
  const ext = {
    list: (ctx, t) => call(ctx, "GET", `/api/tasks/${t}/extensions`),
    request: (ctx, t, body) => call(ctx, "POST", `/api/tasks/${t}/extensions`, body),
    raw: (ctx, t, raw) => call(ctx, "POST", `/api/tasks/${t}/extensions`, undefined, raw),
    approve: (ctx, t, e) => call(ctx, "POST", `/api/tasks/${t}/extensions/${e}/approve`),
    reject: (ctx, t, e) => call(ctx, "POST", `/api/tasks/${t}/extensions/${e}/reject`),
  };
  async function dueDate(ctx, t) {
    const r = await call(ctx, "GET", `/api/tasks/${t}`);
    return r.json?.task?.dueDate;
  }
  async function done() {
    for (const c of contexts) await c.dispose();
    console.log(JSON.stringify(results));
  }
  return { results, login, anon, check, call, newTask, ext, dueDate, done };
}

function assert(cond, msg) { if (!cond) throw new Error(msg); }
const show = (r) => `${r.status} ${JSON.stringify(r.json)?.slice(0, 200)}`;
// 拒否された（4xx。401・404 を除く必要がある項目は各テストで見る）
const rejected = (r) => r.status >= 400 && r.status < 500;

module.exports = { harness, assert, show, rejected };
