// W34 f4 の隠しテスト（集計の振る舞い。時刻は引数で渡す）。採点が tests-hidden/ に置いて流す。
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { openDb } from "../src/lib/db/index.ts";
import { parseSoonDays, summarizeTasks } from "../src/lib/summary.ts";

// 日本時間 2026-11-12 10:00
const now = new Date("2026-11-12T10:00:00+09:00");

describe("f4 hidden", () => {
  it("H1 初期データを、渡した時刻を基準に数える", () => {
    assert.deepEqual(summarizeTasks(openDb(), now), { total: 7, overdue: 0, dueToday: 1, dueSoon: 2 });
  });

  it("H2 日本時間の日付で数える（日本時間の朝 = UTC の前日でも）", () => {
    const morning = new Date("2026-11-13T08:00:00+09:00");
    const s = summarizeTasks(openDb(), morning);
    assert.equal(s.overdue, 1); // 11-12 が期限の進行中のタスク
    assert.equal(s.dueToday, 0);
  });

  it("H3 期限が近いの日数を変えられる", () => {
    assert.equal(summarizeTasks(openDb(), now, 14).dueSoon, 4);
  });

  it("H4 日数の検証", () => {
    assert.deepEqual(parseSoonDays(null), { ok: true, days: 7 });
    for (const ok of ["1", "90"]) assert.equal(parseSoonDays(ok).ok, true, ok);
    for (const bad of ["0", "91", "abc", "1.5", "-1"]) assert.equal(parseSoonDays(bad).ok, false, bad);
  });
});
