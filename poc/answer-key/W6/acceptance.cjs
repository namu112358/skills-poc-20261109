// W6 の受け入れテスト（試行中は候補に見せない）。仕様は poc/tasks/wf-W6.md、採点は grading.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka）を前提にする。
// チェック名の先頭の [U1]〜[U8] は UI チェックリストの項目番号。1 項目のチェックがすべて通れば、その項目は「不具合なし」。
// 実装の方式（API を fetch で呼ぶ / Server Actions など）に依存しないよう、通信の失敗は「ページからの GET 以外のリクエスト」を
// 止める・500 を返すことで再現する。
const { chromium } = require("playwright");

(async () => {
const base = process.argv[2];
const results = [];
const browser = await chromium.launch();

async function login(userId, viewport = { width: 1280, height: 900 }) {
  const ctx = await browser.newContext({ baseURL: base, viewport });
  ctx.setDefaultTimeout(8000);
  const res = await ctx.request.post("/api/login", { data: { userId, password: "password" } });
  if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
  return ctx;
}
async function check(name, fn) {
  let ctxs = [];
  try {
    const detail = await fn((c) => (ctxs.push(c), c));
    results.push({ name, pass: true, detail: detail ?? "" });
  } catch (e) {
    results.push({ name, pass: false, detail: String(e.message ?? e).slice(0, 300) });
  } finally {
    for (const c of ctxs) await c.close().catch(() => {});
  }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }
async function until(fn, msg, timeout = 6000) {
  const end = Date.now() + timeout;
  let last;
  while (Date.now() < end) {
    try { last = await fn(); if (last) return last; } catch (e) { last = e.message; }
    await new Promise((r) => setTimeout(r, 200));
  }
  throw new Error(`${msg}（最後の値: ${String(last).slice(0, 150)}）`);
}
async function apiTasks(ctx) {
  const r = await ctx.request.get("/api/tasks");
  return (await r.json()).tasks;
}
async function open(ctx, path = "/my-tasks") {
  const page = await ctx.newPage();
  await page.goto(path, { waitUntil: "networkidle" });
  return page;
}
const items = (page) => page.locator('[data-testid="my-task"]');
const form = (page) => page.locator('form[aria-label="タスクの追加"]');
const field = (page, name) => form(page).locator(`[name="${name}"]`);
const addButton = (page) => form(page).getByRole("button", { name: "追加する" });
const alertWith = (page, text) => page.getByRole("alert").filter({ hasText: text });
async function itemTexts(page) { return items(page).allInnerTexts(); }
async function itemFor(page, title) { return items(page).filter({ hasText: title }).first(); }
// ページからの GET 以外のリクエスト（API の POST / PATCH、Server Actions）を止める / 500 を返す
async function failWrites(page, mode) {
  await page.route("**/*", (route) => {
    if (route.request().method() === "GET") return route.continue();
    if (mode === "abort") return route.abort("failed");
    return route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: "サーバーエラー" }) });
  });
}

// ---- U8 導線・アクセシビリティ（未ログイン）----
await check("[U8] 未ログインで /my-tasks を開くと /login に移動する", async (keep) => {
  const ctx = keep(await browser.newContext({ baseURL: base }));
  ctx.setDefaultTimeout(8000);
  const page = await ctx.newPage();
  await page.goto("/my-tasks");
  assert(new URL(page.url()).pathname === "/login", `url=${page.url()}`);
});

// ---- U1 表示内容と並び順（sato の初期データ: ID 1 done 11-02, ID 3 in_progress 11-14, ID 6 todo 11-25）----
await check("[U1] 自分の担当タスクだけを期限の近い順に表示する", async (keep) => {
  const page = await open(keep(await login("sato")));
  await until(async () => (await items(page).count()) === 3, "my-task が 3 件にならない");
  const texts = await itemTexts(page);
  const order = ["要件定義書のレビュー", "API 設計", "E2E テストの追加"];
  order.forEach((t, i) => assert(texts[i].includes(t), `${i + 1} 件目が「${t}」ではない: ${JSON.stringify(texts)}`));
  for (const other of ["ログイン画面のデザイン", "DB スキーマ作成", "CI の整備", "リリースノート作成"]) {
    assert(!(await page.content()).includes(other), `ほかの人のタスクが表示されている: ${other}`);
  }
  assert(texts[1].includes("2026-11-14") && texts[2].includes("2026-11-25"), `期限が表示されていない: ${JSON.stringify(texts)}`);
});

