#!/usr/bin/env python3
"""W10 の隠しテストの検証用（下書き・未実行）: 参照実装のコピーを「わざと拙い実装」に書き換える。

使い方: python3 naive_variant_draft.py <参照実装を当てた poc-app のコピー>
  その後 npm run build → runkey-draft.sh <コピー> hidden.cjs で、H1〜H12 がすべて落ち、
  runkey-draft.sh <コピー> acceptance.cjs で公開テストがほぼ通る（拙さが公開の仕様の範囲外である）ことを確かめる。
入れる拙さ（隠しテストの項目との対応）:
  H6/H8 今日を UTC で求める / H7 Date.parse だけで日付を検証 / H8 未来の日付を拒否しない
  H3/H4 Number() で作業時間を受け入れる / H5 1 日の合計を確かめない / H1 削除で本人か確かめない
  H2 本文の userId を記録者に使う / H9 メモを String() で変換、ID を Number() で読む
  H10 送信中のガードなし / H11 失敗しても入力を消す・JSON でない応答で例外 / H12 メモを HTML として表示
注意: H9 の「JSON でない・配列・null」は readJson と検証関数が残るので、この版でも 400 になる見込み。
      H9 が落ちるのは ID（Number("abc") → NaN）とメモの数値の部分。実行して確かめること。
"""
import sys
from pathlib import Path

D = Path(sys.argv[1])


def edit(rel, pairs, strict=True):
    p = D / rel
    s = p.read_text()
    for a, b in pairs:
        if a not in s:
            if strict:
                sys.exit(f"{rel}: 見つからない: {a[:60]}")
            print(f"{rel}: skip: {a[:60]}")
            continue
        s = s.replace(a, b)
    p.write_text(s)


edit("src/lib/time-entries.ts", [
    ("return new Date(now.getTime() + JST_OFFSET_MS).toISOString().slice(0, 10);", "return now.toISOString().slice(0, 10);"),
    ("  const d = new Date(Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3])));\n  return d.toISOString().slice(0, 10) === value;",
     "  return !Number.isNaN(Date.parse(value));"),
    ('    else if (b.workDate > today) errors.push("未来の日付には記録できません");\n', ""),
    ('typeof minutes !== "number" || !Number.isInteger(minutes) || minutes < 1 || minutes > MAX_MINUTES_PER_DAY',
     "Number.isNaN(Number(minutes))"),
    ("minutes: minutes as number", "minutes: Number(minutes)"),
    ("    if (used + input.minutes > MAX_MINUTES_PER_DAY) {", "    if (used < 0) {"),
    ('    if (typeof b.note !== "string") errors.push("メモは文字列で入力してください");\n    else if (b.note.trim()',
     "    if (String(b.note).trim()"),
    ("    else note = b.note.trim();", "    else note = String(b.note).trim();"),
    ('  if (row.user_id !== userId) return "forbidden";\n', ""),
])
edit("src/lib/db/migrations.ts", [(" CHECK (minutes BETWEEN 1 AND 1440)", "")])
edit("src/app/api/tasks/[id]/time-entries/route.ts", [
    ("const result = createTimeEntry(id, user.id, input.value);",
     "const raw = (await readJson(request.clone())) as { userId?: string } | undefined;\n"
     "  const result = createTimeEntry(id, raw?.userId ?? user.id, input.value);"),
])
edit("src/app/api/tasks/[id]/time-entries/[entryId]/route.ts", [
    ("  const entryId = parseEntryId(p.entryId);", "  const entryId = Number(p.entryId);"),
])
edit("src/app/tasks/[id]/time-entries.tsx", [
    ("    if (submitting) return;\n", ""),
    ("disabled={submitting}", "disabled={false}"),
    ('      if (!res.ok) {\n        setError(await errorMessage(res));\n        return;\n      }\n      setMinutes("");\n      setNote("");',
     '      setMinutes("");\n      setNote("");\n      if (!res.ok) {\n        setError(await errorMessage(res));\n        return;\n      }'),
    ("<span>{entry.note}</span>", "<span dangerouslySetInnerHTML={{ __html: entry.note }} />"),
], strict=False)
print("ok")
