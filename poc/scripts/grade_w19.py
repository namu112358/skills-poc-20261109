#!/usr/bin/env python3
"""W19（粗悪な既存実装に引っ張られない）の採点。配点は poc/answer-key/W19/grading.md。

使い方:
  python3 poc/scripts/grade_w19.py <試行ID>                                         試行を採点する（grade.py の共通の採点のあとに W19 の分）
  python3 poc/scripts/grade_w19.py --app <アプリ> --base <コミット> [--out <JSON>] [--no-mutation]   試行前の確認用

見るもの:
  - 公開・隠し: 新しい DB で起動して API で確かめる（点検の担当者・記録・次の点検予定日・絞り込み・遅れの台数・要修理・互換）
  - データの持ち方: 担当者・記録が専用の列や表にあり、その他の項目（extra）に入っていないか。新しいコードが extra を増やしていないか
  - 移行: 旧スキーマ + 本番相当の 5 万件の DB で起動し、データ・担当部署を失わず、点検者・最終点検日を引き継ぐか。前の版に戻せるか
  - 範囲: extra を全部作り直していないか。残した課題を書き残したか
候補ごとに違う名前（API の項目名・クエリの名前・結果の値）は、候補が足したコードの識別子と文字列から候補を作って試す。
見つけられないときは W19/adapters/<試行ID>.json で補正する（"assign"・"record"・"filter" などを上書き）。
"""
import importlib.util
import itertools
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEY = ROOT / "poc" / "answer-key" / "W19"
RESULTS = ROOT / "poc" / "results" / "workflow" / "W19"
sys.path.insert(0, str(HERE))
import grade_w14 as g14  # noqa: E402

_spec = importlib.util.spec_from_file_location("data_w19", KEY / "data_w19.py")
DATA = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(DATA)

BASE_TABLES = ["departments", "users", "sessions", "instruments", "loans", "calibration_records"]
BASE_INST_COLS = ["id", "management_no", "name", "model", "location", "manager_id", "interval_months", "last_calibrated_on",
                  "status", "note", "extra"]
USER_IDS = {u for u, _ in DATA.USERS}
need, show = g14.need, g14.show


def override():
    return json.loads(os.environ.get("W19_OVERRIDE") or "{}")


# ---- 候補のコードから名前の候補を作る ----

def code_tokens(app, base):
    lines = [l for f, l in g14.added_lines(app, base, ["src"]) if ".test." not in f]
    code = "\n".join(lines)
    ids = list(dict.fromkeys(re.findall(r"\b([A-Za-z][A-Za-z0-9_]{1,40})\b", code)))
    lits = list(dict.fromkeys(re.findall(r"[\"'`]([^\"'`\n]{1,40})[\"'`]", code)))
    return ids, lits


def pick(ids, pattern, defaults, limit=10):
    found = [i for i in ids if re.search(pattern, i)]
    return list(dict.fromkeys(defaults + found))[:limit]


