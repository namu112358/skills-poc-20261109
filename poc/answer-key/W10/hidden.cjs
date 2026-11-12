// W10 の隠しテスト（課題文に書かれていないが当然守るべきこと。試行中は候補に見せない）。項目の定義は grading.md。
// 使い方: NODE_PATH=$(npm root -g) node hidden.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーは fake-clock.cjs を読み込んで起動する（NODE_OPTIONS="--require fake-clock.cjs"）。サーバーの時計は
// 2026-11-09T15:30:00Z（日本時間では 2026-11-10 00:30。UTC と日本時間で日付が違う時刻）から進む。
// 判定は「拒否されたか（4xx）」と「状態が変わっていないか」で見る。ステータスコードの細かい違い（403 と 409 など）は問わない。
const { harness, assert, show, rejected } = require("./lib.cjs");

(async () => {
const h = harness(process.argv[2]);
const { check, ext } = h;
const sato = await h.login("sato");
const suzuki = await h.login("suzuki");
const REASON = "作業が遅れているため";

// 保留中の申請を作る（申請者は担当者の sato）
async function pending(due = "2026-12-01", newDueDate = "2026-12-20") {
  const t = await h.newTask(sato, due);
  const r = await ext.request(sato, t, { newDueDate, reason: REASON });
  assert(r.status === 201 && r.json?.extension?.id, `前提の申請ができない: ${show(r)}`);
  return { t, e: r.json.extension.id };
}
async function statusOf(ctx, t, e) {
  const l = await ext.list(ctx, t);
  return (l.json?.extensions ?? []).find((x) => x.id === e)?.status;
}

await check("H01", "権限: 担当者でない人は延長を申請できない（拒否され、申請は作られない）", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const r = await ext.request(suzuki, t, { newDueDate: "2026-12-20", reason: REASON });
  assert(rejected(r) && r.status !== 401 && r.status !== 404, `suzuki が sato のタスクに申請: ${show(r)}`);
  const l = await ext.list(sato, t);
  assert(l.json?.extensions?.length === 0, `申請が作られた: ${show(l)}`);
});

await check("H02", "権限: 申請者本人は自分の申請を承認できない（拒否され、期限も状態も変わらない）", async () => {
  const { t, e } = await pending();
  const r = await ext.approve(sato, t, e);
  assert(rejected(r) && r.status !== 401, `本人が承認: ${show(r)}`);
  const due = await h.dueDate(sato, t);
  const st = await statusOf(sato, t, e);
  assert(due === "2026-12-01" && st === "pending", `dueDate=${due} status=${st}`);
});

await check("H03", "権限: URL のタスクに属さない申請は承認・却下できない（拒否され、元のタスクは変わらない）", async () => {
  const { t, e } = await pending();
  const other = await h.newTask(sato, "2026-12-01");
  const a = await ext.approve(suzuki, other, e);
  const b = await ext.reject(suzuki, other, e);
  assert(rejected(a) && rejected(b), `別のタスクの URL で承認: ${show(a)} / 却下: ${show(b)}`);
  const due = await h.dueDate(sato, t);
  const dueOther = await h.dueDate(sato, other);
  const st = await statusOf(sato, t, e);
  assert(due === "2026-12-01" && dueOther === "2026-12-01" && st === "pending", `dueDate=${due} other=${dueOther} status=${st}`);
});

await check("H04", "なりすまし: 本文の申請者・状態・判断した人・ID は使わない（申請者はログイン中のユーザーで保留中）", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const other = await h.newTask(sato, "2026-12-01");
  const r = await ext.request(sato, t, { newDueDate: "2026-12-20", reason: REASON, requester: "suzuki", status: "approved",
    decidedBy: "suzuki", decidedAt: "2026-11-01T00:00:00.000Z", id: 777777, taskId: other });
  const due = await h.dueDate(sato, t);
  if (r.status === 400) {  // 余計な項目を受け付けない実装も安全とみなす
    const l = await ext.list(sato, t);
    assert(l.json?.extensions?.length === 0 && due === "2026-12-01", `400 だが申請が作られた: ${show(l)}`);
    return "余計な項目を 400 で拒否";
  }
  const x = r.json?.extension;
  assert(r.status === 201 && x, show(r));
  assert(x.requester === "sato" && x.status === "pending" && x.decidedBy === null && x.decidedAt === null && x.id !== 777777
    && x.taskId === t, JSON.stringify(x));
  assert(due === "2026-12-01", `申請しただけで期限が変わった: ${due}`);
  const lo = await ext.list(sato, other);
  assert(lo.json?.extensions?.length === 0, `別のタスクに申請が付いた: ${show(lo)}`);
});

await check("H05", "入力検証: 実在しない日付（2027-02-29・2027-04-31・2027-13-01）は 400", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const out = [];
  for (const d of ["2027-02-29", "2027-04-31", "2027-13-01"]) {
    const r = await ext.request(sato, t, { newDueDate: d, reason: REASON });
    out.push(`${d}:${r.status}`);
  }
  assert(out.every((s) => s.endsWith(":400")), out.join(" "));
});

