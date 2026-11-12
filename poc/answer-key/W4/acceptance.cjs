// W4 の受け入れテスト（試行中は候補に見せない）。仕様は poc/tasks/wf-W4.md。
// 使い方: NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
// サーバーはインメモリ DB で起動したばかり（初期データ: タスク 1〜7、ユーザー sato / suzuki / tanaka、チーム 1・2）を前提にする。
// 前半は初期データを変えないチェック、後半は変更を伴うチェック。変更を伴うチェックは、そのチェックの中で作ったタスク・チームだけを使う。
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
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
const isErr = (r, status) => r.status === status && typeof r.json?.error === "string";
let seq = 0;
async function newTask(ctx, fields) {
  const r = await req(ctx, "POST", "/api/tasks", { title: `W4 確認用 ${++seq}`, status: "todo", dueDate: "2026-12-01", ...fields });
  assert(r.status === 201 && Number.isInteger(r.json?.task?.id), `タスク作成に失敗 ${r.status} ${JSON.stringify(r.json)}`);
  return r.json.task;
}
async function newTeam(ctx, name) {
  const r = await req(ctx, "POST", "/api/teams", { name });
  assert(r.status === 201 && Number.isInteger(r.json?.team?.id), `チーム作成に失敗 ${r.status} ${JSON.stringify(r.json)}`);
  return r.json.team.id;
}

const anon = await browser.newContext({ baseURL: base });
const sato = await login("sato");
const suzuki = await login("suzuki");
const tanaka = await login("tanaka");

// ---- API（初期データを変えない） ----
await check("API: 未ログインは 401（チームの API すべて）", async () => {
  const rs = [await req(anon, "GET", "/api/teams"), await req(anon, "POST", "/api/teams", { name: "x" }),
    await req(anon, "GET", "/api/teams/1/members"), await req(anon, "POST", "/api/teams/1/members", { userId: "tanaka" }),
    await req(anon, "DELETE", "/api/teams/1/members/suzuki")];
  assert(rs.every((r) => r.status === 401), `got ${rs.map((r) => r.status)}`);
});

await check("API: タスク一覧は自分の個人タスクと所属チームのタスクだけ（teamId・owner 付き）", async () => {
  const s = await req(sato, "GET", "/api/tasks"), z = await req(suzuki, "GET", "/api/tasks"), t = await req(tanaka, "GET", "/api/tasks");
  assert(same(ids(s), [1, 2, 3, 5, 6]) && same(ids(z), [1, 2, 3, 4, 5]) && same(ids(t), [4, 7]),
    `sato=${ids(s)} suzuki=${ids(z)} tanaka=${ids(t)}`);
  const expect = { 1: [1, "sato"], 2: [1, "sato"], 3: [1, "sato"], 4: [2, "suzuki"], 5: [1, "sato"], 6: [null, "sato"], 7: [null, "tanaka"] };
  const all = [...s.json.tasks, ...z.json.tasks, ...t.json.tasks];
  const bad = all.filter((x) => x.teamId !== expect[x.id][0] || x.owner !== expect[x.id][1]);
  assert(bad.length === 0, `所属・作成者が違う: ${JSON.stringify(bad.map((x) => [x.id, x.teamId, x.owner]))}`);
});

await check("API: teamId での絞り込み（チーム・personal・所属外・不正な値・status との併用）", async () => {
  const q = async (qs) => ids(await req(sato, "GET", `/api/tasks?${qs}`));
  const got = { team1: await q("teamId=1"), personal: await q("teamId=personal"), team2: await q("teamId=2"),
    bad: await q("teamId=abc"), both: await q("teamId=1&status=todo") };
  assert(same(got.team1, [1, 2, 3, 5]) && same(got.personal, [6]) && same(got.team2, []) && same(got.bad, [1, 2, 3, 5, 6]) &&
    same(got.both, [5]), JSON.stringify(got));
});

