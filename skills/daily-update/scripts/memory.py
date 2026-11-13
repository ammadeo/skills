#!/usr/bin/env python3
"""memory.py: remember the updates channel the user confirmed for a project.

Usage:
  python3 -I memory.py get --repo OWNER/REPO...
  python3 -I memory.py set --project NAME --repo OWNER/REPO... \
                           --channel-id ID --channel-name '#name'

get   prints the remembered project (name, repos, channel, confirmed date) as
      JSON when any given repo belongs to it; exits 1 with nothing printed
      when there is no match.
set   stores the channel for that project, matched by any shared repo, and
      merges the repo lists. Run it only after the user explicitly confirmed
      sending to that channel. Prints the old channel when it replaced one.

File: $DAILY_UPDATE_MEMORY, else ${XDG_CONFIG_HOME:-~/.config}/daily-update/projects.json
"""
import argparse
import datetime
import json
import os
import sys


def path():
    if os.environ.get("DAILY_UPDATE_MEMORY"):
        return os.environ["DAILY_UPDATE_MEMORY"]
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "daily-update", "projects.json")


def load():
    try:
        with open(path(), encoding="utf-8") as f:
            return json.load(f).get("projects", [])
    except FileNotFoundError:
        return []
    except (OSError, ValueError) as e:
        sys.exit(f"cannot read {path()}: {e}")


def norm(repos):
    return sorted({r.strip().lower() for r in repos if r.strip()})


def find(projects, repos):
    want = set(norm(repos))
    return next((p for p in projects if want & set(p["repos"])), None)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=["get", "set"])
    ap.add_argument("--repo", action="append", default=[], required=True)
    ap.add_argument("--project")
    ap.add_argument("--channel-id")
    ap.add_argument("--channel-name")
    a = ap.parse_args()
    projects = load()
    hit = find(projects, a.repo)

    if a.action == "get":
        if not hit:
            sys.exit(1)
        print(json.dumps(hit, ensure_ascii=False))
        return

    if not (a.project and a.channel_id and a.channel_name):
        ap.error("set needs --project, --channel-id and --channel-name")
    channel = {"id": a.channel_id.strip(), "name": "#" + a.channel_name.strip().lstrip("#")}
    today = datetime.date.today().isoformat()
    if hit:
        old = hit["channel"]
        hit.update(project=a.project.strip(), repos=norm(hit["repos"] + a.repo),
                   channel=channel, confirmed=today)
        if old["id"] != channel["id"]:
            print(f"replaced {old['name']} ({old['id']})")
    else:
        projects.append(dict(project=a.project.strip(), repos=norm(a.repo),
                             channel=channel, confirmed=today))
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"projects": projects}, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, p)
    print(f"remembered {channel['name']} ({channel['id']}) for {a.project.strip()} in {p}")


if __name__ == "__main__":
    main()