def full_text(c, path, timeout=120):
    """応答の本文を全部返す（grade_w14 の Client は本文を 2000 文字で切るため。画面や一覧の中を探すときに使う。試行後の修正）。"""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(c.base + path, headers={"authorization": f"Bearer {c.token}"} if c.token else {})
    try:
        with c.opener.open(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
        return str(e)


def deep_find(j, value, path=""):
    """JSON の中で value と等しい値を持つ場所（キーの道のり）を返す。"""
    out = []
    if isinstance(j, dict):
        for k, v in j.items():
            out += deep_find(v, value, f"{path}.{k}")
    elif isinstance(j, list):
        for i, v in enumerate(j):
            out += deep_find(v, value, f"{path}[{i}]")
    elif j == value:
        out.append(path)
    return out


def objects(j):
    if isinstance(j, dict):
        yield j
        for v in j.values():
            yield from objects(v)
    elif isinstance(j, list):
        for v in j:
            yield from objects(v)


def fill(path, iid):
    return re.sub(r"\[[^\]]+\]", str(iid), path, count=1)


def list_nos(j):
    return [x.get("managementNo") for x in g14.list_from(j) if isinstance(x, dict)]


# ---- 公開・隠し（新しい DB） ----

def api_suite(app, work, routes, base):
    pub, hid = g14.Probe(), g14.Probe()
    ids, lits = code_tokens(app, base)
    ov = override()
    db = Path(work) / "api.db"
    srv = g14.Server(app, work, "api", db)
    detail = {"routes": routes}
    if not srv.start():
        detail["start"] = srv.log.read_text()[-600:]
        return pub.results, hid.results, detail
    try:
        c = g14.Client(srv.base()).login("sato")
        lst = c.call("GET", "/api/instruments")
        by_no = {x["managementNo"]: x["id"] for x in g14.list_from(lst["json"]) if isinstance(x, dict) and "managementNo" in x}
        st = {"by_no": by_no}

        def inst(no):
            return c.call("GET", f"/api/instruments/{by_no[no]}")["json"]

        # 担当者を付ける方法を探す
        assign_keys = ov.get("assign_keys") or pick(ids, r"(?i)inspect|assign", ["inspectorId", "inspector_id", "inspectionAssigneeId", "assigneeId", "inspector"])
        # 単数形の inspection（担当者・周期の設定）も含める。記録の送り先（inspections）は除く（2026-11-10 試行後の修正）
        assign_routes = [r for r in routes if re.search(r"(?i)inspector|assign|inspection(?!s)|schedule|plan", r["path"]) and "[" in r["path"]]

        def try_assign(no, user):
            iid = by_no[no]
            def body(key, wrap):
                return {"extra": {key: user}} if wrap else {key: user}
            if st.get("assign"):
                m, path, key, wrap = st["assign"]
                return c.call(m, fill(path, iid), body(key, wrap))
            tries = [("PATCH", "/api/instruments/[id]", k, False) for k in assign_keys]
            for r in assign_routes:
                for m in [x for x in ("PUT", "POST", "PATCH") if x in r["methods"]]:
                    tries += [(m, r["path"], k, False) for k in assign_keys + ["userId", "user_id", "id"]]
            # 担当者をその他の項目（extra）に入れる作りも、業務の点では動けば認める（持ち方は S で見る）
            extra_keys = []
            for _, l in g14.added_lines(app, base, ["src"]):
                for k in re.findall(r"\bextra\??\.\??\[?[\"'`]?(\w+)", l):
                    if re.search(r"(?i)inspect|assign", k) and k not in extra_keys and not re.search(r"(?i)^(last_)?inspect(ed|ions?)$|_on$|date", k):
                        extra_keys.append(k)
            # extra.inspector は初期状態の自由記述の点検者なので、担当者を付ける方法としては試さない（試行後の修正）
            tries += [("PATCH", "/api/instruments/[id]", k, True) for k in extra_keys + [k for k in assign_keys if k not in extra_keys]
                      if k != "inspector"]
            last = None
            for m, path, key, wrap in tries:
                r = c.call(m, fill(path, iid), body(key, wrap))
                last = r
                if 200 <= r["status"] < 300:
                    j = inst(no)
                    # 担当者を、計測器とは別の送り先（GET）でだけ返す作りもある（試行後の修正）
                    if path != "/api/instruments/[id]" and any(x["path"] == path and "GET" in x["methods"] for x in routes):
                        j = {"instrument": j, "assign": c.call("GET", fill(path, iid))["json"]}
                    hits = [p for p in deep_find(j, user) if "manager" not in p.lower()]
                    if hits:
                        st["assign"] = (m, path, key, wrap)
                        return r
            return last or {"status": 0, "text": "担当者を付ける API が見つからない", "json": None}

        def p1():
            r = try_assign("MI-0002", "kato")
            need(st.get("assign"), f"担当者を付けられない: {show(r)}")
            m, path, key, wrap = st["assign"]
            return f"{m} {path} " + ("{extra: {" + key + "}}" if wrap else "{" + key + "}")
        pub.check("P1", "計測器に点検の担当者を付けられる", p1)

        # 点検の記録の方法を探す
        rec_routes = [r for r in routes if re.search(r"(?i)inspect|check", r["path"]) and "POST" in r["methods"]]
        date_keys = ov.get("date_keys") or pick(ids, r"(?i)^(inspect|check|perform)\w*(On|At|Date)$|^date$", ["inspectedOn", "inspectedAt", "date", "inspectionDate", "performedOn"], 6)
        who_keys = ov.get("who_keys") or pick(ids, r"(?i)^(inspector\w*|inspected_?by\w*|performed_?by\w*|checked_?by\w*)$", ["inspectorId", "inspectedBy", "performedBy", "userId", "inspector"], 7)
        res_keys = ov.get("result_keys") or pick(ids, r"(?i)^(result|outcome|judg\w*|verdict)$", ["result", "outcome", "status"], 4)
        goods = ov.get("good") or [x for x in lits if re.fullmatch(r"(?i)good|ok|pass(ed)?|normal|fine|良好", x)] or ["good", "ok", "pass"]
        repairs = ov.get("repair") or [x for x in lits if re.fullmatch(r"(?i)needs?_?repair|repair(_needed)?|needsRepair|ng|fail(ed)?|defect(ive)?|bad|broken|要修理", x)] or ["needs_repair", "ng", "fail"]
        note_key = ov.get("note_key") or next((k for k in ["note", "memo", "comment", "notes", "remarks"] if k in ids), "note")

        def post_rec(no, date, who, good=True, note="定期点検"):
            iid = by_no[no]
            val = (goods if good else repairs)
            if st.get("record"):
                m, path, dk, wk, rk, inst_key = st["record"]
                body = {dk: date, wk: who, rk: (st["good"] if good else st["repair"]), note_key: note}
                if inst_key:
                    body[inst_key] = iid
                return c.call(m, fill(path, iid), body)
            last, fallback = None, None
            for r in rec_routes or [{"path": "/api/instruments/[id]/inspections", "methods": ["POST"]}]:
                inst_keys = [None] if "[" in r["path"] else pick(ids, r"(?i)^instrument_?id$", ["instrumentId", "instrument_id"], 3)
                for inst_key, dk, wk, rk, v in itertools.product(inst_keys, date_keys, who_keys, res_keys, val[:3]):
                    body = {dk: date, wk: who, rk: v, note_key: note}
                    if inst_key:
                        body[inst_key] = iid
                    resp = c.call("POST", fill(r["path"], iid), body)
                    last = resp
                    if 200 <= resp["status"] < 300:
                        # 点検した人の項目名が違うと、無視されて登録した人（ログインした人）が入る作りがある。応答に
                        # 送った人が出なければ、ほかの項目名も試す（試行後の修正。feature-dev 1 の H02 を誤って落としていた）
                        if resp["json"] is not None and who != "sato" and not deep_find(resp["json"], who):
                            fallback = fallback or (("POST", r["path"], dk, wk, rk, inst_key), v, resp)
                            continue
                        st["record"] = ("POST", r["path"], dk, wk, rk, inst_key)
                        if good:
                            st["good"], st["repair"] = v, repairs[0]
                        else:
                            st["repair"], st["good"] = v, goods[0]
                        st["rec_path"] = r["path"]
                        return resp
                    if resp["status"] == 404:
                        break
            if fallback:
                rec, v, resp = fallback
                st["record"] = rec
                if good:
                    st["good"], st["repair"] = v, repairs[0]
                else:
                    st["repair"], st["good"] = v, goods[0]
                st["rec_path"] = rec[1]
                return resp
            return last or {"status": 0, "text": "点検の記録の API が見つからない", "json": None}

        def p2():
            r = post_rec("MI-0003", "2026-08-20", "suzuki")
            need(st.get("record") and 200 <= r["status"] < 300, f"点検を記録できない: {show(r)}")
            st["rec1"] = r["json"]
            return f"{st['record'][1]} {st['record'][2:5]} good={st['good']}"
        pub.check("P2", "点検の記録（点検日・点検した人・結果・メモ）を足せる", p2)

        def get_records(no):
            texts = []
            iid = by_no[no]
            for r in routes:
                if re.search(r"(?i)inspect", r["path"]) and "GET" in r["methods"]:
                    path = fill(r["path"], iid)
                    q = "" if "[" in r["path"] else f"?instrumentId={iid}"
                    texts.append(full_text(c, path + q))
            texts.append(json.dumps(inst(no), ensure_ascii=False))
            return "\n".join(texts)

        def p3():
            need(st.get("record"), "P2 が失敗")
            need("2026-08-20" in get_records("MI-0003"), "記録した点検日が API で見えない")
        pub.check("P3", "点検の記録を見られる", p3)

        def h01():
            need(st.get("assign"), "P1 が失敗")
            r = try_assign("MI-0001", "inoue")
            j = inst("MI-0001")
            stored = any("inoue" == v for o in objects(j) for k, v in o.items() if re.search(r"(?i)inspect|assign", k))
            need(not (200 <= r["status"] < 300 and stored), f"退職者を担当にできてしまう: {show(r)}")
        hid.check("H01", "在籍していない人は担当者に選べない", h01)

        def h02():
            need(st.get("record"), "P2 が失敗")
            r = post_rec("MI-0003", "2026-08-21", "kondo")
            need(not (200 <= r["status"] < 300), f"在籍していない人の点検を記録できてしまう: {show(r)}")
        hid.check("H02", "点検した人も在籍している人に限る", h02)

        def h03():
            need(st.get("record"), "P2 が失敗")
            r = post_rec("MI-0003", "2026-08-25", "sato")
            need(200 <= r["status"] < 300, f"2 回目を記録できない: {show(r)}")
            st["rec2"] = r["json"]
            t = get_records("MI-0003")
            need("2026-08-20" in t and "2026-08-25" in t, "2 回分の記録が残っていない")
        hid.check("H03", "1 台に何回分も記録が残る（履歴）", h03)

        def h04():
            need(st.get("rec1"), "P2 が失敗")
            rid = None
            for o in objects(st["rec1"]):
                if isinstance(o.get("id"), int) and "2026-08-20" in json.dumps(o):
                    rid = o["id"]
                    break
            iid = by_no["MI-0003"]
            paths = [fill(st["rec_path"], iid)] + ([f"{fill(st['rec_path'], iid)}/{rid}", f"/api/inspections/{rid}"] if rid else [])
            for p in paths:
                c.call("DELETE", p)
            need("2026-08-20" in get_records("MI-0003"), "点検の記録を消せてしまう")
            return f"record id {rid}"
        hid.check("H04", "点検の記録は消せない", h04)

        def h05():
            need(st.get("record"), "P2 が失敗")
            # MI-0003 の最後の点検は 2026-08-25、周期は決めていなければ 3 か月 → 2026-11-25
            t = get_records("MI-0003")
            lst = full_text(c, "/api/instruments")
            # 画面（詳細・一覧）に出す作りも認める（試行後の修正）
            if "2026-11-25" not in t + lst:
                lst += full_text(c, f"/instruments/{by_no['MI-0003']}") + full_text(c, "/instruments")
            need("2026-11-25" in t or "2026-11-25" in lst, "次の点検予定日（最後の点検日 + 3 か月）が見えない")
        hid.check("H05", "次の点検予定日は「最後の点検日 + 周期（既定 3 か月）」", h05)

        def h06():
            j = inst("MI-0005")
            s = json.dumps(j, ensure_ascii=False)
            marked = any(re.search(r"(?i)next|due", k) and v is None for o in objects(j) for k, v in o.items())
            marked = marked or any(re.search(r"(?i)never|uninspected|not_?inspected", k) and v for o in objects(j) for k, v in o.items())
            marked = marked or "未点検" in s
            if not marked:
                marked = "未点検" in full_text(c, "/instruments")
            if not marked:
                # 詳細の画面に出す作りも認める（試行後の修正）
                marked = "未点検" in full_text(c, f"/instruments/{by_no['MI-0005']}")
            need(marked, "未点検の計測器が分からない")
        hid.check("H06", "点検の記録が無い計測器は「未点検」と分かる", h06)

        def h07():
            need(st.get("assign"), "P1 が失敗")
            try_assign("MI-0006", "kato")
            keys = pick(ids, r"(?i)inspect|assign", ["inspector", "inspectorId", "inspector_id", "assignee", "assigneeId"], 12)
            for k in keys:
                nos = set(list_nos(c.call("GET", f"/api/instruments?{k}=kato")["json"]))
                if {"MI-0002", "MI-0006"} <= nos and "MI-0001" not in nos:
                    st["filter_key"] = k
                    return f"?{k}=kato"
            # 画面（一覧）での絞り込みも認める（Q5 は利用者が絞り込みたい。試行後の修正: baseline 2 などを落としていた）
            for k in keys:
                page = full_text(c, f"/instruments?{k}=kato")
                if "MI-0002" in page and "MI-0006" in page and "MI-0001" not in page:
                    st["filter_key"] = k
                    return f"画面 /instruments?{k}=kato"
            raise AssertionError("担当者で絞り込めない")
        hid.check("H07", "担当者で絞り込める", h07)

        def h08():
            need(st.get("record") and st.get("assign"), "P1・P2 が失敗")
            # 加藤さんの担当は 4 台。遅れているのは、最後の点検が 2026-01-05 の MI-0002・MI-0007 の 2 台。
            # MI-0006（H07 で担当にした）は旧データの最終点検日 R8.9.10 があり、MI-0008 は直近に点検したので遅れていない。
            # 試行後の修正: 当初は MI-0006 を遅れの側にしていたが、旧データの 9 月の点検の方が新しいため遅れにならない（正しい実装を落としていた）
            try_assign("MI-0007", "kato")
            try_assign("MI-0008", "kato")
            for no in ("MI-0002", "MI-0007"):
                post_rec(no, "2026-01-05", "kato")
            post_rec("MI-0008", "2026-11-01", "kato")
            gets = [r["path"] for r in routes if "GET" in r["methods"] and "[" not in r["path"] and r["path"] != "/api/instruments"]
            for p in gets:
                for q in ("", "?inspector=kato", "?inspectorId=kato"):
                    j = c.call("GET", p + q)["json"]
                    for o in objects(j):
                        vals = list(o.values())
                        if "kato" in vals and any(isinstance(v, int) and not isinstance(v, bool) and v == 2 for v in vals):
                            return f"{p}{q}"
            # 毎朝の集計の仕事（/api/jobs/...。Q5 の「毎朝知りたい」）で、担当者ごとの台数を返す作りも認める（試行後の修正）
            jc = g14.Client(srv.base(), token=g14.JOBS_TOKEN)
            for r in routes:
                if r["path"].startswith("/api/jobs/") and re.search(r"(?i)inspect", r["path"]) and "[" not in r["path"]:
                    j = jc.call("POST" if "POST" in r["methods"] else "GET", r["path"], timeout=300)["json"]
                    for o in objects(j):
                        vals = list(o.values())
                        if "kato" in vals and any(isinstance(v, int) and not isinstance(v, bool) and v == 2 for v in vals):
                            return f"{r['path']}（集計の仕事）"
            fk = st.get("filter_key", "inspector")
            for k in pick(ids, r"(?i)overdue|late|delay", ["overdue", "late", "delayed"], 6):
                for v in ("1", "true"):
                    nos = list_nos(c.call("GET", f"/api/instruments?{fk}=kato&{k}={v}")["json"])
                    if sorted(nos) == ["MI-0002", "MI-0007"]:
                        return f"?{fk}=kato&{k}={v}"
            # 画面（一覧など）に担当者ごとの台数を出す作りも認める（試行後の修正: compound-engineering 2 を落としていた）。
            # 「加藤」の後ろ 80 文字以内に、日付・数の一部でない「2」があれば、担当者ごとの遅れの台数とみなす
            for path in ["/instruments"] + [r["path"] for r in routes if r["path"].startswith("/") and not r["path"].startswith("/api")
                                            and "[" not in r["path"] and re.search(r"(?i)inspect|overdue|summary", r["path"])]:
                text = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", full_text(c, path)))
                for m in re.finditer("加藤", text):
                    if re.search(r"(?<![\d\-/.:])2(?![\d\-/.:])", text[m.end():m.end() + 80]) and re.search("遅れ|期限|overdue", text):
                        return f"画面 {path}"
            raise AssertionError("担当者ごとの、点検が遅れている台数が分からない")
        hid.check("H08", "担当者ごとに、点検が遅れている台数が分かる", h08)

        def h09():
            need(st.get("record"), "P2 が失敗")
            r = post_rec("MI-0010", "2026-11-01", "ito", good=False, note="表示がちらつく")
            need(200 <= r["status"] < 300, f"要修理を記録できない: {show(r)}")
            need((item_of(inst("MI-0010")) or {}).get("status") == "suspended", "要修理でも使用停止にならない")
        hid.check("H09", "要修理なら計測器を使用停止にする", h09)

        def h10():
            nos = list_nos(c.call("GET", "/api/instruments?dept=%E5%B7%A5%E4%BA%8B%E9%83%A8")["json"])
            need(nos == ["MI-0002", "MI-0005", "MI-0006"], f"担当部署で絞り込めなくなった: {nos}")
            iid = by_no["MI-0007"]
            r = c.call("PATCH", f"/api/instruments/{iid}", {"extra": {"memo": "棚 3"}})
            need(r["status"] == 200, f"その他の項目を更新できなくなった: {show(r)}")
            x = item_of(inst("MI-0007")) or {}
            ex = x.get("extra") if isinstance(x.get("extra"), dict) else {}
            need(ex.get("memo") == "棚 3" and ex.get("dept") == "品証", f"その他の項目の重ね方が変わった: {ex}")
            for k in ("id", "managementNo", "name", "status", "extra"):
                need(k in x, f"計測器の応答から {k} が消えた")
        hid.check("H10", "担当部署・その他の項目の API は今までどおり（互換）", h10)
    finally:
        srv.stop()
    detail.update({"assign": st.get("assign"), "record": st.get("record"), "filter_key": st.get("filter_key")})
    return pub.results, hid.results, {**detail, "db": str(db)}


def item_of(j):
    """計測器 1 件の応答から、計測器の本体を取り出す（{"instrument": {...}} などの包みにも対応）。"""
    if isinstance(j, dict):
        for k in ("instrument", "item", "data", "result"):
            if isinstance(j.get(k), dict) and "id" in j[k]:
                return j[k]
        if "id" in j:
            return j
    return None


# ---- データの持ち方 ----

def text_columns(db, table):
    return [c["name"] for c in g14.db_query(db, f'PRAGMA table_info("{table}")') if (c["type"] or "").upper() in ("TEXT", "")]


def structure_checks(app, base, db):
    ck, dt = {}, {}
    if not db or not Path(db).exists():
        return {"checks": {}, "detail": {"error": "API の DB が無い"}}
    tables = [r["name"] for r in g14.db_query(db, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    new_tables = [t for t in tables if t not in BASE_TABLES]
    inst_cols = [c["name"] for c in g14.db_query(db, 'PRAGMA table_info("instruments")')]
    dt["new_tables"], dt["instrument_new_columns"] = new_tables, [c for c in inst_cols if c not in BASE_INST_COLS]
    fk = {t: g14.db_query(db, f'PRAGMA foreign_key_list("{t}")') for t in new_tables}
    # S1: 記録の専用の表（計測器への外部キー・記録した日付がある）
    rec_tables = []
    for t in new_tables:
        if not any(f["table"] == "instruments" for f in fk[t]):
            continue
        for col in text_columns(db, t):
            if g14.db_query(db, f'SELECT 1 FROM "{t}" WHERE "{col}" = ? LIMIT 1', ("2026-08-20",)):
                rec_tables.append(t)
                break
    dt["record_tables"] = rec_tables
    ck["S1"] = bool(rec_tables)
    # S2: 担当者（kato を付けた）が extra の外にある
    mi2 = g14.db_query(db, "SELECT * FROM instruments WHERE management_no = 'MI-0002'")
    outside = [k for k, v in (mi2[0] if mi2 else {}).items() if k != "extra" and k != "manager_id" and v == "kato"]
    for t in new_tables:
        if any(f["table"] == "instruments" for f in fk[t]) and t not in rec_tables:
            for col in text_columns(db, t):
                if g14.db_query(db, f'SELECT 1 FROM "{t}" WHERE "{col}" = ? LIMIT 1', ("kato",)):
                    outside.append(f"{t}.{col}")
    in_extra = bool(mi2) and "kato" in (mi2[0].get("extra") or "")
    dt["assign_outside"], dt["assign_in_extra"] = outside, in_extra
    ck["S2"] = bool(outside) and not in_extra
    # S3: 記録が extra に入っていない
    leaked = g14.db_query(db, "SELECT management_no FROM instruments WHERE extra LIKE '%2026-08-2%' OR extra LIKE '%2026-01-05%'")
    dt["records_in_extra"] = [r["management_no"] for r in leaked]
    ck["S3"] = bool(rec_tables) and not leaked
    # S4: 新しいコードが、点検の情報を extra で読み書きしていない（コメント・移し替えの処理・テストは数えない）。
    # 元の書き方を画面に出すために古いキーを読むことはありうるので、2 か所までは認める。
    key = r"(inspector\w*|inspection\w*|last_inspected)"
    pats = [rf"\bextra\??\.{key}\b", rf"\bextra\??\.?\[\s*[\"'`]{key}", rf"\bextra\s*:\s*\{{[^}}]*\b{key}\s*:",
            rf"extraText\([^)]*[\"'`]{key}[\"'`]"]
    refs = []
    for f, l in g14.added_lines(app, base, ["src"]):
        if ".test." in f or re.search(r"(?i)migrat|backfill|db/", f):
            continue
        s = re.sub(r"//.*", "", l.strip())
        if s.startswith(("*", "/*")):
            continue
        if any(re.search(p, s) for p in pats):
            refs.append(f"{f}: {s[:100]}")
    dt["new_extra_refs"] = refs
    ck["S4"] = len(refs) <= 2
    # S5: 索引（担当者の列・記録の計測器）
    def indexed(table, col):
        for ix in g14.db_query(db, f'PRAGMA index_list("{table}")'):
            cols = [r["name"] for r in g14.db_query(db, f'PRAGMA index_info("{ix["name"]}")')]
            if cols and cols[0] == col:
                return True
        return False
    assign_cols = [x for x in outside if "." not in x]
    idx_assign = any(indexed("instruments", c) for c in assign_cols) or any(
        indexed(x.split(".")[0], x.split(".")[1]) or any(indexed(x.split(".")[0], f["from"]) for f in fk.get(x.split(".")[0], []) if f["table"] == "instruments")
        for x in outside if "." in x)
    idx_rec = any(indexed(t, f["from"]) for t in rec_tables for f in fk[t] if f["table"] == "instruments")
    dt["index_assign"], dt["index_records"] = idx_assign, idx_rec
    ck["S5"] = idx_assign and idx_rec
    return {"checks": ck, "detail": dt}


# ---- 移行（旧 DB・5 万件） ----

def make_old_db(app, base, path):
    bdir = g14.export_base(app, base)
    (bdir / "mk.mjs").write_text("import { openDb } from './src/lib/db/index.ts';\nopenDb(process.argv[2]).close();\n")
    code, out = g14.sh(f"node --experimental-strip-types --no-warnings mk.mjs {path}", bdir, timeout=120)
    if code != 0:
        raise RuntimeError(out[-500:])
    DATA.build_db(str(path))


def assignment_map(db):
    """移行後の DB から、計測器ごとの担当者（利用者の ID）を見つける。列か、計測器を参照する表のどちらか。"""
    cols = [c for c in (r["name"] for r in g14.db_query(db, 'PRAGMA table_info("instruments")')) if c not in BASE_INST_COLS]
    best, best_n = None, 0
    for col in cols:
        rows = g14.db_query(db, f'SELECT management_no AS no, "{col}" AS v FROM instruments WHERE "{col}" IS NOT NULL')
        n = sum(1 for r in rows if r["v"] in USER_IDS)
        if n > best_n:
            best, best_n = {r["no"]: r["v"] for r in rows if r["v"] in USER_IDS}, n
    # 計測器の列に担当者が無いときだけ、計測器を参照する表を見る（試行後の修正: 移行で作った点検の記録が計測器 1 件に 1 行のとき、
    # 記録の「点検した人」を担当者と取り違え、日付が読めて記録ができた行だけを数えていた）
    tables = [] if best_n else [r["name"] for r in g14.db_query(db, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    for t in tables:
        if t in BASE_TABLES:
            continue
        fks = g14.db_query(db, f'PRAGMA foreign_key_list("{t}")')
        ifk = next((f["from"] for f in fks if f["table"] == "instruments"), None)
        ufk = [f["from"] for f in fks if f["table"] == "users"]
        if not ifk or not ufk:
            continue
        for u in ufk:
            # 記録の表の点検した人は担当者ではないので、最も新しい行ではなく、表に計測器 1 行ずつのものだけを見る
            rows = g14.db_query(db, f'SELECT i.management_no AS no, t."{u}" AS v, COUNT(*) OVER (PARTITION BY t."{ifk}") AS c '
                                    f'FROM "{t}" t JOIN instruments i ON i.id = t."{ifk}" WHERE t."{u}" IS NOT NULL')
            if rows and all(r["c"] == 1 for r in rows[:500]):
                n = sum(1 for r in rows if r["v"] in USER_IDS)
                if n > best_n:
                    best, best_n = {r["no"]: r["v"] for r in rows}, n
    return best or {}


def db_contains(db, text, no):
    """計測器 no に関係する行（計測器の行・計測器を参照する表の行）のどこかに text があるか。"""
    rows = g14.db_query(db, "SELECT * FROM instruments WHERE management_no = ?", (no,))
    if not rows:
        return False
    if any(isinstance(v, str) and text in v for v in rows[0].values()):
        return True
    iid = rows[0]["id"]
    for t in [r["name"] for r in g14.db_query(db, "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]:
        if t in BASE_TABLES:
            continue
        for f in g14.db_query(db, f'PRAGMA foreign_key_list("{t}")'):
            if f["table"] == "instruments":
                for r in g14.db_query(db, f'SELECT * FROM "{t}" WHERE "{f["from"]}" = ?', (iid,)):
                    if any(isinstance(v, str) and text in v for v in r.values()):
                        return True
    return False


def migration_suite(app, base, work, static):
    ck, dt = {}, {}
    work = Path(work)
    old = work / "old.db"
    make_old_db(app, base, old)
    before = {r["management_no"]: r for r in g14.db_query(old, f"SELECT {', '.join(BASE_INST_COLS)} FROM instruments")}
    db = work / "migrate.db"
    g14.copy_db(old, db)
    srv = g14.Server(app, work, "migration", db)
    if not srv.start():
        dt["start"] = srv.log.read_text()[-600:]
        return {"checks": ck, "detail": dt}, None
    try:
        t0 = time.time()
        c = g14.Client(srv.base())
        lr = c.call("POST", "/api/login", {"userId": "sato", "password": "password"}, timeout=600)
        first = c.call("GET", "/api/instruments?dept=%E5%B7%A5%E4%BA%8B%E9%83%A8", timeout=600) if lr["status"] == 200 else lr
        dt["first_request_seconds"] = round(time.time() - t0, 2)
        ck["M7"] = first["status"] == 200 and dt["first_request_seconds"] <= 30
    finally:
        srv.stop()
    after = {r["management_no"]: r for r in g14.db_query(db, f"SELECT {', '.join(BASE_INST_COLS)} FROM instruments")} if "extra" in [
        c["name"] for c in g14.db_query(db, 'PRAGMA table_info("instruments")')] else {}
    keep = [c for c in BASE_INST_COLS if c not in ("extra",)]
    lost = [k for k in before if k not in after]
    changed = [k for k in before if k in after and any(before[k][c] != after[k][c] for c in keep)]
    dt["lost_rows"], dt["changed_rows"] = len(lost), len(changed)
    ck["M1"] = bool(after) and not lost and not changed
    ck["M2"] = static["migrations"].get("readable", False) and not static["migrations"].get("rewritten")
    # M4: 担当部署（extra.dept）が変わっていない
    def dept(row):
        try:
            return json.loads(row["extra"] or "{}").get("dept")
        except (ValueError, TypeError):
            return "<壊れた JSON>"
    dept_changed = [k for k in before if k in after and dept(before[k]) != dept(after[k])]
    dt["dept_changed"] = len(dept_changed)
    ck["M4"] = bool(after) and not dept_changed
    # M5: 点検者の名前を利用者に寄せた / M6: 分からない名前・読めない日付の元の書き方が残っている
    truth = DATA.truth()
    amap = assignment_map(db)
    target = [r for r in truth if r["expect_user"]]
    linked = sum(1 for r in target if amap.get(r["no"]) == r["expect_user"])
    dt["linked_ratio"] = round(linked / max(1, len(target)), 4)
    ck["M5"] = dt["linked_ratio"] >= 0.95
    unk = [r for r in truth if r["raw_name"] and not r["expect_user"]][:300] + [r for r in truth if r["raw_date"] and not r["expect_date"]][:300]
    kept = sum(1 for r in unk if db_contains(db, (r["raw_name"] if r["raw_name"] and not r["expect_user"] else r["raw_date"]).strip(), r["no"]))
    dt["unresolved_kept_ratio"] = round(kept / max(1, len(unk)), 4)
    ck["M6"] = dt["unresolved_kept_ratio"] >= 0.99
    # M3: 2 回目の起動で壊れない
    v1 = g14.db_query(db, "PRAGMA user_version")[0]["user_version"]
    n1 = g14.db_query(db, "SELECT COUNT(*) AS n FROM instruments")[0]["n"]
    srv = g14.Server(app, work, "migration2", db)
    ok2 = srv.start()
    try:
        if ok2:
            c = g14.Client(srv.base()).login("sato")
            ok2 = c.call("GET", "/api/instruments?dept=%E5%B7%A5%E4%BA%8B%E9%83%A8", timeout=300)["status"] == 200
    finally:
        srv.stop()
    v2 = g14.db_query(db, "PRAGMA user_version")[0]["user_version"]
    n2 = g14.db_query(db, "SELECT COUNT(*) AS n FROM instruments")[0]["n"]
    ck["M3"] = ok2 and v1 == v2 and n1 == n2
    # M8: 前の版に戻せる
    ck["M8"], dt["rollback"] = rollback_check(app, base, work, db)
    return {"checks": ck, "detail": dt}, db


def rollback_check(app, base, work, db):
    bdir, _ = g14.built_base(app, base)  # 中身ごとに 1 回だけビルドして使い回す（一時領域が一杯になったため）
    if bdir is None:
        return False, "初期状態のビルドに失敗"
    copy = Path(work) / "rollback.db"
    g14.copy_db(db, copy)
    srv = g14.Server(bdir, work, "rollback", copy)
    if not srv.start():
        return False, "前の版が起動しない"
    try:
        c = g14.Client(srv.base()).login("sato")
        lst = c.call("GET", "/api/instruments?dept=%E5%B7%A5%E4%BA%8B%E9%83%A8", timeout=300)
        mi = next((x for x in g14.list_from(lst["json"]) if isinstance(x, dict) and "id" in x), None)
        det = c.call("GET", f"/api/instruments/{mi['id']}") if mi else {"status": 0}
        patch = c.call("PATCH", f"/api/instruments/{mi['id']}", {"note": "戻しの確認"}) if mi else {"status": 0}
        page = c.call("GET", f"/instruments/{mi['id']}") if mi else {"status": 0}
        ok = lst["status"] == 200 and det["status"] == 200 and patch["status"] == 200 and page["status"] == 200
        return ok, {"list": lst["status"], "get": det["status"], "patch": patch["status"], "page": page["status"]}
    finally:
        srv.stop()


# ---- 範囲 ----

def scope_checks(app, base, mig):
    ck = {}
    m = mig.get("checks", {})
    ck["R1"] = bool(m.get("M4")) and bool(m.get("M1"))
    log = g14.git(app, "log", "--format=%B", f"{base}..HEAD")
    docs = "\n".join(l for _, l in g14.added_lines(app, base, ["docs", "README.md", "CLAUDE.md"]))
    text = log + "\n" + docs
    ck["R2"] = bool(re.search(r"(?is)(extra|その他の項目).{0,120}(課題|残|別の|別途|今後|負債|後で|TODO|範囲外|触らな|手を付け)", text)
                    or re.search(r"(?is)(課題|残|別の|別途|今後|負債|TODO|範囲外).{0,120}(extra|その他の項目)", text))
    return {"checks": ck}


def evaluate(app, base, work, mutation=True):
    app, work = Path(app), Path(work)
    work.mkdir(parents=True, exist_ok=True)
    checks = {}
    for name, cmd in [("typecheck", "npm run typecheck"), ("test", "npm test"), ("build", "npm run build")]:
        code, log = g14.sh(cmd, app)
        checks[name] = {"pass": code == 0, "log": log[-800:]}
    static = g14.static_checks(app, base)
    routes = g14.new_routes(app, base)
    out = {"checks": checks, "static": static, "routes": routes}
    if checks["build"]["pass"]:
        out["public"], out["hidden"], out["discovery"] = api_suite(app, work, routes, base)
        out["structure"] = structure_checks(app, base, out["discovery"].get("db"))
        out["migration"], _ = migration_suite(app, base, work, static)
    else:
        out.update({"public": [], "hidden": [], "discovery": {}, "structure": {"checks": {}}, "migration": {"checks": {}}})
    out["scope"] = scope_checks(app, base, out["migration"])
    if mutation:
        import grade_w10  # noqa: E402
        out["mutation"] = grade_w10.mutation(str(app), base, str(work / "mutation"))
    return out


def summary_line(r):
    def bits(xs):
        return "".join("o" if x["pass"] else "x" for x in xs)

    def cks(d, order):
        c = d.get("checks", {})
        return "".join("o" if c.get(k) else "x" for k in order)
    mu = r.get("mutation", {})
    return (f"public {bits(r.get('public', []))} hidden {bits(r.get('hidden', []))} "
            f"structure {cks(r.get('structure', {}), ['S1', 'S2', 'S3', 'S4', 'S5'])} "
            f"migration {cks(r.get('migration', {}), ['M1', 'M2', 'M3', 'M4', 'M5', 'M6', 'M7', 'M8'])} "
            f"scope {cks(r.get('scope', {}), ['R1', 'R2'])} linked={r.get('migration', {}).get('detail', {}).get('linked_ratio')} "
            f"mutation {mu.get('killed')}/{mu.get('mutants')}")


def main():
    args = sys.argv[1:]
    if args and args[0] == "--app":
        app = args[1]
        base = args[args.index("--base") + 1]
        work = tempfile.mkdtemp(prefix="w19-grade-")
        r = evaluate(app, base, work, mutation="--no-mutation" not in args)
        r["checks"] = {k: v["pass"] for k, v in r["checks"].items()}
        r["work"] = work
        text = json.dumps(r, ensure_ascii=False, indent=1, default=str)
        if "--out" in args:
            Path(args[args.index("--out") + 1]).write_text(text + "\n")
        else:
            print(text)
        print(summary_line(r), file=sys.stderr)
        return
    trial = args[0]
    flags = set(args[1:])
    sys.argv = [sys.argv[0], "W19", trial]
    import grade  # noqa: E402
    grade.main()
    result = json.loads(grade.OUT.read_text())
    base = (grade.RAW / "baseline-commit").read_text().strip()
    ov_path = RESULTS / "adapters" / f"{trial}.json"
    if ov_path.exists():
        os.environ["W19_OVERRIDE"] = ov_path.read_text()
    w = evaluate(grade.APP, base, Path(tempfile.mkdtemp(prefix=f"w19-grade-{trial}-")))
    w["checks"] = {k: v["pass"] for k, v in w["checks"].items()}
    result["w19"] = w
    import grade_w10  # noqa: E402
    grade.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
    grade_w10.apply_recount(grade.OUT, grade.RAW)
    print(f"{trial}: {summary_line(w)}")
    if "--cleanup" in flags:
        grade.cleanup()


if __name__ == "__main__":
    main()