await check("API: 閲覧できないタスクの取得は 404（エラーは { error } の JSON）", async () => {
  const rs = { tanaka1: await req(tanaka, "GET", "/api/tasks/1"), sato7: await req(sato, "GET", "/api/tasks/7"),
    sato4: await req(sato, "GET", "/api/tasks/4") };
  const ok = await req(suzuki, "GET", "/api/tasks/4");
  assert(Object.values(rs).every((r) => isErr(r, 404)), JSON.stringify(Object.fromEntries(Object.entries(rs).map(([k, r]) => [k, r.status]))));
  assert(ok.status === 200 && ok.json?.task?.teamId === 2 && ok.json.task.owner === "suzuki", `suzuki/4=${ok.status} ${JSON.stringify(ok.json)}`);
});

await check("API: 所属チームの一覧（自分の役割付き、ID 順）", async () => {
  const s = (await req(sato, "GET", "/api/teams")).json?.teams, z = (await req(suzuki, "GET", "/api/teams")).json?.teams,
    t = (await req(tanaka, "GET", "/api/teams")).json?.teams;
  const pick = (ts) => (ts ?? []).map((x) => [x.id, x.name, x.role]);
  assert(same(pick(s), [[1, "開発チーム", "admin"]]) && same(pick(z), [[1, "開発チーム", "member"], [2, "デザインチーム", "admin"]]) &&
    same(pick(t), [[2, "デザインチーム", "member"]]), JSON.stringify({ s: pick(s), z: pick(z), t: pick(t) }));
});

await check("API: メンバー一覧（ユーザー ID 順）。所属していない・存在しない・不正な ID のチームは 404", async () => {
  const r = await req(suzuki, "GET", "/api/teams/1/members");
  const got = (r.json?.members ?? []).map((m) => [m.userId, m.name, m.role]);
  assert(r.status === 200 && same(got, [["sato", "佐藤", "admin"], ["suzuki", "鈴木", "member"]]), `${r.status} ${JSON.stringify(got)}`);
  const rs = [await req(tanaka, "GET", "/api/teams/1/members"), await req(sato, "GET", "/api/teams/999/members"),
    await req(sato, "GET", "/api/teams/abc/members")];
  assert(rs.every((x) => isErr(x, 404)), `got ${rs.map((x) => x.status)}`);
});

// ---- 画面（初期データを変えない） ----
await check("画面: タスク一覧は閲覧できるタスクだけを、所属（チーム名・個人）付きで表示する", async () => {
  const page = await tanaka.newPage();
  await page.goto("/tasks", { waitUntil: "networkidle" });
  const rows = await page.locator('[data-testid="task-row"]').allTextContents();
  const teams = (await page.locator('[data-testid="task-team"]').allTextContents()).map((s) => s.trim());
  await page.close();
  assert(rows.length === 2 && rows[0].includes("DB スキーマ作成") && rows[1].includes("リリースノート作成"), JSON.stringify(rows));
  assert(same(teams, ["デザインチーム", "個人"]), JSON.stringify(teams));
});

await check("画面: 一覧の所属の絞り込み（select name=teamId で チーム・個人）", async () => {
  const page = await sato.newPage();
  await page.goto("/tasks", { waitUntil: "networkidle" });
  const options = await page.locator('select[name="teamId"] option').evaluateAll((os) => os.map((o) => [o.value, o.textContent.trim()]));
  const want = [["", "すべて"], ["personal", "個人"], ["1", "開発チーム"]];
  assert(same(options, want), `options=${JSON.stringify(options)}`);
  const submit = async (value) => {
    await page.selectOption('select[name="teamId"]', value);
    await Promise.all([page.waitForURL(/teamId=/, { timeout: 10000 }), page.locator('form[aria-label="絞り込み"]').getByRole("button", { name: "絞り込む" }).click()]);
    await page.waitForLoadState("networkidle");
    return (await page.locator('[data-testid="task-team"]').allTextContents()).map((s) => s.trim());
  };
  const team1 = await submit("1");
  const personal = await submit("personal");
  await page.close();
  assert(team1.length === 4 && team1.every((s) => s === "開発チーム") && same(personal, ["個人"]), JSON.stringify({ team1, personal }));
});

