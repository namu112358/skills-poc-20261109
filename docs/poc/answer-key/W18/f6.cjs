// W18 第 6 回「部署ごとの権限」のテスト。項目の定義は grading.md。
// 部署: 品質保証部 qa（sato・kimura・takahashi・kato・hayashi）、製造部 mfg（suzuki・yamada・ito・watanabe・yoshida、inoue は無効）、
//       工事部 field（tanaka・sasaki・yamamoto・kobayashi・matsumoto・shimizu、kondo は無効）
const { harness, main, assert, show, jst, addDays, is2xx, is4xx } = require("./lib.cjs");

const T = "2026-11-10";
const d = (n) => addDays(T, n);

main("f6.cjs", async () => {
  const h = harness(process.argv[2], "GP");
  const { check, call } = h;
  const start = async () => h.setNow(jst(T, "10:00"));
  const noteOf = async (inst) => (await h.getInstrument(inst)).instrument?.note;
  const denied = [];
  const deny = (r, what) => { denied.push([what, r.status ?? r]); return is4xx(r.status ?? r); };

  await check("G01", "台帳の編集は、管理部署（管理者の部署）の人と品質保証部の人だけ", async () => {
    await start();
    const inst = await h.instrument({ managerId: "suzuki" }); // 製造部
    assert(deny(await h.patch(inst, { note: "工事部が編集" }, "tanaka"), "他部署の編集"), "他部署の人が編集できた");
    assert((await noteOf(inst)) !== "工事部が編集", "他部署の編集が反映された");
    const f1 = h.adapter.f1 || {};
    if (f1.key) assert(deny(await h.patch(inst, { [f1.key]: h.level("top") }, "tanaka"), "他部署の重要度の変更"), "他部署が重要度を変えられた");
    assert(deny(await h.patch(inst, { status: "disposed" }, "tanaka"), "他部署の状態の変更"), "他部署が状態を変えられた");
    assert((await h.patch(inst, { note: "製造部が編集" }, "watanabe")).status === 200, "管理部署の人が編集できない");
    assert((await h.patch(inst, { note: "品証が編集" }, "kimura")).status === 200, "品質保証部が編集できない");
  });

  await check("G02", "計測器の登録は品質保証部だけ", async () => {
    await start();
    const body = (no) => ({ managementNo: no, name: "権限テスト", managerId: "suzuki", intervalMonths: 12, lastCalibratedOn: "2026-10-01" });
    const stamp = String(Date.now()).slice(-3);
    assert(deny(await call("watanabe", "POST", "/api/instruments", body(`GQ-1${stamp}`)), "製造部の登録"), "製造部が登録できた");
    const ok = await call("kimura", "POST", "/api/instruments", body(`GQ-2${stamp}`));
    assert(ok.status === 201, `品質保証部の登録: ${show(ok)}`);
  });

  await check("G03", "校正記録の登録と校正の発注は、管理部署と品質保証部だけ", async () => {
    await start();
    const inst = await h.instrument({ managerId: "suzuki" });
    assert(deny(await h.calibrate(inst, d(-1), "fail", "tanaka"), "他部署の校正記録"), "他部署が校正記録を登録できた");
    assert((await h.getInstrument(inst)).instrument?.status === "in_use", "他部署の不合格で使用停止になった");
    const ok = await h.calibrate(inst, d(-1), "pass", "yoshida");
    assert(ok.status === 201, `管理部署の校正記録: ${show(ok)}`);
    assert(deny(await h.order(inst, "tanaka"), "他部署の発注"), "他部署が発注できた");
    assert((await h.agencyOrders(inst)).length === 0, "他部署の発注が受付システムに送られた");
    const o = await h.order(inst, "ito");
    assert(is2xx(o.status), `管理部署の発注: ${show(o)}`);
  });

  await check("G04", "貸出・返却は、管理部署と品質保証部だけ", async () => {
    await start();
    const inst = await h.instrument({ managerId: "suzuki" });
    assert(deny(await h.lend(inst, "tanaka", d(3), "tanaka"), "他部署の貸出"), "他部署が貸し出せた");
    const l = await h.lend(inst, "tanaka", d(3), "ito");
    assert(l.status === 201, `管理部署の貸出: ${l.status}`);
    assert(deny(await h.returnLoan(inst, l.loanId, "tanaka"), "他部署の返却"), "他部署が返却できた");
    assert((await h.returnLoan(inst, l.loanId, "watanabe")) === 200, "管理部署が返却できない");
  });

  await check("G05", "閲覧（一覧・詳細・履歴）と、予約（作成・自分の予約の取消）は全員ができる", async () => {
    await start();
    const inst = await h.instrument({ managerId: "suzuki" });
    assert((await call("tanaka", "GET", "/api/instruments")).status === 200, "一覧");
    assert((await call("tanaka", "GET", `/api/instruments/${inst.id}`)).status === 200, "詳細");
    if (h.adapter.f5?.list) assert((await h.history(inst, "tanaka")).length >= 0, "履歴");
    const rid = await h.mustReserve("tanaka", inst, d(5), d(6));
    assert(is2xx(await h.cancelReservation("tanaka", inst, rid)), "自分の予約の取消");
  });

  await check("G06", "設置場所の一覧の追加・名前の変更は品質保証部だけ", async () => {
    await start();
    const stamp = String(Date.now()).slice(-6);
    assert(deny(await h.createLocation(`製造部が足す場所 ${stamp}`, "watanabe"), "製造部の場所の追加"), "製造部が場所を追加できた");
    const id = await h.locationId(`品証の場所 ${stamp}`);
    const r = await h.op(h.adapter.f3?.rename, "watanabe", { locationId: id, name: `製造部が変えた名前 ${stamp}` });
    assert(r && deny(r, "製造部の場所の名前の変更"), `製造部が名前を変えられた: ${r ? show(r) : "-"}`);
    assert(!(await h.locations()).some((l) => String(l.name).includes("製造部が")), "製造部の変更が反映された");
  });

  await check("G07", "管理部署は管理者の部署で決まる（管理者が無効でもその部署。管理者を変えると管理部署も変わる）", async () => {
    await start();
    const inst = await h.instrument({ managerId: "inoue" }); // 製造部・無効
    assert((await h.patch(inst, { note: "製造部" }, "yoshida")).status === 200, "無効な管理者の部署の人が編集できない");
    assert(deny(await h.patch(inst, { note: "工事部" }, "matsumoto"), "他部署"), "他部署が編集できた");
    assert((await h.patch(inst, { managerId: "tanaka" }, "kimura")).status === 200, "管理者の変更");
    assert((await h.patch(inst, { note: "工事部に移った" }, "matsumoto")).status === 200, "新しい管理部署の人が編集できない");
    assert(deny(await h.patch(inst, { note: "元の部署" }, "yoshida"), "元の部署"), "元の管理部署の人が編集できた");
  });

  await check("G08", "権限が無い操作は 403 で断り、定期実行のジョブは JOBS_TOKEN で今までどおり動く", async () => {
    const bad = denied.filter(([, s]) => s !== 403);
    assert(denied.length > 0 && bad.length === 0, `403 以外: ${JSON.stringify(bad).slice(0, 300)}`);
    for (const job of [h.adapter.f1?.job, h.adapter.f4?.job, { path: "/api/jobs/overdue-loans" }]) {
      if (!job?.path) continue;
      const s = await h.runJob(job, 0);
      assert(is2xx(s), `${job.path}: ${s}`);
    }
  });

  await h.done();
});
