#!/usr/bin/env python3
"""レビュー指摘の処置を 1 件 1 行で記録し、出どころ・観点ごとの採用率(= ノイズの逆)を出す。

記録は非公開リポの情報を含むのでローカルに置く(既定 ~/.claude/review-log.jsonl、REVIEW_LOG で変更)。

usage:
  review_log.py add --source codex --sev P1 --ref common.md#入力と境界 --outcome fixed [--file path] [--repo name] [--note 一言]
  review_log.py stats [--since YYYY-MM-DD] [--by source|ref|sev|repo]
"""
import argparse, collections, datetime, json, os, subprocess, sys

LOG = os.path.expanduser(os.environ.get("REVIEW_LOG", "~/.claude/review-log.jsonl"))
SOURCES = ["self", "codex", "security", "human"]
OUTCOMES = ["fixed", "rejected", "intentional", "ignored"]
MIN_SAMPLES = 5
LOW_ADOPTION = 0.3


def current_repo():
    top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()
    if not top:
        return os.path.basename(os.getcwd())
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True).stdout.strip()
    # worktree でも本体のリポ名で集計する
    return os.path.basename(os.path.dirname(common)) if common.endswith("/.git") else os.path.basename(top)


def add(a):
    row = {"date": datetime.date.today().isoformat(), "repo": a.repo or current_repo(), "source": a.source,
           "sev": a.sev, "ref": a.ref, "outcome": a.outcome}
    if a.file:
        row["file"] = a.file
    if a.note:
        row["note"] = a.note
    os.makedirs(os.path.dirname(LOG), exist_ok=True)
    with open(LOG, "a", encoding="utf8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"記録: {row}")


def stats(a):
    if not os.path.exists(LOG):
        sys.exit(f"記録なし: {LOG}")
    rows = []
    for n, line in enumerate(open(LOG, encoding="utf8"), 1):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            print(f"壊れた行を飛ばした: {LOG}:{n}", file=sys.stderr)
            continue
        if not a.since or r["date"] >= a.since:
            rows.append(r)
    groups = collections.defaultdict(collections.Counter)
    for r in rows:
        groups[r.get(a.by, "-")][r["outcome"]] += 1
    print(f"{a.by:<32} 件数  fixed rejected intentional ignored  採用率")
    for key, c in sorted(groups.items(), key=lambda kv: -sum(kv[1].values())):
        total = sum(c.values())
        rate = c["fixed"] / total
        flag = "  ← 削除・降格の候補" if total >= MIN_SAMPLES and rate < LOW_ADOPTION else ""
        print(f"{key:<32} {total:4d}  {c['fixed']:5d} {c['rejected']:8d} {c['intentional']:11d} {c['ignored']:7d}  {rate:5.0%}{flag}")
    print(f"計 {len(rows)} 件(採用率 = fixed / 件数。{MIN_SAMPLES} 件以上で {LOW_ADOPTION:.0%} 未満に印)")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("add")
    p.add_argument("--source", required=True, choices=SOURCES)
    p.add_argument("--sev", required=True, choices=["P0", "P1", "P2", "P3"])
    p.add_argument("--ref", required=True, help="観点の出どころ。例: common.md#入力と境界 / repo:固有チェックリスト名 / none")
    p.add_argument("--outcome", required=True, choices=OUTCOMES)
    p.add_argument("--file")
    p.add_argument("--repo")
    p.add_argument("--note")
    p.set_defaults(fn=add)
    s = sub.add_parser("stats")
    s.add_argument("--since")
    s.add_argument("--by", default="source", choices=["source", "ref", "sev", "repo"])
    s.set_defaults(fn=stats)
    a = ap.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
