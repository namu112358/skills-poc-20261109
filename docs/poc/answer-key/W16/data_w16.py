#!/usr/bin/env python3
"""W16 の本番相当のデータ（正解データ。作業用コピーには置かない）。

出荷済みの校正台帳（不具合入り）が 2026-11-07〜11-10 の朝に本番で動いた様子を、出荷済みのコードと同じ手順で
シミュレーションし、次の 2 つを同じ出来事から作る。
  - 本番のログ（logger.ts の形式。運用チームが journalctl -o cat で書き出したもの）→ base.patch の incident/2026-11-10/app.log
  - 本番の DB（旧 DB old-db.sql + 出荷済みの version 5 + その間の送信記録）→ 採点の「本番の DB での後退」に使う
使い方:
  python3 data_w16.py log <出力先>                 ログを書き出す
  python3 data_w16.py facts                        二重に届いた送り先など（回答シート・判定の材料）を JSON で出す
  build_prod_db(db_path) は grade_w16.py から呼ぶ（old-db.sql の DB に出荷済みのコードでマイグレーションを当てた後）
乱数は固定の種で、何度作っても同じものになる。
"""
import calendar
import heapq
import json
import random
import sqlite3
import sys
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
SEED = 41
JST = timezone(timedelta(hours=9))
TIMEOUT = 10.0          # 本番の NOTIFY_API_TIMEOUT_MS は未設定（既定 10 秒）
MAX_ATTEMPTS = 5
CURL_MAX_TIME = 60.0    # 運用の cron: curl --max-time 60 --retry 1（回答シートの O1）

# 重要度 A の計測器（本番の DB での値）。last を書いたものは前回校正日をこの値にする（本番の台帳の状態）
A_INSTRUMENTS = {
    "MI-0002": {"last": "2025-11-08"},  # 貸出中（tanaka → 借りている matsumoto）。期限 2026-11-30
    "MI-0003": {"last": "2026-05-03"},  # suzuki、周期 6 か月。期限 2026-11-30
    "MI-0004": {},                      # 管理者 inoue は無効 → 製造部の代表者 yamada。期限 2026-11-30
    "MI-0010": {"last": "2025-11-25"},  # ito。期限 2026-11-30
    "MI-0016": {},                      # yamada。期限 2025-11-30（期限切れ）
    "MI-0022": {},                      # 管理者 kondo は無効 → 工事部の代表者 sasaki。期限切れ
    "MI-0027": {},                      # kimura。期限切れ（11-07 より前に送信済み）
    "MI-0030": {"last": "2025-11-02"},  # 貸出中（takahashi → 借りている shimizu）。期限 2026-11-30
    "MI-0037": {},                      # suzuki。期限切れ（11-07 に送信。11-09 に不合格で使用停止）
    "MI-0041": {},                      # sasaki。期限切れ
    "MI-0044": {},                      # watanabe。期限切れ（11-07 に送信）
    "MI-0047": {},                      # 管理者 inoue は無効 → yamada。期限切れ
    "MI-0048": {},                      # sato。期限切れ（11-07 より前に送信済み）
    "MI-0052": {},                      # yamada。期限切れ（11-07 より前に送信済み）
}
# 重要度を A にした日（本番の DB の更新。ログには出ない）。この日の翌朝の実行から対象になる
A_FROM = {
    "MI-0027": "2026-11-05", "MI-0048": "2026-11-05", "MI-0052": "2026-11-05",
    "MI-0044": "2026-11-06", "MI-0037": "2026-11-06",
    "MI-0002": "2026-11-08", "MI-0004": "2026-11-08", "MI-0016": "2026-11-08", "MI-0022": "2026-11-08",
    "MI-0030": "2026-11-08", "MI-0041": "2026-11-09",
    "MI-0003": "2026-11-09", "MI-0010": "2026-11-09", "MI-0047": "2026-11-09",
}
INSTRUMENTS = {  # 管理番号 → (id, 名称, 型式, 設置場所, 管理者, 周期, 前回校正日, 状態)（old-db.sql の値。last は上で上書き）
    "MI-0002": (2, "絶縁抵抗計", "IR-4056", "工事部 倉庫", "tanaka", 12, "2025-12-08", "on_loan"),
    "MI-0003": (3, "トルクレンチ", "TW-200N", "製造部 第 1 ライン", "suzuki", 6, "2026-06-03", "in_use"),
    "MI-0004": (4, "ノギス", "CD-150AX", "製造部 第 2 ライン", "inoue", 12, "2025-11-27", "in_use"),
    "MI-0010": (10, "温湿度計", None, None, "ito", 12, "2025-12-25", "in_use"),
    "MI-0016": (16, "接地抵抗計", None, None, "yamada", 6, "2025-05-17", "in_use"),
    "MI-0022": (22, "圧力計", None, None, "kondo", 12, "2025-10-03", "in_use"),
    "MI-0027": (27, "ノギス", None, None, "kimura", 24, "2024-03-12", "in_use"),
    "MI-0030": (30, "マイクロメータ", None, None, "takahashi", 12, "2025-12-02", "on_loan"),
    "MI-0037": (37, "絶縁抵抗計", None, None, "suzuki", 12, "2025-07-25", "in_use"),
    "MI-0041": (41, "クランプメータ", None, None, "sasaki", 12, "2025-02-02", "in_use"),
    "MI-0044": (44, "騒音計", None, None, "watanabe", 6, "2026-01-21", "in_use"),
    "MI-0047": (47, "ダイヤルゲージ", None, None, "inoue", 24, "2024-10-17", "in_use"),
    "MI-0048": (48, "デジタルマルチメータ", None, None, "sato", 6, "2026-04-03", "in_use"),
    "MI-0052": (52, "接地抵抗計", None, None, "yamada", 6, "2025-09-02", "in_use"),
}
REPRESENTATIVE = {"inoue": "yamada", "kondo": "sasaki"}   # 無効な管理者 → 部署の代表者
BORROWER = {"MI-0002": "matsumoto", "MI-0030": "shimizu"}
NOT_FOUND = {"shimizu"}  # 通知サービスの社員マスタに無い（人事の ID の付け替え漏れ）→ 400。二重送信とは関係ないおとり
SUSPENDED_ON = {"MI-0037": "2026-11-09"}  # 11-09 10:20 に不合格の校正記録 → 使用停止（ログの calibration.failed）


