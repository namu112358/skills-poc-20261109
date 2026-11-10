// W8 の受け入れテスト（試行中は候補に見せない）。仕様は docs/poc/tasks/wf-W8.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka、タグなし）を前提にする。
// 各チェックは別々のタスク・別々のタグ名を使い、前のチェックの結果に依存しないようにしている。
// 初期データのステータス: 1 done, 2 in_progress, 3 in_progress, 4 todo, 5 todo, 6 todo, 7 done
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
async function add(ctx, taskId, body) {
  const res = await ctx.request.post(`/api/tasks/${taskId}/tags`, { data: body });
  return { status: res.status(), json: await json(res) };
}
async function list(ctx, taskId) {
  const res = await ctx.request.get(`/api/tasks/${taskId}/tags`);
  return { status: res.status(), json: await json(res) };
}
async function del(ctx, taskId, name) {
  const res = await ctx.request.delete(`/api/tasks/${taskId}/tags/${encodeURIComponent(name)}`);
  return { status: res.status() };
}
async function taskIds(ctx, query) {
  const res = await ctx.request.get(`/api/tasks?${query}`);
  const j = await json(res);
  return { status: res.status(), ids: (j?.tasks ?? []).map((t) => t.id) };
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const anon = await browser.newContext({ baseURL: base });
const sato = await login("sato");
const suzuki = await login("suzuki");

// ---- API ----
await check("API: 未ログインは 401（一覧・追加・削除・タグでの絞り込み）", async () => {
  const g = await anon.request.get("/api/tasks/1/tags");
  const p = await anon.request.post("/api/tasks/1/tags", { data: { name: "x" } });
  const d = await anon.request.delete("/api/tasks/1/tags/x");
  const l = await anon.request.get("/api/tasks?tag=x");
  assert(g.status() === 401 && p.status() === 401 && d.status() === 401 && l.status() === 401,
    `get=${g.status()} post=${p.status()} delete=${d.status()} list=${l.status()}`);
});

await check("API: タグが無いタスクは 200 で空配列", async () => {
  const r = await list(sato, 1);
  assert(r.status === 200 && Array.isArray(r.json?.tags) && r.json.tags.length === 0, `got ${r.status} ${JSON.stringify(r.json)}`);
});

await check("API: 付けると 201 で付けた後のタグを返す（前後の空白を除き、付けた古い順。担当者以外も付けられる）", async () => {
  // タスク 2 の担当者は suzuki。sato（担当者でない）が付ける
  const a = await add(sato, 2, { name: "  急ぎ  " });
  assert(a.status === 201 && same(a.json?.tags, ["急ぎ"]), `1 件目: ${a.status} ${JSON.stringify(a.json)}`);
  const b = await add(suzuki, 2, { name: "バグ" });
  assert(b.status === 201 && same(b.json?.tags, ["急ぎ", "バグ"]), `2 件目: ${b.status} ${JSON.stringify(b.json)}`);
  const c = await add(sato, 2, { name: "API" });
  assert(c.status === 201 && same(c.json?.tags, ["急ぎ", "バグ", "API"]), `3 件目: ${c.status} ${JSON.stringify(c.json)}`);
  const r = await list(suzuki, 2);
  assert(r.status === 200 && same(r.json?.tags, ["急ぎ", "バグ", "API"]), `一覧: ${r.status} ${JSON.stringify(r.json)}`);
});

await check("API: 同じタグは 409。大文字と小文字は別のタグ", async () => {
  const a = await add(sato, 3, { name: "Bug" });
  const dup = await add(sato, 3, { name: " Bug " });
  const lower = await add(sato, 3, { name: "bug" });
  assert(a.status === 201 && dup.status === 409 && lower.status === 201, `Bug=${a.status} 重複=${dup.status} bug=${lower.status}`);
  assert(typeof dup.json?.error === "string", `409 の本文: ${JSON.stringify(dup.json)}`);
  const r = await list(sato, 3);
  assert(same(r.json?.tags, ["Bug", "bug"]), `一覧: ${JSON.stringify(r.json)}`);
});

await check("API: 名前の検証（空白だけ・21 文字・空白/カンマ/スラッシュを含む・文字列でない・無い・JSON でない）は 400 と details", async () => {
  const bad = [{ name: "   " }, { name: "あ".repeat(21) }, { name: "a b" }, { name: "a,b" }, { name: "a/b" }, { name: 1 }, {}];
  for (const body of bad) {
    const r = await add(sato, 4, body);
    assert(r.status === 400 && typeof r.json?.error === "string" && Array.isArray(r.json?.details) && r.json.details.length > 0,
      `${JSON.stringify(body)} -> ${r.status} ${JSON.stringify(r.json)}`);
  }
  const raw = await sato.request.post("/api/tasks/4/tags", { headers: { "Content-Type": "application/json" }, data: "{oops" });
  assert(raw.status() === 400, `JSON でない -> ${raw.status()}`);
  const ok = await add(sato, 4, { name: "あ".repeat(20) });
  assert(ok.status === 201, `20 文字 -> ${ok.status}`);
  const r = await list(sato, 4);
  assert(same(r.json?.tags, ["あ".repeat(20)]), `400 のときに保存された: ${JSON.stringify(r.json)}`);
});

await check("API: 存在しないタスク・正の整数でない ID は 404（一覧・追加・削除）", async () => {
  for (const id of ["999", "abc", "0", "-1", "1.5"]) {
    const g = await sato.request.get(`/api/tasks/${id}/tags`);
    const p = await sato.request.post(`/api/tasks/${id}/tags`, { data: { name: "x" } });
    const d = await sato.request.delete(`/api/tasks/${id}/tags/x`);
    assert(g.status() === 404 && p.status() === 404 && d.status() === 404, `id=${id}: get=${g.status()} post=${p.status()} delete=${d.status()}`);
  }
  // エラーは既存の API と同じ { error } の JSON（ルートが無いときの 404 の HTML では通らない）
  const j = await json(await sato.request.post("/api/tasks/999/tags", { data: { name: "x" } }));
  assert(typeof j?.error === "string", `404 の本文が { error } の JSON でない: ${JSON.stringify(j)}`);
});

await check("API: 外すと 204 で一覧から消える（日本語の名前を URL エンコード）。付いていないタグは 404", async () => {
  await add(sato, 5, { name: "確認待ち" });
  await add(sato, 5, { name: "残す" });
  const d = await del(suzuki, 5, "確認待ち");
  assert(d.status === 204, `外す -> ${d.status}`);
  const r = await list(sato, 5);
  assert(same(r.json?.tags, ["残す"]), `外した後: ${JSON.stringify(r.json)}`);
  const again = await del(sato, 5, "確認待ち");
  const never = await del(sato, 5, "ない");
  assert(again.status === 404 && never.status === 404, `もう一度=${again.status} 付いていない=${never.status}`);
});

await check("API: 同じタグを複数のタスクに付けられ、1 つから外してもほかのタスクには残る", async () => {
  await add(sato, 6, { name: "共通" });
  await add(sato, 7, { name: "共通" });
  const d = await del(sato, 6, "共通");
  assert(d.status === 204, `外す -> ${d.status}`);
  const other = await del(sato, 1, "共通");
  assert(other.status === 404, `付いていないタスクから外す -> ${other.status}`);
  const r6 = await list(sato, 6);
  const r7 = await list(sato, 7);
  assert(same(r6.json?.tags, []) && same(r7.json?.tags, ["共通"]), `6=${JSON.stringify(r6.json)} 7=${JSON.stringify(r7.json)}`);
});

await check("API: GET /api/tasks?tag= で絞り込む（status と併用・空は指定なし・付いていないタグは空配列）", async () => {
  // 1 done, 4 todo, 6 todo
  for (const id of [1, 4, 6]) await add(sato, id, { name: "絞込" });
  const t = await taskIds(sato, `tag=${encodeURIComponent("絞込")}`);
  assert(t.status === 200 && same(t.ids, [1, 4, 6]), `tag のみ: ${t.status} ${JSON.stringify(t.ids)}`);
  const ts = await taskIds(sato, `tag=${encodeURIComponent("絞込")}&status=todo`);
  assert(same(ts.ids, [4, 6]), `tag+status: ${JSON.stringify(ts.ids)}`);
  const empty = await taskIds(sato, "tag=");
  assert(empty.status === 200 && same(empty.ids, [1, 2, 3, 4, 5, 6, 7]), `tag が空: ${empty.status} ${JSON.stringify(empty.ids)}`);
  const none = await taskIds(sato, `tag=${encodeURIComponent("どこにもない")}`);
  assert(none.status === 200 && same(none.ids, []), `付いていない: ${none.status} ${JSON.stringify(none.ids)}`);
  const st = await taskIds(sato, "status=done");
  assert(same(st.ids, [1, 7]), `status のみ（既存の動作）: ${JSON.stringify(st.ids)}`);
});

// ---- 画面 ----
async function page(ctx, path) {
  const p = await ctx.newPage();
  await p.goto(path, { waitUntil: "networkidle" });
  return p;
}
async function tagTexts(p) {
  return (await p.locator('[data-testid="tag"]').allInnerTexts()).map((s) => s.trim());
}
async function waitTags(p, want, ms = 8000) {
  const end = Date.now() + ms;
  let got;
  while (Date.now() < end) {
    got = await tagTexts(p);
    if (same(got, want)) return got;
    await p.waitForTimeout(250);
  }
  return got;
}
// 画面のチェック用のタスクを API で作る（API の結果に依存しないよう、画面のチェックごとに新しいタスクを使う）
async function newTask(title, status = "todo") {
  const res = await sato.request.post("/api/tasks", { data: { title, status, assignee: "tanaka", dueDate: "2026-12-01" } });
  const j = await json(res);
  if (res.status() !== 201 || !j?.task?.id) throw new Error(`タスクの作成に失敗: ${res.status()}`);
  return j.task.id;
}

await check("画面: 詳細画面に「タグ」の見出しと、タグが無いときの「タグはまだありません。」", async () => {
  const id = await newTask("画面チェック 空");
  const p = await page(sato, `/tasks/${id}`);
  try {
    assert(await p.getByRole("heading", { name: "タグ", exact: true }).count() > 0, "見出し「タグ」が無い");
    assert(await p.getByText("タグはまだありません。").count() > 0, "空の表示が無い");
    assert((await tagTexts(p)).length === 0, "タグの要素がある");
  } finally { await p.close(); }
});

await check("画面: 追加フォームで付けると一覧に表示され、入力欄が空に戻る（付けた古い順）", async () => {
  const id = await newTask("画面チェック 追加");
  await add(sato, id, { name: "先" });
  const p = await page(sato, `/tasks/${id}`);
  try {
    const form = p.locator('form[aria-label="タグの追加"]');
    assert(await form.count() === 1, "form[aria-label=タグの追加] が無い");
    await form.locator('input[name="name"]').fill("後で");
    await form.getByRole("button", { name: "追加する" }).click();
    const got = await waitTags(p, ["先", "後で"]);
    assert(same(got, ["先", "後で"]), `表示: ${JSON.stringify(got)}`);
    const v = await p.locator('form[aria-label="タグの追加"] input[name="name"]').inputValue();
    assert(v === "", `入力欄が空に戻らない: ${JSON.stringify(v)}`);
    const r = await list(sato, id);
    assert(same(r.json?.tags, ["先", "後で"]), `保存された内容: ${JSON.stringify(r.json)}`);
  } finally { await p.close(); }
});

await check("画面: 追加できないとき（空白だけ・すでに付いている）はフォームの近くに role=alert", async () => {
  const id = await newTask("画面チェック エラー");
  await add(sato, id, { name: "既存" });
  const p = await page(sato, `/tasks/${id}`);
  try {
    const form = p.locator('form[aria-label="タグの追加"]');
    for (const value of ["   ", "既存"]) {
      await form.locator('input[name="name"]').fill(value);
      await form.getByRole("button", { name: "追加する" }).click();
      await p.getByRole("alert").filter({ hasText: /\S/ }).first().waitFor({ timeout: 8000 })
        .catch(() => { throw new Error(`「${value}」で role=alert が出ない`); });
      if (value === "   ") await p.reload({ waitUntil: "networkidle" });
    }
    const r = await list(sato, id);
    assert(same(r.json?.tags, ["既存"]), `保存された内容: ${JSON.stringify(r.json)}`);
  } finally { await p.close(); }
});

await check("画面: 「外す」ボタン（aria-label にタグ名）を押すとそのタグが消える", async () => {
  const id = await newTask("画面チェック 外す");
  for (const name of ["一", "二", "三"]) await add(sato, id, { name });
  const p = await page(sato, `/tasks/${id}`);
  try {
    const btn = p.getByRole("button", { name: "タグ「二」を外す" });
    assert(await btn.count() === 1, "aria-label=タグ「二」を外す のボタンが無い");
    await btn.click();
    const got = await waitTags(p, ["一", "三"]);
    assert(same(got, ["一", "三"]), `表示: ${JSON.stringify(got)}`);
    const r = await list(sato, id);
    assert(same(r.json?.tags, ["一", "三"]), `保存された内容: ${JSON.stringify(r.json)}`);
  } finally { await p.close(); }
});

await check("画面: タグの名前は HTML として解釈しない", async () => {
  const id = await newTask("画面チェック HTML");
  await add(sato, id, { name: "<b>太字</b>".replace("</b>", "") }); // 「/」は使えないので開始タグだけ
  const p = await page(sato, `/tasks/${id}`);
  try {
    const got = await tagTexts(p);
    assert(same(got, ["<b>太字"]), `表示: ${JSON.stringify(got)}`);
    assert(await p.locator('[data-testid="tag"] b').count() === 0, "<b> 要素として解釈された");
    const l = await page(sato, `/tasks`);
    try {
      assert(await l.locator("tbody b").count() === 0, "一覧で <b> 要素として解釈された");
      assert(await l.getByText("<b>太字").count() > 0, "一覧に名前がテキストで表示されない");
    } finally { await l.close(); }
  } finally { await p.close(); }
});

await check("画面: 一覧の各行にタグを付けた古い順に表示し、/tasks?tag=<エンコードした名前> へのリンクにする", async () => {
  const id = await newTask("画面チェック 一覧のタグ");
  for (const name of ["一覧B", "一覧A"]) await add(sato, id, { name });
  const p = await page(sato, "/tasks");
  try {
    const row = p.locator("tr", { has: p.locator(`a[href="/tasks/${id}"]`) });
    assert(await row.count() === 1, "行が見つからない");
    const text = await row.innerText();
    const ib = text.indexOf("一覧B"), ia = text.indexOf("一覧A");
    assert(ib >= 0 && ia > ib, `行の表示: ${JSON.stringify(text)}`);
    const hrefs = await row.locator("a").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
    const want = `/tasks?tag=${encodeURIComponent("一覧A")}`;
    const ok = hrefs.some((h) => h && (h === want || decodeURIComponent(h) === "/tasks?tag=一覧A"));
    assert(ok, `リンク: ${JSON.stringify(hrefs)}`);
  } finally { await p.close(); }
});

await check("画面: /tasks?tag= で絞り込み、「タグ「…」のタスク」と「すべてのタスク」リンクを表示。status と併用できる", async () => {
  const a = await newTask("画面チェック 絞込 未着手", "todo");
  const b = await newTask("画面チェック 絞込 完了", "done");
  await add(sato, a, { name: "画面絞込" });
  await add(sato, b, { name: "画面絞込" });
  const tag = encodeURIComponent("画面絞込");
  const p = await page(sato, `/tasks?tag=${tag}`);
  try {
    const rows = await p.locator('[data-testid="task-row"]').allInnerTexts();
    assert(rows.length === 2 && rows.some((r) => r.includes("絞込 未着手")) && rows.some((r) => r.includes("絞込 完了")), `行: ${JSON.stringify(rows)}`);
    assert(await p.getByText("タグ「画面絞込」のタスク").count() > 0, "「タグ「画面絞込」のタスク」が無い");
    const all = p.getByRole("link", { name: "すべてのタスク" });
    assert(await all.count() > 0, "「すべてのタスク」のリンクが無い");
    await all.first().click();
    await p.waitForLoadState("networkidle");
    const n = await p.locator('[data-testid="task-row"]').count();
    assert(n >= 9 && !p.url().includes("tag="), `解除後: ${n} 行 ${p.url()}`);
    await p.goto(`/tasks?tag=${tag}&status=todo`, { waitUntil: "networkidle" });
    const rows2 = await p.locator('[data-testid="task-row"]').allInnerTexts();
    assert(rows2.length === 1 && rows2[0].includes("絞込 未着手"), `tag+status: ${JSON.stringify(rows2)}`);
  } finally { await p.close(); }
});

await check("既存の動作: ログイン・一覧（絞り込みなしで全件、ステータスの絞り込み）・詳細・タスクの API", async () => {
  const p = await page(sato, "/tasks");
  try {
    assert(await p.locator('[data-testid="task-row"]').count() >= 7, "一覧が全件表示されない");
    await p.goto("/tasks?status=done", { waitUntil: "networkidle" });
    const rows = await p.locator('[data-testid="task-row"]').allInnerTexts();
    assert(rows.length >= 2 && rows.every((r) => r.includes("完了")), `status=done: ${JSON.stringify(rows)}`);
    await p.goto("/tasks/1", { waitUntil: "networkidle" });
    assert((await p.getByTestId("task-title").innerText()).includes("要件定義書のレビュー"), "詳細画面");
  } finally { await p.close(); }
  const g = await sato.request.get("/api/tasks/1");
  const j = await json(g);
  assert(g.status() === 200 && j?.task?.title === "要件定義書のレビュー", `GET /api/tasks/1 -> ${g.status()}`);
  const u = await anon.request.get("/api/tasks");
  assert(u.status() === 401, `未ログインの一覧 -> ${u.status()}`);
});

await browser.close();
console.log(JSON.stringify(results));

})().catch((e) => {
  console.log(JSON.stringify([{ name: "E2E 実行", pass: false, detail: String(e?.message ?? e).slice(0, 500) }]));
  process.exit(0);
});