await check("[U1] タイトルは詳細画面へのリンク、ステータスは選択欄に現在の値が出る", async (keep) => {
  const page = await open(keep(await login("sato")));
  const item = await itemFor(page, "API 設計");
  const href = await item.getByRole("link", { name: "API 設計" }).getAttribute("href");
  assert(href && new URL(href, base).pathname === "/tasks/3", `href=${href}`);
  const values = [];
  for (const [title, status] of [["要件定義書のレビュー", "done"], ["API 設計", "in_progress"], ["E2E テストの追加", "todo"]]) {
    const v = await (await itemFor(page, title)).locator("select").first().inputValue();
    values.push(v);
    assert(v === status, `「${title}」の選択欄の値が ${status} ではない: ${v}`);
  }
  const labels = await (await itemFor(page, "API 設計")).locator("select option").allInnerTexts();
  assert(["未着手", "進行中", "完了"].every((l) => labels.some((x) => x.trim() === l)), `選択肢: ${JSON.stringify(labels)}`);
});

// ---- U3 追加の成功 ----
await check("[U3] 追加すると一覧に表示され、入力欄が空に戻る（担当は自分・未着手）", async (keep) => {
  const ctx = keep(await login("sato"));
  const page = await open(ctx);
  await field(page, "title").fill("追加の確認A");
  await field(page, "dueDate").fill("2026-11-20");
  await addButton(page).click();
  await until(async () => (await itemTexts(page)).some((t) => t.includes("追加の確認A")), "追加したタスクが一覧に出ない");
  await until(async () => (await field(page, "title").inputValue()) === "" && (await field(page, "dueDate").inputValue()) === "", "入力欄が空に戻らない");
  const t = (await apiTasks(ctx)).find((x) => x.title === "追加の確認A");
  assert(t && t.assignee === "sato" && t.status === "todo" && t.dueDate === "2026-11-20", `登録内容: ${JSON.stringify(t)}`);
  // 再読み込み後も期限の順に並ぶ（11-14 の「API 設計」と 11-25 の「E2E テストの追加」の間）
  await page.reload({ waitUntil: "networkidle" });
  const texts = await itemTexts(page);
  const i = texts.findIndex((x) => x.includes("追加の確認A"));
  assert(i > 0 && texts[i - 1].includes("API 設計") && texts[i + 1]?.includes("E2E テストの追加"), `並び: ${JSON.stringify(texts)}`);
});

await check("[U3] 送信中は「追加する」を押せず、二重に登録されない", async (keep) => {
  const ctx = keep(await login("sato"));
  const page = await open(ctx);
  await page.route("**/*", async (route) => {
    if (route.request().method() !== "GET") await new Promise((r) => setTimeout(r, 1500));
    return route.continue();
  });
  await field(page, "title").fill("二重送信の確認");
  await field(page, "dueDate").fill("2026-12-03");
  await addButton(page).click();
  await page.waitForTimeout(300);
  const disabled = await addButton(page).isDisabled();
  await addButton(page).click({ force: true, timeout: 1000 }).catch(() => {});
  await field(page, "title").press("Enter").catch(() => {});
  await page.waitForTimeout(2500);
  await page.unroute("**/*");
  const n = (await apiTasks(ctx)).filter((x) => x.title === "二重送信の確認").length;
  assert(disabled, "送信中にボタンが無効になっていない");
  assert(n === 1, `登録された件数: ${n}`);
});