await check("画面: 閲覧できないタスクの詳細は 404 ページ、閲覧できるタスクは所属を表示する", async () => {
  const page = await sato.newPage();
  const res = await page.goto("/tasks/7", { waitUntil: "networkidle" });
  const status = res.status();
  const titles = await page.locator('[data-testid="task-title"]').count();
  const html = await page.content();
  await page.goto("/tasks/1", { waitUntil: "networkidle" });
  const team1 = (await page.textContent('[data-testid="task-team"]')).trim();
  await page.goto("/tasks/6", { waitUntil: "networkidle" });
  const team6 = (await page.textContent('[data-testid="task-team"]')).trim();
  await page.close();
  assert(status === 404 && titles === 0 && !html.includes("リリースノート作成"), `status=${status} titles=${titles}`);
  assert(team1 === "開発チーム" && team6 === "個人", `task1=${team1} task6=${team6}`);
});

await check("画面: ヘッダーの「チーム」リンクと、チーム一覧（チーム名・役割・詳細へのリンク）", async () => {
  const page = await suzuki.newPage();
  await page.goto("/tasks", { waitUntil: "networkidle" });
  await Promise.all([page.waitForURL(/\/teams$/, { timeout: 10000 }), page.locator("header").getByRole("link", { name: "チーム" }).click()]);
  await page.waitForLoadState("networkidle");
  const items = await page.locator('[data-testid="team"]').allTextContents();
  const hrefs = await page.locator('[data-testid="team"] a').evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  await page.close();
  assert(items.length === 2 && items[0].includes("開発チーム") && items[0].includes("メンバー") && items[1].includes("デザインチーム") &&
    items[1].includes("管理者"), JSON.stringify(items));
  assert(hrefs.some((h) => /\/teams\/1$/.test(h)) && hrefs.some((h) => /\/teams\/2$/.test(h)), JSON.stringify(hrefs));
});

await check("画面: チーム詳細はメンバーと役割を表示し、管理者でなければ追加フォーム・「外す」ボタンを出さない", async () => {
  const page = await suzuki.newPage();
  await page.goto("/teams/1", { waitUntil: "networkidle" });
  const members = await page.locator('[data-testid="member"]').allTextContents();
  const forms = await page.locator('form[aria-label="メンバーの追加"]').count();
  const buttons = await page.getByRole("button", { name: "外す" }).count();
  await page.close();
  assert(members.length === 2 && members[0].includes("佐藤") && members[0].includes("管理者") && members[1].includes("鈴木") &&
    members[1].includes("メンバー"), JSON.stringify(members));
  assert(forms === 0 && buttons === 0, `forms=${forms} buttons=${buttons}`);
});

await check("画面: 所属していないチームの詳細は 404 ページ、管理者には追加フォームと各メンバーの「外す」ボタン", async () => {
  const page = await tanaka.newPage();
  const res = await page.goto("/teams/1", { waitUntil: "networkidle" });
  const status = res.status();
  const members = await page.locator('[data-testid="member"]').count();
  await page.close();
  const admin = await sato.newPage();
  await admin.goto("/teams/1", { waitUntil: "networkidle" });
  const forms = await admin.locator('form[aria-label="メンバーの追加"]').count();
  const input = await admin.locator('form[aria-label="メンバーの追加"] [name="userId"]').count();
  const buttons = await admin.locator('[data-testid="member"]').getByRole("button", { name: "外す" }).count();
  await admin.close();
  assert(status === 404 && members === 0, `tanaka: status=${status} members=${members}`);
  assert(forms === 1 && input === 1 && buttons === 2, `sato: forms=${forms} input=${input} buttons=${buttons}`);
});

