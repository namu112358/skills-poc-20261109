// W10 の隠しテスト（課題文には書いていないが、当然守るべきこと。試行中は候補に見せない）。項目は grading.md の H1〜H12。
// 使い方: POC_FAKE_NOW=<ISO> NODE_PATH=$(npm root -g) node hidden.cjs http://localhost:3100 → 結果を JSON で標準出力に出す
// サーバーの時計は日本時間 2026-11-10 00:30 ごろ（UTC ではまだ 11/09）。各項目は別々の作業日を使い、互いに依存しないようにしている。
const L = require("./lib.cjs");
const { assert, post, list, del, mustPost, squash, form, alertOf, jstToday, jstTomorrow } = L;

(async () => {
const { results, browser, login, check } = await L.setup(process.argv[2]);
const sato = await login("sato");
const suzuki = await login("suzuki");
const base = process.argv[2];

await check("[H1 権限] 他人の記録は削除できない（403 か 404 で、記録は残る）", async () => {
  const e = await mustPost(sato, 1, { workDate: "2026-10-01", minutes: 30, note: "佐藤の記録" });
  const s = await del(suzuki, 1, e.id);
  const still = (await list(sato, 1)).json?.entries?.some((x) => x.id === e.id);
  assert((s === 403 || s === 404) && still, `delete=${s} 残っている=${still}`);
});

await check("[H2 権限] 記録した人はログイン中のユーザー（本文の userId・userName は使わない）", async () => {
  const r = await post(sato, 2, { workDate: "2026-10-02", minutes: 20, note: "なりすまし", userId: "tanaka", userName: "田中", user: "tanaka" });
  const e = r.json?.entry;
  const listed = (await list(sato, 2)).json?.entries?.find((x) => x.note === "なりすまし");
  assert(r.status === 201 && e?.userId === "sato" && e?.userName === "佐藤" && listed?.userId === "sato",
    `got ${r.status} ${JSON.stringify(e)} 一覧=${JSON.stringify(listed)}`);
});

await check("[H3 入力検証] 作業時間は 1 以上の整数だけ（0・負・小数・数字でない文字列は 400 で、記録は増えない）", async () => {
  const bad = [0, -30, 1.5, "abc"];
  const statuses = [];
  for (const minutes of bad) statuses.push((await post(sato, 3, { workDate: "2026-10-03", minutes, note: `不正 ${minutes}` })).status);
  const n = (await list(sato, 3)).json?.entries?.length;
  assert(statuses.every((s) => s === 400) && n === 0, `statuses=${JSON.stringify(statuses)} 記録=${n}`);
});

await check("[H4 境界値] 1 件の作業時間は 24 時間まで（1440 分は可、1441 分は 400）", async () => {
  const ok = await post(sato, 3, { workDate: "2026-10-04", minutes: 1440, note: "24 時間" });
  const ng = await post(suzuki, 3, { workDate: "2026-10-04", minutes: 1441, note: "24 時間超" });
  assert(ok.status === 201 && ng.status === 400, `1440=${ok.status} 1441=${ng.status}`);
});

await check("[H5 境界値] 同じ人の同じ作業日の合計は 24 時間まで（タスクをまたいで数え、他の人・他の日には影響しない）", async () => {
  await mustPost(sato, 1, { workDate: "2026-10-05", minutes: 1000, note: "1000 分" });
  const over = await post(sato, 2, { workDate: "2026-10-05", minutes: 441, note: "超える" });
  const fit = await post(sato, 2, { workDate: "2026-10-05", minutes: 440, note: "ちょうど" });
  const more = await post(sato, 4, { workDate: "2026-10-05", minutes: 1, note: "さらに" });
  const otherUser = await post(suzuki, 2, { workDate: "2026-10-05", minutes: 1440, note: "鈴木" });
  const otherDay = await post(sato, 2, { workDate: "2026-10-06", minutes: 1440, note: "別の日" });
  const st = { over: over.status, fit: fit.status, more: more.status, otherUser: otherUser.status, otherDay: otherDay.status };
  assert(over.status >= 400 && over.status < 500 && fit.status === 201 && more.status >= 400 && more.status < 500
    && otherUser.status === 201 && otherDay.status === 201, JSON.stringify(st));
});

await check("[H6 時差] 作業日の「今日」は日本時間（API で省略したとき・画面の初期値）", async () => {
  const r = await post(sato, 5, { minutes: 5, note: "今日の記録" });
  const page = await sato.newPage();
  await page.goto("/tasks/5", { waitUntil: "networkidle" });
  const initial = await form(page).locator('input[name="workDate"]').inputValue();
  await page.close();
  assert(r.status === 201 && r.json?.entry?.workDate === jstToday && initial === jstToday,
    `API=${r.status} ${r.json?.entry?.workDate} 画面の初期値=${initial}（期待 ${jstToday}）`);
});

await check("[H7 入力検証] 実在しない日付・形式の違う日付は 400（2026-02-30・2026-13-01・2026/10/07・数値・空文字）", async () => {
  const bad = ["2026-02-30", "2026-13-01", "2026/10/07", 20261007, ""];
  const statuses = [];
  for (const workDate of bad) statuses.push((await post(sato, 6, { workDate, minutes: 10, note: `日付 ${workDate}` })).status);
  const n = (await list(sato, 6)).json?.entries?.length;
  assert(statuses.every((s) => s === 400) && n === 0, `statuses=${JSON.stringify(statuses)} 記録=${n}`);
});

await check("[H8 時差・境界値] 未来の作業日は 400、日本時間の今日は記録できる（UTC ではまだ前日）", async () => {
  const today = await post(suzuki, 6, { workDate: jstToday, minutes: 10, note: "日本時間の今日" });
  const tomorrow = await post(suzuki, 6, { workDate: jstTomorrow, minutes: 10, note: "明日" });
  const far = await post(suzuki, 6, { workDate: "2027-01-01", minutes: 10, note: "来年" });
  assert(today.status === 201 && tomorrow.status === 400 && far.status === 400,
    `今日(${jstToday})=${today.status} 明日(${jstTomorrow})=${tomorrow.status} 来年=${far.status}`);
});

await check("[H9 エラー時の振る舞い] 壊れた要求でも 500 にならない（JSON でない・配列・null・メモが文字列でない → 400、不正な ID → 404）", async () => {
  const raw = async (data) => (await sato.request.post("/api/tasks/7/time-entries", { headers: { "content-type": "application/json" }, data })).status();
  const s = {
    notJson: await raw("{minutes: 30"),
    array: await raw("[]"),
    nul: await raw("null"),
    noteNumber: (await post(sato, 7, { workDate: "2026-10-09", minutes: 10, note: 123 })).status,
    taskZero: (await sato.request.get("/api/tasks/0/time-entries")).status(),
    taskAbc: (await sato.request.get("/api/tasks/abc/time-entries")).status(),
    taskDecimal: (await post(sato, "1.5", { workDate: "2026-10-09", minutes: 10 })).status,
    entryAbc: (await sato.request.delete("/api/tasks/7/time-entries/abc")).status(),
  };
  const n = (await list(sato, 7)).json?.entries?.length;
  assert(s.notJson === 400 && s.array === 400 && s.nul === 400 && s.noteNumber === 400 && s.taskZero === 404 && s.taskAbc === 404
    && s.taskDecimal === 404 && s.entryAbc === 404 && n === 0, `${JSON.stringify(s)} 記録=${n}`);
});

await check("[H10 同時操作] 「記録する」を素早く 2 回押しても、記録は 1 件だけ", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/4", { waitUntil: "networkidle" });
  // 応答を遅らせ、1 回目の応答が返る前に 2 回目を押せる状態にする
  await page.route("**/api/tasks/4/time-entries", async (route) => {
    if (route.request().method() === "POST") await new Promise((r) => setTimeout(r, 800));
    await route.continue();
  });
  const f = form(page);
  await f.locator('input[name="minutes"]').fill("7");
  await f.locator('input[name="note"]').fill("二重送信の確認");
  await f.getByRole("button", { name: "記録する" }).dblclick();
  await page.waitForTimeout(3000);
  await page.close();
  const n = ((await list(sato, 4)).json?.entries ?? []).filter((e) => e.note === "二重送信の確認").length;
  assert(n === 1, `記録された件数=${n}`);
});

await check("[H11 エラー時の振る舞い] サーバーエラー（500・JSON でない応答）でもエラーを表示し、入力した内容を消さず、もう一度押せる", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks/2", { waitUntil: "networkidle" });
  let fail = true;
  await page.route("**/api/tasks/2/time-entries", (route) =>
    route.request().method() === "POST" && fail
      ? route.fulfill({ status: 500, contentType: "text/plain", body: "Internal Server Error" })
      : route.continue());
  const f = form(page);
  await f.locator('input[name="workDate"]').fill("2026-10-11");
  await f.locator('input[name="minutes"]').fill("25");
  await f.locator('input[name="note"]').fill("失敗しても残るメモ");
  await f.getByRole("button", { name: "記録する" }).click();
  const a = alertOf(page);
  await a.waitFor({ state: "visible", timeout: 10000 });
  const kept = {
    workDate: await f.locator('input[name="workDate"]').inputValue(),
    minutes: await f.locator('input[name="minutes"]').inputValue(),
    note: await f.locator('input[name="note"]').inputValue(),
  };
  // 2 回目は通す。押せて記録できれば「もう一度押せる」
  fail = false;
  await f.getByRole("button", { name: "記録する" }).click({ timeout: 5000 });
  await page.locator('[data-testid="time-entry"]', { hasText: "失敗しても残るメモ" }).waitFor({ timeout: 10000 });
  await page.close();
  assert(kept.workDate === "2026-10-11" && kept.minutes === "25" && kept.note === "失敗しても残るメモ", `入力の状態=${JSON.stringify(kept)}`);
});

await check("[H12 安全性] メモの HTML は解釈せず、テキストとして表示する", async () => {
  const payload = '<b id="xss-b">太字</b><img src=x onerror="window.__xss=1">';
  await mustPost(suzuki, 5, { workDate: "2026-10-12", minutes: 10, note: payload });
  const page = await sato.newPage();
  await page.goto("/tasks/5", { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  const injected = await page.locator('#xss-b, [data-testid="time-entry"] img').count();
  const xss = await page.evaluate(() => window.__xss === 1);
  const texts = await page.locator('[data-testid="time-entry"]').allTextContents();
  await page.close();
  assert(injected === 0 && !xss && texts.some((t) => t.includes('<b id="xss-b">太字</b>')), `injected=${injected} xss=${xss} texts=${JSON.stringify(texts)}`);
});

void base;
await browser.close();
console.log(JSON.stringify(results));
})();
