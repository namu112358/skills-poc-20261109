// W5 の隠しの単体テスト（試行中は候補に見せない）。採点時に grade_w5.py が試行の作業用コピーの .poc-hidden/ に置いて実行する。
// src/lib/ の既存の関数を直接呼び、仕込みバグの根本原因（画面や API の手前の層）が直ったかを確かめる。
// テスト名の先頭の [B1]〜[B3] は仕込みバグの番号。
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { openDb } from "../src/lib/db/index.ts";
import { createSession, getSessionUser } from "../src/lib/auth.ts";
import { listTasks, updateTask, validateTaskInput } from "../src/lib/tasks.ts";

const base = { status: "todo", assignee: "tanaka", dueDate: "2026-12-01" };

describe("W5 hidden", () => {
  it("[B1] validateTaskInput は 200 文字ちょうどのタイトルを受け付け、201 文字は拒否する", () => {
    const db = openDb();
    assert.equal(validateTaskInput({ ...base, title: "a".repeat(200) }, {}, db).ok, true);
    assert.equal(validateTaskInput({ title: "a".repeat(200) }, { partial: true }, db).ok, true);
    assert.equal(validateTaskInput({ ...base, title: "a".repeat(201) }, {}, db).ok, false);
  });

  it("[B2] セッションは 7 日間有効（1 時間後・7 日後の直前も有効、7 日を過ぎたら無効）", () => {
    const db = openDb();
    const now = new Date("2026-11-09T00:00:00Z");
    const token = createSession("sato", db, now);
    const at = (ms: number) => new Date(now.getTime() + ms);
    assert.equal(getSessionUser(token, db, at(60 * 60 * 1000))?.id, "sato");
    assert.equal(getSessionUser(token, db, at(7 * 24 * 60 * 60 * 1000 - 60 * 1000))?.id, "sato");
    assert.equal(getSessionUser(token, db, at(7 * 24 * 60 * 60 * 1000 + 1)), undefined);
  });

  it("[B3] updateTask の後の listTasks は、更新後の内容を返す（先に一覧を読んでいても）", () => {
    const db = openDb();
    listTasks({}, db);
    listTasks({ status: "done" }, db);
    listTasks({ status: "in_progress" }, db);
    updateTask(2, { status: "done", title: "変更後" }, db);
    assert.ok(listTasks({ status: "done" }, db).some((t) => t.id === 2 && t.title === "変更後"));
    assert.ok(!listTasks({ status: "in_progress" }, db).some((t) => t.id === 2));
    assert.equal(listTasks({}, db).find((t) => t.id === 2)?.status, "done");
  });
});
