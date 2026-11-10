// W18 引き継ぎ h2「台帳の編集で使用停止・廃棄にしても予約が残る」（不具合の修正）のテスト。依頼文は docs/poc/tasks/wf-W18h2.md。
const { harness, main, assert, show, jst, addDays, is2xx, is4xx } = require("./lib.cjs");

const T = "2026-11-10";
const d = (n) => addDays(T, n);
const has = (entries, ...words) => entries.some((e) => words.every((w) => JSON.stringify(e).includes(String(w))));

main("h2.cjs", async () => {
  const h = harness(process.argv[2], "BG");
  const { check, gone } = h;
  const start = async () => h.setNow(jst(T, "10:00"));

  for (const [id, status, label] of [["E01", "suspended", "使用停止"], ["E02", "disposed", "廃棄"]]) {
    await check(id, `台帳の編集で${label}にすると、これからの予約（今日を含む予約も）が取り消される`, async () => {
      await start();
      const inst = await h.instrument();
      const now = await h.mustReserve("suzuki", inst, d(0), d(1));
      const later = await h.mustReserve("tanaka", inst, d(10), d(12));
      const r = await h.patch(inst, { status });
      assert(r.status === 200, `編集: ${show(r)}`);
      const s = [await h.reservationStatus(inst, now), await h.reservationStatus(inst, later)];
      assert(gone(s[0]) && gone(s[1]), `予約の状態: ${JSON.stringify(s)}`);
    });
  }

  await check("E03", "使用中・校正中に変えたときや、状態以外の編集では予約は残る", async () => {
    await start();
    const inst = await h.instrument();
    const rid = await h.mustReserve("suzuki", inst, d(3), d(4));
    assert((await h.patch(inst, { note: "備考だけ" })).status === 200, "備考の編集");
    assert((await h.patch(inst, { status: "calibrating" })).status === 200, "校正中に変更");
    assert((await h.patch(inst, { status: "in_use" })).status === 200, "使用中に変更");
    const s = await h.reservationStatus(inst, rid);
    assert(!gone(s), `予約の状態: ${s}`);
  });

  await check("E04", "取り消した予約は、ほかの予約の取消と同じく変更履歴に残る", async () => {
    await start();
    const inst = await h.instrument();
    await h.mustReserve("kobayashi", inst, d(6), d(7));
    const { added } = await h.newHistory(inst, () => h.patch(inst, { status: "suspended" }, "kimura"));
    assert(has(added, "kobayashi", d(6)), `履歴: ${JSON.stringify(added).slice(0, 400)}`);
  });

  await check("E05", "権限の無い編集・ほかの計測器では、予約は取り消されない", async () => {
    await start();
    const inst = await h.instrument({ managerId: "suzuki" });
    const other = await h.instrument({ managerId: "suzuki" });
    const a = await h.mustReserve("yamamoto", inst, d(3), d(4));
    const b = await h.mustReserve("yamamoto", other, d(3), d(4));
    assert(is4xx((await h.patch(inst, { status: "suspended" }, "tanaka")).status), "他部署が使用停止にできた");
    assert(!gone(await h.reservationStatus(inst, a)), "権限の無い編集で取り消された");
    assert((await h.patch(inst, { status: "suspended" }, "sato")).status === 200, "品質保証部の編集");
    assert(!gone(await h.reservationStatus(other, b)), "ほかの計測器の予約が取り消された");
  });

  await h.done();
});
