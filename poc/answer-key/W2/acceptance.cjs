// W2 の受け入れテスト（試行中は候補に見せない）。仕様は poc/tasks/wf-W2.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka、コメントなし）を前提にする。
// 各チェックは別々のタスクを使い、前のチェックの結果に依存しないようにしている。
const { chromium } = require("playwright");

(async () => {

const base = process.argv[2];
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
function assert(cond, msg) { if (!cond) throw new Error(msg); }
async function json(res) {
  try { return await res.json(); } catch { return undefined; }
}
async function post(ctx, taskId, body) {
  const res = await ctx.request.post(`/api/tasks/${taskId}/comments`, { data: body });
  return { status: res.status(), json: await json(res) };
}
async function list(ctx, taskId) {
  const res = await ctx.request.get(`/api/tasks/${taskId}/comments`);
  return { status: res.status(), json: await json(res) };
}

const anon = await browser.newContext({ baseURL: base });
const sato = await login("sato");
const suzuki = await login("suzuki");

// ---- API ----
await check("API: 未ログインは 401（一覧・投稿・削除）", async () => {
  const g = await anon.request.get("/api/tasks/1/comments");
  const p = await anon.request.post("/api/tasks/1/comments", { data: { body: "x" } });
  const d = await anon.request.delete("/api/tasks/1/comments/1");
  assert(g.status() === 401 && p.status() === 401 && d.status() === 401, `get=${g.status()} post=${p.status()} delete=${d.status()}`);
});

await check("API: コメントが無いタスクは 200 で空配列", async () => {
  const r = await list(sato, 1);
  assert(r.status === 200 && Array.isArray(r.json?.comments) && r.json.comments.length === 0, `got ${r.status} ${JSON.stringify(r.json)}`);
});

await check("API: 投稿すると 201 で指定どおりの形のコメントを返す（本文は前後の空白を除く）", async () => {
  const r = await post(sato, 1, { body: "  最初のコメント  " });
  const c = r.json?.comment;
  assert(r.status === 201 && c, `got ${r.status} ${JSON.stringify(r.json)}`);
  assert(Number.isInteger(c.id), `id=${JSON.stringify(c.id)}`);
  assert(c.taskId === 1 && c.author === "sato" && c.authorName === "佐藤" && c.body === "最初のコメント", JSON.stringify(c));
  assert(typeof c.createdAt === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(c.createdAt), `createdAt=${c.createdAt}`);
  assert(Math.abs(Date.parse(c.createdAt) - Date.now()) < 10 * 60 * 1000, `createdAt が現在時刻から離れている: ${c.createdAt}`);
});

await check("API: 投稿者はログイン中のユーザー（本文の author 指定は無視）", async () => {
  const r = await post(sato, 2, { body: "なりすまし", author: "tanaka", authorName: "田中" });
  assert(r.status === 201 && r.json?.comment?.author === "sato" && r.json.comment.authorName === "佐藤", `got ${r.status} ${JSON.stringify(r.json)}`);
});

await check("API: 一覧は古い順で、そのタスクのコメントだけを返す", async () => {
  for (const body of ["一番目", "二番目", "三番目"]) await post(suzuki, 3, { body });
  await post(suzuki, 4, { body: "別のタスク" });
  const r = await list(sato, 3);
  const bodies = (r.json?.comments ?? []).map((c) => c.body);
  assert(r.status === 200 && JSON.stringify(bodies) === JSON.stringify(["一番目", "二番目", "三番目"]), `got ${r.status} ${JSON.stringify(bodies)}`);
  const c = r.json.comments[0];
  assert(c.taskId === 3 && c.author === "suzuki" && c.authorName === "鈴木", JSON.stringify(c));
});

await check("API: 本文の検証（空・空白だけ・1001 文字・無し・文字列以外・JSON 以外は 400、1000 文字は 201）", async () => {
  const bad = [];
  for (const [label, body] of [["空", { body: "" }], ["空白だけ", { body: "  \n " }], ["1001 文字", { body: "あ".repeat(1001) }],
    ["本文なし", {}], ["数値", { body: 123 }]]) {
    const r = await post(sato, 5, body);
    if (r.status !== 400 || typeof r.json?.error !== "string") bad.push(`${label}=${r.status}`);
  }
  const raw = await sato.request.post("/api/tasks/5/comments", { headers: { "content-type": "application/json" }, data: "{not json" });
  if (raw.status() !== 400) bad.push(`JSON 以外=${raw.status()}`);
  const ok = await post(sato, 5, { body: "あ".repeat(1000) });
  if (ok.status !== 201) bad.push(`1000 文字=${ok.status}`);
  const after = await list(sato, 5);
  if ((after.json?.comments ?? []).length !== 1) bad.push(`保存件数=${(after.json?.comments ?? []).length}（1 件のはず）`);
  assert(bad.length === 0, bad.join(", "));
});

await check("API: 存在しないタスク・不正な ID は 404（エラーは { error } の JSON）", async () => {
  // Next.js 既定の 404（HTML）では通らないよう、本文が仕様どおりの JSON かも確かめる
  const del = await sato.request.delete("/api/tasks/999/comments/1");
  const rs = [await list(sato, 999), await post(sato, 999, { body: "x" }), await list(sato, "abc"),
    { status: del.status(), json: await json(del) }];
  const got = rs.map((r) => `${r.status}:${typeof r.json?.error}`);
  assert(rs.every((r) => r.status === 404 && typeof r.json?.error === "string"), `got ${JSON.stringify(got)}`);
});

await check("API: 他人のコメントは削除できず 403、本人は 204 で削除でき、2 回目は 404", async () => {
  const id = (await post(sato, 6, { body: "削除テスト" })).json?.comment?.id;
  assert(Number.isInteger(id), "投稿に失敗");
  const other = await suzuki.request.delete(`/api/tasks/6/comments/${id}`);
  const still = (await list(sato, 6)).json?.comments?.length;
  const own = await sato.request.delete(`/api/tasks/6/comments/${id}`);
  const gone = (await list(sato, 6)).json?.comments?.length;
  const again = await sato.request.delete(`/api/tasks/6/comments/${id}`);
  assert(other.status() === 403 && still === 1 && own.status() === 204 && gone === 0 && again.status() === 404,
    `other=${other.status()} still=${still} own=${own.status()} gone=${gone} again=${again.status()}`);
});

await check("API: 別のタスクの URL で削除しようとすると 404（コメントは残る）", async () => {
  const id = (await post(sato, 7, { body: "タスク 7 のコメント" })).json?.comment?.id;
  assert(Number.isInteger(id), "投稿に失敗");
  const wrong = await sato.request.delete(`/api/tasks/1/comments/${id}`);
  const still = (await list(sato, 7)).json?.comments?.length;
  assert(wrong.status() === 404 && still === 1, `wrong=${wrong.status()} still=${still}`);
});

// ---- 画面 ----
await check("画面: コメントが無いタスクは「コメントはまだありません。」", async () => {
  // 初期データのタスクは API のチェックでコメントが付いているので、新しく作ったタスクで確かめる
  const page = await suzuki.newPage();
  const created = await suzuki.request.post("/api/tasks", { data: { title: "コメントなし", status: "todo", assignee: "suzuki", dueDate: "2026-12-01" } });
  const tid = (await json(created))?.task?.id;
  assert(Number.isInteger(tid), `タスク作成に失敗 ${created.status()}`);
  await page.goto(`/tasks/${tid}`, { waitUntil: "networkidle" });
  const text = await page.textContent("main");
  const n = await page.locator('[data-testid="comment"]').count();
  await page.close();
  assert(n === 0 && text.includes("コメントはまだありません。"), `comments=${n}`);
});

await check("画面: 既存のコメントを古い順に、投稿者の名前・本文と一緒に表示する", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/3", { waitUntil: "networkidle" });
  const items = await page.locator('[data-testid="comment"]').allTextContents();
  await page.close();
  assert(items.length === 3, `got ${items.length}`);
  assert(items[0].includes("一番目") && items[1].includes("二番目") && items[2].includes("三番目"), JSON.stringify(items));
  assert(items.every((t) => t.includes("鈴木")), `投稿者名がない: ${JSON.stringify(items)}`);
});

await check("画面: フォームから投稿すると一覧に表示される", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/1", { waitUntil: "networkidle" });
  const before = await page.locator('[data-testid="comment"]').count();
  await page.locator('form[aria-label="コメント"] textarea[name="body"]').fill("画面からの投稿");
  await page.locator('form[aria-label="コメント"]').getByRole("button", { name: "投稿する" }).click();
  await page.locator('[data-testid="comment"]', { hasText: "画面からの投稿" }).waitFor({ timeout: 10000 });
  const after = await page.locator('[data-testid="comment"]').count();
  const last = await page.locator('[data-testid="comment"]').last().textContent();
  await page.close();
  const api = (await list(sato, 1)).json?.comments ?? [];
  assert(after === before + 1 && last.includes("画面からの投稿") && last.includes("佐藤"), `before=${before} after=${after} last=${last}`);
  assert(api.some((c) => c.body === "画面からの投稿" && c.author === "sato"), "API から見えない");
});