// ---- U4 入力エラー ----
await check("[U4] タイトルが空白だけのとき理由を role=alert で表示し、入力を残す。直して追加するとエラーが消える", async (keep) => {
  const ctx = keep(await login("sato"));
  const page = await open(ctx);
  await field(page, "title").fill("   ");
  await field(page, "dueDate").fill("2026-12-01");
  await addButton(page).click();
  await until(async () => (await alertWith(page, "タイトルは 1〜200 文字で入力してください").count()) > 0, "エラーの理由が role=alert で表示されない");
  assert((await field(page, "dueDate").inputValue()) === "2026-12-01", "期限の入力が消えた");
  assert((await field(page, "title").inputValue()) === "   ", "タイトルの入力が消えた");
  await field(page, "title").fill("入力エラーの後");
  await addButton(page).click();
  await until(async () => (await itemTexts(page)).some((t) => t.includes("入力エラーの後")), "直した後に追加できない");
  await until(async () => (await alertWith(page, "タイトルは").count()) === 0, "エラーの表示が消えない");
});

// ---- U5 通信エラー・サーバーエラー ----
for (const mode of ["abort", "500"]) {
  await check(`[U5] 追加で${mode === "abort" ? "通信に失敗" : "サーバーが 500 を返"}したとき、メッセージを表示し入力を残す`, async (keep) => {
    const ctx = keep(await login("sato"));
    const page = await open(ctx);
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await failWrites(page, mode);
    await field(page, "title").fill(`失敗の確認 ${mode}`);
    await field(page, "dueDate").fill("2026-12-02");
    await addButton(page).click();
    await until(async () => (await alertWith(page, "追加できませんでした").count()) > 0, "「追加できませんでした」が role=alert で表示されない");
    assert((await field(page, "title").inputValue()) === `失敗の確認 ${mode}`, "タイトルの入力が消えた");
    assert((await field(page, "dueDate").inputValue()) === "2026-12-02", "期限の入力が消えた");
    assert((await page.locator("h1").filter({ hasText: "マイタスク" }).count()) === 1, "画面が表示されなくなった");
  });
}

// ---- U6 ステータスの変更（suzuki: ID 2 in_progress 11-12, ID 5 todo 11-20）----
await check("[U6] 選択欄でステータスを選ぶと保存され、再読み込み後も新しい値", async (keep) => {
  const ctx = keep(await login("suzuki"));
  const page = await open(ctx);
  await (await itemFor(page, "ログイン画面のデザイン")).locator("select").first().selectOption("done");
  await until(async () => (await apiTasks(ctx)).find((t) => t.id === 2)?.status === "done", "保存されない（API で done にならない）");
  await page.reload({ waitUntil: "networkidle" });
  const v = await (await itemFor(page, "ログイン画面のデザイン")).locator("select").first().inputValue();
  assert(v === "done", `再読み込み後の値: ${v}`);
});

await check("[U6] 保存に失敗すると role=alert で知らせ、選択欄を元の値に戻す", async (keep) => {
  const ctx = keep(await login("suzuki"));
  const page = await open(ctx);
  await failWrites(page, "abort");
  const sel = (await itemFor(page, "CI の整備")).locator("select").first();
  await sel.selectOption("in_progress");
  await until(async () => (await alertWith(page, "ステータスを変更できませんでした").count()) > 0, "「ステータスを変更できませんでした」が表示されない");
  await until(async () => (await sel.inputValue()) === "todo", "選択欄が元の値（未着手）に戻らない");
  await page.unroute("**/*");
  assert((await apiTasks(ctx)).find((t) => t.id === 5)?.status === "todo", "失敗したはずの変更が保存されている");
});

// ---- U2 空状態（tanaka の担当 ID 4・7 を suzuki に付け替えて 0 件にする）----
await check("[U2] 担当タスクが無いとき「担当しているタスクはありません。」とフォームを表示し、追加すると消える", async (keep) => {
  const ctx = keep(await login("tanaka"));
  for (const id of [4, 7]) {
    const r = await ctx.request.patch(`/api/tasks/${id}`, { data: { assignee: "suzuki" } });
    assert(r.status() === 200, `付け替え ${id} -> ${r.status()}`);
  }
  const page = await open(ctx);
  assert((await page.getByText("担当しているタスクはありません。").count()) > 0, "空状態の文言が無い");
  assert((await items(page).count()) === 0, "my-task がある");
  assert(await form(page).isVisible(), "追加フォームが表示されていない");
  await field(page, "title").fill("空からの追加");
  await field(page, "dueDate").fill("2026-12-05");
  await addButton(page).click();
  await until(async () => (await items(page).count()) === 1, "追加したタスクが表示されない");
  await until(async () => (await page.getByText("担当しているタスクはありません。").count()) === 0, "空状態の文言が消えない");
});

