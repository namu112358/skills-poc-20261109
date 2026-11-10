// W12 の外部呼び出しの堅牢さのテスト（試行中は候補に見せない）。項目の定義は grading.md。
// 偽の通知サービスに、送り先ごとの「台本」（503・429・400・応答しない など）を仕込み、1 回のジョブの実行でまとめて確かめる。
const { harness, assert, jst } = require("./lib.cjs");

(async () => {
  const h = harness(process.argv[2], "RB");
  const { check } = h;
  const sato = await h.login("sato");
  // 期限の計算や「近づいた」の日数が候補ごとに違っても対象になるよう、どの決め方でも期限の直前になる日にする
  //（前回 2026-03-30・周期 12 か月 → 月末なら 2027-03-31、月末にしなければ 2027-03-30。今日は 2027-03-28）
  await h.setNow(jst("2027-03-28"));
  const mk = (managerId) => h.instrument(sato, { managerId, last: "2026-03-30" });
  const I = {
    retry: await mk("kato"), backoff: await mk("ito"), retryAfter: await mk("watanabe"), cap: await mk("kobayashi"),
    bad: await mk("yoshida"), hang: await mk("matsumoto"), lost: await mk("hayashi"), control: await mk("shimizu"),
  };
  await h.script("kato", [{ status: 503 }, { status: 503 }]);
  await h.script("ito", [{ status: 503 }, { status: 503 }, { status: 503 }, { status: 503 }]);
  await h.script("watanabe", [{ status: 429, retryAfter: 3 }]);
  await h.script("kobayashi", Array.from({ length: 40 }, () => ({ status: 503 })));
  await h.script("yoshida", [{ status: 400 }]);
  await h.script("matsumoto", ["hang"]);
  await h.script("hayashi", ["process_then_hang"]);
  const run1 = await h.runJob();
  const req1 = (await h.state()).requests;
  const reqs = (inst, who) => req1.filter((r) => r.recipient === who && r.raw.includes(inst.no));
  const gaps = (rs) => rs.slice(1).map((r, i) => r.t - rs[i].t);

  await check("R01", "503 のあとに再試行して届ける", async () => {
    const rs = reqs(I.retry, "kato");
    const d = await h.delivered(I.retry, "kato");
    assert(rs.length >= 3 && d.length === 1, `要求 ${rs.length} 回、届いた ${d.length} 件`);
  });

  await check("R02", "再試行の間隔が指数的に伸びる（ジッター可）", async () => {
    const g = gaps(reqs(I.backoff, "ito"));
    assert(g.length >= 2, `再試行の回数が足りない（間隔 ${JSON.stringify(g)}）`);
    assert(g[0] >= 100, `最初の間隔が短すぎる: ${g[0]}ms`);
    assert(g[g.length - 1] >= 1.5 * g[0], `間隔が伸びていない: ${JSON.stringify(g)}ms`);
  });

  await check("R03", "429 の Retry-After（3 秒）を守る", async () => {
    const rs = reqs(I.retryAfter, "watanabe");
    assert(rs.length >= 2, `再試行していない（${rs.length} 回）`);
    assert(rs[1].t - rs[0].t >= 2900, `${rs[1].t - rs[0].t}ms で再試行した`);
  });

  await check("R04", "失敗が続くときは決まった回数で再試行をやめる（2〜10 回）", async () => {
    const n = reqs(I.cap, "kobayashi").length;
    assert(run1.status > 0 && n >= 2 && n <= 10, `要求 ${n} 回（ジョブ ${run1.status}、${run1.ms}ms）`);
  });

  await check("R05", "400 は再試行しない", async () => {
    const n = reqs(I.bad, "yoshida").length;
    assert(n === 1, `要求 ${n} 回`);
  });

  await check("R06", "応答しない通知サービスをタイムアウト（60 秒以内）で打ち切り、再試行して届ける", async () => {
    const rs = reqs(I.hang, "matsumoto");
    const first = rs[0];
    assert(first, "要求が無い");
    const waited = (first.closedAt ?? Infinity) - first.t;
    assert(first.status !== 504 && waited <= 60_000, `打ち切るまで ${Number.isFinite(waited) ? waited + "ms" : "打ち切らない"}（サーバー側で ${first.status ?? "—"}）`);
    assert((await h.delivered(I.hang, "matsumoto")).length === 1, "再試行で届いていない");
  });

  await check("R09", "1 件の失敗で、ほかのお知らせが止まらない", async () => {
    assert((await h.delivered(I.control, "shimizu")).length === 1, "失敗と同じ実行の、ほかの送り先に届いていない");
  });

  await check("R11", "すべての要求に Idempotency-Key を付け、同じお知らせの再試行では同じキーを使う", async () => {
    const mine = req1.filter((r) => r.recipient);
    assert(mine.length > 0, "要求が無い");
    const missing = mine.filter((r) => !r.key).length;
    assert(missing === 0, `キーの無い要求 ${missing}/${mine.length}`);
    const keys = new Set(reqs(I.retry, "kato").map((r) => r.key));
    assert(keys.size === 1, `再試行でキーが変わる: ${[...keys].join(", ")}`);
  });

  // 2 回目の実行（翌日）。失敗し続けた送り先を直す
  await h.script("kobayashi", [], true);
  await h.setNow(jst("2027-03-29"));
  const run2 = await h.runJob();

  await check("R07", "受け付けられたのに応答が返らなかったお知らせを、再試行で二重に届けない", async () => {
    const d = await h.delivered(I.lost, "hayashi");
    const rs = (await h.state()).requests.filter((r) => r.recipient === "hayashi");
    assert(rs.length >= 2, `再試行していない（要求 ${rs.length} 回）`);
    assert(d.length === 1, `届いた件数 ${d.length}（キー: ${rs.map((r) => r.key).join(", ")}）`);
  });

  await check("R08", "送れなかったお知らせを、次の実行で送る", async () => {
    const d = await h.delivered(I.cap, "kobayashi");
    assert(run2.status > 0 && d.length === 1, `2 回目の実行のあと届いた件数 ${d.length}（ジョブ ${run2.status}）`);
  });

  await check("R10", "通知サービスが落ちていても、台帳の更新・校正記録の登録は失敗しない", async () => {
    await h.mode(true);
    try {
      const inst = await h.instrument(sato, { managerId: "sato", last: "2026-03-30" });
      const p = await h.call(sato, "PATCH", `/api/instruments/${inst.id}`, { location: "別の場所" });
      const c = await h.call(sato, "POST", `/api/instruments/${inst.id}/calibrations`, { calibratedOn: "2027-03-28", result: "pass", agency: "x" });
      assert(p.status === 200 && c.status === 201, `更新 ${p.status}、校正記録 ${c.status}`);
    } finally {
      await h.mode(false);
    }
  });

  await h.done();
})().catch((e) => { console.log(JSON.stringify([{ id: "X", name: "robust.cjs の実行", pass: false, detail: String(e) }])); });