await check("画面: 空白だけで投稿すると role=alert のエラーが出て、コメントは増えない", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/3", { waitUntil: "networkidle" });
  const before = (await list(sato, 3)).json.comments.length;
  await page.locator('form[aria-label="コメント"] textarea[name="body"]').fill("   ");
  await page.locator('form[aria-label="コメント"]').getByRole("button", { name: "投稿する" }).click();
  // Next.js が自動で入れるルート通知（next-route-announcer）も role=alert を持つため、文言のある要素だけを見る
  const alertLoc = page.locator('[role="alert"]').filter({ hasText: /\S/ }).first();
  await alertLoc.waitFor({ state: "visible", timeout: 10000 });
  const alert = (await alertLoc.textContent()).trim();
  const shown = await page.locator('[data-testid="comment"]').count();
  await page.close();
  const after = (await list(sato, 3)).json.comments.length;
  assert(alert.length > 0 && after === before && shown === before, `alert="${alert}" before=${before} after=${after} shown=${shown}`);
});

await check("画面: 本文の HTML は解釈せずテキストとして表示する", async () => {
  const payload = '<b id="xss-b">太字</b><img src=x onerror="window.__xss=1">';
  await post(sato, 4, { body: payload });
  const page = await sato.newPage();
  await page.goto("/tasks/4", { waitUntil: "networkidle" });
  const injected = await page.locator('#xss-b, [data-testid="comment"] img').count();
  const xss = await page.evaluate(() => window.__xss === 1);
  const texts = await page.locator('[data-testid="comment"]').allTextContents();
  await page.close();
  assert(injected === 0 && !xss && texts.some((t) => t.includes('<b id="xss-b">太字</b>')), `injected=${injected} xss=${xss} texts=${JSON.stringify(texts)}`);
});

