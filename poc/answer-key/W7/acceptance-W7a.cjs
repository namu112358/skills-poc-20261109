// W7a（完了報告）の受け入れテスト（試行中は候補に見せない）。課題は poc/tasks/wf-W7a.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance-W7a.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka）を前提にする。
// 落とし穴（日時・エラー型）はここでは判定しない（pitfalls.cjs）。[既存] は既存の機能を壊していないかの記録。
const { setup, assert, json, pageText } = require("./common.cjs");

(async () => {
  const base = process.argv[2];
  const { browser, results, login, anon, check } = await setup(base);
  const sato = await login("sato");
  const suzuki = await login("suzuki");
  const guest = await anon();
  const C = (id) => `/api/tasks/${id}/completion`;

  await check("未ログインでは GET・POST・DELETE とも 401", async () => {
    const s = [
      (await guest.request.get(C(3))).status(),
      (await guest.request.post(C(3), { data: {} })).status(),
      (await guest.request.delete(C(3))).status(),
    ];
    assert(s.every((x) => x === 401), `got ${s}`);
  });
  await check("完了報告の無いタスクは { completion: null }（200）", async () => {
    const r = await sato.request.get(C(3));
    const j = await json(r);
    assert(r.status() === 200 && j && j.completion === null, `got ${r.status()} ${JSON.stringify(j)}`);
  });
  let created;
  await check("担当者が完了報告すると 201 で完了報告が返り、メモは前後の空白を除く", async () => {
    const r = await sato.request.post(C(3), { data: { note: "  レビュー済み  ", completedBy: "tanaka" } });
    const j = await json(r);
    created = j?.completion;
    assert(r.status() === 201, `got ${r.status()} ${JSON.stringify(j)?.slice(0, 160)}`);
    assert(created?.taskId === 3 && created.completedBy === "sato" && created.completedByName === "佐藤" && created.note === "レビュー済み",
      JSON.stringify(created));
    assert(typeof created.completedAt === "string" && created.completedAt.length > 0, "completedAt がない");
  });
  await check("完了報告するとタスクのステータスが完了（done）になり、GET で同じ完了報告が返る", async () => {
    const t = await json(await sato.request.get("/api/tasks/3"));
    const g = await json(await sato.request.get(C(3)));
    assert(t?.task?.status === "done", `status=${t?.task?.status}`);
    assert(g?.completion?.completedBy === "sato" && g.completion.note === "レビュー済み" && g.completion.completedAt === created?.completedAt,
      JSON.stringify(g));
  });
  await check("すでに完了のタスクへの完了報告は 409（完了報告済み・初期データで完了の両方）", async () => {
    const a = (await sato.request.post(C(3), { data: {} })).status();
    const b = (await sato.request.post(C(1), { data: {} })).status();
    assert(a === 409 && b === 409, `task3=${a} task1=${b}`);
  });
  await check("担当者以外の完了報告は 403 で、ステータスは変わらない", async () => {
    const r = await sato.request.post(C(2), { data: {} }); // タスク 2 の担当は suzuki
    const t = await json(await sato.request.get("/api/tasks/2"));
    assert(r.status() === 403 && t?.task?.status === "in_progress", `got ${r.status()} status=${t?.task?.status}`);
  });
  await check("存在しないタスク・不正な ID は 404", async () => {
    const s = [
      (await sato.request.get(C(999))).status(),
      (await sato.request.post(C(999), { data: {} })).status(),
      (await sato.request.delete(C(999))).status(),
      (await sato.request.get(C("abc"))).status(),
      (await sato.request.post(C("0"), { data: {} })).status(),
    ];
    assert(s.every((x) => x === 404), `got ${s}`);
  });
  await check("メモが 500 文字を超える・文字列でない・本文がオブジェクトでないときは 400 で、ステータスは変わらない", async () => {
    const s = [
      (await sato.request.post(C(6), { data: { note: "あ".repeat(501) } })).status(),
      (await sato.request.post(C(6), { data: { note: 1 } })).status(),
      (await sato.request.post(C(6), { data: "x", headers: { "content-type": "application/json" } })).status(),
      (await sato.request.post(C(6), { data: "[]", headers: { "content-type": "application/json" } })).status(),
    ];
    const t = await json(await sato.request.get("/api/tasks/6"));
    assert(s.every((x) => x === 400) && t?.task?.status === "todo", `got ${s} status=${t?.task?.status}`);
  });
  await check("メモは省略でき（空文字）、500 文字ちょうどは受け付ける", async () => {
    const a = await sato.request.post(C(6), { data: {} });
    const ja = await json(a);
    const ok500 = await suzuki.request.post(C(5), { data: { note: "い".repeat(500) } }); // タスク 5 の担当は suzuki
    const jb = await json(ok500);
    assert(a.status() === 201 && ja?.completion?.note === "", `omit: ${a.status()} ${JSON.stringify(ja)?.slice(0, 120)}`);
    assert(ok500.status() === 201 && jb?.completion?.note?.length === 500 && jb.completion.completedByName === "鈴木",
      `500: ${ok500.status()} ${JSON.stringify(jb)?.slice(0, 120)}`);
  });
  await check("詳細画面に「完了報告」と完了した人の名前・メモが表示される", async () => {
    const page = await sato.newPage();
    await page.goto("/tasks/3");
    const el = page.locator('[data-testid="completion"]');
    assert((await el.count()) === 1, `completion 要素の数 ${await el.count()}`);
    const text = await el.innerText();
    const heading = await page.getByRole("heading", { name: "完了報告" }).count();
    await page.close();
    assert(heading >= 1, "見出し「完了報告」がない");
    assert(text.includes("佐藤") && text.includes("レビュー済み"), text.slice(0, 200));
  });
  await check("完了報告の無いタスクの詳細画面には完了報告を表示しない", async () => {
    const page = await sato.newPage();
    await page.goto("/tasks/4");
    const n = await page.locator('[data-testid="completion"]').count();
    const heading = await page.getByRole("heading", { name: "完了報告" }).count();
    const title = await page.getByTestId("task-title").innerText();
    await page.close();
    assert(n === 0 && heading === 0 && title === "DB スキーマ作成", `completion=${n} heading=${heading} title=${title}`);
  });
  await check("完了報告をした本人以外の取り消しは 403", async () => {
    const r = await suzuki.request.delete(C(3));
    const g = await json(await sato.request.get(C(3)));
    assert(r.status() === 403 && g?.completion?.completedBy === "sato", `got ${r.status()} ${JSON.stringify(g)?.slice(0, 120)}`);
  });
  await check("本人が取り消すと 204 で、完了報告が消え、ステータスは進行中（in_progress）に戻る", async () => {
    const r = await sato.request.delete(C(3));
    const g = await json(await sato.request.get(C(3)));
    const t = await json(await sato.request.get("/api/tasks/3"));
    assert(r.status() === 204 && g?.completion === null && t?.task?.status === "in_progress",
      `got ${r.status()} completion=${JSON.stringify(g?.completion)} status=${t?.task?.status}`);
  });
  await check("完了報告の無いタスクの取り消しは 409", async () => {
    const a = (await sato.request.delete(C(3))).status();
    const b = (await sato.request.delete(C(1))).status(); // 初期データで完了だが完了報告は無い
    assert(a === 409 && b === 409, `task3=${a} task1=${b}`);
  });
  await check("取り消した後は、もう一度完了報告できる", async () => {
    const r = await sato.request.post(C(3), { data: { note: "再提出" } });
    const j = await json(r);
    assert(r.status() === 201 && j?.completion?.note === "再提出", `got ${r.status()} ${JSON.stringify(j)?.slice(0, 120)}`);
  });
  await check("[既存] タスクの更新（PATCH）とコメントは今までどおり使える", async () => {
    const p = await sato.request.patch("/api/tasks/4", { data: { status: "in_progress" } });
    const c = await sato.request.post("/api/tasks/4/comments", { data: { body: "確認" } });
    const l = await json(await sato.request.get("/api/tasks/4/comments"));
    assert(p.status() === 200 && c.status() === 201 && l?.comments?.length === 1, `patch=${p.status()} comment=${c.status()}`);
  });

  await browser.close();
  console.log(JSON.stringify(results));
})().catch((e) => {
  console.log(JSON.stringify([{ name: "E2E 実行", pass: false, detail: String(e.message ?? e).slice(0, 300) }]));
});
