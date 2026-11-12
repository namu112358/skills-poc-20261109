#!/usr/bin/env python3
"""U1 の画面を並べて順位を付けるページ（人の評価。docs/poc/tasks/wf-U1-design.md §5）を作る。

使い方: python3 scripts/poc/gallery_u1.py <出力先ディレクトリ>
  - results/workflow/U1/<試行ID>.json（繰り返し 0 の動作確認は除く）とスクリーンショットから、<出力先>/index.html と
    <出力先>/shots/ を作る。ページは Artifact として公開し、順位はページの db（rankings/<課題>）に保存する。
  - 構成の名前は、ページで「構成を表示」を押すまで出さない。案の記号は試行 ID から決まり、試行が増えても変わらない。
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs" / "poc" / "results" / "workflow" / "U1"
SHOTS = RESULTS / "shots"
TEMPLATE = Path(__file__).resolve().parent / "gallery_u1.html"
CONFIG_LABEL = {"ui-none": "ツールなし", "ui-all": "4 つすべて", "ui-a": "Impeccable（整理案 A）",
                "ui-fd": "Frontend Design", "ui-pm": "UI/UX Pro Max",
                "ui-fd-md": "Frontend Design + 指示（U2）", "ui-a-md": "Impeccable + 指示（U2）", "ui-all-md": "4 つすべて + 役割の指示（U2）"}
ALPHA = "ACDEFHJKLMNPRTUVWXY"


def code(trial):
    h = int(hashlib.sha256(("w21-blind:" + trial).encode()).hexdigest(), 16)
    return ALPHA[h % len(ALPHA)] + ALPHA[(h // 19) % len(ALPHA)] + str((h // 361) % 10), h


def main(out):
    out = Path(out)
    (out / "shots").mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(RESULTS.glob("U1[abdef]-ui-*.json")):
        r = json.loads(f.read_text())
        t = r["trial"]
        if r["rep"] == 0 or not (SHOTS / f"{t}-desktop.jpg").exists():
            continue
        c, h = code(t)
        shutil.copy(SHOTS / f"{t}-desktop.jpg", out / "shots" / f"{c}-desktop.jpg")  # 依頼者の指示でパソコンの幅だけ見せる
        s = r.get("score", {})
        items.append({"id": t, "code": c, "sort": h % 100000, "task": r["task"], "config": r["config"],
                      "configLabel": CONFIG_LABEL[r["config"]], "rep": r["rep"],
                      "cost": r["transcript"]["cost_usd"], "minutes": round((r.get("elapsed_seconds") or 0) / 60, 1),
                      "skills": r["transcript"]["skills_used"], "checks": s.get("subtotal_50"),
                      "axe": s.get("axe_serious", []) + s.get("axe_moderate", [])})
    if (SHOTS / "U1b-before-desktop.jpg").exists():
        shutil.copy(SHOTS / "U1b-before-desktop.jpg", out / "shots" / "before-desktop.jpg")
    html = TEMPLATE.read_text().replace("/*__DATA__*/[]", json.dumps(items, ensure_ascii=False))
    (out / "index.html").write_text(html)
    print(f"{len(items)} 案を書いた: {out}/index.html")


if __name__ == "__main__":
    main(sys.argv[1])
