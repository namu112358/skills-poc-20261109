#!/usr/bin/env python3
"""ほかのプロジェクトに配る雛形（templates/）と、このリポジトリで使う版が一致しているかを検査する。

使い方: python3 scripts/check-templates.py   （食い違いがあれば終了コード 1）

雛形が正本。食い違いを見つけたら、雛形を直してから、このリポジトリの版に写す。
"""

import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BLOCK = re.compile(r"<!-- 共通規約ここから.*?<!-- 共通規約ここまで -->", re.S)

# (雛形, このリポジトリの版, 比べる範囲)。「雛形を含む」は、このリポジトリの版が雛形の中身をすべて含むこと
# （雛形に、このリポジトリだけの設定を足したもの）を確かめる
PAIRS = [
    ("templates/agents/.claude/settings.json", ".claude/settings.json", "雛形を含む"),
    ("templates/agents/.mcp.json", ".mcp.json", "雛形を含む"),
    ("templates/agents/AGENTS.md", "AGENTS.md", "共通規約のブロック"),
    ("templates/github/docs/github-writing.md", "docs/github-writing.md", "全体"),
    ("templates/agents/scripts/check-skills.py", "scripts/check-skills.py", "全体"),
]


def missing_items(tmpl, local, where="") -> list:
    """雛形（tmpl）にあって、このリポジトリの版（local）にないものを挙げる。"""
    if isinstance(tmpl, dict):
        if not isinstance(local, dict):
            return [f"{where or '/'}: 形が違う（雛形はオブジェクト）"]
        out = []
        for k, v in tmpl.items():
            if k not in local:
                out.append(f"{where}/{k}: ない")
            else:
                out += missing_items(v, local[k], f"{where}/{k}")
        return out
    if isinstance(tmpl, list):
        if not isinstance(local, list):
            return [f"{where}: 形が違う（雛形は配列）"]
        return [f"{where}: {json.dumps(x, ensure_ascii=False)} がない" for x in tmpl if x not in local]
    return [] if tmpl == local else [f"{where}: 値が違う（雛形は {json.dumps(tmpl, ensure_ascii=False)}）"]


def part(path: Path, scope: str):
    text = path.read_text(encoding="utf-8")
    if scope == "全体":
        return text
    m = BLOCK.search(text)
    return m.group(0) if m else None


def main() -> int:
    errors = 0
    for tmpl, local, scope in PAIRS:
        a, b = ROOT / tmpl, ROOT / local
        missing = [p for p in (a, b) if not p.exists()]
        if missing:
            print(f"[NG] {local}: {', '.join(str(p.relative_to(ROOT)) for p in missing)} がありません")
            errors += 1
            continue
        if scope == "雛形を含む":
            problems = missing_items(json.loads(a.read_text(encoding="utf-8")), json.loads(b.read_text(encoding="utf-8")))
            if problems:
                print(f"[NG] {local}（{tmpl} の中身を含んでいない。雛形を正本にして直してください）")
                for x in problems[:20]:
                    print(f"    {x}")
                errors += 1
            else:
                print(f"[OK] {local}（{tmpl} の中身をすべて含む）")
            continue
        ta, tb = part(a, scope), part(b, scope)
        if ta is None or tb is None:
            print(f"[NG] {local}: 「共通規約ここから」「共通規約ここまで」の印が見つかりません")
            errors += 1
            continue
        if ta == tb:
            print(f"[OK] {local}（{scope}が {tmpl} と一致）")
            continue
        print(f"[NG] {local}（{scope}が {tmpl} と食い違う。雛形を正本にして直してください）")
        diff = difflib.unified_diff(ta.splitlines(), tb.splitlines(), tmpl, local, lineterm="", n=1)
        for line in list(diff)[:40]:
            print("    " + line)
        errors += 1
    print(f"\nエラー {errors} 件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
