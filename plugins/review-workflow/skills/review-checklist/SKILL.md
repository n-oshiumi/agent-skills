---
name: review-checklist
description: 言語・フレームワーク非依存のコードレビューチェックリスト(全リポ共通の正本)。実装の自己レビュー、Codex クロスレビュー、PR レビュー、「レビューして」と頼まれたときの「何を見るか」の基準として使い、セキュリティレビューも必ず併せて行う。/review-driven-implement の Phase 3(自己レビュー)と Phase 5(Codex)から参照される。変更差分のレイヤー(backend / frontend / infra / data)に応じて references/ の該当ファイルだけを読む。プロジェクト固有の不変条件・FW 固有の落とし穴は各リポのチェックリストが持ち、本 skill には書かない。
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
6. チェックリストとは別に、同じ差分へセキュリティレビューを必ず1パス当てる(Claude Code: `/security-review`、Codex: 認証・認可 / 入力検証・インジェクション / 秘密・PII の露出 / 追加した依存 を別パスで読む)。
   指摘は同じ P0〜P3 で付け、報告に「セキュリティ: P0/P1 n 件 / 該当なし」を1行入れる。docs のみの差分は対象外。
7. 指摘を受けて処置を決めた側(自己レビューなら自分、Codex・人の指摘なら実装側)が、1件ごとに処置を記録する。ノイズ率(観点ごとの採用率)の元データになる:
   `python3 <この skill のディレクトリ>/scripts/review_log.py add --source self|codex|security|human --sev P? --ref <観点。例 common.md#入力と境界 / security-review / none> --outcome fixed|rejected|intentional|ignored`
   rejected = 指摘が誤り、intentional = 仕様どおり、ignored = 正しいが直さない。

## 項目の書き方(この skill に追記するときのルール)

- 「他のリポにコピーしても意味が通る」項目だけを書く。FW 名・ライブラリ名・API 名が必要な項目はリポ側へ。
- 1項目 = 1行。`- [P?] 確認内容(失敗するとどうなるか)` の形。
- 各ファイルは **10KB 以内**。超えたら統合・削除する(大きいチェックリストは読まれない)。
- review-learning で見つかった新観点は、各ファイル末尾の `## 候補(レビューで発見)` に `- [P?] 観点(リポ名 YYYY-MM-DD)` の形で1行追記する。棚卸し(保守者の `/review-checklist-groom`)で 2 リポ以上再現したものを本文へ昇格し、テスト・lint で機械化できた項目は削除して、`tools/release.sh` で version を上げて配信する。

## 対象外

- 設計・仕様レビュー → `spec-design-multireview` skill
- レビュー手順そのもの(Codex 1回固定・テストゲート等) → `/review-driven-implement`(`process.md` は手順ではなく「指摘の作法」)
