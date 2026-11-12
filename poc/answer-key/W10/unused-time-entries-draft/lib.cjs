// W10 の検査スクリプト（acceptance.cjs・hidden.cjs）の共通部分。試行中は候補に見せない。
// サーバーは fake-clock.cjs で時計をずらして起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka、記録なし）を前提にする。
const { chromium } = require("playwright");

const FAKE_NOW = Date.parse(process.env.POC_FAKE_NOW || "2026-11-09T15:30:00.000Z");
const JST = 9 * 60 * 60 * 1000;
const dateOf = (ms) => new Date(ms).toISOString().slice(0, 10);
// サーバーの「今」（日本時間 2026-11-10 00:30 ごろ。UTC ではまだ 11/09）
const jstToday = dateOf(FAKE_NOW + JST);
const jstTomorrow = dateOf(FAKE_NOW + JST + 24 * 60 * 60 * 1000);
const utcToday = dateOf(FAKE_NOW);

async function setup(base) {
  const results = [];
  const browser = await chromium.launch();
  async function login(userId) {
    const ctx = await browser.newContext({ baseURL: base });
    const res = await ctx.request.post("/api/login", { data: { userId, password: "password" } });
    if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
    return ctx;
  }
  async function check(name, fn) {
    try {
      const detail = await fn();
      results.push({ name, pass: true, detail: detail ?? "" });
    } catch (e) {
      results.push({ name, pass: false, detail: String(e.message ?? e).slice(0, 300) });
    }
  }
  return { results, browser, login, check, anon: await browser.newContext({ baseURL: base }) };
}

function assert(cond, msg) {
  if (!cond) throw new Error(msg);
}
async function json(res) {
  try {
    return await res.json();
  } catch {
    return undefined;
  }
}
const path = (taskId) => `/api/tasks/${taskId}/time-entries`;
async function post(ctx, taskId, body) {
  const res = await ctx.request.post(path(taskId), { data: body });
  return { status: res.status(), json: await json(res) };
}
async function list(ctx, taskId) {
  const res = await ctx.request.get(path(taskId));
  return { status: res.status(), json: await json(res) };
}
async function del(ctx, taskId, entryId) {
  const res = await ctx.request.delete(`${path(taskId)}/${entryId}`);
  return res.status();
}
/** 記録して ID を返す（失敗したら例外。前提の準備に使う） */
async function mustPost(ctx, taskId, body) {
  const r = await post(ctx, taskId, body);
  const id = r.json?.entry?.id;
  assert(r.status === 201 && Number.isInteger(id), `前提の記録に失敗: ${r.status} ${JSON.stringify(r.json)}`);
  return r.json.entry;
}
/** 空白を除いた文字列（「1 時間 30 分」と「1時間30分」を同じに扱う） */
const squash = (s) => String(s ?? "").replace(/\s+/g, "");
const form = (page) => page.locator('form[aria-label="作業時間"]');
// Next.js が自動で入れるルート通知（next-route-announcer）も role=alert を持つため、文言のある要素だけを見る
const alertOf = (page) => page.locator('[role="alert"]').filter({ hasText: /\S/ }).first();

module.exports = {
  FAKE_NOW, jstToday, jstTomorrow, utcToday, setup, assert, json, post, list, del, mustPost, squash, form, alertOf,
};
