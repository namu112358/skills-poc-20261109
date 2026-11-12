// W10 の公開の受け入れテスト（課題文に書いたことだけを確かめる。試行中は候補に見せない）。仕様は poc/tasks/wf-W10.md。
// 使い方: POC_FAKE_NOW=<ISO> NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100 → 結果を JSON で標準出力に出す
// 各チェックは別々のタスク・作業日を使い、前のチェックの結果に依存しないようにしている。
const L = require("./lib.cjs");
const { assert, post, list, del, mustPost, squash, form, alertOf, jstToday, utcToday } = L;

(async () => {
const { results, browser, login, check, anon } = await L.setup(process.argv[2]);
const sato = await login("sato");
const suzuki = await login("suzuki");

// ---- API ----
await check("API: 未ログインは 401（一覧・記録・削除）", async () => {
  const g = await anon.request.get("/api/tasks/1/time-entries");
  const p = await anon.request.post("/api/tasks/1/time-entries", { data: { minutes: 30 } });
  const d = await anon.request.delete("/api/tasks/1/time-entries/1");
  assert(g.status() === 401 && p.status() === 401 && d.status() === 401, `get=${g.status()} post=${p.status()} delete=${d.status()}`);
});

await check("API: 存在しないタスクは 404（一覧・記録）", async () => {
  const g = await list(sato, 9999);
  const p = await post(sato, 9999, { workDate: "2026-11-01", minutes: 30 });
  assert(g.status === 404 && p.status === 404, `get=${g.status} post=${p.status}`);
});

await check("API: 記録が無いタスクは 200 で空配列・合計 0", async () => {
  const r = await list(sato, 1);
  assert(r.status === 200 && Array.isArray(r.json?.entries) && r.json.entries.length === 0 && r.json.totalMinutes === 0,
    `got ${r.status} ${JSON.stringify(r.json)}`);
});

await check("API: 記録すると 201 で指定どおりの形の記録を返す（メモは前後の空白を除く）", async () => {
  const r = await post(sato, 1, { workDate: "2026-11-05", minutes: 90, note: "  設計レビュー  " });
  const e = r.json?.entry;
  assert(r.status === 201 && e, `got ${r.status} ${JSON.stringify(r.json)}`);
  assert(Number.isInteger(e.id), `id=${JSON.stringify(e.id)}`);
  assert(e.taskId === 1 && e.userId === "sato" && e.userName === "佐藤" && e.workDate === "2026-11-05" && e.minutes === 90
    && e.note === "設計レビュー", JSON.stringify(e));
  assert(typeof e.createdAt === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$/.test(e.createdAt), `createdAt=${e.createdAt}`);
  assert(Math.abs(Date.parse(e.createdAt) - L.FAKE_NOW) < 60 * 60 * 1000, `createdAt がサーバーの現在時刻から離れている: ${e.createdAt}`);
});

await check("API: メモを省略すると空文字で記録する", async () => {
  const r = await post(sato, 2, { workDate: "2026-11-04", minutes: 15 });
  assert(r.status === 201 && r.json?.entry?.note === "", `got ${r.status} ${JSON.stringify(r.json)}`);
});

await check("API: 作業時間が無いと 400（details に理由）で、記録は増えない", async () => {
  const before = (await list(sato, 2)).json?.entries?.length;
  const r = await post(sato, 2, { workDate: "2026-11-04", note: "時間なし" });
  const after = (await list(sato, 2)).json?.entries?.length;
  assert(r.status === 400 && typeof r.json?.error === "string" && Array.isArray(r.json?.details) && r.json.details.length > 0,
    `got ${r.status} ${JSON.stringify(r.json)}`);
  assert(before === after, `before=${before} after=${after}`);
});

await check("API: メモは 200 文字まで（前後の空白を除いて 201 文字なら 400）", async () => {
  const ok = await post(sato, 2, { workDate: "2026-11-03", minutes: 10, note: ` ${"あ".repeat(200)} ` });
  const ng = await post(sato, 2, { workDate: "2026-11-03", minutes: 10, note: "あ".repeat(201) });
  assert(ok.status === 201 && ok.json?.entry?.note === "あ".repeat(200) && ng.status === 400, `200 文字=${ok.status} 201 文字=${ng.status}`);
});

await check("API: 一覧は作業日の新しい順・同じ日は記録の新しい順で、そのタスクの記録だけと合計を返す", async () => {
  await mustPost(sato, 3, { workDate: "2026-11-02", minutes: 30, note: "a" });
  await mustPost(suzuki, 3, { workDate: "2026-11-06", minutes: 45, note: "b" });
  await mustPost(sato, 3, { workDate: "2026-11-06", minutes: 60, note: "c" });
  await mustPost(sato, 4, { workDate: "2026-11-06", minutes: 20, note: "別のタスク" });
  const r = await list(suzuki, 3);
  const notes = (r.json?.entries ?? []).map((e) => e.note);
  assert(r.status === 200 && JSON.stringify(notes) === JSON.stringify(["c", "b", "a"]), `got ${r.status} ${JSON.stringify(notes)}`);
  assert(r.json.totalMinutes === 135, `totalMinutes=${r.json.totalMinutes}`);
  const b = r.json.entries[1];
  assert(b.taskId === 3 && b.userId === "suzuki" && b.userName === "鈴木" && b.minutes === 45, JSON.stringify(b));
});

await check("API: 作業日を省略すると今日の日付で記録する", async () => {
  const r = await post(suzuki, 4, { minutes: 5, note: "今日" });
  const d = r.json?.entry?.workDate;
  // 「今日」が日本時間か UTC かは隠しテストで見る。ここではどちらかの今日になっていればよい
  assert(r.status === 201 && (d === jstToday || d === utcToday), `got ${r.status} workDate=${d}`);
});

await check("API: 自分の記録を削除すると 204 で、一覧と合計から消える", async () => {
  const e = await mustPost(sato, 5, { workDate: "2026-11-01", minutes: 40, note: "消す" });
  await mustPost(sato, 5, { workDate: "2026-11-01", minutes: 20, note: "残す" });
  const s = await del(sato, 5, e.id);
  const r = await list(sato, 5);
  const notes = (r.json?.entries ?? []).map((x) => x.note);
  assert(s === 204 && JSON.stringify(notes) === JSON.stringify(["残す"]) && r.json.totalMinutes === 20,
    `delete=${s} notes=${JSON.stringify(notes)} total=${r.json?.totalMinutes}`);
});

await check("API: 無い記録・別のタスクの記録の削除は 404 で、記録は残る", async () => {
  const e = await mustPost(sato, 5, { workDate: "2026-10-31", minutes: 10, note: "タスク 5" });
  const none = await del(sato, 5, 999999);
  const wrong = await del(sato, 1, e.id);
  const still = (await list(sato, 5)).json?.entries?.some((x) => x.id === e.id);
  assert(none === 404 && wrong === 404 && still, `無い=${none} 別タスク=${wrong} 残っている=${still}`);
});

// ---- 画面 ----
await check("画面: 記録が無いタスクは「作業時間」の見出し・「作業時間の記録はまだありません。」・「合計 0分」", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/6", { waitUntil: "networkidle" });
  const heading = await page.getByRole("heading", { name: "作業時間" }).count();
  const text = await page.textContent("main");
  const n = await page.locator('[data-testid="time-entry"]').count();
  const total = squash(await page.textContent('[data-testid="time-total"]'));
  await page.close();
  assert(heading >= 1 && n === 0 && text.includes("作業時間の記録はまだありません。") && total === "合計0分",
    `heading=${heading} entries=${n} total=${total}`);
});

await check("画面: 既存の記録を API と同じ順に、作業日・名前・「1時間30分」の形の時間・メモと一緒に表示する", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/3", { waitUntil: "networkidle" });
  const items = (await page.locator('[data-testid="time-entry"]').allTextContents()).map(squash);
  const total = squash(await page.textContent('[data-testid="time-total"]'));
  await page.close();
  assert(items.length === 3, `got ${items.length}`);
  assert(items[0].includes("1時間") && !items[0].includes("1時間0分") && items[0].includes("佐藤") && items[0].includes("2026-11-06")
    && items[0].includes("c"), `1 件目=${items[0]}`);
  assert(items[1].includes("45分") && items[1].includes("鈴木") && items[2].includes("30分") && items[2].includes("2026-11-02"),
    JSON.stringify(items));
  assert(total === "合計2時間15分", `total=${total}`);
});