def due_on(last, months):
    y, m, _ = map(int, last.split("-"))
    mi = m - 1 + months
    y2, m2 = y + mi // 12, mi % 12 + 1
    return f"{y2:04d}-{m2:02d}-{calendar.monthrange(y2, m2)[1]:02d}"


def last_of(no):
    return A_INSTRUMENTS[no].get("last") or INSTRUMENTS[no][6]


def kind_of(no, today):
    d = due_on(last_of(no), INSTRUMENTS[no][5])
    if today > d:
        return "overdue", d
    dd = datetime.strptime(d, "%Y-%m-%d") - timedelta(days=30)
    return ("due_soon" if today >= dd.strftime("%Y-%m-%d") else "ok"), d


def recipients(no):
    mgr = INSTRUMENTS[no][4]
    out = [REPRESENTATIVE.get(mgr, mgr)]
    if no in BORROWER and BORROWER[no] not in out:
        out.append(BORROWER[no])
    return out


def iso(t):
    return t.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.") + f"{t.microsecond // 1000:03d}Z"


class World:
    """出荷済みのコードの振る舞い（calibration-reminders.ts・notify-client.ts）を時刻つきで再現する。"""

    def __init__(self, seed=None):
        self.rng = random.Random(SEED if seed is None else seed)
        self.rows = []         # calibration_notifications の行
        self.log = []          # (時刻, 行)
        self.deliveries = []   # 通知サービスが実際に送ったもの
        self.requests = []
        self.next_ntf = 48113

    def emit(self, t, level, event, **fields):
        self.log.append((t, json.dumps({"ts": iso(t), "level": level, "event": event, **fields}, ensure_ascii=False, separators=(",", ":"))))

    def raw(self, t, line):
        self.log.append((t, line))

    def latency(self, day, slow):
        r = self.rng.random()
        if not slow:
            return 0.15 + self.rng.random() * 0.35, None
        if r < 0.74:
            return 5.0 + self.rng.random() * 4.6, None
        if r < 0.80:
            return 1.0 + self.rng.random(), 429
        return 10.5 + self.rng.random() * 9, None  # 応答が 10 秒を超える（受け付けて送ってはいる）

    def run(self, t0, day, slow, run_no, starts):
        """1 回のジョブの実行（ジェネレーター。待ち時間を返しながら進む）。"""
        today = day
        self.emit(t0, "info", "job.started", job="calibration-reminders")
        summary = {"today": today, "candidates": 0, "sent": 0, "skipped": 0, "failed": 0}
        t = t0
        for no in sorted(A_INSTRUMENTS):
            if A_FROM[no] >= day:
                continue
            if no in SUSPENDED_ON and SUSPENDED_ON[no] < day:
                continue
            kind, d = kind_of(no, today)
            if kind == "ok":
                continue
            for rcp in recipients(no):
                summary["candidates"] += 1
                if any(r["mno"] == no and r["kind"] == kind and r["due_on"] == d and r["recipient"] == rcp and r["status"] == "sent" for r in self.rows):
                    summary["skipped"] += 1
                    continue
                row = {"id": len(self.rows) + 101, "mno": no, "kind": kind, "due_on": d, "recipient": rcp, "status": "pending",
                       "attempts": 0, "notification_id": None, "last_error": None, "created_at": iso(t), "sent_at": None}
                self.rows.append(row)
                res = None
                for attempt in range(1, MAX_ATTEMPTS + 1):
                    key = f"calibration-notification-{row['id']}-{attempt}"
                    lat, status = self.latency(day, slow)
                    if rcp in NOT_FOUND:
                        lat, status = (0.4 if not slow else 3.1 + self.rng.random() * 3), 400
                    self.requests.append({"t": iso(t), "key": key, "recipient": rcp, "mno": no, "kind": kind, "run": run_no})
                    if status is None:
                        ntf = f"ntf_{self.next_ntf}"
                        self.next_ntf += self.rng.randint(1, 40)
                        self.deliveries.append({"t": iso(t + timedelta(seconds=lat * 0.9)), "key": key, "recipient": rcp, "mno": no,
                                                "kind": kind, "due_on": d, "id": ntf, "run": run_no, "attempt": attempt})
                    if lat > TIMEOUT:
                        dt = yield TIMEOUT
                        t = dt
                        last = {"status": None, "error": f"タイムアウト（{int(TIMEOUT * 1000)}ms）"}
                    else:
                        dt = yield lat
                        t = dt
                        if status is None:
                            res = {"ok": True, "id": ntf, "attempts": attempt}
                            break
                        last = {"status": status, "error": {400: '{"error":"recipient not found"}', 429: '{"error":"too many requests"}'}[status]}
                        if status == 400:
                            res = {"ok": False, "retryable": False, **last, "attempts": attempt}
                            break
                    if attempt < MAX_ATTEMPTS:
                        exp = min(8000, 500 * 2 ** (attempt - 1))
                        wait = round(exp * (0.5 + self.rng.random() * 0.5))
                        if last["status"] == 429:
                            wait = max(wait, 20000)
                        f = {"recipient": rcp, "attempt": attempt}
                        if last["status"] is not None:
                            f["status"] = last["status"]
                        self.emit(t, "warn", "notify.retry", **f, error=last["error"], waitMs=wait)
                        t = yield wait / 1000
                    else:
                        res = {"ok": False, "retryable": True, **last, "attempts": attempt}
                fields = {"instrumentId": INSTRUMENTS[no][0], "managementNo": no, "kind": kind, "dueOn": d, "recipient": rcp, "attempts": res["attempts"]}
                if res["ok"]:
                    row.update(status="sent", attempts=res["attempts"], notification_id=res["id"], sent_at=iso(t))
                    summary["sent"] += 1
                    self.emit(t, "info", "calibration_reminder.sent", **fields, notificationId=res["id"])
                else:
                    row.update(status="failed", attempts=res["attempts"], last_error=f"{res['status'] or ''} {res['error']}".strip())
                    summary["failed"] += 1
                    ef = {**fields}
                    if res["status"] is not None:
                        ef["status"] = res["status"]
                    self.emit(t, "error", "calibration_reminder.failed", **ef, retryable=res["retryable"], error=res["error"])
                t = yield 0.002
        self.emit(t, "info", "job.completed", job="calibration-reminders", **summary, durationMs=int((t - t0).total_seconds() * 1000))

    def day(self, day, slow):
        """その日の 7:30（日本時間）の cron。curl が 120 秒で切ったら 1 回だけ呼び直す。"""
        start = datetime.strptime(day + " 07:30:00", "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST) + timedelta(milliseconds=self.rng.randint(80, 400))
        q = []
        gens = {}
        finished = {}
        seq = 0

        def add(gen_id, at, gen):
            nonlocal seq
            gens[gen_id] = gen
            try:
                w = next(gen)
            except StopIteration:
                finished[gen_id] = at
                return
            seq += 1
            heapq.heappush(q, (at + timedelta(seconds=w), seq, gen_id))

        g1 = self.run(start, day, slow, 1, None)
        gens[1] = g1
        add(1, start, g1)
        retry_at = start + timedelta(seconds=CURL_MAX_TIME + 1 + self.rng.random() * 0.4)
        started2 = False
        while q or not started2:
            if not started2 and (not q or q[0][0] >= retry_at):
                if 1 not in finished:
                    g2 = self.run(retry_at, day, slow, 2, None)
                    add(2, retry_at, g2)
                started2 = True
                continue
            at, _, gid = heapq.heappop(q)
            try:
                w = gens[gid].send(at)
                seq += 1
                heapq.heappush(q, (at + timedelta(seconds=w), seq, gid))
            except StopIteration:
                finished[gid] = at


def noise(w):
    """ジョブと関係の無いログ（おとりを含む）。"""
    def at(s):
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f").replace(tzinfo=JST)
    for d in ["2026-11-07", "2026-11-08", "2026-11-09"]:
        t = at(d + " 08:00:00.231")
        w.emit(t + timedelta(milliseconds=6), "info", "job.completed", job="overdue-loans", today=d, overdue=0)
    w.emit(at("2026-11-10 08:00:00.198") + timedelta(milliseconds=7), "info", "job.completed", job="overdue-loans", today="2026-11-10", overdue=0)
    for s, u in [("2026-11-07 09:12:44.010", "kobayashi"), ("2026-11-09 08:41:02.551", "yoshida"), ("2026-11-09 08:41:09.904", "yoshida"),
                 ("2026-11-09 08:41:21.367", "yoshida"), ("2026-11-09 13:05:37.770", "hayashi"), ("2026-11-10 08:12:15.032", "matsumoto")]:
        w.emit(at(s), "warn", "auth.login_failed", userId=u)
    w.emit(at("2026-11-09 10:05:13.402"), "warn", "job.unauthorized", job="calibration-reminders")
    w.emit(at("2026-11-09 10:05:41.118"), "warn", "job.unauthorized", job="calibration-reminders")
    w.emit(at("2026-11-09 10:20:08.649"), "warn", "calibration.failed", instrumentId=37, managementNo="MI-0037", calibrationId=88,
           calibratedOn="2026-11-06", agency="東日本計測サービス", recordedBy="suzuki")
    # 11-09 2:00 の OS の更新による再起動（アプリの版は同じ）。next start の起動の表示は JSON ではない
    t = at("2026-11-09 02:03:11.000")
    for i, line in enumerate(["> poc-app@0.1.0 start", "> next start", "", "   ▲ Next.js 16.4.3", "   - Local:        http://localhost:3000",
                              "   - Network:      http://10.20.4.17:3000", "", " ✓ Starting...", " ✓ Ready in 512ms"]):
        w.raw(t + timedelta(milliseconds=i), line)


def simulate():
    w = World()
    # 11-07 より前に送信済みのもの（本番の DB にある。ログの範囲の外）
    for no, day in [("MI-0027", "2026-11-06"), ("MI-0048", "2026-11-06"), ("MI-0052", "2026-11-06")]:
        kind, d = kind_of(no, day)
        for rcp in recipients(no):
            t = datetime.strptime(day + " 07:30:01", "%Y-%m-%d %H:%M:%S").replace(tzinfo=JST)
            w.rows.append({"id": len(w.rows) + 101, "mno": no, "kind": kind, "due_on": d, "recipient": rcp, "status": "sent", "attempts": 1,
                           "notification_id": f"ntf_{47900 + len(w.rows)}", "last_error": None, "created_at": iso(t), "sent_at": iso(t + timedelta(seconds=0.3))})
    log_from = len(w.log)
    w.day("2026-11-07", slow=False)
    w.day("2026-11-08", slow=False)
    w.day("2026-11-09", slow=True)
    w.day("2026-11-10", slow=True)
    noise(w)
    return w


def facts(w=None):
    w = w or simulate()
    groups = {}
    for d in w.deliveries:
        groups.setdefault((d["recipient"], d["mno"], d["kind"], d["due_on"]), []).append(d)
    dup = []
    for (rcp, no, kind, due), ds in sorted(groups.items()):
        if len(ds) > 1:
            cause = []
            if len({x["run"] for x in ds}) > 1:
                cause.append("A: 2 回の実行が両方送った")
            runs = {}
            for x in ds:
                runs.setdefault(x["run"], []).append(x)
            if any(len(v) > 1 for v in runs.values()):
                cause.append("B: タイムアウトの後の再試行で、別のキーで送り直した")
            dup.append({"recipient": rcp, "managementNo": no, "kind": kind, "dueOn": due, "count": len(ds),
                        "times_jst": [datetime.strptime(x["t"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC).astimezone(JST).strftime("%m-%d %H:%M:%S") for x in ds],
                        "keys": [x["key"] for x in ds], "cause": cause})
    sent_rows = [r for r in w.rows if r["status"] == "sent"]
    return {"duplicates": dup, "rows": len(w.rows), "sent_rows": len(sent_rows), "deliveries": len(w.deliveries)}


def log_text(w=None):
    w = w or simulate()
    lines = [l for _, l in sorted(w.log, key=lambda x: x[0])]
    return "\n".join(lines) + "\n"


def build_prod_db(path):
    """old-db.sql に出荷済みの version 5 を当てた DB（path）に、本番の 11-10 朝の時点の状態を書き込む。"""
    w = simulate()
    con = sqlite3.connect(path)
    for no, v in A_INSTRUMENTS.items():
        con.execute("UPDATE instruments SET importance = 'A' WHERE management_no = ?", (no,))
        if v.get("last"):
            con.execute("UPDATE instruments SET last_calibrated_on = ? WHERE management_no = ?", (v["last"], no))
    con.execute("UPDATE instruments SET status = 'suspended' WHERE management_no = 'MI-0037'")
    con.execute("INSERT INTO calibration_records (instrument_id, calibrated_on, result, agency, certificate_no, recorded_by, recorded_at) "
                "VALUES (37, '2026-11-06', 'fail', '東日本計測サービス', 'EJ-26-02011', 'suzuki', '2026-11-09T01:20:08.649Z')")
    ids = {no: INSTRUMENTS[no][0] for no in INSTRUMENTS}
    for r in w.rows:
        con.execute("INSERT INTO calibration_notifications (id, instrument_id, kind, due_on, recipient_id, status, attempts, notification_id, "
                    "last_error, created_at, sent_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["id"], ids[r["mno"]], r["kind"], r["due_on"], r["recipient"], r["status"], r["attempts"], r["notification_id"],
                     r["last_error"], r["created_at"], r["sent_at"]))
    con.commit()
    con.close()
    return w


def sent_targets():
    """本番の DB で送信済み（sent）のお知らせ（管理番号・種類・期限・送り先）。11-11 の実行で送り直してはいけないもの。"""
    w = simulate()
    return sorted({(r["mno"], r["kind"], r["due_on"], r["recipient"]) for r in w.rows if r["status"] == "sent"})


if __name__ == "__main__":
    if sys.argv[1] == "log":
        open(sys.argv[2], "w").write(log_text())
    elif sys.argv[1] == "facts":
        print(json.dumps(facts(), ensure_ascii=False, indent=1))
