// W18: 初期状態からある機能の後退テスト（各回の後に毎回行う。試行中は候補に見せない）。項目の定義は grading.md。
// W12 の P03・P04、W13 の P02 と同じ内容。
const { harness, main, assert, show, jst } = require("./lib.cjs");

// 初期データの MI-0001（既存の API の応答の形が変わっていないかを見る）
const MI0001 = { managementNo: "MI-0001", name: "デジタルマルチメータ", model: "DMM-7510", location: "品質保証部 測定室",
  managerId: "sato", intervalMonths: 12, lastCalibratedOn: "2026-01-20", status: "in_use", note: "" };

main("base.cjs", async () => {
  const h = harness(process.argv[2], "BS");
  const { check, call } = h;
  await h.setNow(jst("2026-11-10"));

  await check("B01", "既存の API の応答の形（一覧・詳細の各項目、詳細の currentLoan）が変わらない", async () => {
    const list = await call("sato", "GET", "/api/instruments");
    assert(Array.isArray(list.json?.instruments), `一覧: ${show(list)}`);
    const seed = list.json.instruments.find((i) => i.managementNo === "MI-0001");
    const one = await call("sato", "GET", `/api/instruments/${seed?.id}`);
    for (const [k, v] of Object.entries(MI0001)) {
      assert(seed?.[k] === v && one.json?.instrument?.[k] === v, `${k}: 一覧=${JSON.stringify(seed?.[k])} 詳細=${JSON.stringify(one.json?.instrument?.[k])}`);
    }
    assert("currentLoan" in (one.json ?? {}), `詳細に currentLoan が無い: ${show(one)}`);
  });

  await check("B02", "既存の機能（登録・編集・貸出・返却・校正記録・不合格で使用停止・既存のジョブとその認証）が従来どおり動く", async () => {
    const inst = await h.instrument({ managerId: "sato" });
    const e = await h.patch(inst, { note: "後退テスト" });
    assert(e.status === 200 && e.json?.instrument?.note === "後退テスト", `編集: ${show(e)}`);
    const lend = await h.lend(inst, "suzuki", "2026-11-20");
    assert(lend.status === 201, `貸出: ${lend.status} ${JSON.stringify(lend.json)}`);
    assert((await h.returnLoan(inst, lend.loanId)) === 200, "返却");
    const cal = await h.calibrate(inst, "2026-11-01", "fail");
    assert(cal.status === 201 && cal.json?.instrument?.status === "suspended", `不合格: ${show(cal)}`);
    const c = await h.ctx();
    const job = await c.post("/api/jobs/overdue-loans", { headers: { authorization: `Bearer ${process.env.W18_JOBS_TOKEN}` } });
    assert(job.status() === 200, `overdue-loans: ${job.status()}`);
    const anon = await (await h.ctx()).post("/api/jobs/overdue-loans");
    assert(anon.status() === 401, `overdue-loans（トークンなし）: ${anon.status()}`);
  });

  await h.done();
});