await check("画面: フォームの作業日の初期値は今日で、記録すると一覧と合計に反映される", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/6", { waitUntil: "networkidle" });
  const f = L.form(page);
  const initial = await f.locator('input[name="workDate"]').inputValue();
  await f.locator('input[name="workDate"]').fill("2026-11-08");
  await f.locator('input[name="minutes"]').fill("90");
  await f.locator('input[name="note"]').fill("画面からの記録");
  await f.getByRole("button", { name: "記録する" }).click();
  await page.locator('[data-testid="time-entry"]', { hasText: "画面からの記録" }).waitFor({ timeout: 10000 });
  await page.waitForFunction(() => document.querySelector('[data-testid="time-total"]')?.textContent?.replace(/\s+/g, "") === "合計1時間30分",
    null, { timeout: 10000 }).catch(() => {});
  const item = squash(await page.locator('[data-testid="time-entry"]', { hasText: "画面からの記録" }).textContent());
  const total = squash(await page.textContent('[data-testid="time-total"]'));
  await page.close();
  const api = (await list(sato, 6)).json?.entries ?? [];
  assert(initial === jstToday || initial === utcToday, `初期値=${initial}`);
  assert(item.includes("1時間30分") && item.includes("佐藤") && total === "合計1時間30分", `item=${item} total=${total}`);
  assert(api.some((e) => e.note === "画面からの記録" && e.minutes === 90 && e.workDate === "2026-11-08" && e.userId === "sato"), "API から見えない");
});