// ---- API（変更を伴う） ----
await check("API: 閲覧できないタスクの更新は 404 で、内容は変わらない", async () => {
  const r1 = await req(tanaka, "PATCH", "/api/tasks/1", { title: "乗っ取り" });
  const r6 = await req(tanaka, "PATCH", "/api/tasks/6", { status: "done" });
  const t1 = (await req(sato, "GET", "/api/tasks/1")).json?.task, t6 = (await req(sato, "GET", "/api/tasks/6")).json?.task;
  assert(isErr(r1, 404) && isErr(r6, 404) && t1?.title === "要件定義書のレビュー" && t6?.status === "todo",
    `r1=${r1.status} r6=${r6.status} t1=${t1?.title} t6=${t6?.status}`);
});

await check("API: teamId なしで作ると作成者の個人タスク（本文の owner は無視、ほかの人からは 404）", async () => {
  const t = await newTask(sato, { assignee: "sato", owner: "tanaka" });
  const t2 = await newTask(sato, { assignee: "sato", teamId: null });
  const other = await req(suzuki, "GET", `/api/tasks/${t.id}`);
  const mine = ids(await req(sato, "GET", "/api/tasks?teamId=personal"));
  assert(t.teamId === null && t.owner === "sato" && t2.teamId === null && t2.owner === "sato", JSON.stringify([t, t2]));
  assert(isErr(other, 404) && mine.includes(t.id) && mine.includes(t2.id), `other=${other.status} mine=${mine}`);
});

await check("API: 個人タスクの担当者を作成者以外にすると 400（作成・更新）", async () => {
  const create = await req(sato, "POST", "/api/tasks", { title: "x", status: "todo", assignee: "suzuki", dueDate: "2026-12-01" });
  const t = await newTask(sato, { assignee: "sato" });
  const patch = await req(sato, "PATCH", `/api/tasks/${t.id}`, { assignee: "suzuki" });
  const after = (await req(sato, "GET", `/api/tasks/${t.id}`)).json?.task;
  assert(isErr(create, 400) && isErr(patch, 400) && after?.assignee === "sato", `create=${create.status} patch=${patch.status} assignee=${after?.assignee}`);
});

await check("API: チームのタスクを作る（所属外・存在しないチームは 400、担当者はチームのメンバーだけ）", async () => {
  const t = await newTask(suzuki, { teamId: 2, assignee: "tanaka" });
  const seen = await req(tanaka, "GET", `/api/tasks/${t.id}`), hidden = await req(sato, "GET", `/api/tasks/${t.id}`);
  assert(t.teamId === 2 && t.owner === "suzuki" && seen.status === 200 && isErr(hidden, 404), `${JSON.stringify(t)} tanaka=${seen.status} sato=${hidden.status}`);
  const bad = { notMember: await req(sato, "POST", "/api/tasks", { title: "x", status: "todo", assignee: "sato", dueDate: "2026-12-01", teamId: 2 }),
    missing: await req(sato, "POST", "/api/tasks", { title: "x", status: "todo", assignee: "sato", dueDate: "2026-12-01", teamId: 999 }),
    assignee: await req(suzuki, "POST", "/api/tasks", { title: "x", status: "todo", assignee: "sato", dueDate: "2026-12-01", teamId: 2 }) };
  assert(Object.values(bad).every((r) => isErr(r, 400)), JSON.stringify(Object.fromEntries(Object.entries(bad).map(([k, r]) => [k, r.status]))));
});

await check("API: チームのタスクの担当者はそのチームのメンバーにだけ変えられる（外は 400）", async () => {
  const t = await newTask(sato, { teamId: 1, assignee: "sato" });
  const bad = await req(sato, "PATCH", `/api/tasks/${t.id}`, { assignee: "tanaka" });
  const ok = await req(suzuki, "PATCH", `/api/tasks/${t.id}`, { assignee: "suzuki" });
  assert(isErr(bad, 400) && ok.status === 200 && ok.json?.task?.assignee === "suzuki", `bad=${bad.status} ok=${ok.status} ${JSON.stringify(ok.json)}`);
});

