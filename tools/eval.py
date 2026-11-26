#!/usr/bin/env python3
"""レビュアーの再採点。過去に見逃したバグ(kind=bug)を検出できるか、問題なしの変更(kind=clean)で P0/P1 を出さないかを測る。

ケースと結果は非公開リポの中身を含むので、このリポ(公開)には置かない。既定の置き場は ~/programming/my-tools/review-evals/。

usage:
  tools/eval.py run [--reviewer claude|codex] [--cases DIR] [--only ID ...] [--split dev|holdout|all] [--jobs N] [--min-sev P1] [--label TEXT]
  tools/eval.py fresh   # 最新の結果が今の plugins/ で採点されたものか(release.sh から呼ぶ)
  tools/eval.py spread  # 同じ plugins/ と採点条件で複数回回した結果の recall・誤検知の幅(揺れ)
  tools/eval.py compare # 最新の codex の結果を同じ版の claude の結果に足したとき(実運用の Claude + Codex)に recall・誤検知がどう変わるか
"""
import argparse, collections, hashlib, concurrent.futures as cf, datetime, glob, json, os, subprocess, sys, tempfile, threading, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.expanduser(os.environ.get("REVIEW_EVALS_DIR", "~/programming/my-tools/review-evals"))
PROGRAMMING = os.path.expanduser("~/programming")
SEV = ["P0", "P1", "P2", "P3"]
# holdout はチェックリストの修正に使わないケース。dev の見逃しに合わせた修正が、他のケースにも効くか(壊さないか)を見る
SPLITS = ["dev", "holdout"]
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

