// W10 の公開の受け入れテスト（課題文 poc/tasks/wf-W10.md に書かれていることだけを確かめる。試行中は候補に見せない）。
// 使い方: NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかりを前提にする。各チェックは自分で作ったタスクを使い、互いに依存しない。
// 日付は試行の時期（2026-11）より十分先（2027 年）にして、過去の日付・時差の扱いに左右されないようにしている。
const { harness, assert, show } = require("./lib.cjs");

(async () => {
const h = harness(process.argv[2]);
const { check, ext } = h;
const anon = await h.anon();
const sato = await h.login("sato");
const suzuki = await h.login("suzuki");
const ISO_UTC = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,3})?Z$/;

await check("P01", "未ログインは 401（一覧・申請・承認・却下）", async () => {
  const rs = [await ext.list(anon, 1), await ext.request(anon, 1, { newDueDate: "2027-01-10", reason: "x" }),
    await ext.approve(anon, 1, 1), await ext.reject(anon, 1, 1)];
  assert(rs.every((r) => r.status === 401), rs.map((r) => r.status).join(","));
});

await check("P02", "申請が無いタスクは 200 で空配列", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const r = await ext.list(sato, t);
  assert(r.status === 200 && Array.isArray(r.json?.extensions) && r.json.extensions.length === 0, show(r));
});

await check("P03", "申請すると 201 で指定どおりの形の申請を返す（申請者はログイン中のユーザー、保留中、判断は null）", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const before = Date.now();
  const r = await ext.request(sato, t, { newDueDate: "2027-01-10", reason: "レビュー待ちのため" });
  const e = r.json?.extension;
  assert(r.status === 201 && e, show(r));
  assert(Number.isInteger(e.id) && e.taskId === t && e.requester === "sato" && e.newDueDate === "2027-01-10"
    && e.reason === "レビュー待ちのため" && e.status === "pending" && e.decidedBy === null && e.decidedAt === null, JSON.stringify(e));
  assert(ISO_UTC.test(e.createdAt) && Math.abs(Date.parse(e.createdAt) - before) < 120000, `createdAt=${e.createdAt}`);
  const l = await ext.list(suzuki, t);
  assert(l.status === 200 && l.json?.extensions?.length === 1 && l.json.extensions[0].id === e.id, show(l));
});

await check("P04", "一覧は申請の古い順", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const a = await ext.request(sato, t, { newDueDate: "2027-01-10", reason: "1 回目" });
  await ext.reject(suzuki, t, a.json?.extension?.id);
  const b = await ext.request(sato, t, { newDueDate: "2027-01-20", reason: "2 回目" });
  const l = await ext.list(sato, t);
  const ids = (l.json?.extensions ?? []).map((x) => x.id);
  assert(a.status === 201 && b.status === 201, `${show(a)} / ${show(b)}`);
  assert(ids.length === 2 && ids[0] === a.json.extension.id && ids[1] === b.json.extension.id, show(l));
});

await check("P05", "タスクが無い・ID が正の整数でないときは 404（一覧・申請）", async () => {
  const rs = [await ext.list(sato, 99999), await ext.request(sato, 99999, { newDueDate: "2027-01-10", reason: "x" }),
    await ext.list(sato, "abc"), await ext.request(sato, "abc", { newDueDate: "2027-01-10", reason: "x" })];
  assert(rs.every((r) => r.status === 404), rs.map((r) => r.status).join(","));
});

await check("P06", "新しい期限が YYYY-MM-DD 形式でない・理由が無いときは 400（details に理由）", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const rs = [await ext.request(sato, t, { newDueDate: "2027/01/10", reason: "x" }),
    await ext.request(sato, t, { newDueDate: "2027-01-10" }),
    await ext.request(sato, t, { reason: "x" })];
  assert(rs.every((r) => r.status === 400 && typeof r.json?.error === "string" && Array.isArray(r.json?.details) && r.json.details.length > 0),
    rs.map(show).join(" / "));
  const l = await ext.list(sato, t);
  assert(l.json?.extensions?.length === 0, `申請が作られた: ${show(l)}`);
});

