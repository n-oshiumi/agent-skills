# agent-skills

Claude Code / Codex 共通で使う skill の正本。plugin として配布する。

## 使う側(Claude Code)

```
/plugin marketplace add n-oshiumi/agent-skills
/plugin install review-workflow@naoki-skills
```

リポの `.claude/settings.json` に `extraKnownMarketplaces` と `enabledPlugins` が宣言されていれば、リポを開いたときにインストールを促される。
plugin 経由の skill は名前空間付き: `/review-workflow:review-checklist`、`/review-workflow:threat-coverage`、`/review-workflow:review-driven-implement`、`/review-workflow:spec-design-multireview`(agent は `review-workflow:spec-design-reviewer`)。

## 使う側(Codex)

`plugins/review-workflow/skills/<name>` を `~/.codex/skills/<name>` にコピーまたは symlink する(SKILL.md 形式は同じ)。

## 中身

- `review-checklist`: 言語・FW 非依存のレビューチェックリスト(`references/{severity,common,backend,frontend,infra,data,test,process}.md`、各 ≤12KB)。プロジェクト固有の不変条件は各リポ側に置く。
- `review-driven-implement`: 準備 → 実装+テスト → Codex 外部レビュー1回 → 自己レビュー(今回の差分の P0-P2 = 0 まで) → 検証ゲート → 完了報告のワークフロー。固有設定は各リポの `.claude/review-driven-implement.project.md`。
- `spec-design-multireview`(+ agent `spec-design-reviewer`): PRD・設計 Spec を 4 レンズ(リーン / 価値 / UX / 実現性)の並列サブエージェントで批判的にレビューし、P0/P1 ゼロまで収束させる。各リポの `/review-driven-spec` `/review-driven-design` `/spec-design` から呼ばれる。
- `threat-coverage`: リポごとの「攻撃の種類ごとの対策状況」の表(`docs/reference/security-threat-coverage.md`)を作り、呼ぶたびに同梱の `template.md` の版へ ID 単位で同期する(`scripts/sync.mjs`)。記入済みの表は未修正の穴の一覧なので、各リポだけに置き、このリポには置かない。テンプレの変更は `CHANGES.md` に書く。

## 育てる・配信する

- 観点の追加: 各リポで `/review-learning` を使うと、共通の観点は `references/*.md` 末尾の「## 候補(レビューで発見)」に `(リポ名 日付)` 付きで溜まる。
- 棚卸し: 保守者が `/review-checklist-groom`(`maintainer-skills/`、personal skill として symlink)で候補を昇格・統合・削除し、12KB 上限を守る。
- `/code-review` の差し替え: `maintainer-skills/code-review` を `~/.claude/skills/code-review` に symlink すると、同梱の `/code-review` と `/ship` のレビュー段階がこの基準(review-checklist + セキュリティ1パス)で動く。plugin の skill は名前空間が付いて差し替えにならないため、personal skill として置く。
- `/land`: `maintainer-skills/land` を `~/.claude/skills/land` に symlink する。`/ship` で準備ができた PR をマージゲートを確かめてマージし、ブランチ・worktree・チケットを片付ける。リポ固有のゲートとチケットの手順は `.claude/review-driven-implement.project.md` の「### マージ(/land)」節に書く。
- 配信: `tools/release.sh [patch|minor|major]` が `tools/check.py`(frontmatter・サイズ・version 整合)を通してから version を上げ、commit / tag / push する。利用者は version が上がったときだけ更新を受け取る。
- 精度の測定: `tools/eval.py run` が過去に見逃したバグ(と問題なしの変更)にレビュアーを当て直し、recall と誤検知を出す(ケースは修正に使う `dev` と使わない `holdout` に分け、split ごとにも集計する。`tools/eval.py spread` は同じ条件で複数回回したときの揺れの幅)。`--reviewer codex` で同じケースを Codex にも当て、`tools/eval.py compare` で Claude 単独と Claude + Codex(どちらかが当てれば当たり)の recall・誤検知を比べる。Phase 3 の Codex レビューが見逃しを減らしているかはこれで見る(`review_log.py` の採用率は、実装した側が採用したかの記録で、効いたかの証拠ではない)。`release.sh` は今の `plugins/` で採点していないと止まる(`SKIP_EVAL=1` で飛ばす)。レビュアーは `--plugin-dir` で このリポの `plugins/` を読み(`~/.claude/skills` は使わない)、モデルと effort は `eval.py` の `REVIEW_MODEL` / `REVIEW_EFFORT` に固定する。ケースと結果は非公開リポの中身を含むので、このリポには置かずローカル(`~/programming/my-tools/review-evals/`)に置く。
- ノイズ率: `review-checklist/scripts/review_log.py` が指摘ごとの処置(直した/却下/意図どおり/放置)をローカル(`~/.claude/review-log.jsonl`)に記録し、`stats --by ref` で観点ごとの採用率を出す。棚卸しで採用率の低い観点を削る。
- CI: `.github/workflows/check.yml` が push ごとに `tools/check.py` を回す。
