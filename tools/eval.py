#!/usr/bin/env python3
"""レビュアーの再採点。過去に見逃したバグ(kind=bug)を検出できるか、問題なしの変更(kind=clean)で P0/P1 を出さないかを測る。

ケースと結果は非公開リポの中身を含むので、このリポ(公開)には置かない。既定の置き場は ~/programming/my-tools/review-evals/。

usage:
  tools/eval.py run [--cases DIR] [--only ID ...] [--jobs N] [--min-sev P1] [--label TEXT]
  tools/eval.py fresh   # 最新の結果が今の plugins/ で採点されたものか(release.sh から呼ぶ)
"""
import argparse, collections, hashlib, concurrent.futures as cf, datetime, glob, json, os, subprocess, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.expanduser(os.environ.get("REVIEW_EVALS_DIR", "~/programming/my-tools/review-evals"))
PROGRAMMING = os.path.expanduser("~/programming")
SEV = ["P0", "P1", "P2", "P3"]
LINE_SLACK = 10
SCHEMA = {
    "type": "object",
    "properties": {"findings": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "severity": {"type": "string", "enum": SEV},
            "file": {"type": "string"},
            "line": {"type": "integer"},
            "summary": {"type": "string"},
            "security": {"type": "boolean"},
        },
        "required": ["severity", "file", "line", "summary"],
    }}},
    "required": ["findings"],
}
PROMPT = """このリポジトリの変更 `{base}..{head}` をレビューして。
変更の意図: {intent}

いつもどおりの手順で見る(review-checklist skill とセキュリティレビュー)。コードは編集しない。
差分に起因する指摘だけを返す。file はリポジトリ直下からの相対パス、line は {head} 時点の行番号。"""
PROJECT_SETTINGS_NOTE = """
このリポジトリのプロジェクト固有設定(固有チェックリストの場所を含む)は {path} にある。リポ固有チェックリストはここから辿って読む。"""
CLAUDE_SETTINGS = '{"disableAllHooks":true,"outputStyle":"default"}'
# 同じリポへの worktree add/remove を並行させると .git のロックで落ちる
REPO_LOCKS = collections.defaultdict(threading.Lock)
JUDGE_MODEL = "sonnet"
JUDGE_SCHEMA = {"type": "object", "properties": {"reason": {"type": "string"}, "same": {"type": "array", "items": {"type": "integer"}}}, "required": ["reason", "same"]}
JUDGE_PROMPT = """コードレビューの採点をする。ツールは使わず、下の文だけで判定する。

期待するバグ: {bug}

レビュアーの指摘:
{listing}

reason に、期待するバグの「原因」と「利用者・データに起きる誤動作」を1行ずつ書き、各指摘について両方が一致するかを書く。
両方が一致する指摘の番号をすべて same に入れる。原因が同じでも誤動作が違う(例: 期待は欠測が残る、指摘は処理が失敗する)なら別の不具合。該当が無ければ空配列。"""
READ_ONLY_TOOLS = ["Read", "Grep", "Glob", "Skill", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git show:*)", "Bash(git blame:*)", "Bash(ls:*)"]


def plugins_rev():
    # コミット前に採点して後でコミットしても一致するよう、git の tree ではなく作業ツリーの中身で版を決める
    h = hashlib.sha256()
    for path in sorted(glob.glob(os.path.join(ROOT, "plugins", "**", "*"), recursive=True)):
        if os.path.isfile(path) and "__pycache__" not in path:
            h.update(os.path.relpath(path, ROOT).encode() + b"\0" + open(path, "rb").read())
    return h.hexdigest()


def load_cases(d, only):
    cases = []
    for p in sorted(glob.glob(os.path.join(d, "*.json"))):
        c = json.load(open(p, encoding="utf8"))
        c.setdefault("id", os.path.splitext(os.path.basename(p))[0])
        if only and c["id"] not in only:
            continue
        missing = [k for k in ("kind", "repo", "base", "head", "intent") if not c.get(k)]
        if c.get("kind") == "bug" and not c.get("expected"):
            missing.append("expected")
        if missing:
            sys.exit(f"{p}: {', '.join(missing)} が無い")
        cases.append(c)
    return cases


