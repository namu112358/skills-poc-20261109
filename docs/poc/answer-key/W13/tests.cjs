// W13 の受け入れテスト（P）・隠しテスト（K: 最初の依頼の隠れ要件、C: 変更依頼の後の決まり）。試行中は候補に見せない。
// 項目の定義は grading.md。W13_PHASE=v1 では P01・P02・K01〜K08、v2 では P02・P03・K01〜K08・C01〜C10 を行う。
// 使い方: W13_ADAPTER=... W13_PHASE=v1|v2 W13_JOBS_TOKEN=... POC_FAKE_NOW_FILE=... NODE_PATH=$(npm root -g) node tests.cjs <base>
// 各項目は自分専用の計測器を作って行う（項目どうしの予約が干渉しない）。日付はすべて日本時間。
const { harness, assert, jst, addDays, is2xx, is4xx } = require("./lib.cjs");

const MI0001 = { managementNo: "MI-0001", name: "デジタルマルチメータ", model: "DMM-7510", location: "品質保証部 測定室",
  managerId: "sato", intervalMonths: 12, lastCalibratedOn: "2026-01-20", status: "in_use", note: "" };
const T = "2026-11-10"; // 基準日（各項目は T から始め、必要なら時計を進める）
const d = (n) => addDays(T, n);
const gone = (s) => s === "cancelled" || s === "absent";

