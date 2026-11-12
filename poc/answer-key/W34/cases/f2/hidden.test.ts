// W34 f2 の隠しテスト（リファクタリングの前の振る舞いが保たれているか）。採点が tests-hidden/ に置いて流す。
// タスクの機能は src/lib/tasks/index.ts（PR の形）か src/lib/tasks.ts（元の形）のどちらかから読む。
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { openDb } from "../src/lib/db/index.ts";

const path = existsSync(new URL("../src/lib/tasks/index.ts", import.meta.url))
  ? "../src/lib/tasks/index.ts"
  : "../src/lib/tasks.ts";
const m = await import(path);

describe("f2 hidden", () => {
  it("H1 タイトルは 200 文字まで（201 文字は入力の誤り）", () => {
    assert.equal(m.validateTaskInput({ title: "あ".repeat(201) }, { partial: true }, openDb()).ok, false);
    assert.equal(m.validateTaskInput({ title: "あ".repeat(200) }, { partial: true }, openDb()).ok, true);
  });

  it("H2 存在しない担当者は入力の誤り", () => {
    assert.equal(m.validateTaskInput({ assignee: "nobody" }, { partial: true }, openDb()).ok, false);
    assert.equal(m.validateTaskInput({ assignee: "tanaka" }, { partial: true }, openDb()).ok, true);
  });

  it("H3 すべての項目が誤っていれば、4 つとも報告する", () => {
    const r = m.validateTaskInput({ title: "", status: "x", assignee: "nobody", dueDate: "12/01" }, {}, openDb());
    assert.equal(r.ok, false);
    assert.equal(!r.ok && r.errors.length, 4);
  });

  it("H4 一覧・取得・作成・更新は元のとおり", () => {
    const db = openDb();
    assert.equal(m.listTasks({}, db).length, 7);
    assert.ok(m.listTasks({ status: "todo" }, db).every((t: { status: string }) => t.status === "todo"));
    const created = m.createTask({ title: "新規", status: "todo", assignee: "sato", dueDate: "2026-12-01" }, db);
    assert.equal(m.updateTask(created.id, { status: "done" }, db).status, "done");
    assert.equal(m.updateTask(999, { status: "done" }, db), undefined);
    assert.equal(m.parseTaskId("01"), undefined);
    assert.equal(m.parseTaskId("3"), 3);
  });
});
