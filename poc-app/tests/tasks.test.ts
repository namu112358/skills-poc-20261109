import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { openDb } from "../src/lib/db/index.ts";
import { getTask, isTaskStatus, listTasks } from "../src/lib/tasks.ts";

describe("listTasks", () => {
  it("returns all tasks without a filter", () => {
    assert.equal(listTasks({}, openDb()).length, 7);
  });

  it("filters by status", () => {
    const tasks = listTasks({ status: "todo" }, openDb());
    assert.ok(tasks.length > 0);
    assert.ok(tasks.every((t) => t.status === "todo"));
  });
});

describe("getTask", () => {
  it("returns a task by id, or undefined", () => {
    const db = openDb();
    assert.deepEqual(getTask(1, db), {
      id: 1,
      title: "要件定義書のレビュー",
      status: "done",
      assignee: "sato",
      dueDate: "2026-11-02",
    });
    assert.equal(getTask(999, db), undefined);
  });
});

describe("isTaskStatus", () => {
  it("accepts known statuses only", () => {
    assert.equal(isTaskStatus("done"), true);
    assert.equal(isTaskStatus("unknown"), false);
    assert.equal(isTaskStatus(undefined), false);
  });
});