await check("P07", "理由が 500 文字を超えると 400", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const r = await ext.request(sato, t, { newDueDate: "2027-01-10", reason: "a".repeat(600) });
  assert(r.status === 400, show(r));
});

await check("P08", "保留中の申請があるタスクへの 2 件目の申請は 409", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const a = await ext.request(sato, t, { newDueDate: "2027-01-10", reason: "1 回目" });
  const b = await ext.request(sato, t, { newDueDate: "2027-01-20", reason: "2 回目" });
  assert(a.status === 201 && b.status === 409, `${show(a)} / ${show(b)}`);
});

await check("P09", "承認すると 200 で承認済みの申請と変更後のタスクを返し、タスクの期限が変わる", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const a = await ext.request(sato, t, { newDueDate: "2027-01-10", reason: "x" });
  const before = Date.now();
  const r = await ext.approve(suzuki, t, a.json?.extension?.id);
  const e = r.json?.extension;
  assert(r.status === 200 && e?.status === "approved" && e.decidedBy === "suzuki" && ISO_UTC.test(e.decidedAt ?? "")
    && Math.abs(Date.parse(e.decidedAt) - before) < 120000, show(r));
  assert(r.json?.task?.id === t && r.json.task.dueDate === "2027-01-10", `task=${JSON.stringify(r.json?.task)}`);
  const due = await h.dueDate(sato, t);
  assert(due === "2027-01-10", `GET /api/tasks/${t} の dueDate=${due}`);
});

await check("P10", "却下すると 200 で却下済みの申請を返し、タスクの期限は変わらない", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const a = await ext.request(sato, t, { newDueDate: "2027-01-10", reason: "x" });
  const r = await ext.reject(suzuki, t, a.json?.extension?.id);
  const e = r.json?.extension;
  assert(r.status === 200 && e?.status === "rejected" && e.decidedBy === "suzuki" && ISO_UTC.test(e.decidedAt ?? ""), show(r));
  const due = await h.dueDate(sato, t);
  assert(due === "2026-12-01", `dueDate=${due}`);
});

await check("P11", "却下・承認の後は、同じタスクに新しく申請できる", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const a = await ext.request(sato, t, { newDueDate: "2027-01-10", reason: "x" });
  await ext.reject(suzuki, t, a.json?.extension?.id);
  const b = await ext.request(sato, t, { newDueDate: "2027-01-20", reason: "y" });
  await ext.approve(suzuki, t, b.json?.extension?.id);
  const c = await ext.request(sato, t, { newDueDate: "2027-02-10", reason: "z" });
  assert(b.status === 201 && c.status === 201, `${show(b)} / ${show(c)}`);
});

await check("P12", "存在しない申請の承認・却下は 404", async () => {
  const t = await h.newTask(sato, "2026-12-01");
  const rs = [await ext.approve(suzuki, t, 99999), await ext.reject(suzuki, t, 99999), await ext.approve(suzuki, 99999, 1)];
  assert(rs.every((r) => r.status === 404), rs.map((r) => r.status).join(","));
});

await check("P13", "既存の動作: タスクの一覧・作成・更新が従来どおり動く", async () => {
  const l = await h.call(sato, "GET", "/api/tasks");
  assert(l.status === 200 && Array.isArray(l.json?.tasks) && l.json.tasks.length >= 7, show(l));
  const t = await h.newTask(sato, "2026-12-01");
  const p = await h.call(sato, "PATCH", `/api/tasks/${t}`, { status: "in_progress" });
  assert(p.status === 200 && p.json?.task?.status === "in_progress" && p.json.task.dueDate === "2026-12-01", show(p));
});

await h.done();
})().catch((e) => { console.log(JSON.stringify([{ id: "P00", name: "acceptance.cjs の実行", pass: false, detail: String(e).slice(0, 400) }])); });
