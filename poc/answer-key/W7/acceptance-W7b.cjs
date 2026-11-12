// W7b（作業記録）の受け入れテスト（試行中は候補に見せない）。課題は poc/tasks/wf-W7b.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance-W7b.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka）を前提にする。
// 落とし穴（日時・エラー型）はここでは判定しない（pitfalls.cjs）。[既存] は既存の機能を壊していないかの記録。
const { setup, assert, json } = require("./common.cjs");

(async () => {
  const base = process.argv[2];
  const { browser, results, login, anon, check } = await setup(base);
  const sato = await login("sato");
  const suzuki = await login("suzuki");
  const guest = await anon();
  const W = (id) => `/api/tasks/${id}/worklogs`;

  await check("未ログインでは GET・POST・DELETE とも 401", async () => {
    const s = [
      (await guest.request.get(W(3))).status(),
      (await guest.request.post(W(3), { data: { minutes: 30 } })).status(),
      (await guest.request.delete(`${W(3)}/1`)).status(),
    ];
    assert(s.every((x) => x === 401), `got ${s}`);
  });
  await check("作業記録の無いタスクは空配列と合計 0（200）", async () => {
    const r = await sato.request.get(W(3));
    const j = await json(r);
    assert(r.status() === 200 && Array.isArray(j?.worklogs) && j.worklogs.length === 0 && j.totalMinutes === 0,
      `got ${r.status()} ${JSON.stringify(j)}`);
  });
  let first, second;
  await check("作業記録を追加すると 201 で返り、記録した人はログイン中のユーザー・メモは前後の空白を除く", async () => {
    const r = await sato.request.post(W(3), { data: { minutes: 30, note: "  設計の見直し  ", author: "tanaka" } });
    const j = await json(r);
    first = j?.worklog;
    assert(r.status() === 201, `got ${r.status()} ${JSON.stringify(j)?.slice(0, 160)}`);
    assert(Number.isInteger(first?.id) && first.taskId === 3 && first.author === "sato" && first.authorName === "佐藤" &&
      first.minutes === 30 && first.note === "設計の見直し", JSON.stringify(first));
    assert(typeof first.recordedAt === "string" && first.recordedAt.length > 0, "recordedAt がない");
  });
  await check("メモは省略でき（空文字）、ほかの人も記録できる", async () => {
    const r = await suzuki.request.post(W(3), { data: { minutes: 60 } });
    const j = await json(r);
    second = j?.worklog;
    assert(r.status() === 201 && second?.note === "" && second.author === "suzuki" && second.authorName === "鈴木" && second.minutes === 60,
      `got ${r.status()} ${JSON.stringify(j)?.slice(0, 160)}`);
  });
  await check("一覧は新しい順で、合計が返る", async () => {
    const j = await json(await sato.request.get(W(3)));
    const ids = (j?.worklogs ?? []).map((w) => w.id);
    assert(ids.length === 2 && ids[0] === second?.id && ids[1] === first?.id && j.totalMinutes === 90,
      `ids=${ids} total=${j?.totalMinutes}`);
    assert(j.worklogs[1].recordedAt === first.recordedAt && j.worklogs[1].note === "設計の見直し", JSON.stringify(j.worklogs[1]));
  });
  await check("作業時間が 1〜1440 の整数でない・メモが 200 文字を超える・文字列でない・本文がオブジェクトでないときは 400", async () => {
    const bad = [{ minutes: 0 }, { minutes: 1441 }, { minutes: 1.5 }, { minutes: "30" }, {}, { minutes: 30, note: "あ".repeat(201) }, { minutes: 30, note: 1 }];
    const s = [];
    for (const data of bad) s.push((await sato.request.post(W(6), { data })).status());
    s.push((await sato.request.post(W(6), { data: "x", headers: { "content-type": "application/json" } })).status());
    s.push((await sato.request.post(W(6), { data: "[]", headers: { "content-type": "application/json" } })).status());
    const j = await json(await sato.request.get(W(6)));
    assert(s.every((x) => x === 400) && j?.worklogs?.length === 0, `got ${s} count=${j?.worklogs?.length}`);
  });
  await check("境界値（1 分・1440 分・メモ 200 文字）は受け付ける", async () => {
    const s = [
      (await sato.request.post(W(6), { data: { minutes: 1 } })).status(),
      (await sato.request.post(W(6), { data: { minutes: 1440, note: "う".repeat(200) } })).status(),
    ];
    const j = await json(await sato.request.get(W(6)));
    assert(s.every((x) => x === 201) && j?.totalMinutes === 1441, `got ${s} total=${j?.totalMinutes}`);
  });
  await check("完了（done）のタスクには追加できず 409", async () => {
    const r = await sato.request.post(W(1), { data: { minutes: 10 } });
    const j = await json(await sato.request.get(W(1)));
    assert(r.status() === 409 && j?.worklogs?.length === 0, `got ${r.status()} count=${j?.worklogs?.length}`);
  });
  await check("存在しないタスク・不正な ID は 404", async () => {
    const s = [
      (await sato.request.get(W(999))).status(),
      (await sato.request.post(W(999), { data: { minutes: 10 } })).status(),
      (await sato.request.get(W("abc"))).status(),
      (await sato.request.post(W("0"), { data: { minutes: 10 } })).status(),
      (await sato.request.delete(`${W(999)}/${first?.id}`)).status(),
    ];
    assert(s.every((x) => x === 404), `got ${s}`);
  });
  await check("詳細画面に作業記録が新しい順に並び、名前・作業時間・メモと合計が表示される", async () => {
    const page = await sato.newPage();
    await page.goto("/tasks/3");
    const rows = await page.getByTestId("worklog").allInnerTexts();
    const total = await page.getByTestId("worklog-total").innerText().catch(() => "");
    const heading = await page.getByRole("heading", { name: "作業記録" }).count();
    await page.close();
    assert(heading >= 1, "見出し「作業記録」がない");
    assert(rows.length === 2, `worklog 要素の数 ${rows.length}`);
    assert(rows[0].includes("鈴木") && /60\s*分/.test(rows[0]), `1 行目: ${rows[0].slice(0, 120)}`);
    assert(rows[1].includes("佐藤") && /30\s*分/.test(rows[1]) && rows[1].includes("設計の見直し"), `2 行目: ${rows[1].slice(0, 120)}`);
    assert(/合計\s*90\s*分/.test(total), `合計: ${total}`);
  });
  await check("作業記録の無いタスクの詳細画面には「作業記録はまだありません。」と表示する", async () => {
    const page = await sato.newPage();
    await page.goto("/tasks/4");
    const body = await page.locator("main").innerText();
    const n = await page.getByTestId("worklog").count();
    await page.close();
    assert(n === 0 && body.includes("作業記録はまだありません。"), `worklog=${n}`);
  });
  await check("記録した本人以外の削除は 403、URL のタスクの記録でないときは 404", async () => {
    const a = (await suzuki.request.delete(`${W(3)}/${first?.id}`)).status();
    const b = (await sato.request.delete(`${W(6)}/${first?.id}`)).status();
    const c = (await sato.request.delete(`${W(3)}/999999`)).status();
    const d = (await sato.request.delete(`${W(3)}/abc`)).status();
    const j = await json(await sato.request.get(W(3)));
    assert(a === 403 && b === 404 && c === 404 && d === 404 && j?.worklogs?.length === 2, `other=${a} wrongTask=${b} missing=${c} bad=${d}`);
  });
  await check("本人が削除すると 204 で、一覧と合計から消える", async () => {
    const r = await sato.request.delete(`${W(3)}/${first?.id}`);
    const j = await json(await sato.request.get(W(3)));
    assert(r.status() === 204 && j?.worklogs?.length === 1 && j.worklogs[0].id === second?.id && j.totalMinutes === 60,
      `got ${r.status()} ${JSON.stringify(j)?.slice(0, 160)}`);
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
