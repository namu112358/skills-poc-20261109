# コーディネーターからの回答（別アカウントの担当向け）

別アカウントの担当セッションには send_message が届かないため、判断の依頼と回答を git でやり取りする。

- 担当: 判断が要るときは、自分の作業ブランチの `docs/poc/results/workflow/W1x/QUESTIONS.md` に「日時・質問・選択肢・推奨・止めているか」を追記して push する。
- コーディネーター（session_01QR8ZDMUCQo5J82UtBYZdGD）: 見回り（45〜60 分ごと）のたびに各ブランチの QUESTIONS.md を読み、このファイルに回答を追記して、ブランチ `claude/intelligent-mendel-hyx7aa` に push する。
- 担当: 回答待ちの間は 15 分ごとに `git fetch origin claude/intelligent-mendel-hyx7aa` して、このファイルを読む。ユーザーが担当のセッションに直接書いた指示は、それを優先する。

回答は新しいものを下に追記する。見出しは「## <W> <日時 UTC> — <質問の要約>」。

---
