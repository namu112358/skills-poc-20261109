// W1 の受け入れテスト（試行中は候補に見せない）。
// 使い方: NODE_PATH=$(npm root -g) node acceptance.cjs http://localhost:3100  → 結果を JSON で標準出力に出す
const { chromium } = require("playwright");

(async () => {

const base = process.argv[2];
const results = [];
const browser = await chromium.launch();
const page = await browser.newPage();
page.setDefaultTimeout(10000);

async function rows(path) {
  await page.goto(base + path, { waitUntil: "networkidle" });
  return page.$$eval('[data-testid="task-row"]', (trs) =>
    trs.map((tr) => [...tr.querySelectorAll("td")].map((td) => td.textContent.trim())),
  );
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

await check("担当者で絞り込める（?assignee=sato → 3 件、全件 sato）", async () => {
  const r = await rows("/tasks?assignee=sato");
  assert(r.length === 3 && r.every((c) => c[2] === "sato"), `got ${JSON.stringify(r.map((c) => c[2]))}`);
});
await check("ステータスと担当者を同時に指定できる（sato + todo → 1 件）", async () => {
  const r = await rows("/tasks?assignee=sato&status=todo");
  assert(r.length === 1 && r[0][0] === "E2E テストの追加", `got ${JSON.stringify(r)}`);
});
await check("存在しない担当者は指定なしとして扱う（→ 7 件）", async () => {
  const r = await rows("/tasks?assignee=nobody");
  assert(r.length === 7, `got ${r.length} rows`);
});
await check("選択欄 select[name=assignee] に「すべて」と担当者 3 名（重複なし）", async () => {
  await page.goto(base + "/tasks", { waitUntil: "networkidle" });
  const opts = await page.$$eval('select[name="assignee"] option', (os) => os.map((o) => [o.value, o.textContent.trim()]));
  const values = opts.map((o) => o[0]);
  assert(opts.length === 4, `got ${JSON.stringify(opts)}`);
  assert(values[0] === "" && opts[0][1].includes("すべて"), `first option ${JSON.stringify(opts[0])}`);
  assert(["sato", "suzuki", "tanaka"].every((v) => values.includes(v)), `values ${JSON.stringify(values)}`);
});
await check("画面から担当者を選んで送信すると URL と一覧が変わる（tanaka → 2 件）", async () => {
  await page.goto(base + "/tasks", { waitUntil: "networkidle" });
  await page.selectOption('select[name="assignee"]', "tanaka");
  await Promise.all([page.waitForURL(/assignee=tanaka/), page.click('form button[type="submit"]')]);
  const r = await page.$$eval('[data-testid="task-row"]', (trs) => trs.length);
  assert(r === 2, `got ${r} rows`);
});
await check("既存の動作が壊れていない（指定なし 7 件、status=done 2 件、担当者の選択状態が保持される）", async () => {
  const all = await rows("/tasks");
  const done = await rows("/tasks?status=done");
  assert(all.length === 7 && done.length === 2, `all=${all.length} done=${done.length}`);
  await page.goto(base + "/tasks?assignee=suzuki", { waitUntil: "networkidle" });
  const selected = await page.$eval('select[name="assignee"]', (s) => s.value);
  assert(selected === "suzuki", `selected=${selected}`);
});

await browser.close();
console.log(JSON.stringify(results));
})();