await check("API: 所属の変更は作成者だけ（作成者以外は 403、変更先は所属チームか null、担当者の規則も確かめる）", async () => {
  const t = await newTask(sato, { teamId: 1, assignee: "suzuki" });
  const byOther = await req(suzuki, "PATCH", `/api/tasks/${t.id}`, { teamId: null });
  const toForeign = await req(sato, "PATCH", `/api/tasks/${t.id}`, { teamId: 2 });
  const assigneeBreaks = await req(sato, "PATCH", `/api/tasks/${t.id}`, { teamId: null });
  const still = (await req(suzuki, "GET", `/api/tasks/${t.id}`)).json?.task;
  assert(isErr(byOther, 403) && isErr(toForeign, 400) && isErr(assigneeBreaks, 400) && still?.teamId === 1,
    `byOther=${byOther.status} toForeign=${toForeign.status} assigneeBreaks=${assigneeBreaks.status} teamId=${still?.teamId}`);
  const ok = await req(sato, "PATCH", `/api/tasks/${t.id}`, { teamId: null, assignee: "sato" });
  const gone = await req(suzuki, "GET", `/api/tasks/${t.id}`);
  assert(ok.status === 200 && ok.json?.task?.teamId === null && isErr(gone, 404), `ok=${ok.status} ${JSON.stringify(ok.json)} suzuki=${gone.status}`);
  const back = await req(sato, "PATCH", `/api/tasks/${t.id}`, { teamId: 1 });
  const shared = await req(suzuki, "GET", `/api/tasks/${t.id}`);
  assert(back.status === 200 && back.json?.task?.teamId === 1 && shared.status === 200, `back=${back.status} suzuki=${shared.status}`);
});

await check("API: owner は更新できない（送っても作成者のまま）", async () => {
  const t = await newTask(sato, { teamId: 1, assignee: "sato" });
  const r = await req(suzuki, "PATCH", `/api/tasks/${t.id}`, { owner: "suzuki", title: "題名の変更" });
  const after = (await req(sato, "GET", `/api/tasks/${t.id}`)).json?.task;
  assert(r.status === 200 && after?.owner === "sato" && after.title === "題名の変更", `${r.status} ${JSON.stringify(after)}`);
});

await check("API: チームを作ると作成者が管理者になる（名前は前後の空白を除いて 1〜50 文字）", async () => {
  const r = await req(tanaka, "POST", "/api/teams", { name: "  営業チーム  " });
  const team = r.json?.team;
  assert(r.status === 201 && Number.isInteger(team?.id) && team.name === "営業チーム" && team.role === "admin", `${r.status} ${JSON.stringify(r.json)}`);
  const list = ((await req(tanaka, "GET", "/api/teams")).json?.teams ?? []).map((x) => x.id);
  const members = ((await req(tanaka, "GET", `/api/teams/${team.id}/members`)).json?.members ?? []).map((m) => [m.userId, m.role]);
  const bad = [await req(tanaka, "POST", "/api/teams", { name: "   " }), await req(tanaka, "POST", "/api/teams", { name: "あ".repeat(51) }),
    await req(tanaka, "POST", "/api/teams", {})];
  const ok50 = await req(tanaka, "POST", "/api/teams", { name: "あ".repeat(50) });
  assert(list.includes(team.id) && same(members, [["tanaka", "admin"]]), `list=${list} members=${JSON.stringify(members)}`);
  assert(bad.every((x) => isErr(x, 400)) && ok50.status === 201, `bad=${bad.map((x) => x.status)} ok50=${ok50.status}`);
});