// ---- U7 レスポンシブ ----
async function layoutProblems(page, width) {
  const problems = [];
  const sw = await page.evaluate(() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth));
  if (sw > width + 1) problems.push(`横スクロールあり（scrollWidth=${sw}）`);
  const inView = async (loc, label) => {
    if ((await loc.count()) === 0) return problems.push(`${label} が無い`);
    const b = await loc.first().boundingBox();
    if (!b || b.width === 0) return problems.push(`${label} が表示されていない`);
    if (b.x < -1 || b.x + b.width > width + 1) problems.push(`${label} が幅からはみ出す（x=${Math.round(b.x)}, w=${Math.round(b.width)}）`);
  };
  const n = await items(page).count();
  if (n === 0) problems.push("my-task が無い");
  for (let i = 0; i < n; i++) {
    const it = items(page).nth(i);
    await inView(it, `タスク ${i + 1}`);
    await inView(it.locator("a"), `タスク ${i + 1} のタイトル`);
    await inView(it.locator("select"), `タスク ${i + 1} のステータス`);
    await inView(it.getByText(/\d{4}-\d{2}-\d{2}/), `タスク ${i + 1} の期限`);
  }
  await inView(field(page, "title"), "タイトルの入力欄");
  await inView(field(page, "dueDate"), "期限の入力欄");
  await inView(addButton(page), "追加するボタン");
  return problems;
}
for (const width of [375, 1280]) {
  await check(`[U7] 幅 ${width}px で横スクロールせず、各タスクとフォームが幅に収まる`, async (keep) => {
    const ctx = keep(await login("sato", { width, height: 800 }));
    const page = await open(ctx);
    const problems = await layoutProblems(page, width);
    assert(problems.length === 0, problems.slice(0, 4).join(" / "));
  });
}

// ---- U8 導線・アクセシビリティ（ログイン中）----
await check("[U8] ヘッダーの「マイタスク」リンクからこの画面を開ける（見出し「マイタスク」）", async (keep) => {
  const page = await open(keep(await login("sato")), "/tasks");
  await page.getByRole("link", { name: "マイタスク", exact: true }).first().click();
  await page.waitForURL((u) => new URL(u).pathname === "/my-tasks", { timeout: 6000 });
  assert((await page.getByRole("heading", { level: 1, name: "マイタスク" }).count()) === 1, "h1「マイタスク」が無い");
});

await check("[U8] 入力欄と選択欄にラベルがある（タイトル・期限・ステータス）", async (keep) => {
  const page = await open(keep(await login("sato")));
  assert((await form(page).getByLabel("タイトル").count()) >= 1, "「タイトル」のラベルが入力欄に付いていない");
  assert((await form(page).getByLabel("期限").count()) >= 1, "「期限」のラベルが入力欄に付いていない");
  const n = await items(page).count();
  const named = await items(page).getByRole("combobox", { name: /ステータス/ }).count();
  assert(n > 0 && named === n, `ステータスのラベルが付いた選択欄 ${named} / ${n}`);
});

// ---- 既存の動作 ----
await check("[既存] タスク一覧・詳細画面が今までどおり表示される", async (keep) => {
  const page = await open(keep(await login("sato")), "/tasks");
  assert((await page.locator('[data-testid="task-row"]').count()) >= 7, "タスク一覧の行が足りない");
  await page.goto("/tasks/1", { waitUntil: "networkidle" });
  assert((await page.getByTestId("task-title").innerText()).includes("要件定義書のレビュー"), "詳細画面");
});

await browser.close();
console.log(JSON.stringify(results));
})().catch((e) => {
  console.log(JSON.stringify([{ name: "E2E 実行", pass: false, detail: String(e.message ?? e).slice(0, 500) }]));
});
