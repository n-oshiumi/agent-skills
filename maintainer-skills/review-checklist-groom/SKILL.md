---
name: review-checklist-groom
description: 共通レビューチェックリスト(review-checklist skill)の候補節を棚卸しして本文へ昇格・統合・削除し、10KB 上限を守り、version を上げて plugin として配信する(保守者用)。「チェックリストを育てて」「候補を棚卸し」「チェックリストを配信」「review-checklist を更新」などで発動。月 1 回程度、または候補が 5 件を超えたら実行する。
argument-hint: '[--dry-run]'
---

# review-checklist-groom — 候補の棚卸しと配信

対象: `~/programming/agent-skills/plugins/review-workflow/skills/review-checklist/references/*.md`(`~/.claude/skills/review-checklist` はここへの symlink)。

## 手順

1. `python3 ~/programming/agent-skills/tools/check.py` で現状(各ファイルのサイズ・候補数)を出す。
2. 各 references の `## 候補(レビューで発見)` を全部読み、候補 1 件ごとに次のどれかに倒す:
   - **昇格**: 末尾の `(リポ名 日付)` が 2 リポ以上、または P0/P1 で汎用性が明らか → 本文の該当節へ移す(既存項目と重なるなら既存項目を書き換えて統合。1 行・言語非依存・失敗シナリオが分かる文に整える)。
   - **機械化**: テスト・lint・hook で機械的に落とせる観点 → 削除し、報告に「機械化候補」として残す(実装は各リポで)。
   - **保留**: 1 リポのみ・90 日未満 → そのまま残す。
   - **破棄**: 1 リポのみで 90 日以上再現なし、またはリポ固有と判明 → 削除(固有なら該当リポの候補節へ移す旨を報告)。
3. 本文側も見る: 同じ趣旨が 2 行以上あれば統合。機械化済みと分かる項目は削除。
4. 各ファイルを 10KB 以内に収める(超えるなら統合・削除。分割はしない)。
5. `python3 tools/check.py` が OK になるまで直す。
6. 変更内容を要約してコミットし、`tools/release.sh patch`(本文の意味が変わる大きな改訂なら `minor`)で配信する。`--dry-run` 指定時はここで止め、差分と予定 version を報告する。
7. 報告: 昇格 / 統合 / 削除 / 保留の件数と内容、機械化候補、配信した version。

## ルール

- 項目を発明しない。候補と本文にある文言の統合・言い換えだけ行う。
- 出典タグ `(リポ名 日付)` は昇格時に外す(履歴は git に残る)。
- リポ固有の値(FW 名・パス・ID)が要る項目は本文に入れない。