await check("API: メンバーの追加は管理者だけ（メンバーは 403、所属外は 404、不正な入力は 400、重複は 409）", async () => {
  const id = await newTeam(tanaka, "追加の確認");
  const add = await req(tanaka, "POST", `/api/teams/${id}/members`, { userId: "suzuki" });
  assert(add.status === 201 && add.json?.member?.userId === "suzuki" && add.json.member.name === "鈴木" && add.json.member.role === "member",
    `add=${add.status} ${JSON.stringify(add.json)}`);
  const rs = { dup: await req(tanaka, "POST", `/api/teams/${id}/members`, { userId: "suzuki" }),
    nobody: await req(tanaka, "POST", `/api/teams/${id}/members`, { userId: "nobody" }),
    role: await req(tanaka, "POST", `/api/teams/${id}/members`, { userId: "sato", role: "owner" }),
    byMember: await req(suzuki, "POST", `/api/teams/${id}/members`, { userId: "sato" }),
    byOutsider: await req(sato, "POST", `/api/teams/${id}/members`, { userId: "sato" }) };
  const want = { dup: 409, nobody: 400, role: 400, byMember: 403, byOutsider: 404 };
  const got = Object.fromEntries(Object.entries(rs).map(([k, r]) => [k, r.status]));
  assert(Object.entries(want).every(([k, s]) => isErr(rs[k], s)), JSON.stringify(got));
  const members = ((await req(tanaka, "GET", `/api/teams/${id}/members`)).json?.members ?? []).map((m) => m.userId);
  assert(same(members, ["suzuki", "tanaka"]), `members=${members}`);
});

await check("API: メンバーを外すのは管理者だけ（メンバーは 403、非所属は 404、最後の管理者は 400、ほかに管理者がいれば自分も外せる）", async () => {
  const id = await newTeam(tanaka, "削除の確認");
  await req(tanaka, "POST", `/api/teams/${id}/members`, { userId: "suzuki" });
  const rs = { byMember: await req(suzuki, "DELETE", `/api/teams/${id}/members/tanaka`),
    notMember: await req(tanaka, "DELETE", `/api/teams/${id}/members/sato`),
    lastAdmin: await req(tanaka, "DELETE", `/api/teams/${id}/members/tanaka`) };
  const want = { byMember: 403, notMember: 404, lastAdmin: 400 };
  assert(Object.entries(want).every(([k, s]) => isErr(rs[k], s)), JSON.stringify(Object.fromEntries(Object.entries(rs).map(([k, r]) => [k, r.status]))));
  const addAdmin = await req(tanaka, "POST", `/api/teams/${id}/members`, { userId: "sato", role: "admin" });
  const self = await req(tanaka, "DELETE", `/api/teams/${id}/members/tanaka`);
  const after = await req(tanaka, "GET", `/api/teams/${id}/members`);
  const removeMember = await req(sato, "DELETE", `/api/teams/${id}/members/suzuki`);
  const members = ((await req(sato, "GET", `/api/teams/${id}/members`)).json?.members ?? []).map((m) => m.userId);
  assert(addAdmin.status === 201 && self.status === 204 && isErr(after, 404) && removeMember.status === 204 && same(members, ["sato"]),
    `addAdmin=${addAdmin.status} self=${self.status} after=${after.status} remove=${removeMember.status} members=${members}`);
});

await check("API: チームに加わるとそのチームのタスクが見え、外されると担当者のタスクでも見えなくなる", async () => {
  const id = await newTeam(sato, "権限の確認");
  await req(sato, "POST", `/api/teams/${id}/members`, { userId: "tanaka" });
  const t = await newTask(sato, { teamId: id, assignee: "tanaka" });
  const before = await req(tanaka, "GET", `/api/tasks/${t.id}`);
  const del = await req(sato, "DELETE", `/api/teams/${id}/members/tanaka`);
  const after = await req(tanaka, "GET", `/api/tasks/${t.id}`);
  const patch = await req(tanaka, "PATCH", `/api/tasks/${t.id}`, { status: "done" });
  const list = ids(await req(tanaka, "GET", "/api/tasks"));
  assert(before.status === 200 && del.status === 204 && isErr(after, 404) && isErr(patch, 404) && !list.includes(t.id),
    `before=${before.status} del=${del.status} after=${after.status} patch=${patch.status} list=${list}`);
});

