// W12 の隠しテスト（依頼者が質問されたら答える「隠れ要件」。試行中は候補に見せない）。項目の定義は grading.md。
// 届いたお知らせは、件名・本文に計測器の管理番号（または名称。名称に管理番号を含めている）があるもので数える。
const { harness, assert, jst } = require("./lib.cjs");

(async () => {
  const h = harness(process.argv[2], "HT");
  const { check } = h;
  const sato = await h.login("sato");
  const count = async (inst, who) => (await h.delivered(inst, who)).length;
  const static_ = JSON.parse(process.env.W12_STATIC || "{}");

  await check("H01", "重要度は 3 段階で、既存の計測器は真ん中（B）になる", async () => {
    const lv = h.adapter.levels || [];
    assert(lv.length === 3, `段階の数: ${JSON.stringify(lv)}`);
    // 既存の計測器の値は、旧 DB にマイグレーションを当てたあとの値（grade_w12.py の default_existing）。無ければ初期データの最頻値
    const def = h.adapter.default_existing !== undefined && h.adapter.default_existing !== null ? h.adapter.default_existing : h.adapter.default;
    assert(def === lv[1], `既存の計測器の重要度: ${JSON.stringify(def)}（段階 ${JSON.stringify(lv)}）`);
  });

  await check("H02", "一覧を重要度で絞り込める（API か画面）", async () => {
    assert(h.adapter.filter?.api || h.adapter.filter?.page, `絞り込み: ${JSON.stringify(h.adapter.filter)}`);
  });

  await check("H03", "校正期限は「前回校正日 + 周期」の月の末日", async () => {
    const inst = await h.instrument(sato, { managerId: "suzuki", last: "2026-02-10" }); // 期限 2027-02-28（月末にしないと 02-10）
    await h.setNow(jst("2027-01-15"));
    await h.runJob();
    const early = await count(inst);
    await h.setNow(jst("2027-02-20"));
    await h.runJob();
    const d = await h.delivered(inst);
    assert(early === 0, `月末にしない期限（02-10）の 30 日前（01-15）に届いた: ${early} 件`);
    assert(d.length >= 1, "期限（02-28）の 8 日前に届いていない");
    const naive = /2027-02-10|2027\/0?2\/10|2月10日/;
    assert(!d.some((x) => naive.test(`${x.title}\n${x.body}`)), `期限を 02-10 としている: ${d[0].title}`);
  });

  await check("H04", "期限の 30 日前から知らせる（31 日前は知らせない）", async () => {
    const inst = await h.instrument(sato, { managerId: "takahashi", last: "2026-01-31" }); // 期限 2027-01-31
    await h.setNow(jst("2026-12-31"));
    await h.runJob();
    const before = await count(inst);
    await h.setNow(jst("2027-01-01"));
    await h.runJob();
    const after = await count(inst);
    assert(before === 0 && after === 1, `31 日前: ${before} 件、30 日前: ${after} 件`);
  });

  await check("H05", "「今日」は日本時間で判断する", async () => {
    const inst = await h.instrument(sato, { managerId: "watanabe", last: "2026-03-31" }); // 期限 2027-03-31、30 日前は 03-01
    await h.setNow("2027-02-28T07:00:00.000Z"); // 日本時間 02-28 16:00
    await h.runJob();
    const before = await count(inst);
    await h.setNow("2027-02-28T15:30:00.000Z"); // 日本時間 03-01 00:30（UTC ではまだ 02-28）
    await h.runJob();
    const after = await count(inst);
    assert(before === 0 && after === 1, `日本時間 02-28: ${before} 件、日本時間 03-01 00:30: ${after} 件`);
  });

  await check("H06", "重要度が最も高いもの（A）だけを知らせる（B・C は知らせない）", async () => {
    const mid = await h.instrument(sato, { managerId: "yamamoto", last: "2026-05-31", importance: "mid" }); // 期限 2027-05-31
    const low = await h.instrument(sato, { managerId: "yamamoto", last: "2026-05-31", importance: "low" });
    const top = await h.instrument(sato, { managerId: "yamamoto", last: "2026-05-31", importance: "top" });
    await h.setNow(jst("2027-05-20"));
    await h.runJob();
    const [m, l, t] = [await count(mid), await count(low), await count(top)];
    assert(t >= 1, `A が届いていない（ジョブが動いていない）`);
    assert(m === 0 && l === 0, `B: ${m} 件、C: ${l} 件`);
  });

  await check("H07", "校正中・使用停止・廃棄・不合格で使用停止になったものには知らせない", async () => {
    const m = "kobayashi";
    const xs = [];
    for (const status of ["calibrating", "suspended", "disposed"]) xs.push([status, await h.instrument(sato, { managerId: m, last: "2026-05-31", status })]);
    const failed = await h.instrument(sato, { managerId: m, last: "2026-05-31" });
    await h.calibrate(sato, failed, "2027-05-10", "fail");
    xs.push(["不合格", failed]);
    const control = await h.instrument(sato, { managerId: m, last: "2026-05-31" });
    await h.setNow(jst("2027-05-21"));
    await h.runJob();
    assert((await count(control)) >= 1, "使用中の A に届いていない");
    const got = [];
    for (const [label, inst] of xs) { const n = await count(inst); if (n) got.push(`${label}: ${n} 件`); }
    assert(got.length === 0, got.join("、"));
  });

  await check("H08", "貸出中なら、管理者に加えて借りている人にも知らせる", async () => {
    const inst = await h.instrument(sato, { managerId: "tanaka", last: "2026-06-30" }); // 期限 2027-06-30
    await h.lend(sato, inst, "matsumoto");
    await h.setNow(jst("2027-06-20"));
    await h.runJob();
    const [a, b] = [await count(inst, "tanaka"), await count(inst, "matsumoto")];
    assert(a >= 1 && b >= 1, `管理者 tanaka: ${a} 件、借りている人 matsumoto: ${b} 件`);
  });

  await check("H09", "同じ期限について、期限が近いお知らせは 1 回だけ", async () => {
    const inst = await h.instrument(sato, { managerId: "kimura", last: "2026-07-31" }); // 期限 2027-07-31
    await h.setNow(jst("2027-07-10"));
    await h.runJob();
    await h.runJob();
    await h.setNow(jst("2027-07-11"));
    await h.runJob();
    const n = await count(inst, "kimura");
    assert(n === 1, `${n} 件`);
  });

  await check("H10", "校正記録で期限が変わったら、新しい期限について改めて知らせる", async () => {
    const inst = await h.instrument(sato, { managerId: "kato", last: "2026-08-31" }); // 期限 2027-08-31
    await h.setNow(jst("2027-08-15"));
    await h.runJob();
    const first = await count(inst);
    await h.calibrate(sato, inst, "2027-08-20"); // 新しい期限 2028-08-31
    await h.setNow(jst("2027-08-21"));
    await h.runJob();
    const afterCal = await count(inst);
    await h.setNow(jst("2028-08-10"));
    await h.runJob();
    const next = await count(inst);
    assert(first === 1 && afterCal === 1 && next === 2, `最初: ${first} 件、校正の翌日: ${afterCal} 件、新しい期限の 21 日前: ${next} 件`);
  });

  await check("H11", "期限を過ぎたら「期限切れ」を 1 回だけ知らせる", async () => {
    const inst = await h.instrument(sato, { managerId: "sasaki", last: "2026-09-30" }); // 期限 2027-09-30
    const counts = [];
    for (const d of ["2027-09-20", "2027-10-01", "2027-10-02", "2027-10-20"]) {
      await h.setNow(jst(d));
      await h.runJob();
      counts.push(await count(inst, "sasaki"));
    }
    assert(JSON.stringify(counts) === "[1,2,2,2]", `件数の推移（09-20, 10-01, 10-02, 10-20）: ${JSON.stringify(counts)}（期待 [1,2,2,2]）`);
  });

  await check("H12", "管理者が無効（退職など）なら、管理者の部署の代表者に知らせる", async () => {
    const inst = await h.instrument(sato, { managerId: "inoue", last: "2026-11-30" }); // 期限 2027-11-30。inoue は製造部（代表者 yamada）
    await h.setNow(jst("2027-11-10"));
    await h.runJob();
    const [rep, gone] = [await count(inst, "yamada"), await count(inst, "inoue")];
    assert(rep >= 1 && gone === 0, `代表者 yamada: ${rep} 件、無効な inoue: ${gone} 件`);
  });

  await check("H13", "定期実行は運用の cron から API を呼ぶ形（JOBS_TOKEN で認証し、アプリの中で定期実行しない）", async () => {
    const j = h.adapter.job || {};
    assert(j.path, "ジョブの API が無い");
    assert([401, 403].includes(j.unauthStatus), `トークンなしで ${j.unauthStatus}`);
    assert(!static_.inProcessScheduler?.length, `アプリの中の定期実行: ${JSON.stringify(static_.inProcessScheduler).slice(0, 200)}`);
  });

  await h.done();
})().catch((e) => { console.log(JSON.stringify([{ id: "X", name: "hidden.cjs の実行", pass: false, detail: String(e) }])); });
