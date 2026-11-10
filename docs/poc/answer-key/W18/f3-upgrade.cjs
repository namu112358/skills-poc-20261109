// W18 第 3 回の L08「既存のデータの移行」。採点（grade_w18.py）が 2 段階で呼ぶ。
//   make  : 前の回の版（第 2 回の終わり）のサーバーで、表記ゆれのある設置場所の計測器を登録する。標準エラーに "UPG <JSON>" を出す
//   check : 同じ DB を第 3 回の版で起動したサーバーで、場所の一覧にまとまって移ったかを確かめる（W18_UPG に make の JSON）
const { harness, main, assert, show, jst } = require("./lib.cjs");

const VARIANTS = ["第7工場 第1ライン", "第7工場　第１ライン", "第7工場第1ライン"];
const OTHER = "第7工場 倉庫A";
const key = (s) => String(s ?? "").replace(/[\s　]/g, "").replace(/[０-９]/g, (c) => String(c.charCodeAt(0) - 0xff10));

main("f3-upgrade.cjs", async () => {
  const mode = process.argv[3];
  const h = harness(process.argv[2], "UP");
  await h.setNow(jst("2026-11-10"));
  if (mode === "make") {
    const made = [];
    for (const loc of [...VARIANTS, OTHER, ""]) made.push({ loc, ...(await h.instrument({ location: loc })) });
    const list = await h.call("sato", "GET", "/api/instruments");
    process.stderr.write(`UPG ${JSON.stringify({ made, count: list.json?.instruments?.length })}\n`);
    console.log("[]");
    return;
  }
  const { made, count } = JSON.parse(process.env.W18_UPG || "{}");
  await h.check("L08", "前の版で入っていた設置場所が、表記ゆれをまとめて場所の一覧に移り、計測器の location は名前で読める", async () => {
    assert(made?.length === 5, `前の版でデータを作れていない: ${process.env.W18_UPG}`);
    const list = await h.call("sato", "GET", "/api/instruments");
    const xs = list.json?.instruments || [];
    assert(xs.length === count, `計測器の数: ${xs.length}（移行前 ${count}）`);
    const byId = new Map(xs.map((i) => [i.id, i]));
    const got = made.map((m) => byId.get(m.id)?.location);
    const [a, b, c, other, empty] = got;
    assert(a && a === b && b === c && key(a) === key(VARIANTS[0]), `表記ゆれの 3 台の location: ${JSON.stringify([a, b, c])}`);
    assert(other === OTHER, `別の場所の location: ${JSON.stringify(other)}`);
    assert(!empty, `空だった計測器の location: ${JSON.stringify(empty)}`);
    const mi = xs.find((i) => i.managementNo === "MI-0001");
    assert(mi?.location === "品質保証部 測定室", `MI-0001 の location: ${JSON.stringify(mi?.location)}`);
    const locs = await h.locations();
    const same = locs.filter((l) => key(l.name) === key(VARIANTS[0]));
    assert(same.length === 1, `まとめた場所の数: ${same.length}（${JSON.stringify(locs.map((l) => l.name))}）`);
    assert(locs.some((l) => l.name === OTHER), "別の場所が一覧に無い");
    assert(!locs.some((l) => key(l.name) === ""), "空の名前の場所がある");
  });
  await h.done();
});