// ---- 画面（変更を伴う） ----
await check("画面: 管理者がフォームでメンバーを追加し、「外す」で一覧から消せる", async () => {
  const id = await newTeam(sato, "画面の確認");
  const page = await sato.newPage();
  page.on("dialog", (d) => d.accept()); // 確認ダイアログを出す実装も可
  await page.goto(`/teams/${id}`, { waitUntil: "networkidle" });
  const field = page.locator('form[aria-label="メンバーの追加"] [name="userId"]');
  const tag = await field.evaluate((el) => el.tagName.toLowerCase());
  if (tag === "select") await field.selectOption("tanaka");
  else await field.fill("tanaka");
  await page.locator('form[aria-label="メンバーの追加"]').getByRole("button", { name: "追加する" }).click();
  const item = page.locator('[data-testid="member"]', { hasText: "田中" });
  await item.waitFor({ timeout: 10000 });
  const text = await item.textContent();
  const api1 = ((await req(sato, "GET", `/api/teams/${id}/members`)).json?.members ?? []).map((m) => [m.userId, m.role]);
  assert(text.includes("メンバー") && same(api1, [["sato", "admin"], ["tanaka", "member"]]), `text=${text} api=${JSON.stringify(api1)}`);
  await item.getByRole("button", { name: "外す" }).click();
  await item.waitFor({ state: "detached", timeout: 10000 });
  const left = await page.locator('[data-testid="member"]').allTextContents();
  await page.close();
  const api2 = ((await req(sato, "GET", `/api/teams/${id}/members`)).json?.members ?? []).map((m) => m.userId);
  assert(left.length === 1 && left[0].includes("佐藤") && same(api2, ["sato"]), `left=${JSON.stringify(left)} api=${api2}`);
});

await check("画面: 最後の管理者を外そうとすると role=alert のエラーが出て、一覧は変わらない", async () => {
  const id = await newTeam(sato, "エラーの確認");
  const page = await sato.newPage();
  page.on("dialog", (d) => d.accept());
  await page.goto(`/teams/${id}`, { waitUntil: "networkidle" });
  await page.locator('[data-testid="member"]', { hasText: "佐藤" }).getByRole("button", { name: "外す" }).click();
  // Next.js が自動で入れるルート通知（next-route-announcer）も role=alert を持つため、文言のある要素だけを見る
  const alertLoc = page.locator('[role="alert"]').filter({ hasText: /\S/ }).first();
  await alertLoc.waitFor({ state: "visible", timeout: 10000 });
  const alert = (await alertLoc.textContent()).trim();
  const shown = await page.locator('[data-testid="member"]').count();
  await page.close();
  const api = ((await req(sato, "GET", `/api/teams/${id}/members`)).json?.members ?? []).map((m) => m.userId);
  assert(alert.length > 0 && shown === 1 && same(api, ["sato"]), `alert="${alert}" shown=${shown} api=${api}`);
});

await check("既存の動作が壊れていない（ログイン・未ログインはログイン画面へ・詳細画面のタイトル・タスクの作成と更新）", async () => {
  const page = await sato.newPage();
  // タスク 2 はどのチェックでも変更しない（タスク 1 は「閲覧できないタスクの更新」のチェックで狙われるため使わない）
  await page.goto("/tasks/2", { waitUntil: "networkidle" });
  const title = (await page.textContent('[data-testid="task-title"]')).trim();
  await page.close();
  const anonPage = await anon.newPage();
  await anonPage.goto("/tasks/1", { waitUntil: "networkidle" });
  const url = anonPage.url();
  await anonPage.close();
  const t = await newTask(suzuki, { assignee: "suzuki" });
  const p = await req(suzuki, "PATCH", `/api/tasks/${t.id}`, { status: "done", title: "更新後" });
  const tasks = await req(anon, "GET", "/api/tasks");
  assert(title === "ログイン画面のデザイン" && url.includes("/login") && p.status === 200 && p.json?.task?.status === "done" && tasks.status === 401,
    `title=${title} url=${url} patch=${p.status} anon=${tasks.status}`);
});

await browser.close();
console.log(JSON.stringify(results));
})();
