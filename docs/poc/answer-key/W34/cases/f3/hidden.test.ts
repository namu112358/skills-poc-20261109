// W34 f3 の隠しテスト（期限の延長の振る舞い）。採点が tests-hidden/ に置いて流す。
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { openDb } from "../src/lib/db/index.ts";
import { extendDueDate, extendTask, validateExtendInput } from "../src/lib/extend.ts";

describe("f3 hidden", () => {
  it("H1 日数を足し、月・年をまたげる", () => {
    assert.equal(extendDueDate("2026-11-20", 5), "2026-11-25");
    assert.equal(extendDueDate("2026-11-30", 3), "2026-12-03");
    assert.equal(extendDueDate("2026-12-31", 1), "2027-01-01");
  });

  it("H2 1〜30 の整数だけを受け付ける", () => {
    for (const ok of [1, 30]) assert.equal(validateExtendInput({ days: ok }).ok, true, String(ok));
    for (const bad of [0, 31, -1, 1.5, "3", null]) assert.equal(validateExtendInput({ days: bad }).ok, false, String(bad));
    assert.equal(validateExtendInput(null).ok, false);
  });

  it("H3 延長すると期限が変わって保存される", () => {
    const db = openDb();
    const r = extendTask(4, 3, db);
    assert.equal(r.ok && r.task.dueDate, "2026-11-21");
  });

  it("H4 完了したタスクは延長できず、期限も変わらない", () => {
    const db = openDb();
    const r = extendTask(1, 3, db);
    assert.deepEqual(r, { ok: false, reason: "done" });
  });

  it("H5 無いタスクは not_found", () => {
    assert.deepEqual(extendTask(999, 3, openDb()), { ok: false, reason: "not_found" });
  });
});
