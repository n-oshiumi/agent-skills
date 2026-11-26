---
name: land
description: /ship で準備ができた PR を、マージゲートを確かめてマージし、ブランチ・worktree を片付け、チケット・issue を閉じる(全リポ共通)。リポ固有のゲート・マージ方法・チケットは各リポの .claude/review-driven-implement.project.md の「### マージ(/land)」節から読む。ユーザーが /land [PR番号] と打ったときだけ使う。デプロイはしない。
disable-model-invocation: true
---

# /land — PR をマージして片付ける

`/ship`(PR 作成・レビュー・CI 待ち)の後段。**ユーザーが `/land` を打ったことを、その PR のマージと push の承認とみなす**。デプロイは含まない。

## 0. 固有設定を読む

起動ディレクトリと git ルートの `.claude/review-driven-implement.project.md` を読み、「### マージ(/land)」節を探す。無ければ下の既定で進める。

| 項目 | 既定 |
| --- | --- |
| ゲート | 同ファイル「### テスト・品質ゲート」のコマンド。それも無ければ CI の結果だけ |
| マージ方法 | リポで許可されている方式(`gh repo view --json squashMergeAllowed,mergeCommitAllowed,rebaseMergeAllowed`)のうち squash > merge > rebase |
| チケット | GitHub issue(PR 本文の `Closes #n` に任せる) |

起動ディレクトリが git リポでなければ、固有設定に書かれた git ルート(例: `web-market/`)で作業する。書かれていなければ止めて聞く。

## 1. 対象の PR

- 引数の PR 番号・URL、無ければ今のブランチの PR(`gh pr view --json number,state,headRefName,baseRefName,isDraft,mergeable,reviewDecision,statusCheckRollup`)。
- 別のブランチの PR なら、元のチェックアウトを切り替えず `git worktree add ../<repo>-<branch> <branch>` で開く。

## 2. ゲート(1つでも未達ならマージしない)

- `state` が OPEN、draft でない、`mergeable` が MERGEABLE。
- 必須チェックが全部成功。待ちがあれば終わるまで待つ(失敗なら止める。直すのは `/steward` の役目)。
- `reviewDecision` が CHANGES_REQUESTED でない。未解決のレビュースレッドが無い(`gh api graphql` の `reviewThreads.isResolved`)。
- base を取り込んだ状態でゲートのコマンドが通る(`git fetch origin && git merge origin/<base>`。取り込みで差分が出たら push して CI を待つ)。
- シークレットの混入を見る: `git diff origin/<base>...HEAD | grep -E '^\+'` に鍵・トークンの形が無いか。
- 固有設定にゲートのチェックリストがあれば上から確かめ、【P0】が1件でも未達なら止めて報告する。

## 3. マージ

- `gh pr merge <n> --<方式>`。auto-merge は使わない(この場で結果を確かめる)。
- `gh pr view <n> --json state,mergeCommit` で MERGED になったことを確かめる。`--delete-branch` の後段が失敗してもマージ自体は成功していることがあるので、必ず state で見る。

## 4. 片付け

- PR のブランチを worktree で作業していたなら `git worktree remove <path>`(未コミットの変更が残っていたら消さずに報告)。
- ローカルブランチ `git branch -D <branch>`(マージ済みを確かめてから)。リモートに残っていれば `git push origin --delete <branch>`。
- 元のチェックアウトが base にいれば `git pull`。base 以外にいるなら触らない(checkout / switch / stash をしない)。

## 5. チケット

- 固有設定のチケットの手順に従う。**受け入れ基準を全部満たしたときだけ完了にする**。一部なら完了にせず、終わった範囲と残りをコメントする。
- GitHub issue は `Closes #n` で閉じたかを確かめ、完全に終わっていないのに閉じたら開け直して残りを書く。

## 6. 報告

```
マージ: <ブランチ> → <base>(PR #n / <コミット>)
片付け: worktree / ローカル / リモートのブランチ
チケット: <番号> 完了 | コメントのみ(残り)
デプロイ: 未実施(必要なら手順)
```

## やらないこと

- デプロイ(固有設定にデプロイ手順があっても書くだけ)。
- ゲート未達のまま強行(`--admin` で保護ルールを飛ばさない)。
- `/ship` のウォッチを止める操作(マージで自然に終わる)。
