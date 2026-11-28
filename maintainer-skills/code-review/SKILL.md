---
name: code-review
description: 同梱の /code-review を置き換える personal skill。差分を review-checklist skill の基準とセキュリティレビュー1パスで読み、P0〜P3 を付けて報告する。/ship のレビュー段階、ユーザーが打つ /code-review、「この差分をレビューして」から使う。引数は同梱版と同じ形（effort / 対象 / --fix / --comment / --max-findings）。
---

# code-review — review-checklist 版

同梱の `/code-review` と同じ名前にして、/ship のレビューと手で打つ `/code-review` をこちらに差し替える。
基準は `review-checklist` skill が正本。ここに観点を書き足さない。

## 引数

`[low|medium|high|xhigh|max] [PR番号 | PR URL | ブランチ | パス] [--fix] [--comment] [--max-findings <n>|all]`

- effort を省略したら `high`。`low` / `medium` は P0/P1 だけ、`high` 以上は P2 まで出す。P3 は `max` か `--max-findings all` のときだけ出す。
- `ultra` は同梱版の機能（クラウドでの多エージェントレビュー）なので、ここでは扱わない。`/code-review ultra` を使うよう1行返して終える。
- 件数上限は既定 10。`--max-findings` で変える。

## 手順

1. 対象の差分を決める。
   - PR 番号・URL: `gh pr diff <n>`、base は `gh pr view <n> --json baseRefName`。
   - ブランチ: `git diff <base>...<branch>`。
   - パス: そのファイルの未コミット差分（無ければ base との差分）。
   - 省略: 未コミット差分があればそれ。無ければ `git diff <base>...HEAD`。base は `gh pr view --json baseRefName`、PR が無ければ origin の既定ブランチ。
2. `review-checklist` skill の「使い方」に従う。`severity.md` / `common.md` / `process.md` と、差分のレイヤーに該当する references だけを読む。リポ固有チェックリスト（`.claude/review-driven-implement.project.md` など）があれば読む。
3. 同じ差分にセキュリティレビューを別パスで1回当てる（認証・認可 / 入力検証・インジェクション / 秘密・PII の露出（ログを含む）/ 追加した依存）。docs だけの差分なら飛ばす。
4. 指摘ごとに、反証を試みてから残す（`process.md` の作法）。P0/P1 は「前提 → 入力 → 結果」を書けないなら降格する。
5. 報告する（下記）。
6. `--fix` があれば P0/P1 を作業ツリーに直す（コミットしない）。`--comment` があれば `gh pr review --comment` ではなく行コメント（`gh api repos/{owner}/{repo}/pulls/{n}/comments`）で1件ずつ投稿する。

## 報告

- ReportFindings ツールがあれば、それで1回だけ報告し、本文に指摘を重ねて書かない。
  - `severity`: P0/P1 → `important`、差分が触っていない既存の欠陥 → `pre_existing`、P2/P3 → `nit`。
  - `summary` の先頭に `[P0]` のように等級を付ける。`failure_scenario` に「前提 → 入力 → 結果」を書く。
  - `category` に観点の出所（`common`、`backend`、`security` など）を入れる。
- ツールが無ければ、判定1行 → P0/P1/P2 の件数 → 指摘ごとに `file:line` と1行。
- 最後に「セキュリティ: P0/P1 n 件 / 該当なし」を1行添える。

## やらないこと

- Codex を呼ばない。Codex のレビューは `/review-driven-implement` が実装直後に1回だけ回す。
- `--fix` が無いときに作業ツリーを書き換えない。コミット・push をしない（/ship が受け持つ）。
- `review_log.py` に記録しない。処置を決めた側（直した/直さないを決めた呼び出し元）が記録する。
