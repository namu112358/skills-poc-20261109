// W34 f1 の隠しテスト（直した後の振る舞い）。採点（grade_w34.py）が作業用コピーの tests-hidden/ に置いて流す。
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { openDb } from "../src/lib/db/index.ts";
import { createTask, getTask, listTasks, updateTask, validateTaskInput } from "../src/lib/tasks.ts";

describe("f1 hidden", () => {
  it("H1 更新（PATCH）で優先度を変えると保存される", () => {
    const db = openDb();
    const updated = updateTask(1, { priority: "high" } as never, db) as { priority?: string } | undefined;
    assert.equal(updated?.priority, "high");
    assert.equal((getTask(1, db) as { priority?: string }).priority, "high");
  });

  it("H2 優先度を指定しないと中（medium）になる", () => {
    const db = openDb();
    const t = createTask({ title: "x", status: "todo", assignee: "sato", dueDate: "2026-12-01" } as never, db) as {
      priority?: string;
    };
    assert.equal(t.priority, "medium");
  });

  it("H3 優先度で絞り込める（不正な値は指定なし）", () => {
    const db = openDb();
    createTask({ title: "急ぎ", status: "todo", assignee: "sato", dueDate: "2026-12-01", priority: "high" } as never, db);
    assert.deepEqual(
      listTasks({ priority: "high" } as never, db).map((t) => t.title),
      ["急ぎ"],
    );
    assert.equal(listTasks({ priority: "urgent" } as never, db).length, 8);
  });

  it("H4 不正な優先度は入力の誤りになる", () => {
    assert.equal(validateTaskInput({ priority: "urgent" }, { partial: true }, openDb()).ok, false);
    assert.equal(validateTaskInput({ priority: "low" }, { partial: true }, openDb()).ok, true);
  });

  it("H5 ステータスの絞り込みと組み合わせられる", () => {
    const db = openDb();
    createTask({ title: "急ぎ完了", status: "done", assignee: "sato", dueDate: "2026-12-01", priority: "high" } as never, db);
    createTask({ title: "急ぎ未着手", status: "todo", assignee: "sato", dueDate: "2026-12-01", priority: "high" } as never, db);
    assert.deepEqual(
      listTasks({ status: "todo", priority: "high" } as never, db).map((t) => t.title),
      ["急ぎ未着手"],
    );
  });
});
