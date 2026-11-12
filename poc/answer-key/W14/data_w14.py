#!/usr/bin/env python3
"""W14（安全な DB 移行）の正解データと、本番相当の DB を作る（試行中は候補に見せない）。

- CANONICAL: 品質保証部が持っている正式な場所の一覧（依頼者役の回答シート Q1 と同じ）。
- 生の値（自由入力の設置場所）と、その値の正解の分類:
    target: 必ずこの場所に寄せる（表記ゆれ）
    either: この場所に寄せても、未確認として残しても正解（寄せる根拠が弱い。違う場所に寄せたら誤り）
    unresolved: どの場所にも寄せてはいけない（あいまい・場所ではない・存在しない）。未確認として元の文字列を残す
    blank: 空欄（未設定のまま）
- 本番の 5 万件の分布は、seed を固定した乱数で毎回同じものを作る。うち HIDDEN の値は抽出ファイル（初期状態の
  docs/data/location-values.csv）に載せない（抽出の後にハンディ端末から入った値。規則で寄せられるかを見る）。

使い方:
  python3 data_w14.py export <csv>            初期状態に置く抽出ファイルを書く
  python3 data_w14.py build-db <db>           旧スキーマ（version 4）+ 初期データの DB に 5 万件を足す
  python3 data_w14.py truth                   生の値 → 分類の JSON を標準出力に出す
"""
import csv
import json
import random
import sqlite3
import sys
import unicodedata

CANONICAL = [
    # (ID, 正式名称, 重み)
    ("C01", "品質保証部 測定室", 8),
    ("C02", "品質保証部 校正待ち棚", 3),
    ("C03", "工事部 倉庫", 10),
    ("C04", "工事部 車両 1 号", 4),
    ("C05", "工事部 車両 2 号", 4),
    ("C06", "工事部 車両 3 号", 4),
    ("C07", "製造部 第 1 ライン", 9),
    ("C08", "製造部 第 2 ライン", 9),
    ("C09", "製造部 第 3 ライン", 7),
    ("C10", "製造部 恒温室", 4),
    ("C11", "製造部 検査室", 6),
    ("C12", "製造部 部品倉庫", 5),
    ("C13", "技術部 試験室", 6),
    ("C14", "技術部 電波暗室", 2),
    ("C15", "大阪営業所", 5),
    ("C16", "名古屋営業所", 4),
]
NAME = {cid: name for cid, name, _ in CANONICAL}

FW_DIGIT = str.maketrans("0123456789", "０１２３４５６７８９")
KANJI = {"1": "一", "2": "二", "3": "三"}
DEPT_ABBR = {"品質保証部": ["品証", "品保", "品質保証"], "工事部": ["工事"], "製造部": ["製造"], "技術部": ["技術"]}


def variants(cid):
    """正式名称から、現場で実際に書かれる表記ゆれ（必ず寄せるもの）を作る。"""
    name = NAME[cid]
    tight = name.replace("第 ", "第").replace(" ライン", "ライン").replace("車両 ", "車両").replace(" 号", "号")
    out = {tight, name.replace(" ", ""), name.replace(" ", "　"), tight.replace(" ", "　"), tight.translate(FW_DIGIT),
           tight.translate(FW_DIGIT).replace(" ", "　"), tight.replace(" ", "")}
    for d, k in KANJI.items():
        if d in tight:
            out.add(tight.replace(d, k))
            out.add(tight.replace(d, k).replace(" ", ""))
    if "号" in tight:
        out.add(tight.replace("号", "号車"))
    if "ライン" in tight:
        out.add(tight.replace("ライン", "ﾗｲﾝ"))
        out.add(unicodedata.normalize("NFKC", tight).replace("ライン", "ﾗｲﾝ").replace(" ", ""))
    for dept, abbrs in DEPT_ABBR.items():
        if name.startswith(dept):
            rest = tight[len(dept):].strip()
            for a in abbrs:
                out.add(f"{a} {rest}")
                out.add(f"{a}{rest}")
    if cid in ("C15", "C16"):
        city = name.replace("営業所", "")
        out |= {f"{city} 営業所", f"{city}営", f"{city}営業所 "}
    out.add(name + " ")  # 末尾の空白
    out.discard(name)
    return sorted(out)


EITHER = [
    ("工事部 倉庫 棚B", "C03"), ("工事部倉庫（本社）", "C03"), ("製造部 第 1 ライン 横", "C07"), ("第2ライン", "C08"),
    ("第 3 ライン", "C09"), ("測定室", "C01"), ("検査室", "C11"), ("恒温室", "C10"), ("電波暗室", "C14"),
    ("大阪事務所", "C15"), ("名古屋営業所 倉庫", "C16"), ("品証 測定室 机上", "C01"), ("車両1号", "C04"),
]
UNRESOLVED = ["倉庫", "車両", "ライン", "本社", "現場", "不明", "？", "?", "-", "要確認", "第 4 ライン", "工事部 車両 5 号",
              "東日本計測サービス（校正中）", "A社 貸出中", "品質保証部 測定室→工事部 倉庫", "社外"]
BLANK = ["", " ", "　"]

