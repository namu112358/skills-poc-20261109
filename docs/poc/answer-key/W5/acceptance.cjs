// W5 の受け入れテスト（試行中は候補に見せない）。課題は docs/poc/tasks/wf-W5.md、仕込みバグは bugs.patch。
// 使い方: NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka）を前提にする。
// チェック名の先頭の [B1]〜[B3] は仕込みバグの番号、[既存] は修正で壊れていないかの確認（バグの判定には使わない）。
const { chromium } = require("playwright");

(async () => {

const base = process.argv[2];
const results = [];
const browser = await chromium.launch();

async function login(userId) {
  const ctx = await browser.newContext({ baseURL: base });
  const res = await ctx.request.post("/api/login", { data: { userId, password: "password" } });
  if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
  return { ctx, res };
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
const t200 = "あ".repeat(200);
const t201 = "あ".repeat(201);

const { ctx: sato, res: loginRes } = await login("sato");

// ---- B1: タイトルがちょうど 200 文字だと 400 になる ----
await check("[B1] 200 文字ちょうどのタイトルでタスクを作成できる（201）", async () => {
  const r = await sato.request.post("/api/tasks", { data: { title: t200, status: "todo", assignee: "tanaka", dueDate: "2026-12-01" } });
  const j = await json(r);
  assert(r.status() === 201 && j?.task?.title === t200, `got ${r.status()} ${JSON.stringify(j)?.slice(0, 120)}`);
});
await check("[B1] 200 文字ちょうどのタイトルに更新できる（PATCH 200）", async () => {
  const r = await sato.request.patch("/api/tasks/7", { data: { title: t200 } });
  const j = await json(r);
  assert(r.status() === 200 && j?.task?.title === t200, `got ${r.status()} ${JSON.stringify(j)?.slice(0, 120)}`);
});
await check("[B1] 201 文字のタイトルは今までどおり 400", async () => {
  const p = await sato.request.post("/api/tasks", { data: { title: t201, status: "todo", assignee: "tanaka", dueDate: "2026-12-01" } });
  const q = await sato.request.patch("/api/tasks/6", { data: { title: t201 } });
  assert(p.status() === 400 && q.status() === 400, `post=${p.status()} patch=${q.status()}`);
});

// ---- B2: ログインして約 10 分でセッションが切れる（Cookie は 7 日） ----
// サーバーの時計は進められないので、HTTP では Cookie の有効期限が変わっていないことだけを確かめ、
// セッションの有効期限そのものは hidden.test.ts（src/lib の関数を直接呼ぶ）で確かめる。
await check("[B2] ログインの Cookie の有効期限は 7 日（Max-Age=604800）のまま", async () => {
  const sc = loginRes.headers()["set-cookie"] ?? "";
  assert(/poc_session=/.test(sc) && /Max-Age=604800/i.test(sc), sc.slice(0, 200));
});

// ---- B3: ステータスを変更しても、一覧（絞り込み）に反映されない ----
await check("[B3] ステータスを変更すると API の一覧（絞り込み・すべて）に反映される", async () => {
  // 先に一覧を開いておく（報告の再現手順 1）
  for (const q of ["", "?status=done", "?status=in_progress"]) await sato.request.get(`/api/tasks${q}`);
  const p = await sato.request.patch("/api/tasks/2", { data: { status: "done" } });
  assert(p.status() === 200, `patch=${p.status()}`);
  const done = (await json(await sato.request.get("/api/tasks?status=done")))?.tasks ?? [];
  const prog = (await json(await sato.request.get("/api/tasks?status=in_progress")))?.tasks ?? [];
  const all = (await json(await sato.request.get("/api/tasks")))?.tasks ?? [];
  const inAll = all.find((t) => t.id === 2);
  assert(done.some((t) => t.id === 2) && !prog.some((t) => t.id === 2) && inAll?.status === "done",
    `done=${done.map((t) => t.id)} in_progress=${prog.map((t) => t.id)} all#2=${inAll?.status}`);
});
await check("[B3] ステータスを変更すると一覧画面（/tasks?status=…）に反映される", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks?status=todo");
  await page.goto("/tasks?status=in_progress");
  const p = await sato.request.patch("/api/tasks/4", { data: { status: "in_progress" } });
  assert(p.status() === 200, `patch=${p.status()}`);
  await page.goto("/tasks?status=in_progress");
  const prog = await page.getByTestId("task-row").allInnerTexts();
  await page.goto("/tasks?status=todo");
  const todo = await page.getByTestId("task-row").allInnerTexts();
  await page.close();
  const has = (rows) => rows.some((r) => r.includes("DB スキーマ作成"));
  assert(has(prog) && !has(todo), `in_progress=${prog.length}件(${has(prog)}) todo=${todo.length}件(${has(todo)})`);
});
await check("[B3] タイトル・担当者の変更も一覧に反映される", async () => {
  await sato.request.get("/api/tasks?status=todo");
  const p = await sato.request.patch("/api/tasks/5", { data: { title: "CI の整備（改）", assignee: "tanaka" } });
  assert(p.status() === 200, `patch=${p.status()}`);
  const todo = (await json(await sato.request.get("/api/tasks?status=todo")))?.tasks ?? [];
  const t = todo.find((x) => x.id === 5);
  assert(t?.title === "CI の整備（改）" && t?.assignee === "tanaka", JSON.stringify(t));
});

// ---- 既存の動作（修正で壊れていないか） ----
await check("[既存] 作成したタスクが一覧に出る・詳細画面が開ける・未ログインは 401", async () => {
  const c = await sato.request.post("/api/tasks", { data: { title: "既存確認", status: "todo", assignee: "suzuki", dueDate: "2026-12-02" } });
  const id = (await json(c))?.task?.id;
  const list = (await json(await sato.request.get("/api/tasks?status=todo")))?.tasks ?? [];
  const page = await sato.newPage();
  await page.goto(`/tasks/${id}`);
  const title = await page.getByTestId("task-title").innerText();
  await page.close();
  const anon = await browser.newContext({ baseURL: base });
  const a = await anon.request.get("/api/tasks");
  assert(c.status() === 201 && list.some((t) => t.id === id) && title === "既存確認" && a.status() === 401,
    `create=${c.status()} listed=${list.some((t) => t.id === id)} title=${title} anon=${a.status()}`);
});

await browser.close();
console.log(JSON.stringify(results));

})().catch((e) => {
  console.log(JSON.stringify([{ name: "E2E 実行", pass: false, detail: String(e.message ?? e).slice(0, 300) }]));
});
