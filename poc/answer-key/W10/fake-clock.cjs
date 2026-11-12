// W10 の隠しテスト用: サーバーの時計を POC_FAKE_NOW（既定 2026-11-09T15:30:00.000Z。日本時間では 2026-11-10 00:30）から進める。
// 使い方: NODE_OPTIONS="--require <このファイル>" npx next start …（子プロセスにも NODE_OPTIONS で引き継がれる）
// 引数なしの new Date() と Date.now()・Date() だけを置き換え、日付を指定した new Date(...) は変えない。
"use strict";
const RealDate = Date;
const realNow = RealDate.now.bind(RealDate);
const start = realNow();
const fake = RealDate.parse(process.env.POC_FAKE_NOW || "2026-11-09T15:30:00.000Z");
const now = () => fake + (realNow() - start);

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
