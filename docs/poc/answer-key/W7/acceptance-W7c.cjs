// W7c（自分の作業記録の日別一覧）の受け入れテスト（試行中は候補に見せない）。課題は docs/poc/tasks/wf-W7c.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance-W7c.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかりを前提にする。作業記録は W7b の API で作る。
// 落とし穴（日本時間の日付での絞り込み・表示、エラー型）はここでは判定しない（pitfalls.cjs）。記録は「今」作るので、
// 日本時間の今日と UTC の今日のどちらの日付で返しても合格にする（日付の境目は pitfalls.cjs で見る）。
const { setup, assert, json } = require("./common.cjs");

function ymd(d) {
  return d.toISOString().slice(0, 10);
}

(async () => {
  const base = process.argv[2];
  const { browser, results, login, anon, check } = await setup(base);
  const sato = await login("sato");
  const suzuki = await login("suzuki");
  const guest = await anon();
  const M = "/api/me/worklogs";
  const now = new Date();
  const days = [...new Set([ymd(new Date(now.getTime() + 9 * 3600 * 1000)), ymd(now)])];
  const add = async (ctx, task, minutes, note) => json(await ctx.request.post(`/api/tasks/${task}/worklogs`, { data: { minutes, note } }));

  await check("未ログインでは 401", async () => {
    const r = await guest.request.get(`${M}?date=${days[0]}`);
    assert(r.status() === 401, `got ${r.status()}`);
  });
  await check("記録の無い日は空配列と合計 0（200）、date をそのまま返す", async () => {
    const r = await sato.request.get(`${M}?date=2001-01-01`);
    const j = await json(r);
    assert(r.status() === 200 && j?.date === "2001-01-01" && Array.isArray(j?.worklogs) && j.worklogs.length === 0 && j.totalMinutes === 0,
      `got ${r.status()} ${JSON.stringify(j)?.slice(0, 160)}`);
  });
  const a = await add(sato, 3, 30, "設計");
  const b = await add(sato, 6, 45, "");
  await add(suzuki, 3, 60, "鈴木の記録");
  let day, list;
  await check("今日の自分の作業記録が古い順に返り、タスクの名前と合計が付く（ほかの人の記録は含まない）", async () => {
    for (const d of days) {
      const j = await json(await sato.request.get(`${M}?date=${d}`));
      if ((j?.worklogs ?? []).length > 0) { day = d; list = j; break; }
    }
    assert(list, `今日（${days.join(" / ")}）の記録が返らない`);
    const ids = list.worklogs.map((w) => w.id);
    assert(ids.length === 2 && ids[0] === a?.worklog?.id && ids[1] === b?.worklog?.id && list.totalMinutes === 75,
      `ids=${ids} total=${list.totalMinutes}`);
    const w = list.worklogs[0];
    assert(w.taskId === 3 && w.taskTitle === "API 設計" && w.author === "sato" && w.authorName === "佐藤" && w.minutes === 30 &&
      w.note === "設計" && typeof w.recordedAt === "string" && w.recordedAt.length > 0, JSON.stringify(w));
    assert(list.worklogs[1].taskTitle === "E2E テストの追加", JSON.stringify(list.worklogs[1]));
  });
  await check("ほかの人は自分の記録だけが見える", async () => {
    const j = await json(await suzuki.request.get(`${M}?date=${day}`));
    assert(j?.worklogs?.length === 1 && j.worklogs[0].author === "suzuki" && j.totalMinutes === 60, JSON.stringify(j)?.slice(0, 160));
  });
  await check("date が無い・形式が違う・存在しない日付は 400", async () => {
    const s = [];
    for (const q of ["", "?date=", "?date=20261110", "?date=2026-1-1", "?date=2026-02-30", "?date=2026-13-01", "?date=abc"]) {
      s.push((await sato.request.get(`${M}${q}`)).status());
    }
    assert(s.every((x) => x === 400), `got ${s}`);
  });
  await check("画面に見出し・日付・記録（タスクへのリンク・作業時間・メモ）と合計が表示される", async () => {
    const page = await sato.newPage();
    await page.goto(`/my/worklogs?date=${day}`);
    const heading = await page.getByRole("heading", { name: "自分の作業記録" }).count();
    const body = await page.locator("main").innerText();
    const rows = await page.getByTestId("my-worklog").allInnerTexts();
    const href = await page.getByTestId("my-worklog").first().locator("a").first().getAttribute("href").catch(() => "");
    const total = await page.getByTestId("my-worklog-total").innerText().catch(() => "");
    await page.close();
    assert(heading >= 1 && body.includes(day), `見出し=${heading} 日付の表示なし`);
    assert(rows.length === 2 && rows[0].includes("API 設計") && /30\s*分/.test(rows[0]) && rows[0].includes("設計") && rows[1].includes("E2E テストの追加") && /45\s*分/.test(rows[1]),
      `rows=${JSON.stringify(rows).slice(0, 200)}`);
    assert(/\/tasks\/3$/.test(href ?? ""), `リンク: ${href}`);
    assert(/合計\s*75\s*分/.test(total), `合計: ${total}`);
  });
  await check("記録の無い日の画面は「この日の作業記録はありません。」", async () => {
    const page = await sato.newPage();
    await page.goto("/my/worklogs?date=2001-01-01");
    const body = await page.locator("main").innerText();
    const n = await page.getByTestId("my-worklog").count();
    await page.close();
    assert(n === 0 && body.includes("この日の作業記録はありません。"), `n=${n}`);
  });
  await check("日付が無い・正しくないときの画面は「日付を YYYY-MM-DD の形で指定してください。」", async () => {
    const out = [];
    for (const q of ["", "?date=2026-02-30"]) {
      const page = await sato.newPage();
      await page.goto(`/my/worklogs${q}`);
      out.push((await page.locator("main").innerText()).includes("日付を YYYY-MM-DD の形で指定してください。") && (await page.getByTestId("my-worklog").count()) === 0);
      await page.close();
    }
    assert(out.every(Boolean), `got ${out}`);
  });
  await check("未ログインで画面を開くとログイン画面へ移動する", async () => {
    const page = await guest.newPage();
    await page.goto(`/my/worklogs?date=${day}`);
    const url = page.url();
    await page.close();
    assert(/\/login/.test(url), url);
  });
  await check("[既存] タスクの作業記録の API は今までどおり使える", async () => {
    const j = await json(await sato.request.get("/api/tasks/3/worklogs"));
    assert(j?.worklogs?.length === 2 && j.totalMinutes === 90, JSON.stringify(j)?.slice(0, 160));
  });

  await browser.close();
  console.log(JSON.stringify(results));
})().catch((e) => {
  console.log(JSON.stringify([{ name: "E2E 実行", pass: false, detail: String(e.message ?? e).slice(0, 300) }]));
});
