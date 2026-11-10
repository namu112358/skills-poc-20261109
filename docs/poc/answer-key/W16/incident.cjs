// W16 の隠しテスト: 障害（校正期限のお知らせの二重送信）の原因に効く修正か（試行中は候補に見せない）。項目の定義は grading.md。
// 使い方: node incident.cjs <base> main            … I1〜I5（サーバーには NOTIFY_API_TIMEOUT_MS=2000 を渡しておく）
//         node incident.cjs <base> crash-setup <file> <a|b>  … I6 の前半: 計測器を作り、ジョブを始めて 1.8 秒後に抜ける
//                                                  （このあと採点スクリプトがサーバーを強制終了して起動し直す）
//         node incident.cjs <base> crash-check <file> <a|b>  … I6 の後半: 3 時間後と翌朝に実行し、全員にちょうど 1 回届いたか
// 「要求」は通知サービスに届いた POST（失敗した応答・タイムアウトを含む）、「届いた」は通知サービスが実際に送ったもの
//（Idempotency-Key が前と同じなら新しく届いたとは数えない。本物の通知サービスと同じ）。
const fs = require("node:fs");
const { harness, assert, jst, sleep } = require("./lib.cjs");

const base = process.argv[2];
const phase = process.argv[3] || "main";

async function main() {
  const h = harness(base, "IN");
  const { check } = h;
  const sato = await h.login("sato");
  // 期限 2027-03-31（前回 2026-03-30・周期 12 か月）の 3 日前。どの決め方でも「期限が近い」の範囲
  await h.setNow(jst("2027-03-28"));
  const mk = (managerId) => h.instrument(sato, { managerId, last: "2026-03-30" });
  const latency = (ms) => fetch(`${process.env.W12_NOTIFY}/__mode`, { method: "POST", body: JSON.stringify({ latencyMs: ms }) });
  const counts = async (insts) => {
    const out = [];
    for (const [inst, who] of insts) {
      out.push({ no: inst.no, who, requests: (await h.requested(inst, who)).length, delivered: (await h.delivered(inst, who)).length });
    }
    return out;
  };
  const fmt = (cs) => cs.map((c) => `${c.no}/${c.who}: 要求 ${c.requests} 回・届いた ${c.delivered} 件`).join("、");
  const keysOf = async (inst, who) => (await h.requested(inst, who)).map((r) => r.key);
  const facts = {};

  // I1: 同時に 2 回起動（cron の呼び直し・手での実行が重なる）
  await latency(600);
  const i1 = [];
  for (const who of ["kato", "ito", "watanabe"]) i1.push([await mk(who), who]);
  const [r1a, r1b] = await Promise.all([h.runJob(), h.runJob()]);
  const r1c = await h.runJob();
  await latency(0);
  const c1 = await counts(i1);
  facts.I1 = { runs: [r1a.status, r1b.status, r1c.status], counts: c1 };
  await check("I1", "同時に 2 回起動しても、同じお知らせの要求は 1 回だけ（3 回目の実行でも送り直さない）", async () => {
    assert(c1.every((c) => c.delivered === 1), `届いていない・二重に届いた: ${fmt(c1)}`);
    assert(c1.every((c) => c.requests === 1), `通知サービスへの要求が重なった（通知サービス側の重複排除に頼っている）: ${fmt(c1)}`);
  });

  // I2: 前の実行の途中で 2 回目が始まる（本番の 11-09・11-10 と同じ形）
  await latency(800);
  const i2 = [];
  for (const who of ["hayashi", "yoshida", "kobayashi", "matsumoto", "kimura"]) i2.push([await mk(who), who]);
  const p2a = h.runJob();
  await sleep(1200);
  const p2b = h.runJob();
  const [r2a, r2b] = await Promise.all([p2a, p2b]);
  await latency(0);
  const r2c = await h.runJob();
  const c2 = await counts(i2);
  facts.I2 = { runs: [r2a.status, r2b.status, r2c.status], counts: c2 };
  await check("I2", "前の実行の途中で 2 回目が始まっても、同じお知らせの要求は 1 回だけ", async () => {
    assert(c2.every((c) => c.delivered === 1), `届いていない・二重に届いた: ${fmt(c2)}`);
    assert(c2.every((c) => c.requests === 1), `通知サービスへの要求が重なった: ${fmt(c2)}`);
  });

  // I3: 受け付けられたのに応答が返らない（タイムアウト）→ 同じ実行の再試行
  await h.script("tanaka", ["process_then_hang"], true);
  const i3 = await mk("tanaka");
  const r3a = await h.runJob();
  await h.script("tanaka", [], true);
  const r3b = await h.runJob();
  const k3 = await keysOf(i3, "tanaka");
  const d3 = (await h.delivered(i3, "tanaka")).length;
  facts.I3 = { runs: [r3a.status, r3b.status], keys: k3, delivered: d3 };
  await check("I3", "応答が返らずタイムアウトしたお知らせを、再試行で二重に届けない（受け付けられていた場合）", async () => {
    assert(d3 === 1, `届いた ${d3} 件（要求のキー: ${k3.join(", ")}）`);
  });

  // I4: 何度送ってもタイムアウト（実は毎回受け付けられている）→ 失敗として残り、次の実行で送り直す
  await h.script("suzuki", Array.from({ length: 12 }, () => "process_then_hang"), true);
  const i4 = await mk("suzuki");
  const r4a = await h.runJob();
  await h.script("suzuki", [], true);
  await h.setNow(jst("2027-03-29"));
  const r4b = await h.runJob();
  const k4 = await keysOf(i4, "suzuki");
  const d4 = (await h.delivered(i4, "suzuki")).length;
  facts.I4 = { runs: [r4a.status, r4b.status], keys: k4, delivered: d4 };
  await check("I4", "タイムアウトが続いたお知らせを、次の実行で送り直しても二重に届けない（同じキーで送り直す）", async () => {
    assert(d4 === 1, `届いた ${d4} 件（要求 ${k4.length} 回、キー ${new Set(k4).size} 種類）`);
  });

  // I5: 本番の状況の再現（遅い通知サービス・一部はタイムアウト・途中で 2 回目の実行）
  await latency(700);
  await h.script("sasaki", ["process_then_hang"], true);
  await h.script("yamamoto", ["process_then_hang"], true);
  const i5 = [];
  for (const who of ["sasaki", "yamamoto", "takahashi", "shimizu"]) i5.push([await mk(who), who]);
  const p5a = h.runJob();
  await sleep(1000);
  const p5b = h.runJob();
  const [r5a, r5b] = await Promise.all([p5a, p5b]);
  await latency(0);
  await h.script("sasaki", [], true);
  await h.script("yamamoto", [], true);
  await h.setNow(jst("2027-03-30"));
  const r5c = await h.runJob();
  const c5 = await counts(i5);
  facts.I5 = { runs: [r5a.status, r5b.status, r5c.status], counts: c5 };
  await check("I5", "本番の状況（遅い応答・タイムアウト・実行の重なり）でも、全員にちょうど 1 回届く", async () => {
    assert(c5.every((c) => c.delivered === 1), fmt(c5));
  });

  facts.keys = { tanaka: k3, suzuki: k4 };
  h.results.push({ id: "_facts", name: "記録", pass: true, detail: JSON.stringify(facts).slice(0, 6000) });
  await h.done();
}