await check("画面: API がエラーを返したら、フォームの近くに role=alert でエラーを表示する", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/7", { waitUntil: "networkidle" });
  await page.route("**/api/tasks/7/time-entries", (route) =>
    route.request().method() === "POST"
      ? route.fulfill({ status: 400, contentType: "application/json",
          body: JSON.stringify({ error: "入力内容に誤りがあります", details: ["作業時間を入力してください"] }) })
      : route.continue());
  const f = L.form(page);
  await f.locator('input[name="workDate"]').fill("2026-11-08");
  await f.locator('input[name="minutes"]').fill("30");
  await f.getByRole("button", { name: "記録する" }).click();
  const a = alertOf(page);
  await a.waitFor({ state: "visible", timeout: 10000 });
  const text = (await a.textContent()).trim();
  const n = await page.locator('[data-testid="time-entry"]').count();
  await page.close();
  assert(text.length > 0 && n === 0, `alert="${text}" entries=${n}`);
});

await check("画面: 「削除」ボタンは自分の記録にだけ表示され、押すと一覧と合計から消える", async () => {
  await mustPost(suzuki, 7, { workDate: "2026-11-01", minutes: 30, note: "鈴木の記録" });
  await mustPost(sato, 7, { workDate: "2026-11-02", minutes: 60, note: "佐藤の記録" });
  const page = await sato.newPage();
  page.on("dialog", (d) => d.accept()); // 確認ダイアログを出す実装も可
  await page.goto("/tasks/7", { waitUntil: "networkidle" });
  const other = page.locator('[data-testid="time-entry"]', { hasText: "鈴木の記録" });
  const mine = page.locator('[data-testid="time-entry"]', { hasText: "佐藤の記録" });
  const otherButtons = await other.getByRole("button", { name: "削除" }).count();
  const mineButtons = await mine.getByRole("button", { name: "削除" }).count();
  assert(otherButtons === 0 && mineButtons === 1, `他人の記録のボタン=${otherButtons} 自分の記録のボタン=${mineButtons}`);
  await mine.getByRole("button", { name: "削除" }).click();
  await mine.waitFor({ state: "detached", timeout: 10000 });
  await page.waitForFunction(() => document.querySelector('[data-testid="time-total"]')?.textContent?.replace(/\s+/g, "") === "合計30分",
    null, { timeout: 10000 }).catch(() => {});
  const total = squash(await page.textContent('[data-testid="time-total"]'));
  const left = await page.locator('[data-testid="time-entry"]').count();
  await page.close();
  const api = (await list(sato, 7)).json?.entries ?? [];
  assert(left === 1 && total === "合計30分" && api.length === 1 && api[0].userId === "suzuki", `left=${left} total=${total} api=${api.length}`);
});

await check("既存の動作が壊れていない（タスク一覧 API 7 件以上・詳細画面のタイトル・未ログインはログイン画面へ）", async () => {
  const r = await sato.request.get("/api/tasks");
  const tasks = (await L.json(r))?.tasks ?? [];
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
