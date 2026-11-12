// SF1 第 4 回の隠しテスト（Issue「複数のタスクをまとめて完了にできるようにする（API）」）。試行の場には入れない。
// 課題文に書かれていないが、当然守るべきこと（全部か無しか・入力の誤りで 500 にしない・重複・冪等・既存の形とそろえる）を確かめる。
// 使い方: node bulk-hidden.cjs http://localhost:3100  → 結果を JSON で標準出力に出す。サーバーは初期データの状態で起動しておく。
(async () => {
const base = process.argv[2];
let cookie = "";
async function req(method, path, body, raw) {
  const res = await fetch(base + path, { method, headers: { "content-type": "application/json", cookie }, body: raw !== undefined ? raw : body === undefined ? undefined : JSON.stringify(body), redirect: "manual" });
  const sc = res.headers.get("set-cookie"); if (sc && path === "/api/login") cookie = sc.split(";")[0];
  let json = null; try { json = await res.json(); } catch {}
  return { status: res.status, json };
}
const results = [];
async function check(name, fn) { try { results.push({ name, pass: true, detail: (await fn()) ?? "" }); } catch (e) { results.push({ name, pass: false, detail: String(e.message ?? e).slice(0, 300) }); } }
const assert = (c, m) => { if (!c) throw new Error(m); };
const task = async (id) => (await req("GET", `/api/tasks/${id}`)).json?.task;
const B = "/api/tasks/bulk-complete";
await req("POST", "/api/login", { userId: "sato", password: "password" });
assert(cookie, "login failed");
// 初期データ: 1 done, 2 in_progress, 3 in_progress, 4 todo, 5 todo, 6 todo, 7 done

await check("H1 全部か無しか: 存在しない ID を含むと 4xx で、ほかのタスクも変わらない", async () => {
  const r = await req("POST", B, { ids: [4, 99999] });
  assert(r.status >= 400 && r.status < 500, `status ${r.status}`);
  assert((await task(4)).status === "todo", "task 4 changed");
});
await check("H2 不正な ID（文字列・0・負・小数・null）は 400 で、何も変わらない", async () => {
  for (const bad of ["a", 0, -1, 1.5, null]) {
    const r = await req("POST", B, { ids: [5, bad] });
    assert(r.status === 400, `${JSON.stringify(bad)} -> ${r.status}`);
  }
  assert((await task(5)).status === "todo", "task 5 changed");
});
await check("H3 空の配列は 400", async () => {
  const r = await req("POST", B, { ids: [] });
  assert(r.status === 400, `status ${r.status}`);
});
await check("H4 壊れた本文（JSON でない・null・ids がオブジェクトや文字列）は 400 で、500 にならない", async () => {
  for (const [raw, body] of [["{", undefined], ["null", undefined], [undefined, { ids: { a: 1 } }], [undefined, { ids: "1,2" }]]) {
    const r = await req("POST", B, body, raw);
    assert(r.status === 400, `${raw ?? JSON.stringify(body)} -> ${r.status}`);
  }
});
await check("H5 重複した ID は 500 にならず、返すタスクは重複しない（400 で拒むのも可）", async () => {
  const r = await req("POST", B, { ids: [6, 6] });
  assert(r.status === 200 || r.status === 400, `status ${r.status}`);
  if (r.status === 200) {
    const ids = (r.json?.tasks ?? []).map((t) => t.id);
    assert(new Set(ids).size === ids.length, `duplicated ${JSON.stringify(ids)}`);
  }
});
await check("H6 すでに完了のタスクを含んでも 200（冪等）", async () => {
  const r = await req("POST", B, { ids: [1, 7] });
  assert(r.status === 200, `status ${r.status}`);
  assert((await task(1)).status === "done" && (await task(7)).status === "done", "not done");
});
await check("H7 返すタスクの形が GET /api/tasks/:id と同じ（項目がそろう）", async () => {
  const r = await req("POST", B, { ids: [3] });
  assert(r.status === 200, `status ${r.status}`);
  const got = r.json?.tasks?.[0]; const ref = await task(3);
  assert(got && ref, "missing");
  const a = Object.keys(got).sort().join(","), b = Object.keys(ref).sort().join(",");
  assert(a === b, `bulk {${a}} vs get {${b}}`);
});
await check("H8 最終更新日時（あれば）が更新される", async () => {
  const before = await task(2);
  if (!("updatedAt" in before)) return "updatedAt が無い版（対象外として合格）";
  await new Promise((r) => setTimeout(r, 1100));
  const r = await req("POST", B, { ids: [2] });
  assert(r.status === 200, `status ${r.status}`);
  const after = await task(2);
  assert(after.updatedAt !== before.updatedAt, `updatedAt unchanged ${after.updatedAt}`);
});

console.log(JSON.stringify(results));
})();