# 抽出（2026-10）の後にハンディ端末から入った値。抽出ファイルには載せない（規則で寄せられるかを見る）
HIDDEN = {
    "製造部　第３ライン": "C09", "品証測定室": "C01", "工事部車両２号": "C05", "技術部　電波暗室": "C14",
    "品保 校正待ち棚": "C02", "製造部第二ﾗｲﾝ": "C08", "名古屋　営業所": "C16", "工事部　車両三号": "C06",
    "製造部　恒温室": "C10", "技術試験室": "C13", "製造 部品倉庫": "C12", "大阪 営業所 ": "C15",
}

TOTAL = 50_000
HIDDEN_PER_VALUE = 25


def truth():
    t = {}
    for cid, name, _ in CANONICAL:
        t[name] = {"class": "target", "id": cid}
        for v in variants(cid):
            t.setdefault(v, {"class": "target", "id": cid})
    for v, cid in EITHER:
        t[v] = {"class": "either", "id": cid}
    for v in UNRESOLVED:
        t[v] = {"class": "unresolved", "id": None}
    for v in BLANK:
        t[v] = {"class": "blank", "id": None}
    for v, cid in HIDDEN.items():
        assert v not in t or t[v]["id"] == cid, v
        t[v] = {"class": "target", "id": cid, "hidden": True}
    return t


def distribution():
    """生の値の一覧（5 万件ぶん。決まった順序）。"""
    rng = random.Random(1410)
    values = []
    hidden_total = HIDDEN_PER_VALUE * len(HIDDEN)
    rest = TOTAL - hidden_total
    weights = sum(w for _, _, w in CANONICAL)
    n_either, n_unres, n_blank = int(rest * 0.04), int(rest * 0.03), int(rest * 0.03)
    n_target = rest - n_either - n_unres - n_blank
    for cid, name, w in CANONICAL:
        n = round(n_target * w / weights)
        vs = variants(cid)
        for i in range(n):
            # 52% は正式名称どおり、残りは表記ゆれ（よく使われるものほど多い）
            if rng.random() < 0.58:
                values.append(name)
            else:
                k = min(int(rng.paretovariate(1.2)) - 1, len(vs) - 1)
                values.append(vs[(k + hash_stable(cid)) % len(vs)])
    for pool, n in ((EITHER, n_either), (UNRESOLVED, n_unres), (BLANK, n_blank)):
        for i in range(n):
            v = pool[int(rng.paretovariate(1.0) - 1) % len(pool)]
            values.append(v[0] if isinstance(v, tuple) else v)
    for v in HIDDEN:
        values += [v] * HIDDEN_PER_VALUE
    values = values[:TOTAL]
    while len(values) < TOTAL:
        values.append(CANONICAL[0][1])
    rng.shuffle(values)
    return values


def hash_stable(s):
    return sum(ord(c) for c in s)


def export(path):
    counts = {}
    for v in distribution():
        if v in HIDDEN:
            continue
        counts[v] = counts.get(v, 0) + 1
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["設置場所", "件数"])
        for v, n in sorted(counts.items(), key=lambda x: (-x[1], x[0])):
            w.writerow([v, n])


PREFIXES = ["KA", "KB", "KC", "KD", "KE", "KF"]
NAMES = [("デジタルマルチメータ", "DMM-7510"), ("絶縁抵抗計", "IR-4056"), ("トルクレンチ", "TW-200N"), ("ノギス", "CD-150AX"),
         ("接地抵抗計", "ER-4105"), ("クランプメータ", "CM-2033"), ("マイクロメータ", "MDC-25"), ("検電器", "HT-610"),
         ("オシロスコープ", "DS-1054"), ("温湿度計", "TR-72"), ("ダイヤルゲージ", "DG-10"), ("騒音計", "NL-42")]
MANAGERS = ["sato", "tanaka", "suzuki", "inoue", "yamamoto", "kimura", "kobayashi", "takahashi", "ito"]
STATUSES = ["in_use"] * 80 + ["calibrating"] * 6 + ["suspended"] * 4 + ["disposed"] * 10


def build_db(path):
    """旧スキーマ（version 4。初期データ入り）の DB に、本番相当の計測器 5 万件を足す。初期データの 10 件は残す。"""
    rng = random.Random(2014)
    con = sqlite3.connect(path)
    assert con.execute("PRAGMA user_version").fetchone()[0] == 4, "旧スキーマ（version 4）の DB を渡す"
    values = distribution()
    rows = []
    for i, loc in enumerate(values):
        prefix, num = PREFIXES[i // 9999], i % 9999 + 1
        name, model = NAMES[rng.randrange(len(NAMES))]
        y, m, d = rng.choice([2024, 2025, 2026]), rng.randint(1, 12), rng.randint(1, 28)
        rows.append((f"{prefix}-{num:04d}", name, model, loc, MANAGERS[rng.randrange(len(MANAGERS))],
                     rng.choice([6, 12, 12, 12, 24]), f"{y}-{m:02d}-{d:02d}", STATUSES[rng.randrange(len(STATUSES))],
                     "" if rng.random() < 0.9 else "旧台帳から移行"))
    con.executemany(
        "INSERT INTO instruments (management_no, name, model, location, manager_id, interval_months, last_calibrated_on, status, note)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
    con.commit()
    con.close()


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "export":
        export(sys.argv[2])
    elif cmd == "build-db":
        build_db(sys.argv[2])
    elif cmd == "truth":
        print(json.dumps(truth(), ensure_ascii=False, indent=1))
    else:
        sys.exit(__doc__)
