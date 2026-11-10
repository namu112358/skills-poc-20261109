// W15 の採点用: B 社の CSV の日付（2026 年 12 月）が採点の日より後になるため、未来の日付を誤りにする候補を
// 誤って落とさないよう、採点のサーバーの時計を POC_FAKE_NOW に進める（node --require で読み込む。試行の後に足した補正）。
const target = Date.parse(process.env.POC_FAKE_NOW || "");
if (!Number.isNaN(target)) {
  const Real = Date;
  const offset = target - Real.now();
  function FakeDate(...args) {
    if (!new.target) return new Real(Real.now() + offset).toString();
    return args.length === 0 ? new Real(Real.now() + offset) : new Real(...args);
  }
  FakeDate.prototype = Real.prototype;
  FakeDate.now = () => Real.now() + offset;
  FakeDate.parse = Real.parse;
  FakeDate.UTC = Real.UTC;
  globalThis.Date = FakeDate;
}