await check("H06", "エラー時の振る舞い: 壊れた本文・型の違う値・不正な申請 ID でも 500 にならず 400 / 404 を返す", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const bodies = [["{", true], ["[]", true], ["null", true], ['"text"', true],
    [JSON.stringify({ newDueDate: 20270110, reason: REASON }), true], [JSON.stringify({ newDueDate: "2026-12-20", reason: 123 }), true],
    [JSON.stringify({ newDueDate: ["2026-12-20"], reason: REASON }), true]];
  const out = [];
  for (const [raw] of bodies) {
    const r = await ext.raw(sato, t, raw);
    out.push({ what: `body ${raw.slice(0, 40)}`, status: r.status, ok: r.status === 400 });
  }
  for (const bad of ["abc", "0", "1.5", "-1", "99999999999999999999"]) {
    const r = await ext.approve(suzuki, t, bad);
    out.push({ what: `approve id ${bad}`, status: r.status, ok: r.status === 404 });
  }
  const l = await ext.list(sato, t);
  assert(out.every((o) => o.ok), out.filter((o) => !o.ok).map((o) => `${o.what} -> ${o.status}`).join(" / "));
  assert(l.json?.extensions?.length === 0, `申請が作られた: ${show(l)}`);
});

await check("H07", "境界値: 新しい期限が今の期限と同じ・より前なら 400、1 日後なら受け付ける", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const same = await ext.request(sato, t, { newDueDate: "2026-12-01", reason: REASON });
  const earlier = await ext.request(sato, t, { newDueDate: "2026-11-25", reason: REASON });
  const next = await ext.request(sato, t, { newDueDate: "2026-12-02", reason: REASON });
  assert(same.status === 400 && earlier.status === 400 && next.status === 201,
    `同じ日=${same.status} 前の日=${earlier.status} 1 日後=${next.status}`);
});

await check("H08", "境界値: 理由は前後の空白を除いて 1〜500 文字（空白だけは 400、500 文字は受け付け、501 文字は 400）", async () => {
  const t1 = await h.newTask(sato, "2026-12-01");
  const t2 = await h.newTask(sato, "2026-12-01");
  const blank = await ext.request(sato, t1, { newDueDate: "2026-12-20", reason: " \n\t " });
  const over = await ext.request(sato, t1, { newDueDate: "2026-12-20", reason: "あ".repeat(501) });
  const max = await ext.request(sato, t2, { newDueDate: "2026-12-20", reason: "あ".repeat(500) });
  assert(blank.status === 400 && over.status === 400 && max.status === 201,
    `空白だけ=${blank.status} 501 文字=${over.status} 500 文字=${max.status}`);
});

await check("H09", "入力検証: 新しい期限に過去の日付（今の期限より後でも、今日より前）は指定できない", async () => {
  const t = await h.newTask(sato, "2026-11-01");  // すでに期限切れのタスク
  const r = await ext.request(sato, t, { newDueDate: "2026-11-05", reason: REASON });
  assert(r.status === 400, `2026-11-05（今日は 2026-11-10）: ${show(r)}`);
});

await check("H10", "時差: 「今日」は日本時間で判断する（UTC では 11-09、日本時間では 11-10 の時刻に、11-09 は過去、11-10 は受け付ける）", async () => {
  const t1 = await h.newTask(sato, "2026-11-01");
  const t2 = await h.newTask(sato, "2026-11-01");
  const y = await ext.request(sato, t1, { newDueDate: "2026-11-09", reason: REASON });
  const today = await ext.request(sato, t2, { newDueDate: "2026-11-10", reason: REASON });
  assert(y.status === 400 && today.status === 201, `11-09=${y.status} 11-10=${today.status}`);
});

await check("H11", "二重処理: 判断済みの申請は承認・却下し直せない（拒否され、状態と期限は変わらない）", async () => {
  const a = await pending();
  const r1 = await ext.approve(suzuki, a.t, a.e);
  assert(r1.status === 200, `前提の承認: ${show(r1)}`);
  const again = await ext.approve(suzuki, a.t, a.e);
  const rej = await ext.reject(suzuki, a.t, a.e);
  const dueA = await h.dueDate(sato, a.t);
  const stA = await statusOf(sato, a.t, a.e);
  const b = await pending();
  const r2 = await ext.reject(suzuki, b.t, b.e);
  assert(r2.status === 200, `前提の却下: ${show(r2)}`);
  const appr = await ext.approve(suzuki, b.t, b.e);
  const dueB = await h.dueDate(sato, b.t);
  const stB = await statusOf(sato, b.t, b.e);
  assert(rejected(again) && rejected(rej) && rejected(appr),
    `承認済みの再承認=${again.status} 承認済みの却下=${rej.status} 却下済みの承認=${appr.status}`);
  assert(stA === "approved" && dueA === "2026-12-20" && stB === "rejected" && dueB === "2026-12-01",
    `承認済み: ${stA} ${dueA} / 却下済み: ${stB} ${dueB}`);
});

await check("H12", "同時更新: 申請の後に期限がもっと先へ変えられていたら、承認しても期限を短くしない", async () => {
  const { t, e } = await pending("2026-12-01", "2026-12-20");
  const p = await h.call(suzuki, "PATCH", `/api/tasks/${t}`, { dueDate: "2026-12-31" });
  assert(p.status === 200, `前提の期限変更: ${show(p)}`);
  const r = await ext.approve(suzuki, t, e);
  const due = await h.dueDate(sato, t);
  assert(due === "2026-12-31", `承認=${r.status} で期限が ${due} になった（2026-12-31 のままであるべき）`);
});

await h.done();
})().catch((e) => { console.log(JSON.stringify([{ id: "H00", name: "hidden.cjs の実行", pass: false, detail: String(e).slice(0, 400) }])); });
