// W7d（タスクの予定）の受け入れテスト（試行中は候補に見せない）。課題は poc/tasks/wf-W7d.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance-W7d.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかりを前提にする。
// 落とし穴（日本時間の入力を UTC で保存し日本時間で表示する、エラー型）はここでは判定しない（pitfalls.cjs）。
const { setup, assert, json } = require("./common.cjs");

(async () => {
  const base = process.argv[2];
  const { browser, results, login, anon, check } = await setup(base);
  const sato = await login("sato");
  const suzuki = await login("suzuki");
  const guest = await anon();
  const S = (id) => `/api/tasks/${id}/schedules`;

  await check("未ログインでは GET・POST とも 401", async () => {
    const s = [(await guest.request.get(S(6))).status(), (await guest.request.post(S(6), { data: { title: "x", startsAt: "2026-11-20T10:00" } })).status()];
    assert(s.every((x) => x === 401), `got ${s}`);
  });
  await check("予定の無いタスクは空配列（200）", async () => {
    const r = await sato.request.get(S(6));
    const j = await json(r);
    assert(r.status() === 200 && Array.isArray(j?.schedules) && j.schedules.length === 0, `got ${r.status()} ${JSON.stringify(j)}`);
  });
  let late, early, mid;
  await check("担当者が登録すると 201 で返り、登録した人はログイン中のユーザー・件名は前後の空白を除く", async () => {
    const r = await sato.request.post(S(6), { data: { title: "  リリース判定  ", startsAt: "2026-11-22T09:00", createdBy: "tanaka" } });
    const j = await json(r);
    late = j?.schedule;
    assert(r.status() === 201, `got ${r.status()} ${JSON.stringify(j)?.slice(0, 160)}`);
    assert(Number.isInteger(late?.id) && late.taskId === 6 && late.createdBy === "sato" && late.createdByName === "佐藤" && late.title === "リリース判定",
      JSON.stringify(late));
    assert(typeof late.startsAt === "string" && late.startsAt.length > 0 && typeof late.createdAt === "string" && late.createdAt.length > 0, "startsAt・createdAt がない");
  });
  await check("一覧は開始日時の早い順", async () => {
    early = (await json(await sato.request.post(S(6), { data: { title: "設計レビュー", startsAt: "2026-11-20T10:00" } })))?.schedule;
    mid = (await json(await sato.request.post(S(6), { data: { title: "テスト計画", startsAt: "2026-11-20T15:00" } })))?.schedule;
    const j = await json(await sato.request.get(S(6)));
    const ids = (j?.schedules ?? []).map((s) => s.id);
    assert(ids.length === 3 && ids[0] === early?.id && ids[1] === mid?.id && ids[2] === late?.id, `ids=${ids}`);
    assert(j.schedules[2].startsAt === late.startsAt && j.schedules[0].createdByName === "佐藤", JSON.stringify(j.schedules[2]));
  });
  await check("担当者以外は 403、完了（done）のタスクは 409", async () => {
    const a = (await suzuki.request.post(S(6), { data: { title: "x", startsAt: "2026-11-20T10:00" } })).status();
    const b = (await sato.request.post(S(1), { data: { title: "x", startsAt: "2026-11-20T10:00" } })).status();
    const j = await json(await suzuki.request.get(S(6)));
    assert(a === 403 && b === 409 && j?.schedules?.length === 3, `other=${a} done=${b} count=${j?.schedules?.length}`);
  });
  await check("件名・開始日時が正しくない・本文がオブジェクトでないときは 400", async () => {
    const bad = [
      { startsAt: "2026-11-20T10:00" }, { title: "   ", startsAt: "2026-11-20T10:00" }, { title: "あ".repeat(101), startsAt: "2026-11-20T10:00" },
      { title: 1, startsAt: "2026-11-20T10:00" }, { title: "x" }, { title: "x", startsAt: "2026-11-20 10:00" }, { title: "x", startsAt: "2026-11-20T10:00:00Z" },
      { title: "x", startsAt: "2026-02-30T10:00" }, { title: "x", startsAt: "2026-11-20T25:00" }, { title: "x", startsAt: 1 },
    ];
    const s = [];
    for (const data of bad) s.push((await sato.request.post(S(6), { data })).status());
    s.push((await sato.request.post(S(6), { data: "x", headers: { "content-type": "application/json" } })).status());
    s.push((await sato.request.post(S(6), { data: "[]", headers: { "content-type": "application/json" } })).status());
    const j = await json(await sato.request.get(S(6)));
    assert(s.every((x) => x === 400) && j?.schedules?.length === 3, `got ${s} count=${j?.schedules?.length}`);
  });
  await check("境界値（件名 100 文字・23:59）は受け付ける", async () => {
    const r = await sato.request.post(S(3), { data: { title: "い".repeat(100), startsAt: "2026-12-31T23:59" } });
    assert(r.status() === 201, `got ${r.status()}`);
  });
  await check("存在しないタスク・不正な ID は 404", async () => {
    const s = [
      (await sato.request.get(S(999))).status(),
      (await sato.request.post(S(999), { data: { title: "x", startsAt: "2026-11-20T10:00" } })).status(),
      (await sato.request.get(S("abc"))).status(),
      (await sato.request.post(S("0"), { data: { title: "x", startsAt: "2026-11-20T10:00" } })).status(),
    ];
    assert(s.every((x) => x === 404), `got ${s}`);
  });
  await check("詳細画面に予定が早い順に並び、件名と登録した人が表示される", async () => {
    const page = await sato.newPage();
    await page.goto("/tasks/6");
    const heading = await page.getByRole("heading", { name: "予定" }).count();
    const rows = await page.getByTestId("schedule").allInnerTexts();
    await page.close();
    assert(heading >= 1, "見出し「予定」がない");
    assert(rows.length === 3 && rows[0].includes("設計レビュー") && rows[1].includes("テスト計画") && rows[2].includes("リリース判定") && rows.every((r) => r.includes("佐藤")),
      `rows=${JSON.stringify(rows).slice(0, 200)}`);
  });
  await check("予定の無いタスクの詳細画面には「予定はありません。」と表示する", async () => {
    const page = await sato.newPage();
    await page.goto("/tasks/4");
    const body = await page.locator("main").innerText();
    const n = await page.getByTestId("schedule").count();
    await page.close();
    assert(n === 0 && body.includes("予定はありません。"), `n=${n}`);
  });
  await check("[既存] 作業記録とコメントは今までどおり使える", async () => {
    const w = await sato.request.post("/api/tasks/4/worklogs", { data: { minutes: 10 } });
    const c = await sato.request.post("/api/tasks/4/comments", { data: { body: "確認" } });
    assert(w.status() === 201 && c.status() === 201, `worklog=${w.status()} comment=${c.status()}`);
  });

  await browser.close();
  console.log(JSON.stringify(results));
})().catch((e) => {
  console.log(JSON.stringify([{ name: "E2E 実行", pass: false, detail: String(e.message ?? e).slice(0, 300) }]));
});
