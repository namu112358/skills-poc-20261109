// ログインとセッション。Next.js に依存しない部分（単体テストの対象）。Cookie の読み書きは session.ts。
import { randomBytes } from "node:crypto";
import { getDb, type Db } from "./db/index.ts";
import { verifyPassword } from "./password.ts";
import type { User } from "./users.ts";

export const SESSION_COOKIE = "poc_session";
export const SESSION_TTL_MS = 7 * 24 * 60 * 60 * 1000;

/** ID とパスワードが正しければユーザーを返す。 */
export function authenticate(userId: string, password: string, db: Db = getDb()): User | undefined {
  const row = db.prepare("SELECT id, name, password_hash FROM users WHERE id = ?").get(userId) as
    | { id: string; name: string; password_hash: string }
    | undefined;
  if (!row || !verifyPassword(password, row.password_hash)) return undefined;
  return { id: row.id, name: row.name };
}

export function createSession(userId: string, db: Db = getDb(), now: Date = new Date()): string {
  const token = randomBytes(32).toString("hex");
  const expiresAt = new Date(now.getTime() + SESSION_TTL_MS).toISOString();
  db.prepare("INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)").run(token, userId, expiresAt);
  return token;
}

/** 有効なセッションのユーザーを返す。期限切れ・不明なトークンは undefined。 */
export function getSessionUser(token: string | undefined, db: Db = getDb(), now: Date = new Date()): User | undefined {
  if (!token) return undefined;
  return db
    .prepare("SELECT u.id, u.name FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token = ? AND s.expires_at > ?")
    .get(token, now.toISOString()) as User | undefined;
}

export function deleteSession(token: string, db: Db = getDb()): void {
  db.prepare("DELETE FROM sessions WHERE token = ?").run(token);
}
