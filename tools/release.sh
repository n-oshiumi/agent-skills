#!/usr/bin/env bash
# skill を直したあとの配信。version を上げて commit / tag / push する。
# usage: tools/release.sh [patch|minor|major] [--dry-run]
set -euo pipefail
cd "$(dirname "$0")/.."
kind=${1:-patch}; dry=${2:-}
[ -z "$(git status --porcelain)" ] || { echo "作業ツリーに未コミットの変更があります。先にコミットしてください。"; git status --short; exit 1; }
python3 tools/check.py
cur=$(python3 -c 'import json;print(json.load(open("plugins/review-workflow/.claude-plugin/plugin.json"))["version"])')
IFS=. read -r a b c <<<"$cur"
case $kind in patch) c=$((c+1));; minor) b=$((b+1)); c=0;; major) a=$((a+1)); b=0; c=0;; *) echo "usage: release.sh [patch|minor|major]"; exit 1;; esac
new="$a.$b.$c"
last=$(git describe --tags --abbrev=0 2>/dev/null || git rev-list --max-parents=0 HEAD)
log=$(git log --format='- %s' "$last"..HEAD -- plugins | grep -v '^- release:' || true)
echo "v$cur → v$new"; echo "$log"
[ "$dry" = "--dry-run" ] && { echo "(dry-run: 何も変更していません)"; exit 0; }
python3 - "$new" <<'PY'
import json,sys
v=sys.argv[1]
for p in ["plugins/review-workflow/.claude-plugin/plugin.json",".claude-plugin/marketplace.json"]:
    d=json.load(open(p))
    if "plugins" in d:
        for e in d["plugins"]: e["version"]=v
    else: d["version"]=v
    json.dump(d,open(p,"w"),ensure_ascii=False,indent=2); open(p,"a").write("\n")
PY
msg=$(printf 'release: v%s\n\n%s' "$new" "$log")
git add -A && git commit -q -m "$msg"
git tag "v$new"
git push -q origin main --tags
echo "pushed v$new。利用者は次回起動または /plugin update で受け取る。"