def review(case, timeout):
    repo = os.path.join(PROGRAMMING, case["repo"])
    with REPO_LOCKS[repo]:
        if subprocess.run(["git", "-C", repo, "cat-file", "-e", case["head"] + "^{commit}"], capture_output=True).returncode:
            subprocess.run(["git", "-C", repo, "fetch", "-q", "origin"], capture_output=True)
    wt = tempfile.mkdtemp(prefix=f"review-eval-{case['id']}-")
    os.rmdir(wt)
    with REPO_LOCKS[repo]:
        subprocess.run(["git", "-C", repo, "worktree", "add", "-q", "--detach", wt, case["head"]], check=True, capture_output=True)
    try:
        prompt, extra = PROMPT.format(**case), []
        # 親ディレクトリの固有設定を使うネストしたリポは、worktree からその設定が見えないので明示して渡す
        if case.get("project_settings"):
            path = os.path.join(PROGRAMMING, case["project_settings"])
            prompt += PROJECT_SETTINGS_NOTE.format(path=path)
            extra = ["--add-dir", os.path.dirname(os.path.dirname(path))]
        cmd = ["claude", "-p", prompt, "--settings", CLAUDE_SETTINGS, "--output-format", "json",
               "--json-schema", json.dumps(SCHEMA), "--permission-mode", "default", *extra, "--allowedTools", *READ_ONLY_TOOLS]
        t = time.time()
        r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, timeout=timeout)
        out = json.loads(r.stdout)
        if out.get("is_error") or "structured_output" not in out:
            raise RuntimeError(f"reviewer error: {str(out.get('result'))[:300]}")
        return out["structured_output"]["findings"], round(time.time() - t), out.get("total_cost_usd")
    finally:
        with REPO_LOCKS[repo]:
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt], capture_output=True)


def same_path(a, b):
    a, b = a.lstrip("./"), b.lstrip("./")
    return a == b or a.endswith("/" + b) or b.endswith("/" + a)


def matches(f, exp):
    for loc in exp.get("locations") or [exp]:
        lo, hi = loc["lines"]
        if same_path(f["file"], loc["file"]) and lo - LINE_SLACK <= f["line"] <= hi + LINE_SLACK:
            return True
    return False


def in_expected_file(f, exp):
    return any(same_path(f["file"], loc["file"]) for loc in exp.get("locations") or [exp])


def judge(exp, candidates):
    listing = "\n".join(f"{i}: [{f['severity']}] {f['file']}:{f['line']} {f['summary']}" for i, f in enumerate(candidates))
    cmd = ["claude", "-p", JUDGE_PROMPT.format(bug=exp["bug"], listing=listing), "--settings", CLAUDE_SETTINGS,
           "--output-format", "json", "--json-schema", json.dumps(JUDGE_SCHEMA), "--model", JUDGE_MODEL]
    out = json.loads(subprocess.run(cmd, cwd=tempfile.gettempdir(), capture_output=True, text=True, timeout=300).stdout)
    same = [candidates[i] for i in out["structured_output"]["same"] if 0 <= i < len(candidates)]
    return same, out.get("total_cost_usd") or 0


def is_blocking(f, min_sev):
    return SEV.index(f["severity"]) <= SEV.index(min_sev)


def score(case, findings, min_sev):
    blocking = [f for f in findings if is_blocking(f, min_sev)]
    if case["kind"] == "clean":
        return {"false_positives": len(blocking)}
    hits, matched, judged, cost = [], [], [], 0
    for n, exp in enumerate(case["expected"]):
        located = [f for f in findings if matches(f, exp)]
        if any(is_blocking(f, min_sev) for f in located):
            hits.append("hit"); matched += located; continue
        # 同じバグを呼び出し側など別の行で指摘することがあるので、同じファイルの指摘だけ意味で照合する
        rest = [f for f in findings if in_expected_file(f, exp) and f not in located]
        same, c = judge(exp, rest) if rest else ([], 0)
        cost += c
        if same:
            hits.append("hit" if any(is_blocking(f, min_sev) for f in same) else "low-severity"); matched += same
            judged += [{"expected": n, "file": f["file"], "line": f["line"]} for f in same]
        else:
            hits.append("low-severity" if located else "miss"); matched += located
    row = {"expected": hits, "unrelated_blocking": sum(1 for f in blocking if f not in matched), "judge_cost_usd": round(cost, 3)}
    if judged:
        row["judged"] = judged
    return row


