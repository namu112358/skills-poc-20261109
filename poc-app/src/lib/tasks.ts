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

const TASKS: readonly Task[] = [
  { id: 1, title: "要件定義書のレビュー", status: "done", assignee: "sato", dueDate: "2026-11-02" },
  { id: 2, title: "ログイン画面のデザイン", status: "in_progress", assignee: "suzuki", dueDate: "2026-11-12" },
  { id: 3, title: "API 設計", status: "in_progress", assignee: "sato", dueDate: "2026-11-14" },
  { id: 4, title: "DB スキーマ作成", status: "todo", assignee: "tanaka", dueDate: "2026-11-18" },
  { id: 5, title: "CI の整備", status: "todo", assignee: "suzuki", dueDate: "2026-11-20" },
  { id: 6, title: "E2E テストの追加", status: "todo", assignee: "sato", dueDate: "2026-11-25" },
  { id: 7, title: "リリースノート作成", status: "done", assignee: "tanaka", dueDate: "2026-11-05" },
];

export function isTaskStatus(value: unknown): value is TaskStatus {
  return typeof value === "string" && (TASK_STATUSES as readonly string[]).includes(value);
}

export type TaskFilter = {
  status?: TaskStatus;
};

export function listTasks(filter: TaskFilter = {}): Task[] {
  return TASKS.filter((task) => filter.status === undefined || task.status === filter.status);
}
