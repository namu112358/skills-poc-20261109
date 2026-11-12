// W12・W13 の採点用: サーバーの時計を、ファイル（POC_FAKE_NOW_FILE）に書いた時刻から進める。
// ファイルの中身は ISO 8601 の時刻 1 行。ファイルを書き換えると、その時刻から改めて進む（テスト側が lib.cjs の setNow で書く）。
// 使い方: NODE_OPTIONS="--require <このファイル>" POC_FAKE_NOW_FILE=/tmp/x npx next start …
// 引数なしの new Date() と Date.now()・Date() だけを置き換え、日付を指定した new Date(...) は変えない。
"use strict";
const fs = require("node:fs");
const RealDate = Date;
const realNow = RealDate.now.bind(RealDate);
const file = process.env.POC_FAKE_NOW_FILE;
let cache = { mtimeMs: -1, base: realNow(), setAt: realNow() };

function now() {
  if (!file) return realNow();
  try {
    const st = fs.statSync(file);
    if (st.mtimeMs !== cache.mtimeMs) {
      const v = RealDate.parse(fs.readFileSync(file, "utf8").trim());
      if (!Number.isNaN(v)) cache = { mtimeMs: st.mtimeMs, base: v, setAt: realNow() };
    }
  } catch {
    // ファイルが無ければ本当の時刻
  }
  return cache.base + (realNow() - cache.setAt);
}

function FakeDate(...args) {
  if (!new.target) return new RealDate(now()).toString();
  return args.length === 0 ? new RealDate(now()) : new RealDate(...args);
}
Object.setPrototypeOf(FakeDate, RealDate);
FakeDate.prototype = RealDate.prototype;
FakeDate.now = now;
FakeDate.parse = RealDate.parse;
FakeDate.UTC = RealDate.UTC;
globalThis.Date = FakeDate;