def run(a):
    cases = load_cases(a.cases, a.only)
    if not cases:
        sys.exit(f"ケースが無い: {a.cases}/*.json")
    rows = []
    with cf.ThreadPoolExecutor(a.jobs) as ex:
        futs = {ex.submit(review, c, a.timeout): c for c in cases}
        for fut in cf.as_completed(futs):
            c = futs[fut]
            try:
                findings, sec, cost = fut.result()
                rows.append({"id": c["id"], "kind": c["kind"], "seconds": sec, "cost_usd": cost, **score(c, findings, a.min_sev), "findings": findings})
            except Exception as e:
                rows.append({"id": c["id"], "kind": c["kind"], "error": str(e)[:500]})
            print(f"  {c['id']}: {json.dumps({k: v for k, v in rows[-1].items() if k not in ('findings', 'id')}, ensure_ascii=False)}", flush=True)

    bug = [r for r in rows if r["kind"] == "bug" and "error" not in r]
    clean = [r for r in rows if r["kind"] == "clean" and "error" not in r]
    exp = [h for r in bug for h in r["expected"]]
    summary = {
        "recall": round(exp.count("hit") / len(exp), 3) if exp else None,
        "found_but_low_severity": exp.count("low-severity"),
        "clean_cases_with_false_positive": sum(1 for r in clean if r["false_positives"]) if clean else None,
        "clean_cases": len(clean),
        "errors": sum(1 for r in rows if "error" in r),
        "cost_usd": round(sum((r.get("cost_usd") or 0) + r.get("judge_cost_usd", 0) for r in rows), 2),
    }
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H%M")
    result = {"at": stamp, "label": a.label, "plugins_rev": plugins_rev(), "min_sev": a.min_sev, "summary": summary, "cases": sorted(rows, key=lambda r: r["id"])}
    os.makedirs(os.path.join(DATA, "results"), exist_ok=True)
    path = os.path.join(DATA, "results", f"{stamp}.json")
    prev = sorted(glob.glob(os.path.join(DATA, "results", "*.json")))
    json.dump(result, open(path, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))
    ids = {r["id"] for r in rows}
    prev = [f for f in prev if {r["id"] for r in json.load(open(f, encoding="utf8"))["cases"]} == ids]
    if prev:
        p = json.load(open(prev[-1], encoding="utf8"))["summary"]
        print(f"前回 {os.path.basename(prev[-1])}: recall {p['recall']} → {summary['recall']} / clean 誤検知 {p['clean_cases_with_false_positive']} → {summary['clean_cases_with_false_positive']}")
    print(f"保存: {path}")
    return 1 if summary["errors"] else 0


def fresh(_):
    if not glob.glob(os.path.join(DATA, "cases", "*.json")):
        print("評価ケースなし(採点をスキップ)"); return 0
    ids = {json.load(open(p, encoding="utf8")).get("id") or os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(DATA, "cases", "*.json"))}
    # --only で一部だけ回した結果では配信の判断に使わない
    results = [p for p in sorted(glob.glob(os.path.join(DATA, "results", "*.json")))
               if {r["id"] for r in json.load(open(p, encoding="utf8"))["cases"]} >= ids]
    rev = plugins_rev()
    if results and json.load(open(results[-1], encoding="utf8"))["plugins_rev"] == rev:
        print(f"最新の採点は今の plugins/ ({rev[:12]}) で実施済み"); return 0
    print(f"今の plugins/ ({rev[:12]}) で採点していない。`tools/eval.py run` を回して結果を確かめてから配信する(飛ばすなら SKIP_EVAL=1)")
    return 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--cases", default=os.path.join(DATA, "cases"))
    r.add_argument("--only", nargs="*")
    r.add_argument("--jobs", type=int, default=3)
    r.add_argument("--min-sev", default="P1", choices=SEV)
    r.add_argument("--timeout", type=int, default=1800)
    r.add_argument("--label", default="")
    r.set_defaults(fn=run)
    sub.add_parser("fresh").set_defaults(fn=fresh)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
