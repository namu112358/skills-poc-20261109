#!/usr/bin/env python3
"""W19 の採点用: 本番相当の旧 DB（マイグレーション 5 まで + 約 5 万件の計測器）を作る（正解データ。試行中は候補に見せない）。

計測器のその他の項目（extra）に、担当部署（dept）・点検者（inspector）・最終点検日（last_inspected）・メモを、決まりなく入れる。
- 点検者: 6 割は利用者の名前（一部は「さん」「様」つき・前後の空白）、1 割は分からない名前（外部委託・メーカー点検・不明）、3 割は無し。
- 最終点検日: 「2026-09-01」「2026/9/1」「R8.9.10」と、読めないもの（先月・未定・2026-02-30）。
truth() は管理番号ごとの正解（寄せるべき利用者・読めるべき日付・元の書き方）を返す。乱数の種を固定し、毎回同じ DB を作る。
使い方: python3 data_w19.py build-db <DB のパス>   （初期状態のアプリで作った旧スキーマの DB に足す）
"""
import json
import random
import sqlite3
import sys

N = 50000
SEED = 1919
DEPTS = ["品質保証部", "製造部", "工事部", "品証", "製造部 第1課", ""]
# 初期データの利用者（seed.ts と同じ）。inoue・kondo は在籍していない
USERS = [("sato", "佐藤"), ("suzuki", "鈴木"), ("tanaka", "田中"), ("kimura", "木村"), ("yamada", "山田"), ("sasaki", "佐々木"),
         ("takahashi", "高橋"), ("ito", "伊藤"), ("watanabe", "渡辺"), ("yamamoto", "山本"), ("kobayashi", "小林"), ("kato", "加藤"),
         ("yoshida", "吉田"), ("matsumoto", "松本"), ("hayashi", "林"), ("shimizu", "清水"), ("inoue", "井上"), ("kondo", "近藤")]
ACTIVE = [u for u in USERS if u[0] not in ("inoue", "kondo")]
UNKNOWN = ["外部委託", "メーカー点検", "不明", "前任者"]
BAD_DATES = ["先月", "未定", "2026-02-30", "9月頃"]


def _rows():
    rnd = random.Random(SEED)
    for n in range(N):
        no = f"Z{chr(65 + n // 10000)}-{n % 10000:04d}"  # ZA-0000〜ZE-9999（初期データの MI-xxxx とぶつからない）
        uid, uname = rnd.choice(ACTIVE)
        extra = {}
        dept = rnd.choice(DEPTS)
        if dept:
            extra["dept"] = dept
        r = rnd.random()
        expect_user, raw_name = None, ""
        if r < 0.6:
            iu, iname = rnd.choice(USERS)
            raw_name = iname + rnd.choice(["", "", "", "さん", "様", " "])
            if rnd.random() < 0.1:
                raw_name = " " + raw_name
            expect_user = iu
        elif r < 0.7:
            raw_name = rnd.choice(UNKNOWN)
        if raw_name:
            extra["inspector"] = raw_name
        raw_date, expect_date = "", None
        if raw_name or rnd.random() < 0.1:
            y, m, d = 2026, rnd.randint(1, 10), rnd.randint(1, 28)
            fmt = rnd.random()
            if fmt < 0.6:
                raw_date, expect_date = f"{y}-{m:02d}-{d:02d}", f"{y}-{m:02d}-{d:02d}"
            elif fmt < 0.8:
                raw_date, expect_date = f"{y}/{m}/{d}", f"{y}-{m:02d}-{d:02d}"
            elif fmt < 0.9:
                raw_date, expect_date = f"R8.{m}.{d}", f"{y}-{m:02d}-{d:02d}"
            else:
                raw_date = rnd.choice(BAD_DATES)
            extra["last_inspected"] = raw_date
        if rnd.random() < 0.15:
            extra["memo"] = rnd.choice(["置き場所に注意", "予備機", "ケース破損あり", "貸出多い"])
        yield {"no": no, "manager": uid, "extra": extra, "expect_user": expect_user, "raw_name": raw_name,
               "raw_date": raw_date, "expect_date": expect_date, "interval": rnd.choice([6, 12, 12, 24]),
               "last_cal": f"2025-{rnd.randint(1, 12):02d}-{rnd.randint(1, 28):02d}",
               "status": rnd.choice(["in_use"] * 8 + ["calibrating", "suspended"])}


def truth():
    return list(_rows())


def build_db(path):
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    ver = con.execute("PRAGMA user_version").fetchone()[0]
    if ver != 5:
        raise RuntimeError(f"旧スキーマ（version 5）の DB ではありません: {ver}")
    con.executemany(
        "INSERT INTO instruments (management_no, name, model, location, manager_id, interval_months, last_calibrated_on, status, note, extra) "
        "VALUES (?, ?, '', '本社', ?, ?, ?, ?, '', ?)",
        [(r["no"], "計測器 " + r["no"], r["manager"], r["interval"], r["last_cal"], r["status"], json.dumps(r["extra"], ensure_ascii=False))
         for r in _rows()])
    con.commit()
    con.close()


if __name__ == "__main__":
    if sys.argv[1] == "build-db":
        build_db(sys.argv[2])
    else:
        t = truth()
        print(len(t), sum(1 for r in t if r["expect_user"]), sum(1 for r in t if r["raw_name"] and not r["expect_user"]),
              sum(1 for r in t if r["raw_date"] and not r["expect_date"]))
