// W18 第 1 回「重要度と校正期限の通知」のテスト（W12 の public.cjs の P01・P02 と hidden.cjs の H01〜H13 を写した）。
// 届いたお知らせは、件名・本文に計測器の管理番号があるもので数える。項目の定義は grading.md。
const { harness, main, assert, show, jst } = require("./lib.cjs");

main("f1.cjs", async () => {
  const h = harness(process.argv[2], "HT");
  const { check } = h;
  const f1 = h.adapter.f1 || {};
  const static_ = JSON.parse(process.env.W18_STATIC || "{}");
  const count = async (inst, who) => (await h.delivered(inst, who)).length;
  const inst = (o) => h.instrument({ managerId: "sato", importance: "top", ...o });

  await check("P01", "重要度を付けられ、付けた重要度が API で読める", async () => {
    assert(f1.key && f1.levels?.length >= 2, `重要度の項目が見つからない: ${JSON.stringify(f1)}`);
    const i = await inst({ last: "2026-10-01" });
    const r = await h.getInstrument(i);
    assert(r.instrument?.[f1.key] === h.level("top"), show(r));
  });

  await check("P02", "重要度が最も高い計測器の校正期限が近づくと、管理者に通知サービスで知らせる", async () => {
    await h.setNow(jst("2027-04-25"));
    const i = await inst({ managerId: "kato", last: "2026-04-28" }); // 期限は 2027-04-28〜30
    const s = await h.runReminders();
    assert(s >= 200 && s < 300, `ジョブ: ${s}`);
    assert((await count(i, "kato")) >= 1, "管理者 kato に届いていない");
  });

  await check("H01", "重要度は 3 段階で、既存の計測器は真ん中（B）になる", async () => {
    const lv = f1.levels || [];
    assert(lv.length === 3, `段階の数: ${JSON.stringify(lv)}`);
    const list = await h.call("sato", "GET", "/api/instruments");
    const seed = (list.json?.instruments || []).filter((i) => /^MI-00(0[1-9]|10)$/.test(i.managementNo));
    const vals = seed.map((i) => i[f1.key]);
    const mid = vals.filter((v) => JSON.stringify(v) === JSON.stringify(lv[1])).length;
    assert(mid >= seed.length / 2 && seed.length === 10, `初期データの重要度: ${JSON.stringify(vals)}（段階 ${JSON.stringify(lv)}）`);
  });

  await check("H02", "一覧を重要度で絞り込める（API）", async () => {
    const top = await inst({ last: "2026-10-01" });
    const param = f1.filter?.param;
    assert(param, "絞り込みの項目が見つからない（アダプター）");
    const r = await h.call("sato", "GET", `/api/instruments?${param}=${encodeURIComponent(String(h.level("top")))}`);
    const xs = r.json?.instruments || [];
    assert(xs.some((i) => i.id === top.id) && xs.every((i) => i[f1.key] === h.level("top")) && !xs.some((i) => i.managementNo === "MI-0001"),
      `絞り込み: ${show(r)}`);
  });

  await check("H03", "校正期限は「前回校正日 + 周期」の月の末日", async () => {
    const i = await inst({ managerId: "suzuki", last: "2026-02-10" }); // 期限 2027-02-28
    await h.setNow(jst("2027-01-15"));
    await h.runReminders();
    const early = await count(i);
    await h.setNow(jst("2027-02-20"));
    await h.runReminders();
    const d = await h.delivered(i);
    assert(early === 0, `月末にしない期限（02-10）の 30 日前（01-15）に届いた: ${early} 件`);
    assert(d.length >= 1, "期限（02-28）の 8 日前に届いていない");
    assert(!d.some((x) => /2027-02-10|2027\/0?2\/10|2月10日/.test(`${x.title}\n${x.body}`)), `期限を 02-10 としている: ${d[0].title}`);
  });

  await check("H04", "期限の 30 日前から知らせる（31 日前は知らせない）", async () => {
    const i = await inst({ managerId: "takahashi", last: "2026-01-31" }); // 期限 2027-01-31
    await h.setNow(jst("2026-12-31"));
    await h.runReminders();
    const before = await count(i);
    await h.setNow(jst("2027-01-01"));
    await h.runReminders();
    const after = await count(i);
    assert(before === 0 && after === 1, `31 日前: ${before} 件、30 日前: ${after} 件`);
  });

  await check("H05", "「今日」は日本時間で判断する", async () => {
    const i = await inst({ managerId: "watanabe", last: "2026-03-31" }); // 期限 2027-03-31、30 日前は 03-01
    await h.setNow("2027-02-28T07:00:00.000Z");
    await h.runReminders();
    const before = await count(i);
    await h.setNow("2027-02-28T15:30:00.000Z"); // 日本時間 03-01 00:30
    await h.runReminders();
    const after = await count(i);
    assert(before === 0 && after === 1, `日本時間 02-28: ${before} 件、日本時間 03-01 00:30: ${after} 件`);
  });

  await check("H06", "重要度が最も高いもの（A）だけを知らせる（B・C は知らせない）", async () => {
    const mid = await inst({ managerId: "yamamoto", last: "2026-05-31", importance: "mid" });
    const low = await inst({ managerId: "yamamoto", last: "2026-05-31", importance: "low" });
    const top = await inst({ managerId: "yamamoto", last: "2026-05-31" });
    await h.setNow(jst("2027-05-20"));
    await h.runReminders();
    const [m, l, t] = [await count(mid), await count(low), await count(top)];
    assert(t >= 1, "A が届いていない（ジョブが動いていない）");
    assert(m === 0 && l === 0, `B: ${m} 件、C: ${l} 件`);
  });

  await check("H07", "校正中・使用停止・廃棄・不合格で使用停止になったものには知らせない", async () => {
    const xs = [];
    for (const status of ["calibrating", "suspended", "disposed"]) xs.push([status, await inst({ managerId: "kobayashi", last: "2026-05-31", status })]);
    const failed = await inst({ managerId: "kobayashi", last: "2026-05-31" });
    await h.setNow(jst("2027-05-10"));
    const cal = await h.calibrate(failed, "2027-05-10", "fail");
    assert(cal.status === 201, `校正記録: ${show(cal)}`);
    xs.push(["不合格", failed]);
    const control = await inst({ managerId: "kobayashi", last: "2026-05-31" });
    await h.setNow(jst("2027-05-21"));
    await h.runReminders();
    assert((await count(control)) >= 1, "使用中の A に届いていない");
    const got = [];
    for (const [label, i] of xs) { const n = await count(i); if (n) got.push(`${label}: ${n} 件`); }
    assert(got.length === 0, got.join("、"));
  });

  await check("H08", "貸出中なら、管理者に加えて借りている人にも知らせる", async () => {
    const i = await inst({ managerId: "tanaka", last: "2026-06-30" }); // 期限 2027-06-30
    await h.setNow(jst("2027-06-01"));
    const l = await h.lend(i, "matsumoto", "2027-07-31");
    assert(l.status === 201, `貸出: ${l.status} ${JSON.stringify(l.json)}`);
    await h.setNow(jst("2027-06-20"));
    await h.runReminders();
    const [a, b] = [await count(i, "tanaka"), await count(i, "matsumoto")];
    assert(a >= 1 && b >= 1, `管理者 tanaka: ${a} 件、借りている人 matsumoto: ${b} 件`);
  });

  await check("H09", "同じ期限について、期限が近いお知らせは 1 回だけ", async () => {
    const i = await inst({ managerId: "kimura", last: "2026-07-31" });
    await h.setNow(jst("2027-07-10"));
    await h.runReminders();
    await h.runReminders();
    await h.setNow(jst("2027-07-11"));
    await h.runReminders();
    const n = await count(i, "kimura");
    assert(n === 1, `${n} 件`);
  });

  await check("H10", "校正記録で期限が変わったら、新しい期限について改めて知らせる", async () => {
    const i = await inst({ managerId: "kato", last: "2026-08-31" }); // 期限 2027-08-31
    await h.setNow(jst("2027-08-15"));
    await h.runReminders();
    const first = await count(i);
    await h.calibrate(i, "2027-08-20"); // 新しい期限 2028-08-31
    await h.setNow(jst("2027-08-21"));
    await h.runReminders();
    const afterCal = await count(i);
    await h.setNow(jst("2028-08-10"));
    await h.runReminders();
    const next = await count(i);
    assert(first === 1 && afterCal === 1 && next === 2, `最初: ${first} 件、校正の翌日: ${afterCal} 件、新しい期限の 21 日前: ${next} 件`);
  });

  await check("H11", "期限を過ぎたら「期限切れ」を 1 回だけ知らせる", async () => {
    const i = await inst({ managerId: "sasaki", last: "2026-09-30" }); // 期限 2027-09-30
    const counts = [];
    for (const d of ["2027-09-20", "2027-10-01", "2027-10-02", "2027-10-20"]) {
      await h.setNow(jst(d));
      await h.runReminders();
      counts.push(await count(i, "sasaki"));
    }
    assert(JSON.stringify(counts) === "[1,2,2,2]", `件数の推移（09-20, 10-01, 10-02, 10-20）: ${JSON.stringify(counts)}（期待 [1,2,2,2]）`);
  });

  await check("H12", "管理者が無効（退職など）なら、管理者の部署の代表者に知らせる", async () => {
    const i = await inst({ managerId: "inoue", last: "2026-11-30" }); // inoue は製造部（代表者 yamada）
    await h.setNow(jst("2027-11-10"));
    await h.runReminders();
    const [rep, goneUser] = [await count(i, "yamada"), await count(i, "inoue")];
    assert(rep >= 1 && goneUser === 0, `代表者 yamada: ${rep} 件、無効な inoue: ${goneUser} 件`);
  });

  await check("H13", "定期実行は運用の cron から API を呼ぶ形（JOBS_TOKEN で認証し、アプリの中で定期実行しない）", async () => {
    assert(f1.job?.path, "ジョブの API が無い");
    const anon = await (await h.ctx()).fetch(f1.job.path, { method: f1.job.method || "POST" });
    assert([401, 403].includes(anon.status()), `トークンなしで ${anon.status()}`);
    assert(!static_.inProcessScheduler?.length, `アプリの中の定期実行: ${JSON.stringify(static_.inProcessScheduler).slice(0, 200)}`);
  });

  await h.done();
});
