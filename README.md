# agent-skills

Claude Code / Codex 共通で使う skill の正本。plugin として配布する。

## 使う側(Claude Code)

```
/plugin marketplace add n-oshiumi/agent-skills
/plugin install review-workflow@naoki-skills
```

リポの `.claude/settings.json` に `extraKnownMarketplaces` と `enabledPlugins` が宣言されていれば、リポを開いたときにインストールを促される。
plugin 経由の skill は名前空間付き: `/review-workflow:review-checklist`、`/review-workflow:review-driven-implement`、`/review-workflow:spec-design-multireview`(agent は `review-workflow:spec-design-reviewer`)。

## 使う側(Codex)

`plugins/review-workflow/skills/<name>` を `~/.codex/skills/<name>` にコピーまたは symlink する(SKILL.md 形式は同じ)。

## 中身

- `review-checklist`: 言語・FW 非依存のレビューチェックリスト(`references/{severity,common,backend,frontend,infra,data,test,process}.md`、各 ≤10KB)。プロジェクト固有の不変条件は各リポ側に置く。
- `review-driven-implement`: 準備 → 実装+テスト → 自己レビュー → 検証ゲート → 外部レビュー1回 → 完了報告のワークフロー。固有設定は各リポの `.claude/review-driven-implement.project.md`。
- `spec-design-multireview`(+ agent `spec-design-reviewer`): PRD・設計 Spec を 4 レンズ(リーン / 価値 / UX / 実現性)の並列サブエージェントで批判的にレビューし、P0/P1 ゼロまで収束させる。各リポの `/review-driven-spec` `/review-driven-design` `/spec-design` から呼ばれる。

## 育てる・配信する

- 観点の追加: 各リポで `/review-learning` を使うと、共通の観点は `references/*.md` 末尾の「## 候補(レビューで発見)」に `(リポ名 日付)` 付きで溜まる。
- 棚卸し: 保守者が `/review-checklist-groom`(`maintainer-skills/`、personal skill として symlink)で候補を昇格・統合・削除し、10KB 上限を守る。
- 配信: `tools/release.sh [patch|minor|major]` が `tools/check.py`(frontmatter・サイズ・version 整合)を通してから version を上げ、commit / tag / push する。利用者は version が上がったときだけ更新を受け取る。
- 精度の測定: `tools/eval.py run` が過去に見逃したバグ(と問題なしの変更)にレビュアーを当て直し、recall と誤検知を出す。`release.sh` は今の `plugins/` で採点していないと止まる(`SKIP_EVAL=1` で飛ばす)。ケースと結果は非公開リポの中身を含むので、このリポには置かずローカル(`~/programming/my-tools/review-evals/`)に置く。
- ノイズ率: `review-checklist/scripts/review_log.py` が指摘ごとの処置(直した/却下/意図どおり/放置)をローカル(`~/.claude/review-log.jsonl`)に記録し、`stats --by ref` で観点ごとの採用率を出す。棚卸しで採用率の低い観点を削る。
- CI: `.github/workflows/check.yml` が push ごとに `tools/check.py` を回す。
