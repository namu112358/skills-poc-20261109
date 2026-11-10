# W16（ログから障害の原因を探す）— 引き継ぎメモ

2026-11-10 07:05 UTC、準備の担当（session_01QR8ZDNr1NKndq8g95LBXXq）が作成。このアカウントの 7 日間の使用量の上限が近いため、試行は別アカウントの担当に引き継ぐ（ユーザー判断、コーディネーター経由）。準備の担当は試行を 1 本も流していない。

## 状態

| 項目 | 状態 |
|---|---|
| 設計書 | [`docs/poc/tasks/wf-W16-design.md`](../../../tasks/wf-W16-design.md)（試行前に固定。§8 試行前の確認、§9 確認の記録） |
| 正解データ・採点 | [`docs/poc/answer-key/W16/`](../../../answer-key/W16/grading.md)（grading.md・base.patch・persona.md・incident.cjs ほか） |
| 報告① | 送付済み・コーディネーター承認済み（2026-11-10 06:49 UTC）。このまま試行する |
| 試行 | **未着手**（5 条件 × 2 回 = 10 本）。開始の時期は引き継ぎ先の担当がコーディネーターに確認する |
| 次にやること | 試行 → 採点 → ブラインドレビュー → `score_w16.py` → report.md・report.html → PLAN.md §5.1・§6 に W16 を追加 → PR |

ブランチ: `agent/poc-w16`（main d491044 起点）。準備のコミット: ca6d037（題材・正解データ・採点）、0c6d30d（承認の記録）。

## 承認済みの内容（コーディネーター、2026-11-10）

- 報告①のとおり、このまま試行する（原因の特定を難しくする案は、罠を測ることになるので採らない）。原因の特定を別の `claude -p` が 2 回独立に判定する方式も了承。
- **report に必ず書くこと**:
  1. 試行前の観察: 試運転（baseline、1 ステップ 150〜200 秒で打ち切り、採点に使わない）で、baseline が 2 分・$0.4 前後で原因を 2 つとも見つけた（判定 A・B とも full）。ただし隠しテストの I4・I6a に落ち、ログ・監視 0 点で、設計の筋を除いて 72.5 点だった（`precheck/grade-smoke-baseline.json`・`precheck/smoke-baseline-run*-report.md`）。
  2. 結論の前提: 原因の特定は天井に近くなる見込みで、条件の差は主に「直し方の深さ」（次の実行での送り直しのキー・途中で止まったときの回復・本番の DB・ログ）に出る、という読み方で結果を見る。
  3. 判断の記録: `docs/notify-api.md` から B の答えに近い記述「応答が返らなかった（タイムアウトした）要求も、サービス側では受け付けて送っていることがあるので、送り直すときは同じキーを使うこと」を試行前に消した。あわせて通知クライアントの「試行ごとにキーを変える」理由のコメント（誤った理由）も消した（コードはそのまま）。W12 の文書との違いの全体は設計書 §9。

## 試行の手順

```bash
# 0) 準備（コンテナごとに 1 回）
(cd poc-app && npm ci)                    # run-trial.sh が poc-app/node_modules を写す
bash scripts/poc/fetch-plugins.sh         # 候補のプラグイン（固定コミット）を .poc-cache/ に取る

# 1) 試行（2 本並列。前半は各条件の 1 回目、後半は 2 回目で順番を逆に）
scripts/poc/run_w16_trials.sh superpowers:1 gstack:1 baseline:1 &
scripts/poc/run_w16_trials.sh feature-dev:1 compound-engineering:1 &
wait
scripts/poc/run_w16_trials.sh baseline:2 gstack:2 superpowers:2 &
scripts/poc/run_w16_trials.sh compound-engineering:2 feature-dev:2 &
wait
#   試行ごとに run-trial.sh → grade_w16.py → reinject_w16.py → judge_w16.py → w16_slim.py を順に行う
#   記録: docs/poc/results/workflow/raw/W16-<候補>-<回>/、進み具合: raw/w16-runner.log

# 2) 採点者の確認
#   - results/workflow/W16/judge/<ID>.json の needs_review（2 回の判定の食い違い）→ judge/<ID>.override.json に決めた値と理由
#   - results/workflow/W16/reinject/<ID>.json の status=needs_review → reinject/<ID>.override.json に書き換え（{"A": [...], "B": [...]}）を書いて reinject_w16.py を再実行
#   - 候補がジョブの API・重要度の名前を変えていたら results/workflow/W16/adapters/<ID>.json で補正して grade_w16.py を再実行

# 3) ブラインドレビュー → 点数
python3 scripts/poc/blind_w16.py prepare <出力先>   # R01.md〜 と CONTEXT.md。2 名のレビュー担当（別の claude -p）が grading.md の a〜f を 0〜3 点で付け、
                                                   # results/workflow/W16/blind/reviewer-1.json・reviewer-2.json に書く
python3 scripts/poc/blind_w16.py collect
python3 scripts/poc/score_w16.py                   # results/workflow/W16/scores.json
# 4) 作業用コピーの片付け: python3 scripts/poc/grade.py W16 <ID> --cleanup-only
```

