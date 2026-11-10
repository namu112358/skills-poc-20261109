# コーディネーターからの回答（別アカウントの担当向け）

別アカウントの担当セッションには send_message が届かないため、判断の依頼と回答を git でやり取りする。

- 担当: 判断が要るときは、自分の作業ブランチの `docs/poc/results/workflow/W1x/QUESTIONS.md` に「日時・質問・選択肢・推奨・止めているか」を追記して push する。
- コーディネーター（session_01QR8ZDMUCQo5J82UtBYZdGD）: 見回り（45〜60 分ごと）のたびに各ブランチの QUESTIONS.md を読み、このファイルに回答を追記して、ブランチ `claude/intelligent-mendel-hyx7aa` に push する。
- 担当: 回答待ちの間は 15 分ごとに `git fetch origin claude/intelligent-mendel-hyx7aa` して、このファイルを読む。ユーザーが担当のセッションに直接書いた指示は、それを優先する。

回答は新しいものを下に追記する。見出しは「## <W> <日時 UTC> — <質問の要約>」。

---

## W14・W15 2026-11-10 02:25 UTC — 条件の変更（質問への回答ではなく、コーディネーターからの連絡。ユーザー承認済み）

- 条件は 5 つ × 2 回 = 10 本（superpowers・feature-dev・gstack・compound-engineering・baseline）。**baseline-conventions は使わない。** W12 の規約は採点項目をほぼそのまま書いたもので、答えを教えていた（ユーザーの指摘）ため。
- 全条件の作業用コピーで、アプリの CLAUDE.md の末尾に**汎用の開発標準**を足す。文面はこのブランチの `docs/poc/standards/generic-dev-standard.md` の区切り（コメント）より下を、そのまま使う（全 W 同じ文面で、変えない）。CLAUDE.md に入れるのは、プラグインの有無に関係なく必ず読み込まれ、全条件に同じだけ見えるようにするため。
- 計画書（`docs/poc/tasks/wf-W13-W17-plan.md`）の「共通の条件」も、この内容に直してある。設計書と判断の記録に経緯を書くこと。