await check("画面: 「削除」ボタンは自分のコメントにだけ表示され、押すと一覧から消える", async () => {
  const mine = (await post(suzuki, 7, { body: "鈴木のコメント" })).json?.comment?.id;
  assert(Number.isInteger(mine), "投稿に失敗");
  // タスク 7 には sato のコメント 1 件と suzuki のコメント 1 件がある
  const page = await suzuki.newPage();
  await page.goto("/tasks/7", { waitUntil: "networkidle" });
  const satoItem = page.locator('[data-testid="comment"]', { hasText: "タスク 7 のコメント" });
  const mineItem = page.locator('[data-testid="comment"]', { hasText: "鈴木のコメント" });
  const satoButtons = await satoItem.getByRole("button", { name: "削除" }).count();
  const mineButtons = await mineItem.getByRole("button", { name: "削除" }).count();
  assert(satoButtons === 0 && mineButtons === 1, `他人のコメントのボタン=${satoButtons} 自分のコメントのボタン=${mineButtons}`);
  page.on("dialog", (d) => d.accept()); // 確認ダイアログを出す実装も可
  await mineItem.getByRole("button", { name: "削除" }).click();
  await mineItem.waitFor({ state: "detached", timeout: 10000 });
  const left = await page.locator('[data-testid="comment"]').allTextContents();
  await page.close();
  const api = (await list(sato, 7)).json?.comments ?? [];
  assert(left.length === 1 && api.length === 1 && api[0].author === "sato", `left=${JSON.stringify(left)} api=${api.length}`);
});

await check("既存の動作が壊れていない（タスク一覧 API 7 件以上・詳細画面のタイトル・未ログインはログイン画面へ）", async () => {
  const r = await sato.request.get("/api/tasks");
  const tasks = (await json(r))?.tasks ?? [];
  const page = await sato.newPage();
  await page.goto("/tasks/1", { waitUntil: "networkidle" });
  const title = (await page.textContent('[data-testid="task-title"]')).trim();
  await page.close();
  const anonPage = await anon.newPage();
  await anonPage.goto("/tasks/1", { waitUntil: "networkidle" });
  const url = anonPage.url();
  await anonPage.close();
  assert(r.status() === 200 && tasks.length >= 7 && title === "要件定義書のレビュー" && url.includes("/login"), `api=${r.status()}/${tasks.length} title=${title} url=${url}`);
});

await browser.close();
console.log(JSON.stringify(results));
})();
