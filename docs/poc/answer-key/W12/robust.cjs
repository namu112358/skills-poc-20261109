// W12 の外部呼び出しの堅牢さのテスト（試行中は候補に見せない）。項目の定義は grading.md。
// 偽の通知サービスに、送り先ごとの「台本」（503・429・400・応答しない など）を仕込む。
// 台本ごとに計測器を 1 台作り、ジョブを 1 回ずつ実行する（1 件の失敗でジョブ全体を止める実装でも、
// ほかの項目を測れるようにするため。2026-11-10 変更、report の判断の記録）。1 件の失敗で止まらないかは R09 で見る。
const { harness, assert, jst } = require("./lib.cjs");

(async () => {
  const h = harness(process.argv[2], "RB");
  const { check } = h;
  const sato = await h.login("sato");
  // 期限の計算や「近づいた」の日数が候補ごとに違っても対象になるよう、どの決め方でも期限の直前になる日にする
  //（前回 2026-03-30・周期 12 か月 → 月末なら 2027-03-31、月末にしなければ 2027-03-30。今日は 2027-03-28）
  await h.setNow(jst("2027-03-28"));
  const mk = (managerId) => h.instrument(sato, { managerId, last: "2026-03-30" });
  const reqsOf = async (inst, who) => (await h.state()).requests.filter((r) => r.recipient === who && r.raw.includes(inst.no));
  const gaps = (rs) => rs.slice(1).map((r, i) => r.t - rs[i].t);
  // 台本を仕込み、その計測器を作ってジョブを 1 回実行する
  async function scenario(who, actions) {
    if (actions.length) await h.script(who, actions);
    const inst = await mk(who);
    const run = await h.runJob();
    return { inst, run, reqs: await reqsOf(inst, who) };
  }

  const retry = await scenario("kato", [{ status: 503 }, { status: 503 }]);
  await check("R01", "503 のあとに再試行して届ける", async () => {
    const d = await h.delivered(retry.inst, "kato");
    assert(retry.reqs.length >= 3 && d.length === 1, `要求 ${retry.reqs.length} 回、届いた ${d.length} 件`);
  });
  await check("R11", "すべての要求に Idempotency-Key を付け、同じお知らせの再試行では同じキーを使う", async () => {
    const all = (await h.state()).requests.filter((r) => r.recipient);
    assert(all.length > 0, "要求が無い");
    const missing = all.filter((r) => !r.key).length;
    assert(missing === 0, `キーの無い要求 ${missing}/${all.length}`);
    const keys = new Set(retry.reqs.map((r) => r.key));
    assert(retry.reqs.length >= 2 && keys.size === 1, `再試行の要求 ${retry.reqs.length} 回、キー: ${[...keys].join(", ")}`);
  });

  const backoff = await scenario("ito", [{ status: 503 }, { status: 503 }, { status: 503 }, { status: 503 }]);
  await check("R02", "再試行の間隔が指数的に伸びる（ジッター可）", async () => {
    const g = gaps(backoff.reqs);
    assert(g.length >= 2, `再試行の回数が足りない（間隔 ${JSON.stringify(g)}）`);
    assert(g[0] >= 100, `最初の間隔が短すぎる: ${g[0]}ms`);
    assert(g[g.length - 1] >= 1.5 * g[0], `間隔が伸びていない: ${JSON.stringify(g)}ms`);
  });

  const ra = await scenario("watanabe", [{ status: 429, retryAfter: 3 }]);
  await check("R03", "429 の Retry-After（3 秒）を守る", async () => {
    assert(ra.reqs.length >= 2, `再試行していない（${ra.reqs.length} 回）`);
    assert(ra.reqs[1].t - ra.reqs[0].t >= 2900, `${ra.reqs[1].t - ra.reqs[0].t}ms で再試行した`);
  });

  const hang = await scenario("matsumoto", ["hang"]);
  await check("R06", "応答しない通知サービスをタイムアウト（60 秒以内）で打ち切り、再試行して届ける", async () => {
    const first = hang.reqs[0];
    assert(first, "要求が無い");
    const waited = (first.closedAt ?? Infinity) - first.t;
    // 60 秒のタイムアウトは合格。打ち切りの検出までの遅れ（計測の誤差）として 2 秒を見込む
    assert(first.status !== 504 && waited <= 62_000, `打ち切るまで ${Number.isFinite(waited) ? waited + "ms" : "打ち切らない"}（サーバー側で ${first.status ?? "—"}）`);
    assert((await h.delivered(hang.inst, "matsumoto")).length === 1, "再試行で届いていない");
  });

  const lost = await scenario("hayashi", ["process_then_hang"]);

  // 400 と、失敗と関係ない送り先を同じ実行で（400 の計測器を先に作る）
  await h.script("yoshida", [{ status: 400 }]);
  const bad = await mk("yoshida");
  const control = await mk("shimizu");
  await h.runJob();
  await check("R05", "400 は再試行しない", async () => {
    const n = (await reqsOf(bad, "yoshida")).length;
    assert(n === 1, `要求 ${n} 回`);
  });
  await check("R09", "1 件の失敗で、ほかのお知らせが止まらない", async () => {
    assert((await h.delivered(control, "shimizu")).length === 1, "400 と同じ実行の、ほかの送り先に届いていない");
  });

  const cap = await scenario("kobayashi", Array.from({ length: 40 }, () => ({ status: 503 })));
  await check("R04", "失敗が続くときは決まった回数で再試行をやめる（2〜10 回）", async () => {
    const n = cap.reqs.length;
    assert(cap.run.status > 0 && n >= 2 && n <= 10, `要求 ${n} 回（ジョブ ${cap.run.status}、${cap.run.ms}ms）`);
  });

  // 翌日の実行。失敗し続けた送り先を直す
  await h.script("kobayashi", [], true);
  await h.setNow(jst("2027-03-29"));
  const run2 = await h.runJob();
  await check("R07", "受け付けられたのに応答が返らなかったお知らせを、再試行で二重に届けない", async () => {
    const d = await h.delivered(lost.inst, "hayashi");
    const rs = (await h.state()).requests.filter((r) => r.recipient === "hayashi");
    assert(rs.length >= 2, `再試行していない（要求 ${rs.length} 回）`);
    assert(d.length === 1, `届いた件数 ${d.length}（キー: ${rs.map((r) => r.key).join(", ")}）`);
  });
  await check("R08", "送れなかったお知らせを、次の実行で送る", async () => {
    const d = await h.delivered(cap.inst, "kobayashi");
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