// I6 は 2 回に分ける。a: 止めたときに送信中だった要求は、通知サービスでは送られた（応答の前に止まった）。
// b: 止めたときに送信中だった要求は、通知サービスに届いていなかった（送られていない）。どちらも、あとの実行のあとに全員にちょうど 1 回届くこと。
const CRASH = {
  a: { prefix: "CR", last: "2026-05-30", day: "2027-05-27", next: "2027-05-28", second: { delay: 4000 },
       who: ["kato", "ito", "watanabe", "kimura", "hayashi"] },
  // b の時点では a の計測器も期限切れのお知らせの対象になるので、台本が混ざらないよう送り先を変える
  b: { prefix: "CS", last: "2026-06-30", day: "2027-06-27", next: "2027-06-28", second: "hang",
       who: ["yamamoto", "sasaki", "tanaka", "shimizu", "yoshida"] },
};

async function crashSetup(file, variant) {
  const v = CRASH[variant];
  const h = harness(base, v.prefix);
  const sato = await h.login("sato");
  await h.setNow(jst(v.day)); // 期限の 3〜4 日前
  const who = v.who;
  // 1 件目は 1 秒で応答し、2 件目の応答の途中（1.8 秒後）でサーバーを止める
  await h.script(who[0], [{ delay: 1000 }], true);
  await h.script(who[1], [v.second], true);
  for (const w of who.slice(2)) await h.script(w, [], true);
  const insts = [];
  for (const w of who) insts.push([await h.instrument(sato, { managerId: w, last: v.last }), w]);
  h.runJob().catch(() => {});
  await sleep(1800);
  fs.writeFileSync(file, JSON.stringify(insts));
  console.log(JSON.stringify([]));
  process.exit(0);
}

async function crashCheck(file, variant) {
  const v = CRASH[variant];
  const h = harness(base, v.prefix);
  const insts = JSON.parse(fs.readFileSync(file, "utf8"));
  for (const [, w] of insts) await h.script(w, [], true);
  const before = [];
  for (const [inst, who] of insts) before.push((await h.delivered(inst, who)).length);
  await sleep(3000); // a の 2 件目（4 秒後に送られる）を待つ
  await h.setNow(jst(v.day, "10:30")); // 3 時間後（運用チームが手で実行し直す）
  const ra = await h.runJob();
  await h.setNow(jst(v.next)); // 翌朝の cron
  const rb = await h.runJob();
  const after = [];
  for (const [inst, who] of insts) after.push({ no: inst.no, who, delivered: (await h.delivered(inst, who)).length, requests: (await h.requested(inst, who)).length });
  const name = variant === "a"
    ? "実行の途中でサーバーが止まっても（送信中の要求は送られていた）、あとの実行で残りを送り、二重に届けない"
    : "実行の途中でサーバーが止まっても（送信中の要求は届いていなかった）、あとの実行で送る（ロック・送信中の記録が残り続けない）";
  await h.check(`I6${variant}`, name, async () => {
    assert(after.every((c) => c.delivered === 1),
      `止まる前に届いた ${JSON.stringify(before)}、そのあと（3 時間後 ${ra.status}・翌朝 ${rb.status}）: ${after.map((c) => `${c.no}/${c.who} 届いた ${c.delivered}・要求 ${c.requests}`).join("、")}`);
  });
  await h.done();
}

(async () => {
  if (phase === "main") await main();
  else if (phase === "crash-setup") await crashSetup(process.argv[4], process.argv[5] || "a");
  else if (phase === "crash-check") await crashCheck(process.argv[4], process.argv[5] || "a");
})().catch((e) => { console.log(JSON.stringify([{ id: "X", name: `incident.cjs ${phase} の実行`, pass: false, detail: String(e) }])); });
