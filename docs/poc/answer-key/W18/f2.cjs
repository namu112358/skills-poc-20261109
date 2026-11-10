// W18 第 2 回「貸出の予約」のテスト（W13 の tests.cjs の P01・K01〜K08 を写し、W18 で足した K09 を加えた）。
// 各項目は自分専用の計測器を作って行う。日付はすべて日本時間。項目の定義は grading.md。
const { harness, main, assert, jst, addDays, is2xx, is4xx } = require("./lib.cjs");

const T = "2026-11-10";
const d = (n) => addDays(T, n);

main("f2.cjs", async () => {
  const h = harness(process.argv[2], "RV");
  const { check, gone } = h;
  const start = async () => h.setNow(jst(T));

  await check("P01", "予約を作れて、一覧で誰が・いつからいつまでかが読める", async () => {
    await start();
    const inst = await h.instrument();
    const id = await h.mustReserve("suzuki", inst, d(5), d(7));
    const x = (await h.reservations(inst)).find((i) => String(i.id) === String(id));
    assert(x, "一覧に無い");
    assert(x.start === d(5) && x.end === d(7) && x.user === "suzuki", `一覧の内容: ${JSON.stringify(x.item).slice(0, 300)}`);
  });

  await check("K01", "過去の日からは予約できず、今日からはできる。終了日が開始日より前は不可", async () => {
    await start();
    const inst = await h.instrument();
    assert(is4xx((await h.reserve("suzuki", inst, d(-1), d(1))).status), "昨日から予約できた");
    assert(is4xx((await h.reserve("suzuki", inst, d(4), d(3))).status), "終了日が前の予約ができた");
    const today = await h.reserve("suzuki", inst, d(0), d(0));
    assert(is2xx(today.status), `今日から: ${today.status} ${JSON.stringify(today.json)?.slice(0, 200)}`);
  });

  await check("K02", "期間が 1 日でも重なる予約はできない（端の日が同じでも）。隣り合う期間はできる", async () => {
    await start();
    const inst = await h.instrument();
    await h.mustReserve("suzuki", inst, d(10), d(12));
    for (const [s, e] of [[d(12), d(14)], [d(8), d(10)], [d(11), d(11)], [d(9), d(13)]]) {
      const r = await h.reserve("tanaka", inst, s, e);
      assert(is4xx(r.status), `${s}〜${e} が通った: ${r.status}`);
    }
    const ok1 = await h.reserve("tanaka", inst, d(13), d(15));
    const ok2 = await h.reserve("tanaka", inst, d(7), d(9));
    assert(is2xx(ok1.status) && is2xx(ok2.status), `隣り合う期間: ${ok1.status} ${ok2.status}`);
  });

  await check("K03", "取り消した予約は枠を空ける", async () => {
    await start();
    const inst = await h.instrument();
    const id = await h.mustReserve("suzuki", inst, d(20), d(22));
    const c = await h.cancelReservation("suzuki", inst, id);
    assert(is2xx(c), `本人の取消: ${c}`);
    const r = await h.reserve("tanaka", inst, d(20), d(22));
    assert(is2xx(r.status), `取消の後の予約: ${r.status}`);
  });

  await check("K04", "貸出中の計測器は、返却予定日までと重なる予約はできず、翌日からはできる", async () => {
    await start();
    const inst = await h.instrument();
    const l = await h.lend(inst, "matsumoto", d(5));
    assert(l.status === 201, `貸出: ${l.status}`);
    assert(is4xx((await h.reserve("suzuki", inst, d(3), d(6))).status), "返却予定日と重なる予約ができた");
    assert(is4xx((await h.reserve("suzuki", inst, d(5), d(6))).status), "返却予定日からの予約ができた");
    const ok = await h.reserve("suzuki", inst, d(6), d(8));
    assert(is2xx(ok.status), `返却予定日の翌日から: ${ok.status}`);
  });

  await check("K05", "他人の予約の期間にかかる貸出はしない。予約した本人には予約の期間に貸し出せる", async () => {
    await start();
    const inst = await h.instrument();
    await h.mustReserve("suzuki", inst, d(2), d(4));
    assert(is4xx((await h.lend(inst, "tanaka", d(3))).status), "他人への貸出（予約と重なる）ができた");
    assert(is4xx((await h.lend(inst, "tanaka", d(2))).status), "他人への貸出（返却予定日が予約の開始日）ができた");
    const short = await h.lend(inst, "tanaka", d(1));
    assert(short.status === 201, `予約の前日までの貸出: ${short.status}`);
    assert((await h.returnLoan(inst, short.loanId)) === 200, "返却");
    await h.setNow(jst(d(2)));
    const own = await h.lend(inst, "suzuki", d(4));
    assert(own.status === 201, `予約した本人への貸出: ${own.status}`);
  });

  await check("K06", "使用停止・廃棄の計測器は予約できない", async () => {
    await start();
    for (const status of ["suspended", "disposed"]) {
      const inst = await h.instrument({ status });
      const r = await h.reserve("suzuki", inst, d(3), d(4));
      assert(is4xx(r.status), `${status}: ${r.status}`);
    }
    const ok = await h.reserve("suzuki", await h.instrument(), d(3), d(4));
    assert(is2xx(ok.status), `使用中（対照）: ${ok.status}`);
  });

  await check("K07", "取り消せるのは予約した本人と計測器の管理者で、ほかの人はできない", async () => {
    await start();
    const inst = await h.instrument({ managerId: "kato" });
    const a = await h.mustReserve("suzuki", inst, d(5), d(6));
    const b = await h.mustReserve("suzuki", inst, d(8), d(9));
    assert(is4xx(await h.cancelReservation("tanaka", inst, a)), "ほかの人が取り消せた");
    assert(!gone(await h.reservationStatus(inst, a)), "ほかの人の取消で取り消された");
    assert(is2xx(await h.cancelReservation("kato", inst, a)), "管理者が取り消せない");
    assert(is2xx(await h.cancelReservation("suzuki", inst, b)), "本人が取り消せない");
    assert(gone(await h.reservationStatus(inst, a)) && gone(await h.reservationStatus(inst, b)), "取り消した予約が残っている");
  });

  await check("K08", "校正で不合格になり使用停止になったら、これからの予約は取り消しになる", async () => {
    await start();
    const inst = await h.instrument();
    const id = await h.mustReserve("suzuki", inst, d(6), d(7));
    const cal = await h.calibrate(inst, d(-1), "fail");
    assert(cal.status === 201, `校正記録: ${cal.status}`);
    const s = await h.reservationStatus(inst, id);
    assert(gone(s), `予約の状態: ${s}`);
  });

  await check("K09", "校正期限を過ぎる日は予約できない（期限当日まではできる）", async () => {
    await start();
    const inst = await h.instrument({ last: "2026-01-10", interval: 11 }); // 期限 2026-12-31（月末）。月末にしない期限は 2026-12-10
    const ok = await h.reserve("suzuki", inst, "2026-12-29", "2026-12-31");
    assert(is2xx(ok.status), `期限当日まで: ${ok.status} ${JSON.stringify(ok.json)?.slice(0, 200)}`);
    const ng = await h.reserve("tanaka", inst, "2027-01-01", "2027-01-02");
    assert(is4xx(ng.status), `期限の翌日から: ${ng.status}`);
    const ng2 = await h.reserve("tanaka", inst, "2026-12-20", "2027-01-05");
    assert(is4xx(ng2.status), `期限をまたぐ: ${ng2.status}`);
  });

  await h.done();
});
