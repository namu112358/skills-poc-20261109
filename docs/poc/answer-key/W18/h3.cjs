// W18 引き継ぎ h3「状態『修理中』を足す」のテスト。依頼文は docs/poc/tasks/wf-W18h3.md。状態の値は依頼文で repairing に決めている。
// 状態を見ている処理（貸出・予約・予約の取消・お知らせ・発注・絞り込み・履歴・権限）に漏れなく入ったかを確かめる。
const { harness, main, assert, show, jst, addDays, sleep, is2xx, is4xx } = require("./lib.cjs");

const T = "2026-11-10";
const d = (n) => addDays(T, n);
const has = (entries, ...words) => entries.some((e) => words.every((w) => JSON.stringify(e).includes(String(w))));

main("h3.cjs", async () => {
  const h = harness(process.argv[2], "RP");
  const { check, call } = h;
  const start = async () => h.setNow(jst(T, "10:00"));
  const statusOf = async (inst) => (await h.getInstrument(inst)).instrument?.status;

  await check("R01", "使用中・使用停止から修理中にでき、戻せる。API で読め、一覧を修理中で絞り込める", async () => {
    await start();
    const a = await h.instrument();
    const b = await h.instrument({ status: "suspended" });
    for (const i of [a, b]) {
      const r = await h.patch(i, { status: "repairing" });
      assert(r.status === 200 && (await statusOf(i)) === "repairing", `修理中にする: ${show(r)}`);
    }
    const list = await call("sato", "GET", "/api/instruments?status=repairing");
    const xs = list.json?.instruments || [];
    assert(xs.some((x) => x.id === a.id) && xs.every((x) => x.status === "repairing"), `絞り込み: ${show(list)}`);
    assert((await h.patch(a, { status: "in_use" })).status === 200 && (await statusOf(a)) === "in_use", "使用中に戻す");
    assert((await h.patch(b, { status: "suspended" })).status === 200 && (await statusOf(b)) === "suspended", "使用停止に戻す");
  });

  await check("R02", "修理中の計測器は貸し出せず、予約もできない", async () => {
    await start();
    const i = await h.instrument();
    assert((await h.patch(i, { status: "repairing" })).status === 200, "修理中にする");
    assert(is4xx((await h.lend(i, "suzuki", d(3))).status), "貸し出せた");
    assert(is4xx((await h.reserve("suzuki", i, d(5), d(6))).status), "予約できた");
  });

  await check("R03", "修理中にすると、これからの予約（今日を含む）が取り消される", async () => {
    await start();
    const i = await h.instrument();
    const a = await h.mustReserve("suzuki", i, d(0), d(1));
    const b = await h.mustReserve("tanaka", i, d(8), d(9));
    assert((await h.patch(i, { status: "repairing" })).status === 200, "修理中にする");
    const s = [await h.reservationStatus(i, a), await h.reservationStatus(i, b)];
    assert(h.gone(s[0]) && h.gone(s[1]), `予約の状態: ${JSON.stringify(s)}`);
  });

  await check("R04", "修理中の計測器には校正期限のお知らせを送らない", async () => {
    const rep = await h.instrument({ managerId: "kimura", importance: "top", last: "2026-10-31" }); // 期限 2027-10-31
    const ctl = await h.instrument({ managerId: "kimura", importance: "top", last: "2026-10-31" });
    await h.setNow(jst("2027-10-01"));
    assert((await h.patch(rep, { status: "repairing" })).status === 200, "修理中にする");
    await h.setNow(jst("2027-10-20"));
    await h.runReminders();
    assert((await h.delivered(ctl)).length >= 1, "使用中の A に届いていない（ジョブが動いていない）");
    const n = (await h.delivered(rep)).length;
    assert(n === 0, `修理中に ${n} 件届いた`);
  });

  await check("R05", "修理中の計測器は校正機関に発注できない（受付システムに送らない）", async () => {
    await start();
    const i = await h.instrument();
    assert((await h.patch(i, { status: "repairing" })).status === 200, "修理中にする");
    const r = await h.order(i);
    await sleep(500);
    assert(is4xx(r.status), `発注: ${show(r)}`);
    assert((await h.agencyOrders(i)).length === 0, "受付システムに送られた");
  });

  await check("R06", "修理中にする・戻すが、変更した人つきで履歴に残る", async () => {
    await start();
    const i = await h.instrument();
    const a = await h.newHistory(i, () => h.patch(i, { status: "repairing" }, "kimura"));
    assert(has(a.added, "kimura") && (has(a.added, "repairing") || has(a.added, "修理中")), `修理中にした履歴: ${JSON.stringify(a.added).slice(0, 300)}`);
    const b = await h.newHistory(i, () => h.patch(i, { status: "in_use" }, "kimura"));
    assert(b.added.length >= 1 && (has(b.added, "repairing") || has(b.added, "修理中")), `戻した履歴: ${JSON.stringify(b.added).slice(0, 300)}`);
  });

  await check("R07", "修理中にできるのは台帳を編集できる人だけ（他部署は 403）", async () => {
    await start();
    const i = await h.instrument({ managerId: "suzuki" }); // 製造部
    const r = await h.patch(i, { status: "repairing" }, "tanaka");
    assert(r.status === 403 && (await statusOf(i)) === "in_use", `他部署: ${show(r)}`);
    assert((await h.patch(i, { status: "repairing" }, "watanabe")).status === 200, "管理部署の人ができない");
  });

  await check("R08", "修理から戻すと、また貸出・予約・発注ができる", async () => {
    await start();
    const i = await h.instrument();
    await h.patch(i, { status: "repairing" });
    assert((await h.patch(i, { status: "in_use" })).status === 200, "使用中に戻す");
    const rid = await h.reserve("suzuki", i, d(5), d(6));
    assert(is2xx(rid.status), `予約: ${show(rid)}`);
    const l = await h.lend(i, "suzuki", d(2));
    assert(l.status === 201, `貸出: ${l.status}`);
    assert((await h.returnLoan(i, l.loanId)) === 200, "返却");
    assert(is2xx((await h.order(i)).status), "発注");
  });

  await h.done();
});
