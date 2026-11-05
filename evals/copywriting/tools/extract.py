#!/usr/bin/env python3
"""Extract bilingual strings L("en","pl") keyed by file + identifier, from a worktree or a git ref."""
import json, os, re, subprocess, sys
FILES = ["SaveMyEyes/Sources/Views/SharedStrings.swift", "SaveMyEyes/Sources/Views/MenuSettingsPane.swift",
         "SaveMyEyes/Sources/Views/SettingsForm.swift", "SaveMyEyes/Sources/Views/CalendarAccessWarning.swift",
         "SaveMyEyes/Sources/Views/IdeaCard.swift"]
STR = r'"((?:[^"\\]|\\.)*)"'
PAT = re.compile(r'(?:static let (\w+)\s*=\s*|\.(\w+):\s*|(\w+):\s*)L\(\s*' + STR + r'\s*,\s*' + STR + r'\s*\)', re.S)

def read(root, ref, f):
    if ref:
        r = subprocess.run(["git", "-C", root, "show", f"{ref}:{f}"], capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""
    p = os.path.join(root, f)
    return open(p).read() if os.path.exists(p) else ""

def extract(root, ref=None):
    out = {}
    for f in FILES:
        src = read(root, ref, f)
        short = os.path.basename(f).replace(".swift", "")
        seen = {}
        # long-break ideas get positional keys
        long_start = src.find("static let long")
        long_end = src.find("static let short") if long_start >= 0 else -1
        for m in PAT.finditer(src):
            name = m.group(1) or m.group(2) or m.group(3)
            if short == "IdeaCard" and long_start >= 0:
                if long_start < m.start() < long_end:
                    name = "long." + name
                elif m.start() > long_end and m.group(3):
                    name = "short." + name
            n = seen.get(name, 0); seen[name] = n + 1
            key = f"{short}.{name}" + (f"[{n}]" if (name.startswith("long.") or name.startswith("short.") or n) else "")
            if name.startswith("long.") or name.startswith("short."):
                key = f"{short}.{name}[{n}]"
            out[key] = {"en": m.group(4), "pl": m.group(5)}
    h = os.path.join(root, "HEADLINE.txt")
    if not ref and os.path.exists(h):
        out["HEADLINE"] = {"en": open(h).read().strip(), "pl": ""}
    return out

if __name__ == "__main__":
    base = sys.argv[1]
    runs = sys.argv[2:]
    data = {"master": extract(os.path.join(base, runs[0]), "HEAD")}
    for r in runs:
        data[r] = extract(os.path.join(base, r))
    json.dump(data, open(os.path.join(base, "strings.json"), "w"), ensure_ascii=False, indent=1)
    keys = list(data["master"].keys())
    for r in runs:
        for k in data[r]:
            if k not in keys: keys.append(k)
    for k in keys:
        m = data["master"].get(k, {}).get("en")
        vals = [data[r].get(k, {}).get("en") for r in runs]
        if any(v != m for v in vals):
            print(f"\n## {k}\n  master: {m}")
            for r, v in zip(runs, vals):
                print(f"  {r:8}: {'(unchanged)' if v == m else v}")
