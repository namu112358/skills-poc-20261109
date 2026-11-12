// W7 の受け入れテスト・落とし穴の判定で共通に使う処理（試行中は候補に見せない）。
const { chromium } = require("playwright");

async function setup(base) {
  // 画面の日時がブラウザの時刻設定に頼っていないかを確かめるため、ブラウザのタイムゾーンは UTC にする
  const browser = await chromium.launch();
  const results = [];
  async function login(userId) {
    const ctx = await browser.newContext({ baseURL: base, timezoneId: "UTC" });
    const res = await ctx.request.post("/api/login", { data: { userId, password: "password" } });
    if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
    return ctx;
  }
  async function anon() {
    return browser.newContext({ baseURL: base, timezoneId: "UTC" });
  }
  async function check(name, fn) {
    try {
      const detail = await fn();
      results.push({ name, pass: true, detail: detail ?? "" });
    } catch (e) {
      results.push({ name, pass: false, detail: String(e.message ?? e).slice(0, 300) });
    }
  }
  return { browser, results, login, anon, check };
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

/** 詳細画面の、指定した要素（無ければ main 全体）の文字列。 */
async function pageText(ctx, path, selector) {
  const page = await ctx.newPage();
  await page.goto(path);
  const el = page.locator(selector);
  const n = await el.count();
  const text = n > 0 ? (await el.allInnerTexts()).join("\n") : await page.locator("body").innerText();
  const status = await page.evaluate(() => document.title);
  await page.close();
  return { found: n, text, status };
}

module.exports = { setup, assert, json, pageText };
