// W10 の採点用: サーバーの時計をずらす（NODE_OPTIONS="--require <このファイル>"、POC_FAKE_NOW=<ISO 8601>）。
// 起動した時点を POC_FAKE_NOW とし、そこから実時間で進む。引数なしの new Date() と Date.now() だけを差し替える。
// 既定の 2026-11-09T15:30:00Z は日本時間の 2026-11-10 00:30（UTC ではまだ 11/09）で、日付の扱いの時差を確かめるため。
"use strict";
const fake = Date.parse(process.env.POC_FAKE_NOW || "2026-11-09T15:30:00.000Z");
const RealDate = Date;
const offset = fake - RealDate.now();
// クラスの継承ではなく関数にし、静的メソッド（UTC・parse）も自前で持たせる（Next.js が Date の自前のプロパティだけを写す場合があるため）
function FakeDate(...args) {
  if (!new.target) return new RealDate(RealDate.now() + offset).toString();
  return args.length === 0 ? new RealDate(RealDate.now() + offset) : new RealDate(...args);
}
FakeDate.prototype = RealDate.prototype;
FakeDate.now = () => RealDate.now() + offset;
FakeDate.UTC = RealDate.UTC;
FakeDate.parse = RealDate.parse;
globalThis.Date = FakeDate;