- 費用の上限は付けない（`run_w16_trials.sh` が `POC_MAX_TRIAL_USD` を外す）。1 試行が $30 を超えたら、続ける前にコーディネーターに報告。使用量の上限で失敗した試行は、リセット後にやり直して判断の記録に書く。
- `two_axis.py` にはまだ W16 が無い。report の前に W16 を足す（品質は score_w16.py の quality、効率は §4.4 のとおり baseline 2 回の平均を基準に）。report を作る `report_w16.py` もまだ無い（W14 の `report_w14.py` を写して作る想定）。

## 出どころのコミット

| もの | 出どころ |
|---|---|
| 初期状態の土台（W12 の `base.patch`・`reference.patch`） | `origin/agent/poc-w12` ab36ab4 の時点（`base.patch` の sha256 は W13 と同じ `a70273846daa…`） |
| `fake-clock.cjs`・`lib.cjs`・`public.cjs`・`hidden.cjs`・`robust.cjs`・`old-db.sql` | W12 の同名のファイル（ab36ab4 の時点）の写し |
| `fake-notify.cjs` | W12 のものに応答の遅れ（`latencyMs`・`{delay}`）を足した |
| `w16_slim.py` | W12 の `w12_slim.py`（ab36ab4）の写し |
| 依頼者役・`ask-po` | main の `answer_persona.py`・`ask-po`（W14・W15 と同じ。シナリオ名 W16 で `answer-key/W16/persona.md` を読む） |
| `blind_w16.py` | main の `blind_w14.py` の写し |
| 計画 | `claude/intelligent-mendel-hyx7aa` ff5fa28 の `docs/poc/tasks/wf-W13-W17-plan.md` |

## 気をつける点

- **main の取り込み**: `run-trial.sh` は W14・W15 の条件に `W16` を足しただけ（初期状態・汎用の開発標準・`ask-po`・依頼者役・課題文の末尾・W5 の入口と介入の定型文）。W12・W13 の PR が main に入ったら取り込み、衝突は W16 の分岐だけを残す形で解く。ほかの W の既定の動作は変えていない。
- **ディスク**: 採点は試行ごとに一時ディレクトリ（`/tmp/w16-grade-*`・`/tmp/w16-reinject-*`）を作り、消さない（削除の運用）。`next build` の写しが残るので、容量が足りなくなったらコーディネーターに相談する。`w16_slim.py` は採点の後に HOME（セッションの記録は `raw/<ID>/home-transcripts` に写してから）と node_modules（poc-app へのハードリンクに置き換え）を片付ける。
- **node_modules はシンボリックリンクにしない**: Next.js 16 の Turbopack がリンク先の `next` を見つけられずビルドに失敗する（試行前の確認で踏んだ）。写しかハードリンクにする。
- **時刻**: 試行の採点は偽の時計で動く（2027 年の日付）。本番の DB の確認（M1〜M3）は 2026-11-11 7:30（日本時間）。
- **再注入の費用**: 1 試行あたり $0.03〜0.15（claude -p）。原因の判定は 2 回で $0.1 前後。どちらも候補の費用には含めず、report に別に書く。
- **Claude Code の版**: このコンテナでは 2.1.322（W12・W13 は 2.1.321）。引き継ぎ先の版も report に書く。
- **不正の点検**（report の「試行間の独立性・不正の点検」）: `grade.py` の `isolation_suspects`（作業用コピーの外・正解データ・`results/`）、WebFetch・WebSearch の使用、依頼者役の答えすぎ（`po-questions.jsonl` で、聞かれていない項目を明かした回数）を全試行で数える。
- **PR**: docs/github-writing.md に従い、作業中は draft。全試行の採点と report がそろったら Ready にし、CI が通り、変更が `docs/poc/`・`scripts/poc/` の範囲なら最後の push の直後に自動マージ（SQUASH）を有効にする（`merge_pull_request` は使わない）。
- 試運転の記録（raw）はリポジトリに入れていない（採点に使わないため）。要約は `precheck/` の 2 つの report と grade・judge・reinject の JSON。
