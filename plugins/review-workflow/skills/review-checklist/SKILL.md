---
name: review-checklist
description: 言語・フレームワーク非依存のコードレビューチェックリスト(全リポ共通の正本)。実装の自己レビュー、Codex クロスレビュー、PR レビューで「何を見るか」の基準として使う。/review-driven-implement の Phase 3(自己レビュー)と Phase 5(Codex)から参照される。変更差分のレイヤー(backend / frontend / infra / data)に応じて references/ の該当ファイルだけを読む。プロジェクト固有の不変条件・FW 固有の落とし穴は各リポのチェックリストが持ち、本 skill には書かない。
---

# review-checklist — 共通コードレビュー基準

全リポで同じ基準でレビューするための正本。Claude Code と Codex の両方が同じファイルを読む
(`~/.codex/skills/review-checklist` は本ディレクトリへの symlink)。

## 使い方

1. レビュー範囲を特定する: `git diff --name-only <base>...HEAD`
2. 差分のレイヤーを判定し、**該当する references だけ**読む(全部読まない):

   | 差分に含まれるもの | 読むファイル |
   | --- | --- |
   | 常に | `references/severity.md`, `references/common.md` |
   | レビュー(自己・Codex・PR)を行うとき | `references/process.md`(証拠・スコープ・反証・出力の作法) |
   | API・サービス層・ジョブ・認可・外部連携 | `references/backend.md` |
   | 画面・コンポーネント・状態管理・スタイル | `references/frontend.md` |
   | IaC・CI/CD・コンテナ・環境変数・デプロイ設定 | `references/infra.md` |
   | スキーマ・マイグレーション・バックフィル・PII を含む保存データ | `references/data.md` |
   | テストコードの追加・変更 | `references/test.md` |

3. 次にリポ固有チェックリスト(各リポの `/review-driven-implement` PROJECT ブロックに記載)を読む。
   固有側は **ビジネス不変条件・FW 固有の落とし穴・過去事故の再発防止**だけを持つ。共通側と重複する項目は固有側から削る。
4. 指摘は `references/severity.md` の定義で P0〜P3 を付け、P0/P1 は必ず「この入力・状態 → この誤動作」の失敗シナリオを添える。
   シナリオを書けない指摘は P2 以下に降格する。
5. 指摘には根拠を `ファイル:行` で示す。

## 項目の書き方(この skill に追記するときのルール)

- 「他のリポにコピーしても意味が通る」項目だけを書く。FW 名・ライブラリ名・API 名が必要な項目はリポ側へ。
- 1項目 = 1行。`- [P?] 確認内容(失敗するとどうなるか)` の形。
- 各ファイルは **10KB 以内**。超えたら統合・削除する(大きいチェックリストは読まれない)。
- review-learning で見つかった新観点は、各ファイル末尾の `## 候補(レビューで発見)` に `- [P?] 観点(リポ名 YYYY-MM-DD)` の形で1行追記する。棚卸し(保守者の `/review-checklist-groom`)で 2 リポ以上再現したものを本文へ昇格し、テスト・lint で機械化できた項目は削除して、`tools/release.sh` で version を上げて配信する。

## 対象外

- 設計・仕様レビュー → `spec-design-multireview` skill
- レビュー手順そのもの(Codex 1回固定・テストゲート等) → `/review-driven-implement`(`process.md` は手順ではなく「指摘の作法」)
