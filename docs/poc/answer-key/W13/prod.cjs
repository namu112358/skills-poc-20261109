// W13 の「本番の DB」: 旧スキーマの DB（old-db.sql）で最初の版（v1）のアプリを動かし、v1 のアダプターで予約を入れる（grading.md の「マイグレーション」）。
// 使い方: node prod.cjs make <base>   … 日本時間 2026-11-10 に予約を入れ、入れた予約を JSON で出す（W13_ADAPTER は v1 のもの）
//         node prod.cjs check <base>  … 変更後（v2）のアプリで、入れた予約が残り、確定として有効かを確かめる（W13_ADAPTER は v2 のもの、
//                                       W13_PROD に make の出力。日本時間 2026-11-15）
const { harness, assert, jst, is2xx, is4xx } = require("./lib.cjs");

// old-db.sql の計測器（id・管理番号・管理者）
const MI = {
  "MI-0001": { id: 1, no: "MI-0001", managerId: "sato" },
  "MI-0003": { id: 3, no: "MI-0003", managerId: "suzuki" },
  "MI-0006": { id: 6, no: "MI-0006", managerId: "yamamoto" },
  "MI-0009": { id: 9, no: "MI-0009", managerId: "takahashi" },
  "MI-0010": { id: 10, no: "MI-0010", managerId: "ito" },
  "MI-0014": { id: 14, no: "MI-0014", managerId: "tanaka" },
};

async function make(base) {
  const h = harness(base, "PR");
  await h.setNow(jst("2026-11-10"));
  const out = { made: [], errors: [] };
  const add = async (key, user, no, s, e, alt) => {
    let r = await h.reserve(user, MI[no], s, e);
    if (!is2xx(r.status) && alt) {
      out.errors.push(`${key}: ${s}〜${e} -> ${r.status}（短い期間でやり直す）`);
      r = await h.reserve(user, MI[no], alt[0], alt[1]);
      [s, e] = alt;
    }
    if (is2xx(r.status) && r.id !== undefined) out.made.push({ key, user, no, start: s, end: e, id: r.id });
    else out.errors.push(`${key}: ${r.status} ${JSON.stringify(r.json)?.slice(0, 200)}`);
    return r.id;
  };
  await add("A", "suzuki", "MI-0001", "2026-11-20", "2026-11-22");
  // 14 日を超える予約。計測器は校正期限が遠い MI-0014（前回 2026-11-12・12 か月）。当初の MI-0003 は 2026-12-03 が校正期限で、
  // 「期間中に校正期限が来る予約は受けない」とした実装（feature-dev-1）で断られたため変えた（2026-11-10 補正。判断の記録）
  await add("B", "suzuki", "MI-0014", "2026-12-01", "2026-12-20", ["2026-12-01", "2026-12-07"]);
  await add("D", "sato", "MI-0009", "2026-11-16", "2026-11-18");
  const c = await add("C", "tanaka", "MI-0006", "2026-11-25", "2026-11-26");
  if (c !== undefined) {
    const s = await h.act("tanaka", "cancel", MI["MI-0006"], c);
    const x = out.made.find((m) => m.key === "C");
    x.cancelled = is2xx(s);
    if (!is2xx(s)) out.errors.push(`C の取消: ${s}`);
  }
  // 確かめ: v1 のアプリで一覧に出ること
  for (const m of out.made) {
    m.v1_status = await h.statusOf(MI[m.no], m.id);
  }
  await h.done();
  return out;
}

async function check(base) {
  const prod = JSON.parse(process.env.W13_PROD || "{}");
  const h = harness(base, "PC");
  const { check } = h;
  await h.setNow(jst("2026-11-15"));
  const made = prod.made || [];
  const live = made.filter((m) => m.key !== "C");
  const found = {};
  const statuses = new Set();
  for (const no of Object.keys(MI)) {
    try {
      for (const x of await h.list(MI[no])) statuses.add(JSON.stringify(x.raw));
    } catch { /* 一覧が無い */ }
  }
  for (const m of made) {
    try {
      const items = await h.list(MI[m.no]);
      found[m.key] = items.find((x) => String(x.id) === String(m.id))
        ?? items.find((x) => x.start === m.start && x.end === m.end && x.user === m.user);
    } catch (e) { found[m.key] = undefined; }
  }
  await check("N3x", "本番の予約（取消以外）が、同じ期間・同じ人のまま一覧に残る", async () => {
    assert(live.length >= 3, `本番の DB に予約を入れられていない: ${JSON.stringify(prod.errors)}`);
    for (const m of live) {
      const f = found[m.key];
      assert(f && f.start === m.start && f.end === m.end && f.user === m.user, `${m.key}（${m.no} ${m.start}〜${m.end}）: ${JSON.stringify(f?.item)?.slice(0, 200)}`);
    }
  });
  await check("N4", "本番の予約（14 日を超えるものを含む）は確定、取り消した予約は取消のまま", async () => {
    assert(live.length >= 3, "本番の予約が無い");
    for (const m of live) assert(found[m.key]?.status === "approved", `${m.key}: ${found[m.key]?.status}（${JSON.stringify(found[m.key]?.raw)}）`);
    const c = made.find((m) => m.key === "C");
    if (c?.cancelled) {
      const s = found.C ? found.C.status : "absent";
      assert(s === "cancelled" || s === "absent", `取り消した予約: ${s}`);
    }
  });
  await check("N5", "本番の DB で、本番の予約と重なる予約は断り、新しい予約は仮予約として作れて承認できる", async () => {
    const a = live.find((m) => m.key === "A");
    assert(a, "予約 A が無い");
    const ng = await h.reserve("tanaka", MI["MI-0001"], "2026-11-21", "2026-11-21");
    assert(is4xx(ng.status), `本番の予約と重なる予約: ${ng.status}`);
    const id = await h.mustReserve("suzuki", MI["MI-0010"], "2026-11-25", "2026-11-26");
    const s0 = await h.statusOf(MI["MI-0010"], id);
    assert(s0 === "pending", `新しい予約の状態: ${s0}`);
    const ap = await h.act("ito", "approve", MI["MI-0010"], id);
    assert(is2xx(ap), `承認: ${ap}`);
    const s1 = await h.statusOf(MI["MI-0010"], id);
    assert(s1 === "approved", `承認の後: ${s1}`);
  });
  await check("S1", "移行後の予約の状態の値が、変更後のコードが知っている値だけ", async () => {
    const unknown = [...statuses].filter((s) => h.canon(JSON.parse(s)).startsWith("?"));
    assert(statuses.size > 0, "予約が読めない");
    assert(unknown.length === 0, `知らない値: ${unknown.join(", ")}（変更後の値: ${JSON.stringify(h.adapter.status)}）`);
  });
  h.results.push({ id: "facts", name: "記録", pass: true, detail: JSON.stringify({ statuses: [...statuses], found: Object.fromEntries(Object.entries(found).map(([k, v]) => [k, v && { id: v.id, status: v.status, raw: v.raw }])) }) });
  await h.done();
}

(async () => {
  const [mode, base] = process.argv.slice(2);
  if (mode === "make") {
    const out = await make(base).catch((e) => ({ made: [], errors: [String(e)] }));
    console.error("PROD " + JSON.stringify(out));
  } else {
    await check(base);
  }
})().catch((e) => { console.log(JSON.stringify([{ id: "X", name: "prod.cjs の実行", pass: false, detail: String(e) }])); });
