// W18 第 3 回「設置場所のマスタ化」のテスト。項目の定義は grading.md。既存のデータの移行（L08）は f3-upgrade.cjs。
const { harness, main, assert, show, jst, is2xx, is4xx, pick } = require("./lib.cjs");

main("f3.cjs", async () => {
  const h = harness(process.argv[2], "LC");
  const { check, call } = h;
  const f3 = h.adapter.f3 || {};
  const stamp = String(Date.now()).slice(-6);
  const nameOf = async (inst) => (await h.getInstrument(inst)).instrument?.location;

  await check("L01", "場所の一覧を API で取れ、場所を追加できる（表記ゆれで同じになる名前は追加できない）", async () => {
    const before = await h.locations();
    const r = await h.createLocation(`検査棟 第1室 ${stamp}`);
    assert(is2xx(r.status) && r.id !== undefined, `追加: ${show(r)}`);
    const after = await h.locations();
    assert(after.length === before.length + 1 && after.some((l) => String(l.id) === String(r.id)), "一覧に増えていない");
    const dup = await h.createLocation(`検査棟　第１室${stamp}`);
    assert(is4xx(dup.status), `表記ゆれの重複: ${show(dup)}`);
    assert((await h.locations()).length === after.length, "重複が増えた");
  });

  await check("L02", "計測器に場所を設定でき、一覧・詳細の location（既存の項目名）は場所の名前", async () => {
    await h.locationId(`校正待ち棚 ${stamp}`);
    const inst = await h.instrument({ location: `校正待ち棚 ${stamp}` });
    assert((await nameOf(inst)) === `校正待ち棚 ${stamp}`, `詳細の location: ${await nameOf(inst)}`);
    const list = await call("sato", "GET", "/api/instruments");
    const row = (list.json?.instruments || []).find((i) => i.id === inst.id);
    assert(row?.location === `校正待ち棚 ${stamp}`, `一覧の location: ${JSON.stringify(row?.location)}`);
  });

  await check("L03", "古い形（location に名前の文字列）での登録・編集も、一覧にある名前（空白・全角半角の違いを含む）なら受け付け、無い名前は断る", async () => {
    const id = await h.locationId(`資材倉庫 2 ${stamp}`);
    const r = await call("sato", "POST", "/api/instruments", { managementNo: `LC-9${stamp.slice(-3)}`, name: "旧端末からの登録", managerId: "kato",
      intervalMonths: 12, lastCalibratedOn: "2026-10-01", location: `資材倉庫　２ ${stamp}` });
    assert(r.status === 201, `旧形式の登録: ${show(r)}`);
    const inst = { id: pick(r.json, h.adapter.instrument?.id || "instrument.id") };
    assert((await nameOf(inst)) === `資材倉庫 2 ${stamp}`, `登録後の location: ${await nameOf(inst)}`);
    if (f3.instrumentIdField) {
      const got = (await h.getInstrument(inst)).instrument?.[f3.instrumentIdField];
      assert(String(got) === String(id), `場所の ID: ${got}（期待 ${id}）`);
    }
    const bad = await h.patch(inst, { location: `どこにもない場所 ${stamp}` });
    assert(is4xx(bad.status), `一覧に無い名前の編集: ${show(bad)}`);
    const other = await h.locationId(`検証室`);
    const ok = await h.patch(inst, { location: "検証室" });
    assert(ok.status === 200 && (await nameOf(inst)) === "検証室", `旧形式の編集: ${show(ok)} / ${other}`);
  });

  await check("L04", "場所の名前を変えると、その場所の計測器の location も新しい名前になる", async () => {
    const name = `仮置き場 ${stamp}`;
    const id = await h.locationId(name);
    const inst = await h.instrument({ location: name });
    const r = await h.op(f3.rename, "sato", { locationId: id, name: `第2仮置き場 ${stamp}` });
    assert(r && is2xx(r.status), `名前の変更: ${r ? show(r) : "アダプターに無い"}`);
    assert((await nameOf(inst)) === `第2仮置き場 ${stamp}`, `計測器の location: ${await nameOf(inst)}`);
  });

  await check("L05", "計測器が置かれている場所は削除できない（置かれていない場所は削除できる）", async () => {
    const used = await h.locationId(`使用中の棚 ${stamp}`);
    await h.instrument({ location: `使用中の棚 ${stamp}` });
    const empty = await h.createLocation(`空き棚 ${stamp}`);
    const a = await h.op(f3.delete, "sato", { locationId: used });
    assert(a && is4xx(a.status), `置かれている場所の削除: ${a ? show(a) : "アダプターに無い"}`);
    assert((await h.locations()).some((l) => String(l.id) === String(used)), "置かれている場所が消えた");
    const b = await h.op(f3.delete, "sato", { locationId: empty.id });
    assert(b && is2xx(b.status), `空の場所の削除: ${b ? show(b) : "-"}`);
  });

  await check("L06", "一覧を場所で絞り込める（API）", async () => {
    const name = `絞り込み室 ${stamp}`;
    const id = await h.locationId(name);
    const a = await h.instrument({ location: name });
    await h.instrument({ location: "検証室" });
    const q = f3.filter ? `${f3.filter.param}=${encodeURIComponent(String(h.adapter.f3.filter.value === "name" ? name : id))}` : `locationId=${id}`;
    const r = await call("sato", "GET", `/api/instruments?${q}`);
    const xs = r.json?.instruments || [];
    assert(xs.length >= 1 && xs.some((i) => i.id === a.id) && xs.every((i) => i.location === name), `絞り込み（${q}）: ${show(r)}`);
  });

  await check("L07", "校正期限のお知らせの設置場所は、場所の今の名前", async () => {
    const name = `通知確認室 ${stamp}`;
    const id = await h.locationId(name);
    const inst = await h.instrument({ managerId: "kato", importance: "top", last: "2026-03-31", location: name }); // 期限 2027-03-31
    const r = await h.op(f3.rename, "sato", { locationId: id, name: `通知確認室・改 ${stamp}` });
    assert(r && is2xx(r.status), `名前の変更: ${r ? show(r) : "-"}`);
    await h.setNow(jst("2027-03-20"));
    await h.runReminders();
    const d = await h.delivered(inst, "kato");
    assert(d.length >= 1, "お知らせが届いていない");
    assert(d.some((x) => `${x.title}\n${x.body}`.includes(`通知確認室・改 ${stamp}`)), `お知らせの本文: ${d[0].body?.slice(0, 200)}`);
  });

  await h.done();
});
