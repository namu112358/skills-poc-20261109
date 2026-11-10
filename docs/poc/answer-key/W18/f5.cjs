// W18 第 5 回「変更履歴（監査ログ）」のテスト。履歴の形は候補ごとに違うため、操作の前後で増えた履歴の JSON に、
// 誰が（利用者 ID）・何を（値）が入っているかで確かめる。項目の定義は grading.md。
const { harness, main, assert, show, jst, addDays, sleep, is2xx, is4xx, pick } = require("./lib.cjs");

const T = "2026-11-10";
const d = (n) => addDays(T, n);
const has = (entries, ...words) => entries.some((e) => words.every((w) => JSON.stringify(e).includes(String(w))));
const dump = (xs) => JSON.stringify(xs).slice(0, 400);

main("f5.cjs", async () => {
  const h = harness(process.argv[2], "AU");
  const { check } = h;
  const f5 = h.adapter.f5 || {};
  const start = async () => h.setNow(jst(T, "10:00"));

  await check("A01", "台帳の項目を編集すると、誰が・どの項目を・何から何に変えたかが残る", async () => {
    await start();
    const inst = await h.instrument({ managerId: "kato" });
    const { added } = await h.newHistory(inst, () => h.patch(inst, { name: `改名後 ${inst.no}`, note: "監査テスト" }, "kimura"));
    assert(added.length >= 1, "履歴が増えていない");
    assert(has(added, "kimura", `検証用計測器 ${inst.no}`, `改名後 ${inst.no}`), `名称の変更前後と変更した人: ${dump(added)}`);
    assert(has(added, "監査テスト"), `備考の変更: ${dump(added)}`);
  });

  await check("A02", "登録と、重要度・設置場所の変更が残る（設置場所は名前で）", async () => {
    await start();
    const inst = await h.instrument({ managerId: "kato" });
    const all = await h.history(inst);
    assert(has(all, "sato", inst.no), `登録の履歴: ${dump(all)}`);
    const f1 = h.adapter.f1 || {};
    const { added } = await h.newHistory(inst, () => h.patch(inst, { [f1.key]: h.level("top") }, "sato"));
    assert(has(added, "sato", h.level("top")), `重要度の変更: ${dump(added)}`);
    await h.locationId("監査室");
    const { added: moved } = await h.newHistory(inst, async () => h.patch(inst, await h.locationBody("監査室"), "sato"));
    assert(has(moved, "検証室", "監査室"), `設置場所の変更（名前）: ${dump(moved)}`);
  });

  await check("A03", "貸出と返却が残る（借りた人が分かる）", async () => {
    await start();
    const inst = await h.instrument();
    let loanId;
    const { added } = await h.newHistory(inst, async () => { loanId = (await h.lend(inst, "matsumoto", d(3), "kato")).loanId; });
    assert(has(added, "kato", "matsumoto"), `貸出: ${dump(added)}`);
    const { added: back } = await h.newHistory(inst, () => h.returnLoan(inst, loanId, "kimura"));
    assert(back.length >= 1 && has(back, "kimura"), `返却: ${dump(back)}`);
  });

  await check("A04", "校正記録の登録と、それによる状態の変化（不合格で使用停止）が残る", async () => {
    await start();
    const inst = await h.instrument();
    const { added } = await h.newHistory(inst, () => h.calibrate(inst, d(-1), "fail", "kimura"));
    assert(has(added, "kimura") && (has(added, "suspended") || has(added, "使用停止")), `校正記録: ${dump(added)}`);
  });

  await check("A05", "予約の作成と取消が残る（予約した人・取り消した人が分かる）", async () => {
    await start();
    const inst = await h.instrument({ managerId: "kato" });
    let rid;
    const { added } = await h.newHistory(inst, async () => { rid = await h.mustReserve("suzuki", inst, d(4), d(5)); });
    assert(has(added, "suzuki", d(4)), `予約: ${dump(added)}`);
    const { added: c } = await h.newHistory(inst, () => h.cancelReservation("kato", inst, rid));
    assert(c.length >= 1 && has(c, "kato"), `取消: ${dump(c)}`);
  });

  await check("A06", "発注と、受付システムが受け付けたことが残る", async () => {
    await start();
    const inst = await h.instrument();
    const { added } = await h.newHistory(inst, async () => { await h.order(inst, "kato"); await sleep(1500); });
    const got = await h.agencyOrders(inst);
    assert(has(added, "kato"), `発注: ${dump(added)}`);
    assert(got.length === 1 && has(added, got[0].orderId), `受付番号が残っていない: ${dump(added)}`);
  });

  await check("A07", "失敗した操作（入力誤り・状態の誤り）は履歴に残らない", async () => {
    await start();
    const inst = await h.instrument();
    const { added } = await h.newHistory(inst, async () => {
      const a = await h.patch(inst, { intervalMonths: 0 });
      const b = await h.calibrate(inst, "2026-13-01", "pass");
      const c = await h.lend(inst, "nobody-xx", d(3));
      assert(is4xx(a.status) && is4xx(b.status) && is4xx(c.status), `失敗するはずの操作: ${a.status} ${b.status} ${c.status}`);
    });
    assert(added.length === 0, `残った履歴: ${dump(added)}`);
  });

  await check("A08", "履歴は API で変更・削除できない", async () => {
    await start();
    const inst = await h.instrument();
    await h.patch(inst, { note: "消せない" });
    const before = await h.history(inst);
    assert(before.length >= 1, "履歴が無い");
    const path = h.adapter.f5.list.path.replace("{instrumentId}", inst.id);
    const one = pick(before[0], f5.fields?.id || "id");
    const tries = [["DELETE", path], ["PUT", path, []], ["PATCH", path, {}], ["POST", path, { note: "x" }]];
    if (one !== undefined) tries.push(["DELETE", `${path}/${one}`], ["PATCH", `${path}/${one}`, { actorId: "kato" }]);
    for (const [m, p, b] of tries) {
      const r = await h.call("sato", m, p, b);
      assert(!is2xx(r.status), `${m} ${p}: ${r.status}`);
    }
    const after = await h.history(inst);
    assert(JSON.stringify(after) === JSON.stringify(before), "履歴が変わった");
  });

  await check("A09", "設置場所の変更は当時の名前で残り、後で場所の名前を変えても変わらない。新しい順に返す", async () => {
    await start();
    const inst = await h.instrument();
    const stamp = String(Date.now()).slice(-6);
    const id = await h.locationId(`旧名の部屋 ${stamp}`);
    await h.patch(inst, await h.locationBody(`旧名の部屋 ${stamp}`));
    await h.setNow(jst(T, "11:00"));
    await h.patch(inst, { note: "あとの変更" });
    const r = await h.op(h.adapter.f3?.rename, "sato", { locationId: id, name: `新名の部屋 ${stamp}` });
    assert(r && is2xx(r.status), `場所の名前の変更: ${r ? show(r) : "-"}`);
    const all = await h.history(inst);
    assert(has(all, `旧名の部屋 ${stamp}`), `当時の名前が残っていない: ${dump(all)}`);
    const iNote = all.findIndex((e) => JSON.stringify(e).includes("あとの変更"));
    const iLoc = all.findIndex((e) => JSON.stringify(e).includes(`旧名の部屋 ${stamp}`));
    assert(iNote >= 0 && iLoc >= 0 && iNote < iLoc, `新しい順でない（備考 ${iNote} 番目、設置場所 ${iLoc} 番目）`);
  });

  await h.done();
});
