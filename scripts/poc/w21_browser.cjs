// W21a・W21b の隠しの検査・アクセシビリティの自動検査・スクリーンショット（docs/poc/tasks/wf-W21-design.md の「採点」）。
// 使い方: node scripts/poc/w21_browser.cjs <a|b|d|e|f> <起動済みのアプリの URL> <スクリーンショットの出力先の接頭辞>
//   結果を JSON で標準出力に書く。axe-core は採点側だけで使う（POC_AXE に axe.min.js のパス。npm i axe-core@4.10.3 で入れたもの）。
const { chromium } = require("playwright");
const fs = require("fs");

const [kind, base, shotPrefix] = process.argv.slice(2);
const AXE = fs.readFileSync(process.env.POC_AXE, "utf8");
const SEED = [
  { id: 1, title: "要件定義書のレビュー", status: "done", assignee: "sato", name: "佐藤", due: "2026-11-02" },
  { id: 2, title: "ログイン画面のデザイン", status: "in_progress", assignee: "suzuki", name: "鈴木", due: "2026-11-12" },
  { id: 3, title: "API 設計", status: "in_progress", assignee: "sato", name: "佐藤", due: "2026-11-14" },
  { id: 4, title: "DB スキーマ作成", status: "todo", assignee: "tanaka", name: "田中", due: "2026-11-18" },
  { id: 5, title: "CI の整備", status: "todo", assignee: "suzuki", name: "鈴木", due: "2026-11-20" },
  { id: 6, title: "E2E テストの追加", status: "todo", assignee: "sato", name: "佐藤", due: "2026-11-25" },
  { id: 7, title: "リリースノート作成", status: "done", assignee: "tanaka", name: "田中", due: "2026-11-05" },
];
// 期限は形式を変えてもよい（2026-11-14・2026/11/14・11/14・11月14日）
function dueShown(text, due) {
  const [y, m, d] = due.split("-");
  const mi = String(Number(m)), di = String(Number(d));
  return [due, `${y}/${m}/${d}`, `${mi}/${di}`, `${m}/${d}`, `${mi}月${di}日`].some((s) => text.includes(s));
}
const norm = (s) => s.replace(/\s+/g, " ");

async function login(context) {
  const res = await context.request.post(base + "/api/login", { data: { userId: "sato", password: "password" } });
  return res.ok();
}
async function overflow(page) {
  return page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
}
async function axe(page) {
  await page.addScriptTag({ content: AXE });
  const r = await page.evaluate(async () => {
    const res = await window.axe.run(document, { resultTypes: ["violations"] });
    return res.violations.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length }));
  });
  return r;
}