いつもどおりの手順で見る(review-workflow:review-checklist skill とセキュリティレビュー)。コードは編集しない。
差分に起因する指摘だけを返す。file はリポジトリ直下からの相対パス、line は {head} 時点の行番号。"""
PROJECT_SETTINGS_NOTE = """
このリポジトリのプロジェクト固有設定(固有チェックリストの場所を含む)は {path} にある。リポ固有チェックリストはここから辿って読む。"""
CLAUDE_SETTINGS = '{"disableAllHooks":true,"outputStyle":"default"}'
# 同じリポへの worktree add/remove を並行させると .git のロックで落ちる
REPO_LOCKS = collections.defaultdict(threading.Lock)
JUDGE_MODEL = "sonnet"
# 採点の条件は実行環境から決めない。effort は settings の modelSettings で変わり、
# ~/.claude/skills の review-checklist は main の作業ツリー(未コミット込み)を指すので、
# どちらも ROOT の版と結果に記録した値に固定する
REVIEW_MODEL = "opus"
REVIEW_EFFORT = "high"
# 実運用の ~/.codex/config.toml と同じ値。~/.codex/skills の review-checklist は main の作業ツリーを指すので、ROOT の版を明示して読ませる
CODEX_MODEL = "gpt-6.1-sol"
CODEX_EFFORT = "high"
CODEX_SKILL_NOTE = """
レビューの基準は {path}(review-checklist skill の正本)。SKILL.md の手順に従い、そこから references を辿って読む。~/.codex/skills の review-checklist は使わない。"""
CONDITIONS = {"claude": (REVIEW_MODEL, REVIEW_EFFORT), "codex": (CODEX_MODEL, CODEX_EFFORT)}
USER_RULES = os.path.expanduser("~/.claude/CLAUDE.md")
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


def load_cases(d, only, split="all"):
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
        if c.get("split") not in SPLITS:
            sys.exit(f"{p}: split は {' / '.join(SPLITS)} のどちらか")
        if split != "all" and c["split"] != split:
            continue
        cases.append(c)
    return cases


def strict(schema):
    # codex の --output-schema は全プロパティ required・additionalProperties false しか受け付けない
    if schema.get("type") == "object":
        props = {k: strict(v) for k, v in schema["properties"].items()}
        return {**schema, "properties": props, "required": list(props), "additionalProperties": False}
    if schema.get("type") == "array":
        return {**schema, "items": strict(schema["items"])}
    return schema


def review(case, timeout, reviewer="claude"):
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
        if reviewer == "codex":
            return review_codex(wt, prompt, timeout)
        cmd = ["claude", "-p", prompt, "--settings", CLAUDE_SETTINGS, "--output-format", "json",
               "--json-schema", json.dumps(SCHEMA), "--permission-mode", "default", *review_env_args(), *extra, "--allowedTools", *READ_ONLY_TOOLS]
        t = time.time()
        r = subprocess.run(cmd, cwd=wt, capture_output=True, text=True, timeout=timeout)
        out = json.loads(r.stdout)
        if out.get("is_error") or "structured_output" not in out:
            raise RuntimeError(f"reviewer error: {str(out.get('result'))[:300]}")
        return out["structured_output"]["findings"], round(time.time() - t), out.get("total_cost_usd")
    finally:
        with REPO_LOCKS[repo]:
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", wt], capture_output=True)


def review_codex(wt, prompt, timeout):
    prompt = prompt.replace("review-workflow:review-checklist skill", "review-checklist skill") + CODEX_SKILL_NOTE.format(
        path=os.path.join(ROOT, "plugins", "review-workflow", "skills", "review-checklist", "SKILL.md"))
    with tempfile.TemporaryDirectory(prefix="review-eval-codex-") as tmp:
        schema, out = os.path.join(tmp, "schema.json"), os.path.join(tmp, "out.json")
        json.dump(strict(SCHEMA), open(schema, "w", encoding="utf8"))
        cmd = ["codex", "exec", "-C", wt, "-s", "read-only", "-m", CODEX_MODEL, "-c", f"model_reasoning_effort={CODEX_EFFORT}",
               "--output-schema", schema, "-o", out, prompt]
        t = time.time()
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, stdin=subprocess.DEVNULL)
        # 終了コードが 0 でも最終メッセージが書かれないことがあるので、出力ファイルの中身で決める
        if not os.path.exists(out) or not open(out, encoding="utf8").read().strip():
            raise RuntimeError(f"codex error (exit {r.returncode}): {r.stderr[-300:]}")
        return json.load(open(out, encoding="utf8"))["findings"], round(time.time() - t), None


def review_env_args():
    # user の設定源を外すと ~/.claude/skills と user の CLAUDE.md も読まれなくなるので、規約だけ明示して足す
    args = ["--model", REVIEW_MODEL, "--effort", REVIEW_EFFORT, "--setting-sources", "project,local",
            "--plugin-dir", os.path.join(ROOT, "plugins", "review-workflow")]
    if os.path.exists(USER_RULES):
        args += ["--append-system-prompt-file", USER_RULES]
    return args


def reviewer_of(result):
    # reviewer を記録する前の結果はすべて claude
    return result.get("reviewer", "claude")


def same_conditions(result, reviewer="claude"):
    return reviewer_of(result) == reviewer and (result.get("review_model"), result.get("review_effort")) == CONDITIONS[reviewer]


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
        futs = {ex.submit(review, c, a.timeout, a.reviewer): c for c in cases}
        for fut in cf.as_completed(futs):
            c = futs[fut]
            try:
                findings, sec, cost = fut.result()
                rows.append({"id": c["id"], "kind": c["kind"], "split": c["split"], "seconds": sec, "cost_usd": cost, **score(c, findings, a.min_sev), "findings": findings})
            except Exception as e:
                rows.append({"id": c["id"], "kind": c["kind"], "split": c["split"], "error": str(e)[:500]})
            # holdout の当否を1件ずつ見ると、それに合わせてチェックリストを直したくなるので集計だけ出す
            shown = {k: v for k, v in rows[-1].items() if k not in ("findings", "id")} if c["split"] == "dev" else {"split": "holdout", "error": rows[-1].get("error")}
            print(f"  {c['id']}: {json.dumps(shown, ensure_ascii=False)}", flush=True)

    summary = {**summarize(rows),
               "errors": sum(1 for r in rows if "error" in r),
               "cost_usd": round(sum((r.get("cost_usd") or 0) + r.get("judge_cost_usd", 0) for r in rows), 2),
               "by_split": {s: summarize([r for r in rows if r["split"] == s]) for s in SPLITS if any(r["split"] == s for r in rows)}}
    stamp = datetime.datetime.now().strftime("%Y-%m-%dT%H%M")
    model, effort = CONDITIONS[a.reviewer]
    result = {"at": stamp, "label": a.label, "reviewer": a.reviewer, "plugins_rev": plugins_rev(), "review_model": model, "review_effort": effort, "min_sev": a.min_sev, "summary": summary, "cases": sorted(rows, key=lambda r: r["id"])}
    os.makedirs(os.path.join(DATA, "results"), exist_ok=True)
    path = os.path.join(DATA, "results", f"{stamp}.json")
    prev = sorted(glob.glob(os.path.join(DATA, "results", "*.json")))
    json.dump(result, open(path, "w", encoding="utf8"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False))
    ids = {r["id"] for r in rows}
    prev = [f for f in prev if {r["id"] for r in json.load(open(f, encoding="utf8"))["cases"]} == ids
            and reviewer_of(json.load(open(f, encoding="utf8"))) == a.reviewer]
    if prev and not same_conditions(json.load(open(prev[-1], encoding="utf8")), a.reviewer):
        print(f"前回 {os.path.basename(prev[-1])} は採点条件(モデル・effort・skill の読み込み)が違うので比べない")
        prev = []
    if prev:
        p = json.load(open(prev[-1], encoding="utf8"))["summary"]
        print(f"前回 {os.path.basename(prev[-1])}: recall {p['recall']} → {summary['recall']} / clean 誤検知 {p['clean_cases_with_false_positive']} → {summary['clean_cases_with_false_positive']}")
        for s, cur in summary["by_split"].items():
            old = p.get("by_split", {}).get(s)
            if old:
                print(f"  {s}: recall {old['recall']} → {cur['recall']} / clean 誤検知 {old['clean_cases_with_false_positive']} → {cur['clean_cases_with_false_positive']}")
    print(f"保存: {path}")
    return 1 if summary["errors"] else 0


def summarize(rows):
    bug = [r for r in rows if r["kind"] == "bug" and "error" not in r]
    clean = [r for r in rows if r["kind"] == "clean" and "error" not in r]
    exp = [h for r in bug for h in r["expected"]]
    return {
        "recall": round(exp.count("hit") / len(exp), 3) if exp else None,
        "found_but_low_severity": exp.count("low-severity"),
        "clean_cases_with_false_positive": sum(1 for r in clean if r["false_positives"]) if clean else None,
        "clean_cases": len(clean),
    }


def spread(_):
    groups = collections.defaultdict(list)
    for p in sorted(glob.glob(os.path.join(DATA, "results", "*.json"))):
        r = json.load(open(p, encoding="utf8"))
        if r["summary"].get("errors"):
            continue
        key = (r.get("plugins_rev"), reviewer_of(r), r.get("review_model"), r.get("review_effort"), r.get("min_sev"), tuple(sorted((c["id"], c.get("split")) for c in r["cases"])))
        groups[key].append(r)
    found = False
    for (rev, reviewer, model, effort, _, ids), rs in groups.items():
        if len(rs) < 2:
            continue
        found = True
        print(f"{rev[:12]} {reviewer} {model}/{effort} ケース{len(ids)}件 × {len(rs)}回 ({', '.join(r['at'] for r in rs)})")
        for name, pick in [("全体", lambda r: r["summary"])] + [(s, lambda r, s=s: r["summary"].get("by_split", {}).get(s)) for s in SPLITS]:
            vals = [pick(r) for r in rs]
            if any(v is None for v in vals):
                continue
            rec = [v["recall"] for v in vals if v["recall"] is not None]
            fp = [v["clean_cases_with_false_positive"] for v in vals if v["clean_cases_with_false_positive"] is not None]
            print(f"  {name}: recall {min(rec)}〜{max(rec)} / clean 誤検知 {min(fp)}〜{max(fp)}" if rec and fp else f"  {name}: 集計なし")
    if not found:
        print("同じ plugins/ と採点条件で2回以上回した結果が無い")
    return 0


def load_results():
    return [json.load(open(p, encoding="utf8")) for p in sorted(glob.glob(os.path.join(DATA, "results", "*.json")))]


def union(a, b):
    # 実運用では Codex の指摘を受けてから自己レビューするので、どちらかが当てれば当たり、どちらかが誤検知すれば誤検知
    rows = []
    for x in a["cases"]:
        y = {r["id"]: r for r in b["cases"]}[x["id"]]
        row = {"id": x["id"], "kind": x["kind"], "split": x.get("split")}
        if x["kind"] == "bug":
            order = ["hit", "low-severity", "miss"]
            row["expected"] = [min(h1, h2, key=order.index) for h1, h2 in zip(x["expected"], y["expected"])]
        else:
            row["false_positives"] = x["false_positives"] + y["false_positives"]
        rows.append(row)
    return rows


def compare(_):
    results = [r for r in load_results() if not r["summary"].get("errors")]
    codex = [r for r in results if same_conditions(r, "codex")]
    if not codex:
        sys.exit("codex の結果が無い。`tools/eval.py run --reviewer codex` を先に回す")
    def peers(cx):
        ids = {c["id"] for c in cx["cases"]}
        return [r for r in results if same_conditions(r, "claude") and r["plugins_rev"] == cx["plugins_rev"] and {c["id"] for c in r["cases"]} == ids]
    # --only の試し打ちが最新でも比べられるよう、同じ版・同じケースの claude の結果がある最新の codex を使う
    pairs = [(cx, peers(cx)) for cx in codex if peers(cx)]
    if not pairs:
        sys.exit("同じ版・同じケースで claude と codex の両方を採点した結果が無い")
    cx, claude = pairs[-1]
    ids = {c["id"] for c in cx["cases"]}
    def line(name, s):
        return f"{name}: recall {s['recall']} / clean 誤検知 {s['clean_cases_with_false_positive']}/{s['clean_cases']}"
    print(f"codex {cx['at']} と claude {len(claude)}回 ({', '.join(r['at'] for r in claude)})、ケース{len(ids)}件")
    print("  " + line("codex 単独", summarize(cx["cases"])))
    for cl in claude:
        both = union(cl, cx)
        only = [r["id"] for r, c in zip(both, cl["cases"]) if r["kind"] == "bug" and r["expected"].count("hit") > c["expected"].count("hit")]
        dev_only = [i for i in only if {c["id"]: c for c in cx["cases"]}[i].get("split") == "dev"]
        print(f"  {cl['at']}  {line('claude 単独', summarize(cl['cases']))}  →  {line('claude+codex', summarize(both))}")
        # holdout の個別の当否は出さない(チェックリストの修正に使わないため)
        print(f"    codex だけが当てたケース: dev {dev_only or 'なし'} / holdout {len(only) - len(dev_only)}件")
    return 0


def fresh(_):
    if not glob.glob(os.path.join(DATA, "cases", "*.json")):
        print("評価ケースなし(採点をスキップ)"); return 0
    ids = {json.load(open(p, encoding="utf8")).get("id") or os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(DATA, "cases", "*.json"))}
    # --only で一部だけ回した結果では配信の判断に使わない
    # 配信の判断は claude の結果で行う(codex の結果は compare で比べるためのもの)
    results = [p for p in sorted(glob.glob(os.path.join(DATA, "results", "*.json")))
               if {r["id"] for r in json.load(open(p, encoding="utf8"))["cases"]} >= ids
               and reviewer_of(json.load(open(p, encoding="utf8"))) == "claude"]
    rev = plugins_rev()
    last = json.load(open(results[-1], encoding="utf8")) if results else {}
    if last.get("plugins_rev") == rev and same_conditions(last, "claude"):
        print(f"最新の採点は今の plugins/ ({rev[:12]}) で実施済み"); return 0
    print(f"今の plugins/ ({rev[:12]}) で採点していない。`tools/eval.py run` を回して結果を確かめてから配信する(飛ばすなら SKIP_EVAL=1)")
    return 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--reviewer", default="claude", choices=list(CONDITIONS))
    r.add_argument("--cases", default=os.path.join(DATA, "cases"))
    r.add_argument("--only", nargs="*")
    r.add_argument("--split", default="all", choices=SPLITS + ["all"])
    r.add_argument("--jobs", type=int, default=3)
    r.add_argument("--min-sev", default="P1", choices=SEV)
    r.add_argument("--timeout", type=int, default=1800)
    r.add_argument("--label", default="")
    r.set_defaults(fn=run)
    sub.add_parser("fresh").set_defaults(fn=fresh)
    sub.add_parser("spread").set_defaults(fn=spread)
    sub.add_parser("compare").set_defaults(fn=compare)
    a = ap.parse_args()
    sys.exit(a.fn(a))


if __name__ == "__main__":
    main()