(async () => {
  const h = harness(process.argv[2], "TS");
  const { check, phase } = h;
  const v2 = phase === "v2";
  const start = async () => h.setNow(jst(T));

  if (!v2) {
    await check("P01", "予約を作れて、一覧で誰が・いつからいつまでかが読める", async () => {
      await start();
      const inst = await h.instrument();
      const id = await h.mustReserve("suzuki", inst, d(5), d(7));
      const x = (await h.list(inst)).find((i) => String(i.id) === String(id));
      assert(x, "一覧に無い");
      assert(x.start === d(5) && x.end === d(7) && x.user === "suzuki", `一覧の内容: ${JSON.stringify(x.item).slice(0, 300)}`);
    });
  }

  await check("P02", "既存の API の応答の形と、既存の機能（貸出・返却・校正記録・不合格で使用停止・既存のジョブ）が従来どおり", async () => {
    await start();
    const sato = await h.as("sato");
    const list = await h.call(sato, "GET", "/api/instruments");
    const seed = list.json?.instruments?.find((i) => i.managementNo === "MI-0001");
    const one = await h.call(sato, "GET", `/api/instruments/${seed?.id}`);
    for (const [k, v] of Object.entries(MI0001)) {
      assert(seed?.[k] === v && one.json?.instrument?.[k] === v, `${k}: 一覧=${JSON.stringify(seed?.[k])} 詳細=${JSON.stringify(one.json?.instrument?.[k])}`);
    }
    assert("currentLoan" in (one.json ?? {}), "詳細に currentLoan が無い");
    const inst = await h.instrument();
    const lend = await h.lend(inst, "suzuki", d(20));
    assert(lend.status === 201, `貸出: ${lend.status}`);
    assert((await h.returnLoan(inst, lend.loanId)) === 200, "返却");
    const cal = await h.calibrate(inst, d(-1), "fail");
    assert(cal.status === 201 && cal.json?.instrument?.status === "suspended", `不合格: ${cal.status}`);
    const job = await (await h.ctx()).post("/api/jobs/overdue-loans", { headers: { authorization: `Bearer ${process.env.W13_JOBS_TOKEN}` } });
    assert(job.status() === 200, `overdue-loans: ${job.status()}`);
    const anon = await (await h.ctx()).post("/api/jobs/overdue-loans");
    assert(anon.status() === 401, `overdue-loans（トークンなし）: ${anon.status()}`);
  });

  if (v2) {
    await check("P03", "（変更依頼）仮予約を管理者が承認すると確定になり、14 日を大きく超える予約は断る", async () => {
      await start();
      const inst = await h.instrument();
      const id = await h.mustReserve("suzuki", inst, d(3), d(9));
      const before = await h.statusOf(inst, id);
      assert(before !== "approved", `承認の前から確定になっている: ${before}`);
      const s = await h.act("kato", "approve", inst, id);
      assert(is2xx(s), `管理者の承認: ${s}`);
      const after = await h.statusOf(inst, id);
      assert(after === "approved", `承認の後の状態: ${after}`);
      const long = await h.reserve("tanaka", inst, d(20), d(49));
      assert(is4xx(long.status), `30 日の予約: ${long.status}`);
    });
  }

  // ---- K: 最初の依頼の隠れ要件（v1 でも v2 でも同じ意味で確かめる） ----
  await check("K01", "過去の日からは予約できず、今日からはできる。終了日が開始日より前は不可", async () => {
    await start();
    const inst = await h.instrument();
    const past = await h.reserve("suzuki", inst, d(-1), d(1));
    assert(is4xx(past.status), `昨日から: ${past.status}`);
    const rev = await h.reserve("suzuki", inst, d(4), d(3));
    assert(is4xx(rev.status), `終了日が前: ${rev.status}`);
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
    const c = await h.act("suzuki", "cancel", inst, id);
    assert(is2xx(c), `本人の取消: ${c}`);
    const r = await h.reserve("tanaka", inst, d(20), d(22));
    assert(is2xx(r.status), `取消の後の予約: ${r.status}`);
  });

  await check("K04", "貸出中の計測器は、返却予定日までと重なる予約はできず、翌日からはできる", async () => {
    await start();
    const inst = await h.instrument();
    const l = await h.lend(inst, "matsumoto", d(5));
    assert(l.status === 201, `貸出: ${l.status}`);
    const ng = await h.reserve("suzuki", inst, d(3), d(6));
    assert(is4xx(ng.status), `返却予定日と重なる予約: ${ng.status}`);
    const ng2 = await h.reserve("suzuki", inst, d(5), d(6));
    assert(is4xx(ng2.status), `返却予定日からの予約: ${ng2.status}`);
    const ok = await h.reserve("suzuki", inst, d(6), d(8));
    assert(is2xx(ok.status), `返却予定日の翌日から: ${ok.status}`);
  });

  await check("K05", "他人の予約の期間にかかる貸出はしない。予約した本人には予約の期間に貸し出せる", async () => {
    await start();
    const inst = await h.instrument();
    await h.effective("suzuki", inst, d(2), d(4));
    const other = await h.lend(inst, "tanaka", d(3));
    assert(is4xx(other.status), `他人への貸出（予約と重なる）: ${other.status}`);
    const other2 = await h.lend(inst, "tanaka", d(2));
    assert(is4xx(other2.status), `他人への貸出（返却予定日が予約の開始日）: ${other2.status}`);
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
    const o = await h.act("tanaka", "cancel", inst, a);
    assert(is4xx(o), `ほかの人の取消: ${o}`);
    assert(!gone(await h.statusOf(inst, a)), "ほかの人の取消で取り消された");
    const m = await h.act("kato", "cancel", inst, a);
    assert(is2xx(m), `管理者の取消: ${m}`);
    const s = await h.act("suzuki", "cancel", inst, b);
    assert(is2xx(s), `本人の取消: ${s}`);
    assert(gone(await h.statusOf(inst, a)) && gone(await h.statusOf(inst, b)), "取り消した予約が残っている");
  });

  await check("K08", "校正で不合格になり使用停止になったら、これからの予約は取り消しになる", async () => {
    await start();
    const inst = await h.instrument();
    const id = await h.effective("suzuki", inst, d(6), d(7));
    const cal = await h.calibrate(inst, d(-1), "fail");
    assert(cal.status === 201, `校正記録: ${cal.status}`);
    const s = await h.statusOf(inst, id);
    assert(gone(s), `予約の状態: ${s}`);
  });

  if (v2) {
    // ---- C: 変更依頼の後の決まり ----
    await check("C01", "新しい予約は仮予約で、管理者の承認で確定になる（区別できる）", async () => {
      await start();
      const inst = await h.instrument();
      const id = await h.mustReserve("suzuki", inst, d(3), d(4));
      const s0 = await h.statusOf(inst, id);
      assert(s0 === "pending", `作った直後の状態: ${s0}`);
      assert(is2xx(await h.act("kato", "approve", inst, id)), "承認");
      const s1 = await h.statusOf(inst, id);
      assert(s1 === "approved", `承認の後の状態: ${s1}`);
    });

    await check("C02", "承認できるのは計測器の管理者だけ（予約した本人・ほかの人はできない）", async () => {
      await start();
      const inst = await h.instrument({ managerId: "kato" });
      const id = await h.mustReserve("suzuki", inst, d(3), d(4));
      const self = await h.act("suzuki", "approve", inst, id);
      const other = await h.act("tanaka", "approve", inst, id);
      assert(is4xx(self) && is4xx(other), `本人 ${self}・ほかの人 ${other}`);
      const s = await h.statusOf(inst, id);
      assert(s === "pending", `本人・ほかの人の承認の後: ${s}`);
      assert(is2xx(await h.act("kato", "approve", inst, id)), "管理者の承認");
    });

    await check("C03", "管理者が無効なら、部署の代表者が承認できる（同じ部署のほかの人はできない）", async () => {
      await start();
      const inst = await h.instrument({ managerId: "inoue" }); // 退職。製造部の代表者は yamada
      const id = await h.mustReserve("suzuki", inst, d(3), d(4));
      const ito = await h.act("ito", "approve", inst, id);
      assert(is4xx(ito), `同じ部署のほかの人: ${ito}`);
      const y = await h.act("yamada", "approve", inst, id);
      assert(is2xx(y), `代表者の承認: ${y}`);
      assert((await h.statusOf(inst, id)) === "approved", "確定になっていない");
    });

    await check("C04", "管理者は仮予約を却下でき、却下した予約は枠を空ける", async () => {
      await start();
      const inst = await h.instrument();
      const id = await h.mustReserve("suzuki", inst, d(5), d(7));
      const r = await h.act("kato", "reject", inst, id);
      assert(is2xx(r), `却下: ${r}`);
      const s = await h.statusOf(inst, id);
      assert(s === "rejected" || s === "cancelled" || s === "absent", `却下の後の状態: ${s}`); // 却下と取消の区別は問わない（C08 で承認できないことを見る）
      const again = await h.reserve("tanaka", inst, d(5), d(7));
      assert(is2xx(again.status), `却下の後の予約: ${again.status}`);
    });

    await check("C05", "仮予約も枠を押さえる（仮予約と重なる予約はできない）", async () => {
      await start();
      const inst = await h.instrument();
      await h.mustReserve("suzuki", inst, d(5), d(7));
      const r = await h.reserve("tanaka", inst, d(7), d(8));
      assert(is4xx(r.status), `仮予約と重なる予約: ${r.status}`);
    });

    await check("C06", "開始日を過ぎた仮予約は期限切れで、承認できず、枠を空ける（当日なら承認できる）", async () => {
      await start();
      const inst = await h.instrument();
      const a = await h.mustReserve("suzuki", inst, d(3), d(5));
      const b = await h.mustReserve("suzuki", inst, d(8), d(8));
      await h.setNow(jst(d(4)));
      await h.runJobs();
      const ap = await h.act("kato", "approve", inst, a);
      assert(is4xx(ap), `開始日の翌日の承認: ${ap}`);
      const r = await h.reserve("tanaka", inst, d(4), d(5));
      assert(is2xx(r.status), `期限切れの仮予約の期間の予約: ${r.status}`);
      await h.setNow(jst(d(8), "09:00"));
      await h.runJobs();
      const bp = await h.act("kato", "approve", inst, b);
      assert(is2xx(bp), `開始日の当日の承認: ${bp}`);
    });

    await check("C07", "期間は開始日と終了日を含めて 14 日まで", async () => {
      await start();
      const inst = await h.instrument();
      const ok = await h.reserve("suzuki", inst, d(1), d(14));
      assert(is2xx(ok.status), `14 日: ${ok.status} ${JSON.stringify(ok.json)?.slice(0, 200)}`);
      const ng = await h.reserve("suzuki", inst, d(20), d(34));
      assert(is4xx(ng.status), `15 日: ${ng.status}`);
    });

    await check("C08", "承認・却下できるのは仮予約だけ（取消・却下したものは承認できない）", async () => {
      await start();
      const inst = await h.instrument();
      const a = await h.mustReserve("suzuki", inst, d(3), d(4));
      assert(is2xx(await h.act("suzuki", "cancel", inst, a)), "本人の取消");
      const s1 = await h.act("kato", "approve", inst, a);
      assert(is4xx(s1), `取り消した予約の承認: ${s1}`);
      const b = await h.mustReserve("suzuki", inst, d(6), d(7));
      assert(is2xx(await h.act("kato", "reject", inst, b)), "却下");
      const s2 = await h.act("kato", "approve", inst, b);
      assert(is4xx(s2), `却下した予約の承認: ${s2}`);
      const st = await h.statusOf(inst, b);
      assert(st !== "approved", `却下した予約が確定になった: ${st}`);
    });

    await check("C09", "予約した本人は、仮予約も確定した予約も取り消せ、枠が空く", async () => {
      await start();
      const inst = await h.instrument();
      const a = await h.mustReserve("suzuki", inst, d(3), d(4));
      assert(is2xx(await h.act("suzuki", "cancel", inst, a)), "仮予約の取消");
      const b = await h.effective("suzuki", inst, d(6), d(7));
      const c = await h.act("suzuki", "cancel", inst, b);
      assert(is2xx(c), `確定した予約の取消: ${c}`);
      const r = await h.reserve("tanaka", inst, d(6), d(7));
      assert(is2xx(r.status), `取消の後の予約: ${r.status}`);
    });

    await check("C10", "仮予約は他人の貸出を止め、却下・期限切れの予約は止めない", async () => {
      await start();
      const inst = await h.instrument();
      const a = await h.mustReserve("suzuki", inst, d(1), d(2));
      const l1 = await h.lend(inst, "tanaka", d(1));
      assert(is4xx(l1.status), `仮予約と重なる貸出: ${l1.status}`);
      assert(is2xx(await h.act("kato", "reject", inst, a)), "却下");
      const l2 = await h.lend(inst, "tanaka", d(1));
      assert(l2.status === 201, `却下の後の貸出: ${l2.status}`);
      assert((await h.returnLoan(inst, l2.loanId)) === 200, "返却");
      const inst2 = await h.instrument();
      await h.mustReserve("suzuki", inst2, d(3), d(6));
      await h.setNow(jst(d(4)));
      await h.runJobs();
      const l3 = await h.lend(inst2, "tanaka", d(6));
      assert(l3.status === 201, `期限切れの仮予約と重なる貸出: ${l3.status}`);
    });
  }

  await h.done();
})().catch((e) => { console.log(JSON.stringify([{ id: "X", name: "tests.cjs の実行", pass: false, detail: String(e) }])); });
