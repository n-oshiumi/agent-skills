# /review-driven-implement — プロジェクト固有設定

共通ワークフローは `review-driven-implement` skill(`~/.claude/skills/`)。ここには固有の値だけ書く。

### テスト・品質ゲート
- ユニット/結合: `<コマンド>`
- 品質ゲート(lint / 型 / build): `<コマンド>`

### 検証ゲートの適用範囲
- UI: <対象画面 / スクショの撮り方>
- E2E クリティカルパス: <スクリプトと対象経路。無ければ「なし」>

### 参照(チェックリスト・学習記録)
- チェックリスト正本: 共通 = `review-checklist` skill / 固有 = `<パス。無ければ「なし」>`
- 学習記録: `docs/review-learnings/`(`/review-learning` で記録)

### リスク段階
変更の中身で決める(作者・行数では決めない)。どちらにも当たらなければ「中」。書かなければ skill の既定を使う。
- 高(Codex 必須 + 人が diff を読む + 戻し方を書く): `<例: app/Auth/** , **/payment/** , database/migrations/** , .github/workflows/** , terraform/**>`
- 低(Codex 省略): `<例: docs/** , **/*.md , tests/** , 文言ファイル>`

### Codex に渡す追加コンテキスト
- <仕様の場所、境界、既知の制約>

### review-learning
- 置き場: `docs/review-learnings/`(雛形 `_template.md` をコピー、`YYYY-MM-DD-<slug>.md`)
- domain 語彙: <例: auth / api / frontend / data / testing>
- 還流先(リポ固有の観点): `<固有チェックリストのパス>` の「## 候補(レビューで発見)」
- 追加ルール: <あれば>
