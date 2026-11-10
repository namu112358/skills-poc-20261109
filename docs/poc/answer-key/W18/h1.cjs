// W18 引き継ぎ h1「副管理者」（横断的な仕様変更）のテスト。依頼文は docs/poc/tasks/wf-W18h1.md。項目の定義は grading.md。
const { harness, main, assert, show, jst, addDays, sleep, is2xx, is4xx } = require("./lib.cjs");

const T = "2026-11-10";
const d = (n) => addDays(T, n);
const has = (entries, ...words) => entries.some((e) => words.every((w) => JSON.stringify(e).includes(String(w))));

main("h1.cjs", async () => {
  const h = harness(process.argv[2], "SM");
  const { check } = h;
  const field = h.adapter.h1?.field;
  const start = async () => h.setNow(jst(T, "10:00"));
  const subOf = async (inst) => (await h.getInstrument(inst)).instrument?.[field];

  await check("S01", "副管理者を設定・変更・解除でき、API で読める。無効な人・管理者と同じ人は設定できない", async () => {
    await start();
    assert(field, "副管理者の項目が見つからない（アダプター）");
    const inst = await h.instrument({ managerId: "suzuki" });
    assert(is2xx((await h.setSubManager(inst, "watanabe")).status) && (await subOf(inst)) === "watanabe", `設定: ${await subOf(inst)}`);
    const list = await h.call("sato", "GET", "/api/instruments");
    assert((list.json?.instruments || []).find((i) => i.id === inst.id)?.[field] === "watanabe", "一覧で読めない");
    assert(is2xx((await h.setSubManager(inst, "ito")).status) && (await subOf(inst)) === "ito", "変更");
    assert(is4xx((await h.setSubManager(inst, "inoue")).status), "無効な人を設定できた");
    assert(is4xx((await h.setSubManager(inst, "suzuki")).status), "管理者と同じ人を設定できた");
    assert((await subOf(inst)) === "ito", `断った設定が反映された: ${await subOf(inst)}`);
    assert(is2xx((await h.setSubManager(inst, null)).status) && !(await subOf(inst)), `解除: ${await subOf(inst)}`);
  });

  await check("S02", "校正期限のお知らせが、管理者に加えて副管理者にも届く", async () => {
    const inst = await h.instrument({ managerId: "kato", importance: "top", last: "2026-04-30" }); // 期限 2027-04-30
    assert(is2xx((await h.setSubManager(inst, "tanaka")).status), "設定");
    await h.setNow(jst("2027-04-20"));
    await h.runReminders();
    const [m, s] = [(await h.delivered(inst, "kato")).length, (await h.delivered(inst, "tanaka")).length];
    assert(m >= 1 && s >= 1, `管理者 kato: ${m} 件、副管理者 tanaka: ${s} 件`);
  });

  await check("S03", "副管理者は、管理者と同じように他人の予約を取り消せる", async () => {
    await start();
    const inst = await h.instrument({ managerId: "kato" });
    await h.setSubManager(inst, "yamamoto");
    const rid = await h.mustReserve("suzuki", inst, d(4), d(5));
    assert(is4xx(await h.cancelReservation("kobayashi", inst, rid)), "ほかの人が取り消せた");
    assert(is2xx(await h.cancelReservation("yamamoto", inst, rid)), "副管理者が取り消せない");
    assert(h.gone(await h.reservationStatus(inst, rid)), "取り消されていない");
  });

  await check("S04", "副管理者は、ほかの部署の人でも、その計測器の編集・校正記録・発注・貸出・返却ができる（ほかの人は今までどおりできない）", async () => {
    await start();
    const inst = await h.instrument({ managerId: "suzuki" }); // 製造部
    await h.setSubManager(inst, "sasaki"); // 工事部
    assert((await h.patch(inst, { note: "副管理者が編集" }, "sasaki")).status === 200, "副管理者の編集");
    assert(is4xx((await h.patch(inst, { note: "ほかの人" }, "shimizu")).status), "工事部のほかの人が編集できた");
    const l = await h.lend(inst, "matsumoto", d(2), "sasaki");
    assert(l.status === 201, `副管理者の貸出: ${l.status}`);
    assert((await h.returnLoan(inst, l.loanId, "sasaki")) === 200, "副管理者の返却");
    const c = await h.calibrate(inst, d(-1), "pass", "sasaki");
    assert(c.status === 201, `副管理者の校正記録: ${show(c)}`);
    const o = await h.order(inst, "sasaki");
    assert(is2xx(o.status), `副管理者の発注: ${show(o)}`);
  });

  await check("S05", "副管理者の設定・変更・解除が変更履歴に残る", async () => {
    await start();
    const inst = await h.instrument({ managerId: "kato" });
    const a = await h.newHistory(inst, () => h.setSubManager(inst, "hayashi", "kimura"));
    assert(has(a.added, "kimura", "hayashi"), `設定: ${JSON.stringify(a.added).slice(0, 300)}`);
    const b = await h.newHistory(inst, () => h.setSubManager(inst, null, "kimura"));
    assert(b.added.length >= 1 && has(b.added, "hayashi"), `解除: ${JSON.stringify(b.added).slice(0, 300)}`);
  });

  await check("S06", "副管理者を決めていない計測器は今までどおり（お知らせは管理者だけ、他部署は編集できない）", async () => {
    const inst = await h.instrument({ managerId: "yamada", importance: "top", last: "2026-06-30" }); // 製造部
    assert(!(await subOf(inst)), `副管理者の初期値: ${await subOf(inst)}`);
    assert(is4xx((await h.patch(inst, { note: "他部署" }, "sasaki")).status), "他部署が編集できた");
    await h.setNow(jst("2027-06-20"));
    await h.runReminders();
    const st = await h.notifyState();
    const to = [...new Set(st.deliveries.filter((x) => `${x.title}\n${x.body}`.includes(inst.no)).map((x) => x.recipient))];
    assert(JSON.stringify(to) === '["yamada"]', `送り先: ${JSON.stringify(to)}`);
  });

  await h.done();
});