(async () => {
  const browser = await chromium.launch();
  const out = { kind, checks: {}, axe: {}, overflow: {}, errors: [] };
  const TARGET = { a: "/", b: "/tasks", d: "/lp", e: "/dashboard", f: "/tasks/new" };
  const NEEDS_LOGIN = { a: false, b: true, d: false, e: true, f: true };
  const target = TARGET[kind];
  for (const [label, width] of [["desktop", 1280], ["mobile", 375]]) {
    const context = await browser.newContext({ viewport: { width, height: 900 }, deviceScaleFactor: 1, locale: "ja-JP" });
    if (NEEDS_LOGIN[kind]) await login(context);
    const page = await context.newPage();
    try {
      await page.goto(base + target, { waitUntil: "networkidle", timeout: 30000 });
      await page.waitForTimeout(500);
      out.overflow[label] = await overflow(page);
      out.axe[label] = await axe(page);
      await page.screenshot({ path: `${shotPrefix}-${label}.jpg`, fullPage: true, type: "jpeg", quality: 85 });
    } catch (e) {
      out.errors.push(`${label}: ${e.message.slice(0, 200)}`);
    }
    await context.close();
  }
  out.checks.no_overflow_375 = out.overflow.mobile !== undefined && out.overflow.mobile <= 1;

  if (kind === "a") {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    try {
      await page.goto(base + "/", { waitUntil: "networkidle" });
      const path = new URL(page.url()).pathname;
      const h1 = await page.locator("h1").first().isVisible().catch(() => false);
      const loginLinks = await page.locator('a[href*="/login"]').count();
      out.checks.landing_shown = path === "/" && h1;
      out.checks.link_to_login = path === "/" && loginLinks > 0;
      // ログイン画面へのリンクをたどれる
      if (loginLinks > 0) {
        // Next.js の Link は画面内で移動するので、読み込みの完了ではなく URL の変化を待つ（2026-11-11 採点の誤りを直した）
        await page.locator('a[href*="/login"]').first().click();
        await page.waitForURL((u) => u.pathname === "/login", { timeout: 10000 }).catch(() => {});
        out.checks.link_to_login = out.checks.link_to_login && new URL(page.url()).pathname === "/login";
      }
    } catch (e) {
      out.errors.push("landing: " + e.message.slice(0, 200));
    }
    await ctx.close();
    // ログインできる（/login の画面から）と、ログイン済みは / → /tasks
    const ctx2 = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const p2 = await ctx2.newPage();
    try {
      await p2.goto(base + "/login", { waitUntil: "networkidle" });
      await p2.locator('input[name="userId"]').fill("sato");
      await p2.locator('input[name="password"]').fill("password");
      await Promise.all([p2.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 15000 }), p2.locator('input[name="password"]').press("Enter")]);
      out.checks.login_works = true;
      await p2.goto(base + "/", { waitUntil: "networkidle" });
      out.checks.logged_in_redirect = new URL(p2.url()).pathname === "/tasks";
    } catch (e) {
      out.checks.login_works = out.checks.login_works || false;
      out.checks.logged_in_redirect = false;
      out.errors.push("login: " + e.message.slice(0, 200));
    }
    await ctx2.close();
  } else if (kind === "d") {
    // SaaS の LP: 未ログインで /lp に h1 と料金（600 円）が出て、申し込みからログイン画面へ行ける
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    const page = await ctx.newPage();
    try {
      await page.goto(base + "/lp", { waitUntil: "networkidle" });
      const text = norm(await page.locator("body").innerText());
      out.checks.page_shown = new URL(page.url()).pathname === "/lp" && (await page.locator("h1").first().isVisible().catch(() => false));
      out.checks.pricing = /600/.test(text) && text.includes("フリー") && text.includes("ビジネス");
      out.checks.faq = /よくある(ご)?質問|FAQ/i.test(text);
      const n = await page.locator('a[href*="/login"]').count();
      out.checks.cta_to_login = n > 0;
      if (n > 0) {
        await page.locator('a[href*="/login"]').first().click();
        await page.waitForURL((u) => u.pathname === "/login", { timeout: 10000 }).catch(() => {});
        out.checks.cta_to_login = new URL(page.url()).pathname === "/login";
      }
    } catch (e) {
      out.errors.push("lp: " + e.message.slice(0, 200));
    }
    await ctx.close();
  } else if (kind === "e") {
    // ダッシュボード: 未ログインは /login へ。ログイン後、ステータスの名前と件数（未着手 3・進行中 2・完了 2）、担当者の名前が出る
    const c0 = await browser.newContext();
    const p0 = await c0.newPage();
    try {
      await p0.goto(base + "/dashboard", { waitUntil: "networkidle" });
      out.checks.requires_login = new URL(p0.url()).pathname.startsWith("/login");
    } catch (e) { out.errors.push("dash-anon: " + e.message.slice(0, 200)); }
    await c0.close();
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await login(ctx);
    const page = await ctx.newPage();
    try {
      await page.goto(base + "/dashboard", { waitUntil: "networkidle" });
      const text = norm(await page.locator("body").innerText());
      out.checks.page_shown = new URL(page.url()).pathname === "/dashboard" && (await page.locator("h1").first().isVisible().catch(() => false));
      out.checks.status_counts = ["未着手", "進行中", "完了"].every((s) => text.includes(s)) && /3/.test(text) && /2/.test(text);
      out.checks.assignees = ["佐藤", "鈴木", "田中"].every((n) => text.includes(n)) || ["sato", "suzuki", "tanaka"].every((n) => text.includes(n));
      await page.goto(base + "/tasks", { waitUntil: "networkidle" });
      out.checks.header_link = (await page.locator('a[href="/dashboard"], a[href^="/dashboard?"]').count()) > 0;
    } catch (e) {
      out.errors.push("dash: " + e.message.slice(0, 200));
    }
    await ctx.close();
  } else if (kind === "f") {
    // 登録画面: 未ログインは /login へ。ラベルで入力して登録すると /tasks に戻り、一覧に出る。空のタイトルでは登録されずエラーが出る
    const c0 = await browser.newContext();
    const p0 = await c0.newPage();
    try {
      await p0.goto(base + "/tasks/new", { waitUntil: "networkidle" });
      out.checks.requires_login = new URL(p0.url()).pathname.startsWith("/login");
    } catch (e) { out.errors.push("new-anon: " + e.message.slice(0, 200)); }
    await c0.close();
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await login(ctx);
    const page = await ctx.newPage();
    const title = "採点用の登録テスト " + Date.now();
    try {
      await page.goto(base + "/tasks", { waitUntil: "networkidle" });
      out.checks.link_from_list = (await page.locator('a[href="/tasks/new"]').count()) > 0;
      await page.goto(base + "/tasks/new", { waitUntil: "networkidle" });
      const submit = page.locator('form button[type="submit"], form button:not([type]), form input[type="submit"]').last();
      // 空のまま送ると、登録されずにエラーが出る（ブラウザの required による止め方も可）
      await submit.click().catch(() => {});
      await page.waitForTimeout(800);
      const stayed = new URL(page.url()).pathname === "/tasks/new";
      const msg = (await page.locator('[role="alert"], [aria-invalid="true"], :invalid').count()) > 0;
      out.checks.error_on_empty = stayed && msg;
      await page.getByLabel(/タイトル/).first().fill(title);
      const due = page.getByLabel(/期限/).first();
      await due.fill("2026-12-01");
      const who = page.getByLabel(/担当/).first();
      if ((await who.count()) && (await who.evaluate((el) => el.tagName)) === "SELECT") {
        await who.selectOption({ value: "tanaka" }).catch(() => who.selectOption({ label: "田中" }).catch(() => {}));
      } else if (await who.count()) {
        await who.fill("tanaka").catch(() => {});
      }
      await Promise.all([page.waitForURL((u) => u.pathname === "/tasks", { timeout: 15000 }), submit.click()]);
      const text = norm(await page.locator("body").innerText());
      out.checks.create_works = text.includes(title);
    } catch (e) {
      out.checks.create_works = false;
      out.errors.push("new: " + e.message.slice(0, 200));
    }
    await ctx.close();
  } else {
    const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
    await login(ctx);
    const page = await ctx.newPage();
    try {
      await page.goto(base + "/tasks", { waitUntil: "networkidle" });
      const text = norm(await page.locator("body").innerText());
      const hrefs = await page.locator("a[href]").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
      out.checks.all_tasks_linked = SEED.every((t) => text.includes(t.title) && hrefs.some((h) => new RegExp(`/tasks/${t.id}(?:$|[?#/])`).test(h)));
      out.checks.assignee_and_due = SEED.every((t) => dueShown(text, t.due)) && SEED.every((t) => text.includes(t.name) || text.includes(t.assignee));
      // 絞り込みの操作: 「完了」を選べる選択欄・ボタン・リンク・ラジオのどれか
      const ctl =
        (await page.locator("select option", { hasText: "完了" }).count()) +
        (await page.locator('a[href*="status=done"]').count()) +
        (await page.getByRole("button", { name: /完了/ }).count()) +
        (await page.getByRole("radio", { name: /完了/ }).count()) +
        (await page.getByRole("tab", { name: /完了/ }).count());
      out.checks.filter_control = ctl > 0;
      await page.goto(base + "/tasks?status=done", { waitUntil: "networkidle" });
      const t2 = norm(await page.locator("main").first().innerText().catch(() => page.locator("body").innerText()));
      out.checks.filter_done = SEED.every((t) => (t.status === "done") === t2.includes(t.title));
    } catch (e) {
      out.errors.push("tasks: " + e.message.slice(0, 200));
    }
    await ctx.close();
  }
  await browser.close();
  process.stdout.write(JSON.stringify(out));
})();
