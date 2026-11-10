# W13 再開メモ（担当セッションが止まったときに引き継ぐため）

最終更新: 2026-11-10 10:45 UTC

## 終わっていること

- 設計・正解データ・採点の仕組み（`docs/poc/tasks/wf-W13-design.md`、`docs/poc/answer-key/W13/`、`scripts/poc/grade_w13.py` ほか）。コーディネーター確認済み。
- 試行 10 本すべて（superpowers-2 は 5 時間の上限で失敗し、10:13 UTC にやり直して完了）。アダプターは全試行で確定済み。
- 補正 3・4 の前の条件での採点（`W13/prefix/`）。
- ブラインドレビューの資料（`blind_w13.py prepare`、対応表 `W13/blind/mapping.json`）。レビュー担当 2 名を起動済み（結果は `W13/blind/reviewer-1.json`・`-2.json`）。
- `report_w13.py`（文章は `W13/notes.json` から）、`two_axis.py` に W13。

## 残っていること（この順）

2. 全 10 本を最終版の採点で採点し直す: `for t in ...; do python3 scripts/poc/grade_w13.py W13-$t-$n; done`。
3. 補正 3・4 の前の条件での採点: `python3 scripts/poc/grade_w13.py <ID> --prefix`（結果は `W13/prefix/`。report の表に使う）。
4. ブラインドレビュー: `python3 scripts/poc/blind_w13.py prepare <dir>` → 独立したサブエージェント 2 名（昇順・降順）→ `W13/blind/reviewer-1.json`・`-2.json` → `blind_w13.py collect`。
5. `python3 scripts/poc/score_w13.py` → report.md・report.html（判断の記録は `W13/decisions.md` から。補正 3・4 の前後の表、K08 を依頼者に聞いたか）→ PLAN.md §5.1・§6 に W13 → `two_axis.py` に W13。
6. PR（draft → Ready、CI 通過後に自動マージ（SQUASH））。W12 が main に入っていれば main を取り込んで衝突を解消してから。
7. 片付け: `python3 scripts/poc/grade.py W13 <ID> --cleanup-only`（ブラインドの資料作りの後）。
