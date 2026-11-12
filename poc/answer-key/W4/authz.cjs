// W4 の認可プローブ（試行中は候補に見せない）。「認可の正しさ」の自動確認分（10 点）に使う。
// 受け入れテスト（acceptance.cjs）とは別のサーバー（起動したばかりのインメモリ DB）で実行する。
// 仕様（poc/tasks/wf-W4.md）から導ける、攻撃者の視点の入力（所属外の ID・型の違う値・権限の昇格・画面からの漏えい）を試す。
// 使い方: NODE_PATH=$(npm root -g) node authz.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
const { chromium } = require("playwright");

(async () => {

const base = process.argv[2];
const results = [];
const browser = await chromium.launch();

async function login(userId) {
  const ctx = await browser.newContext({ baseURL: base });
  const res = await ctx.request.post("/api/login", { data: { userId, password: "password" } });
  if (res.status() !== 200) throw new Error(`login ${userId} -> ${res.status()}`);
  return ctx;
}
async function check(name, fn) {
  try {
    const detail = await fn();
    results.push({ name, pass: true, detail: detail ?? "" });
  } catch (e) {
    results.push({ name, pass: false, detail: String(e.message ?? e).slice(0, 300) });
  }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }
async function json(res) {
  try { return await res.json(); } catch { return undefined; }
}
async function req(ctx, method, path, data) {
  const res = await ctx.request.fetch(path, { method, ...(data === undefined ? {} : { data }) });
  return { status: res.status(), json: await json(res) };
}
const ids = (r) => (r.json?.tasks ?? []).map((t) => t.id);
const members = async (ctx, id) => ((await req(ctx, "GET", `/api/teams/${id}/members`)).json?.members ?? []).map((m) => [m.userId, m.role]);
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const sato = await login("sato");
const suzuki = await login("suzuki");
const tanaka = await login("tanaka");

await check("所属外のチームの ID を文字列で送っても、そのチームのタスクは作れない", async () => {
  const r = await req(sato, "POST", "/api/tasks", { title: "侵入", status: "todo", assignee: "sato", dueDate: "2026-12-01", teamId: "2" });
  const leaked = ((await req(suzuki, "GET", "/api/tasks?teamId=2")).json?.tasks ?? []).filter((t) => t.title === "侵入");
  assert(r.status === 400 && leaked.length === 0, `status=${r.status} leaked=${leaked.length}`);
});

await check("所属外のチームで絞り込んでも、そのチームのタスクは返らない（API）", async () => {
  const r = await req(sato, "GET", "/api/tasks?teamId=2");
  assert(r.status === 200 && same(ids(r), []), `status=${r.status} ids=${ids(r)}`);
});

await check("所属外のチームで絞り込んでも、そのチームのタスクは表示されない（画面）", async () => {
  const page = await tanaka.newPage();
  await page.goto("/tasks?teamId=1", { waitUntil: "networkidle" });
  const rows = await page.locator('[data-testid="task-row"]').count();
  const text = await page.textContent("body");
  await page.close();
  assert(rows === 0 && !text.includes("要件定義書のレビュー") && !text.includes("API 設計"), `rows=${rows}`);
});

await check("閲覧できないタスクの詳細画面に、タイトルなどの内容が出ない", async () => {
  const page = await tanaka.newPage();
  await page.goto("/tasks/1", { waitUntil: "networkidle" });
  const html = await page.content();
  await page.close();
  assert(!html.includes("要件定義書のレビュー"), "タスク 1 のタイトルがページに含まれている");
});

await check("作成者でないメンバーは、別の所属チームへの付け替えもできない（403、所属は変わらない）", async () => {
  // タスク 2 は開発チーム（作成者 sato）。suzuki は開発チームとデザインチームの両方に所属している
  const r = await req(suzuki, "PATCH", "/api/tasks/2", { teamId: 2, assignee: "suzuki" });
  const t = (await req(sato, "GET", "/api/tasks/2")).json?.task;
  assert(r.status === 403 && t?.teamId === 1, `status=${r.status} teamId=${t?.teamId}`);
});

await check("管理者でないメンバーは、自分を管理者にできない（403。409 などで存在を漏らさない）", async () => {
  const r = await req(suzuki, "POST", "/api/teams/1/members", { userId: "suzuki", role: "admin" });
  const m = await members(sato, 1);
  assert(r.status === 403 && same(m, [["sato", "admin"], ["suzuki", "member"]]), `status=${r.status} members=${JSON.stringify(m)}`);
});

await check("管理者でないメンバーは、管理者を外せない", async () => {
  const r = await req(suzuki, "DELETE", "/api/teams/1/members/sato");
  const m = await members(sato, 1);
  assert(r.status === 403 && same(m, [["sato", "admin"], ["suzuki", "member"]]), `status=${r.status} members=${JSON.stringify(m)}`);
});

await check("ほかのチームの管理者でも、所属していないチームのメンバーは外せない（404）", async () => {
  // tanaka は自分のチームでは管理者だが、開発チームには所属していない
  const own = await req(tanaka, "POST", "/api/teams", { name: "田中のチーム" });
  const r = await req(tanaka, "DELETE", "/api/teams/1/members/suzuki");
  const m = await members(sato, 1);
  assert(own.status === 201 && r.status === 404 && same(m, [["sato", "admin"], ["suzuki", "member"]]), `own=${own.status} status=${r.status} members=${JSON.stringify(m)}`);
});

await check("外された管理者は、そのチームのメンバーを操作できなくなる", async () => {
  const team = (await req(sato, "POST", "/api/teams", { name: "引き継ぎ" })).json?.team;
  assert(Number.isInteger(team?.id), "チーム作成に失敗");
  await req(sato, "POST", `/api/teams/${team.id}/members`, { userId: "tanaka", role: "admin" });
  const removed = await req(tanaka, "DELETE", `/api/teams/${team.id}/members/sato`);
  const add = await req(sato, "POST", `/api/teams/${team.id}/members`, { userId: "suzuki" });
  const m = await members(tanaka, team.id);
  assert(removed.status === 204 && add.status === 404 && same(m, [["tanaka", "admin"]]), `removed=${removed.status} add=${add.status} members=${JSON.stringify(m)}`);
});

await browser.close();
console.log(JSON.stringify(results));
})();
