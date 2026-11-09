import { getDb, type Db } from "./db/index.ts";

export type TaskStatus = "todo" | "in_progress" | "done";

export type Task = {
  id: number;
  title: string;
  status: TaskStatus;
  assignee: string;
  dueDate: string; // YYYY-MM-DD
};

export const TASK_STATUSES: readonly TaskStatus[] = ["todo", "in_progress", "done"];

export const STATUS_LABELS: Record<TaskStatus, string> = {
  todo: "未着手",
  in_progress: "進行中",
  done: "完了",
};

export function isTaskStatus(value: unknown): value is TaskStatus {
  return typeof value === "string" && (TASK_STATUSES as readonly string[]).includes(value);
}

export type TaskFilter = {
  status?: TaskStatus;
};

type TaskRow = { id: number; title: string; status: TaskStatus; assignee: string; due_date: string };

function toTask(row: TaskRow): Task {
  return { id: row.id, title: row.title, status: row.status, assignee: row.assignee, dueDate: row.due_date };
}

export function listTasks(filter: TaskFilter = {}, db: Db = getDb()): Task[] {
  const rows = db
    .prepare("SELECT id, title, status, assignee, due_date FROM tasks WHERE (:status IS NULL OR status = :status) ORDER BY id")
    .all({ status: filter.status ?? null }) as TaskRow[];
  return rows.map(toTask);
}

export function getTask(id: number, db: Db = getDb()): Task | undefined {
  const row = db.prepare("SELECT id, title, status, assignee, due_date FROM tasks WHERE id = ?").get(id) as
    | TaskRow
    | undefined;
  return row && toTask(row);
}
