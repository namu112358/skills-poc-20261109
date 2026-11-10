// W18 第 4 回「外部の校正機関への発注連携」のテスト。受付システムは偽物（fake-agency.cjs）。項目の定義は grading.md。
const { harness, main, assert, show, jst, addDays, sleep, is2xx, is4xx } = require("./lib.cjs");

const T = "2026-11-10";
const d = (n) => addDays(T, n);

main("f4.cjs", async () => {
  const h = harness(process.argv[2], "OD");
  const { check } = h;
  const start = async () => h.setNow(jst(T, "10:00"));
  const statusOf = async (inst) => (await h.getInstrument(inst)).instrument?.status;
  const open = (o) => o.status === "pending" || o.status === "accepted";

  await check("O01", "使用中の計測器を発注でき、受付システムに 1 件届き（管理番号・名称・型式・発注者）、計測器は校正中、受付番号と返却予定日が読める", async () => {
    await start();
    const inst = await h.instrument({ model: "OD-MODEL-1" });
    const r = await h.order(inst, "sato");
    assert(is2xx(r.status), `発注: ${show(r)}`);
    await sleep(1500);
    const got = await h.agencyOrders(inst);
    assert(got.length === 1, `受付システムの発注: ${got.length} 件`);
    assert(got[0].item?.name === `検証用計測器 ${inst.no}` && got[0].item?.model === "OD-MODEL-1" && got[0].requestedBy === "sato",
      `送った内容: ${JSON.stringify(got[0]).slice(0, 300)}`);
    assert((await statusOf(inst)) === "calibrating", `計測器の状態: ${await statusOf(inst)}`);
    const os = await h.orders(inst);
    assert(os.length === 1 && os[0].status === "accepted", `発注の状況: ${JSON.stringify(os.map((o) => o.status))}`);
    assert(os[0].externalId === got[0].orderId && os[0].returnOn === got[0].estimatedReturnOn,
      `受付番号・返却予定日: ${JSON.stringify([os[0].externalId, os[0].returnOn])}（受付 ${got[0].orderId} ${got[0].estimatedReturnOn}）`);
  });

  await check("O02", "貸出中・校正中・廃棄の計測器は発注できず、使用停止の計測器はできる", async () => {
    await start();
    const loaned = await h.instrument();
    assert((await h.lend(loaned, "suzuki", d(3))).status === 201, "貸出");
    const xs = [["貸出中", loaned], ["校正中", await h.instrument({ status: "calibrating" })], ["廃棄", await h.instrument({ status: "disposed" })]];
    const bad = [];
    for (const [label, inst] of xs) { const r = await h.order(inst); if (!is4xx(r.status)) bad.push(`${label}: ${r.status}`); }
    assert(bad.length === 0, bad.join("、"));
    assert((await h.agencyOrders(xs[0][1])).length === 0, "受付システムに送られた");
    const suspended = await h.instrument({ status: "suspended" });
    const ok = await h.order(suspended);
    assert(is2xx(ok.status), `使用停止: ${show(ok)}`);
  });

  await check("O03", "受付システムが止まっていても発注は受け付けて未送信で残り、戻った後のジョブで送られる", async () => {
    await start();
    const inst = await h.instrument();
    await h.agencyMode(true);
    let r;
    try {
      r = await h.order(inst);
    } finally {
      await h.agencyMode(false);
    }
    assert(is2xx(r.status), `止まっている間の発注: ${show(r)}`);
    const os = await h.orders(inst);
    assert(os.length === 1 && os[0].status === "pending", `発注の状況: ${JSON.stringify(os.map((o) => o.status))}`);
    assert((await h.agencyOrders(inst)).length === 0, "受け付けられている");
    const s = await h.runOrderJob();
    assert(is2xx(s), `ジョブ: ${s}`);
    await sleep(1500);
    assert((await h.agencyOrders(inst)).length === 1, `ジョブの後の受付: ${(await h.agencyOrders(inst)).length} 件`);
    assert((await h.orders(inst))[0].status === "accepted", `ジョブの後の状況: ${(await h.orders(inst))[0].status}`);
  });

  await check("O04", "受付システムが受け付けた後に応答が返らなくても、送り直しで二重に発注しない", async () => {
    await start();
    const inst = await h.instrument();
    await h.agencyScript(inst.no, ["process_then_hang"]);
    const r = await h.order(inst);
    assert(is2xx(r.status) || r.status >= 500, `発注: ${show(r)}`);
    for (let i = 0; i < 2; i++) { await h.runOrderJob(); await sleep(500); }
    const got = await h.agencyOrders(inst);
    assert(got.length === 1, `受付システムの発注: ${got.length} 件`);
    const os = await h.orders(inst);
    assert(os.length === 1 && os[0].status === "accepted" && os[0].externalId === got[0].orderId,
      `発注の状況: ${JSON.stringify(os.map((o) => [o.status, o.externalId]))}`);
  });

  await check("O05", "発注すると、その計測器のこれからの予約が取り消され、予約した人に通知サービスで知らせる", async () => {
    await start();
    const inst = await h.instrument();
    const id = await h.mustReserve("suzuki", inst, d(5), d(6));
    const r = await h.order(inst);
    assert(is2xx(r.status), `発注: ${show(r)}`);
    await sleep(1500);
    assert(h.gone(await h.reservationStatus(inst, id)), `予約の状態: ${await h.reservationStatus(inst, id)}`);
    const n = await h.delivered(inst, "suzuki");
    assert(n.length >= 1, "予約した人に届いていない");
  });

  await check("O06", "1 台に進行中の発注は 1 件だけ", async () => {
    await start();
    const inst = await h.instrument();
    assert(is2xx((await h.order(inst)).status), "1 件目");
    await h.patch(inst, { status: "suspended" });
    const second = await h.order(inst);
    assert(is4xx(second.status), `2 件目: ${show(second)}`);
    assert((await h.agencyOrders(inst)).length === 1, `受付システムの発注: ${(await h.agencyOrders(inst)).length} 件`);
  });

  await check("O07", "校正記録を登録すると発注は完了になり、再び発注できる", async () => {
    await start();
    const inst = await h.instrument();
    assert(is2xx((await h.order(inst)).status), "発注");
    const cal = await h.calibrate(inst, d(0), "pass");
    assert(cal.status === 201, `校正記録: ${show(cal)}`);
    const os = await h.orders(inst);
    assert(os.length === 1 && !open(os[0]) && os[0].status === "completed", `校正の後の発注: ${JSON.stringify(os.map((o) => o.status))}`);
    assert((await statusOf(inst)) === "in_use", `計測器の状態: ${await statusOf(inst)}`);
    assert(is2xx((await h.order(inst)).status), "再びの発注");
  });

  await check("O08", "発注の送り直しのジョブは JOBS_TOKEN で認証し、受付システムの 400 は送り直さない", async () => {
    await start();
    const job = h.adapter.f4?.job;
    assert(job?.path, "ジョブの API が無い");
    const anon = await (await h.ctx()).fetch(job.path, { method: job.method || "POST" });
    assert([401, 403].includes(anon.status()), `トークンなしで ${anon.status()}`);
    const inst = await h.instrument();
    await h.agencyScript(inst.no, [{ status: 400 }]);
    await h.order(inst);
    await h.runOrderJob();
    await h.runOrderJob();
    const tries = (await h.agencyState()).requests.filter((r) => r.managementNo === inst.no).length;
    assert(tries === 1, `400 の発注を送った回数: ${tries}`);
  });

  await h.done();
});
