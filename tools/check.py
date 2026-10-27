#!/usr/bin/env python3
"""plugin の整合検査。release.sh と CI から呼ぶ。失敗は exit 1。"""
import glob, json, os, re, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LIMIT = 10 * 1024
errors, info = [], []

def frontmatter(path):
    s = open(path, encoding="utf8").read()
    m = re.match(r"---\n(.*?)\n---", s, re.S)
    if not m:
        errors.append(f"{path}: frontmatter がない"); return None
    try:
        import yaml
        d = yaml.safe_load(m.group(1))
    except ImportError:
        d = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
        d = {k.strip(): v.strip() for k, v in d.items()}
    except Exception as e:
        errors.append(f"{path}: frontmatter が YAML として不正: {str(e).splitlines()[0]}"); return None
    for k in ("name", "description"):
        if not d or k not in d:
            errors.append(f"{path}: frontmatter に {k} がない")
    return d

for skill in sorted(glob.glob(os.path.join(ROOT, "plugins", "*", "skills", "*", "SKILL.md")) + glob.glob(os.path.join(ROOT, "maintainer-skills", "*", "SKILL.md"))):
    frontmatter(skill)

for ref in sorted(glob.glob(os.path.join(ROOT, "plugins", "*", "skills", "*", "references", "*.md"))):
    size = os.path.getsize(ref)
    rel = os.path.relpath(ref, ROOT)
    text = open(ref, encoding="utf8").read()
    m = re.search(r"^## 候補.*$", text, re.M)
    cand = text[m.end():] if m else ""
    n_cand = sum(1 for l in cand.splitlines() if l.startswith("- "))
    info.append(f"{rel}: {size:5d} B, 候補 {n_cand}")
    if size > LIMIT:
        errors.append(f"{rel}: {size} B > {LIMIT} B(統合・削除して 10KB 以内にする)")

# 同期のキーが重複すると sync.mjs が片方の行を見失う。版と変更履歴のずれは配信後に各リポで気付けない。
for tpl in sorted(glob.glob(os.path.join(ROOT, "plugins", "*", "skills", "*", "template.md"))):
    rel = os.path.relpath(tpl, ROOT)
    text = open(tpl, encoding="utf8").read()
    ids = re.findall(r"^\| `([\w.-]+)` \|", text, re.M)
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        errors.append(f"{rel}: ID が重複 {', '.join(dup)}")
    if any(i.startswith("local.") for i in ids):
        errors.append(f"{rel}: local. の ID はテンプレに置かない(昇格時に付け直す)")
    m = re.search(r"template-version:\s*(\d+)", text)
    changes = os.path.join(os.path.dirname(tpl), "CHANGES.md")
    if not m:
        errors.append(f"{rel}: template-version が無い")
    elif not os.path.exists(changes) or not re.search(rf"^- v{m.group(1)}\b", open(changes, encoding="utf8").read(), re.M):
        errors.append(f"{rel}: CHANGES.md に v{m.group(1)} の記載が無い")
    else:
        info.append(f"{rel}: v{m.group(1)}, {len(ids)} 行")

for plugin in sorted(glob.glob(os.path.join(ROOT, "plugins", "*", ".claude-plugin", "plugin.json"))):
    p = json.load(open(plugin)); name = p["name"]
    mk = json.load(open(os.path.join(ROOT, ".claude-plugin", "marketplace.json")))
    entry = next((e for e in mk["plugins"] if e["name"] == name), None)
    if not entry:
        errors.append(f"marketplace.json に {name} が無い")
    elif entry.get("version") != p.get("version"):
        errors.append(f"{name}: version 不一致 plugin.json={p.get('version')} marketplace.json={entry.get('version')}")
    else:
        info.append(f"{name}: v{p['version']}")

print("\n".join(info))
if errors:
    print("\nNG:\n- " + "\n- ".join(errors)); sys.exit(1)
print("\nOK")
