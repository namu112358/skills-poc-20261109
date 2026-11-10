// W12 の受け入れテスト（課題文に書かれた範囲。試行中は候補に見せない）。項目の定義は grading.md。
// （W16 の後退の確認に使う。W12 の同名のファイル（origin/agent/poc-w12 ab36ab4 の時点）をそのまま写した）
// 使い方: W12_ADAPTER=... W12_NOTIFY=... W12_JOBS_TOKEN=... POC_FAKE_NOW_FILE=... NODE_PATH=$(npm root -g) node public.cjs <base>
const { harness, assert, show, jst } = require("./lib.cjs");

// 初期データの MI-0001（既存の API の応答の形が変わっていないかを見る）
const MI0001 = { managementNo: "MI-0001", name: "デジタルマルチメータ", model: "DMM-7510", location: "品質保証部 測定室",
  managerId: "sato", intervalMonths: 12, lastCalibratedOn: "2026-01-20", status: "in_use", note: "" };

(async () => {
  const h = harness(process.argv[2], "AC");
  const { check, call } = h;
  const sato = await h.login("sato");

  await check("P01", "重要度を付けられ、付けた重要度が API で読める", async () => {
    assert(h.adapter.key && h.adapter.levels?.length >= 2, `重要度の項目が見つからない: ${JSON.stringify(h.adapter)}`);
    const inst = await h.instrument(sato, { last: "2026-10-01", importance: "top" });
    const r = await call(sato, "GET", `/api/instruments/${inst.id}`);
    assert(r.json?.instrument?.[h.adapter.key] === h.level("top"), show(r));
  });

  await check("P02", "重要度が最も高い計測器の校正期限が近づくと、管理者に通知サービスで知らせる", async () => {
    await h.setNow(jst("2027-04-25"));
    const inst = await h.instrument(sato, { managerId: "kato", last: "2026-04-28", importance: "top" }); // 期限は 2027-04-28〜30
    const j = await h.runJob();
    assert(j.status >= 200 && j.status < 300, `ジョブ: ${j.status}`);
    const d = await h.delivered(inst, "kato");
    assert(d.length >= 1, `管理者 kato に届いていない（届いた全件: ${(await h.state()).deliveries.length}）`);
  });

  await check("P03", "既存の API の応答の形が変わらず、重要度を送らない登録も受け付ける", async () => {
    const list = await call(sato, "GET", "/api/instruments");
    assert(Array.isArray(list.json?.instruments), `一覧: ${show(list)}`);
    const seed = list.json.instruments.find((i) => i.managementNo === "MI-0001");
    const one = await call(sato, "GET", `/api/instruments/${seed?.id}`);
    for (const [k, v] of Object.entries(MI0001)) {
      assert(seed?.[k] === v && one.json?.instrument?.[k] === v, `${k}: 一覧=${JSON.stringify(seed?.[k])} 詳細=${JSON.stringify(one.json?.instrument?.[k])}`);
    }
    assert("currentLoan" in (one.json ?? {}), `詳細に currentLoan が無い: ${show(one)}`);
    const r = await call(sato, "POST", "/api/instruments", { managementNo: "AC-0900", name: "旧画面からの登録", managerId: "sato", intervalMonths: 12, lastCalibratedOn: "2026-10-01" });
    assert(r.status === 201, `重要度なしの登録: ${show(r)}`);
  });

  await check("P04", "既存の機能（貸出・返却・校正記録・不合格で使用停止・既存のジョブ）が従来どおり動く", async () => {
    const inst = await h.instrument(sato, { last: "2026-10-01", importance: undefined });
    const lend = await call(sato, "POST", `/api/instruments/${inst.id}/loans`, { borrowerId: "suzuki", dueOn: "2027-12-01" });
    assert(lend.status === 201, `貸出: ${show(lend)}`);
    const ret = await call(sato, "POST", `/api/instruments/${inst.id}/loans/${lend.json.loan.id}/return`);
    assert(ret.status === 200, `返却: ${show(ret)}`);
    const cal = await call(sato, "POST", `/api/instruments/${inst.id}/calibrations`, { calibratedOn: "2026-11-01", result: "fail", agency: "x" });
    assert(cal.status === 201 && cal.json?.instrument?.status === "suspended", `不合格: ${show(cal)}`);
    const c = await h.ctx();
    const job = await c.post("/api/jobs/overdue-loans", { headers: { authorization: `Bearer ${process.env.W12_JOBS_TOKEN}` } });
    assert(job.status() === 200, `overdue-loans: ${job.status()}`);
    const anon = await (await h.ctx()).post("/api/jobs/overdue-loans");
    assert(anon.status() === 401, `overdue-loans（トークンなし）: ${anon.status()}`);
  });

  await h.done();
})().catch((e) => { console.log(JSON.stringify([{ id: "X", name: "public.cjs の実行", pass: false, detail: String(e) }])); });
