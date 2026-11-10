// W18 のコードの指標を測る（docs/poc/answer-key/W18/grading.md の「コードの指標」）。全系列・全回で同じ測り方。
// 使い方: node metrics.mjs <アプリのディレクトリ>   → 標準出力に JSON
//   対象は src/ の .ts・.tsx（テストは tests/ にあるので含まれない。src の中の *.test.* も除く）。
//   - complexity: 関数ごとの循環的複雑度（1 + if・三項・&&・||・??・case・for・while・do・catch の数）
//   - size: ファイルの行数（空行を含む）・関数の行数
//   - duplication: jscpd（最小 50 トークン）で見つけた重複の行の割合と箇所数
//   - lint: eslint.config.mjs（typescript-eslint の recommended と複雑さの目安）の警告・誤りの数
//   - tests: tests/ のテストケースの数（it( / test( の数）
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const TOOLS = process.env.W18_METRICS_TOOLS || HERE; // node_modules のある場所
const app = path.resolve(process.argv[2]);

function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== "node_modules" && e.name !== ".next") walk(p, out); }
    else if (/\.(ts|tsx)$/.test(e.name) && !/\.d\.ts$/.test(e.name) && !/\.test\./.test(e.name)) out.push(p);
  }
  return out;
}

const files = walk(path.join(app, "src")).sort();
const functions = [];
const fileSizes = [];
for (const f of files) {
  const text = fs.readFileSync(f, "utf8");
  const rel = path.relative(app, f);
  fileSizes.push({ file: rel, lines: text.split("\n").length });
  const sf = ts.createSourceFile(f, text, ts.ScriptTarget.Latest, true, f.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS);
  const isFn = (n) => ts.isFunctionDeclaration(n) || ts.isMethodDeclaration(n) || ts.isArrowFunction(n) || ts.isFunctionExpression(n)
    || ts.isConstructorDeclaration(n) || ts.isGetAccessor(n) || ts.isSetAccessor(n);
  function nameOf(n) {
    if (n.name && ts.isIdentifier(n.name)) return n.name.text;
    if (n.parent && ts.isVariableDeclaration(n.parent) && ts.isIdentifier(n.parent.name)) return n.parent.name.text;
    if (n.parent && ts.isPropertyAssignment(n.parent) && n.parent.name && ts.isIdentifier(n.parent.name)) return n.parent.name.text;
    return "(無名)";
  }
  function complexity(fn) {
    let c = 1;
    const visit = (n) => {
      if (n !== fn && isFn(n)) return; // 入れ子の関数は別に数える
      switch (n.kind) {
        case ts.SyntaxKind.IfStatement: case ts.SyntaxKind.ConditionalExpression: case ts.SyntaxKind.CaseClause:
        case ts.SyntaxKind.ForStatement: case ts.SyntaxKind.ForInStatement: case ts.SyntaxKind.ForOfStatement:
        case ts.SyntaxKind.WhileStatement: case ts.SyntaxKind.DoStatement: case ts.SyntaxKind.CatchClause:
          c++; break;
        case ts.SyntaxKind.BinaryExpression: {
          const k = n.operatorToken.kind;
          if (k === ts.SyntaxKind.AmpersandAmpersandToken || k === ts.SyntaxKind.BarBarToken || k === ts.SyntaxKind.QuestionQuestionToken) c++;
          break;
        }
      }
      ts.forEachChild(n, visit);
    };
    visit(fn);
    return c;
  }
  const visit = (n) => {
    if (isFn(n) && n.body) {
      const start = sf.getLineAndCharacterOfPosition(n.getStart()).line;
      const end = sf.getLineAndCharacterOfPosition(n.getEnd()).line;
      functions.push({ file: rel, name: nameOf(n), line: start + 1, lines: end - start + 1, complexity: complexity(n) });
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
}

const sum = (xs) => xs.reduce((a, b) => a + b, 0);
const pct = (xs, p) => { if (!xs.length) return 0; const s = [...xs].sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.floor(p * s.length))]; };
const cx = functions.map((f) => f.complexity);

// 重複（jscpd）
let duplication = { error: "not run" };
try {
  const out = path.join(fs.mkdtempSync("/tmp/w18-jscpd-"), "r");
  execFileSync(path.join(TOOLS, "node_modules/.bin/jscpd"), ["--min-tokens", "50", "--reporters", "json", "--output", out, "--silent",
    "--format", "typescript,tsx", "--ignore", "**/*.test.*,**/node_modules/**,**/.next/**", path.join(app, "src")], { stdio: "pipe" });
  const r = JSON.parse(fs.readFileSync(path.join(out, "jscpd-report.json"), "utf8"));
  const t = r.statistics?.total ?? {};
  duplication = { clones: t.clones ?? 0, duplicatedLines: t.duplicatedLines ?? 0, lines: t.lines ?? 0, percentage: t.percentage ?? 0,
    examples: (r.duplicates ?? []).slice(0, 15).map((d) => `${path.relative(app, d.firstFile.name)}:${d.firstFile.start} = ${path.relative(app, d.secondFile.name)}:${d.secondFile.start} (${d.lines} 行)`) };
} catch (e) {
  duplication = { error: String(e.message ?? e).slice(0, 300) };
}

// lint（eslint）
let lint = { error: "not run" };
try {
  let raw;
  try {
    raw = execFileSync(path.join(TOOLS, "node_modules/.bin/eslint"), ["--config", path.join(HERE, "eslint.config.mjs"), "--format", "json", "--no-warn-ignored", "src"],
      { cwd: app, stdio: ["ignore", "pipe", "pipe"], maxBuffer: 64 * 1024 * 1024, env: { ...process.env, NODE_PATH: path.join(TOOLS, "node_modules") } });
  } catch (e) {
    raw = e.stdout; // 誤りがあると終了コードが 1 になる
    if (!raw?.length) throw e;
  }
  const rs = JSON.parse(raw.toString());
  const byRule = {};
  for (const r of rs) for (const m of r.messages) byRule[m.ruleId ?? "parse"] = (byRule[m.ruleId ?? "parse"] ?? 0) + 1;
  lint = { warnings: sum(rs.map((r) => r.warningCount)), errors: sum(rs.map((r) => r.errorCount)), byRule };
} catch (e) {
  lint = { error: String(e.message ?? e).slice(0, 300) };
}

// テストケースの数
const testFiles = fs.existsSync(path.join(app, "tests")) ? fs.readdirSync(path.join(app, "tests")).filter((f) => /\.(ts|tsx|js|mjs)$/.test(f)) : [];
const testCases = sum(testFiles.map((f) => (fs.readFileSync(path.join(app, "tests", f), "utf8").match(/\b(it|test)\s*\(/g) ?? []).length));

const fl = fileSizes.map((f) => f.lines);
console.log(JSON.stringify({
  files: files.length,
  lines: sum(fl),
  size: { maxFileLines: Math.max(0, ...fl), filesOver300: fileSizes.filter((f) => f.lines > 300).map((f) => f.file),
    largest: [...fileSizes].sort((a, b) => b.lines - a.lines).slice(0, 5), maxFunctionLines: Math.max(0, ...functions.map((f) => f.lines)) },
  complexity: { functions: functions.length, mean: functions.length ? +(sum(cx) / functions.length).toFixed(2) : 0, p90: pct(cx, 0.9),
    max: Math.max(0, ...cx), over10: functions.filter((f) => f.complexity > 10).length,
    worst: [...functions].sort((a, b) => b.complexity - a.complexity).slice(0, 8) },
  duplication,
  lint,
  tests: { files: testFiles.length, cases: testCases },
}));
