#!/usr/bin/env python3
"""Live monitor and dashboard for the execute phase of the critical-change skill.

  monitor.py check  CONFIG                       validate the config as text; nothing runs
  monitor.py serve  CONFIG [--port N] [--demo [ok|fail]]
                                                 run the checks and serve the dashboard
  monitor.py status CONFIG                       one line; exit 1 if the monitor is down or a critical check is red
  monitor.py run    CONFIG ID [ID ...]           have the running monitor run on-demand checks now

CONFIG is monitor.json, next to change.json. The monitor only watches: it runs
the checks, shows them, and never writes to the change document. The page is
assets/dashboard/index.html, served as it is. --demo runs no command at all
and draws invented readings, to look at the page.
"""
import argparse
import copy
import json
import math
import os
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import change  # noqa: E402

PAGE = HERE.parent / "assets" / "dashboard" / "index.html"
STALE = 15          # seconds without a state file update before the monitor counts as down
DEMO_SMOKE = 36     # seconds into --demo at which the first on-demand check runs by itself


def read_config(path):
    """Returns (config, errors). Nothing is executed."""
    try:
        cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return {}, [f"cannot read {path}: {err}"]
    e, seen = [], set()
    checks = cfg.get("checks")
    if not isinstance(checks, list) or not checks:
        return cfg, ["checks: list at least one check"]
    for i, c in enumerate(checks):
        id_ = c.get("id") if isinstance(c, dict) else None
        if not isinstance(id_, str) or not re.fullmatch(r"[A-Z]\d+", id_):
            e.append(f"checks[{i}]: id must look like H1 or S1")
            continue
        if id_ in seen:
            e.append(f"{id_}: duplicate id")
        seen.add(id_)
        for key in ("label", "cmd"):
            if not isinstance(c.get(key), str) or not c[key].strip():
                e.append(f"{id_}: {key} is missing")
        if c.get("kind") not in ("ping", "chart"):
            e.append(f"{id_}: kind must be ping (passes or fails) or chart (a number over time)")
        if not isinstance(c.get("critical"), bool):
            e.append(f"{id_}: critical must be true or false")
        live, demand = c.get("every"), c.get("on_demand") is True
        if (live is None) == (not demand):
            e.append(f"{id_}: give every (seconds) for a check that loops, or on_demand: true for one that runs when asked")
        elif live is not None and (not isinstance(live, (int, float)) or live < 2):
            e.append(f"{id_}: every must be 2 seconds or more")
        if c.get("kind") == "chart":
            if demand:
                e.append(f"{id_}: a chart needs readings over time, so it cannot be on_demand")
            if not isinstance(c.get("unit"), str):
                e.append(f"{id_}: a chart needs a unit")
            if not any(isinstance(c.get(k), (int, float)) for k in ("min", "max")):
                e.append(f"{id_}: a chart needs min or max, the limit that turns it red")
    if not (Path(path).resolve().parent / cfg.get("change", "change.json")).exists():
        e.append(f"change: {cfg.get('change', 'change.json')} not found next to the config")
    return cfg, e


def demo_reading(c, t, scenario, started):
    """An invented reading for --demo. Smooth, inside the limits, and for 'fail' one critical chart breaks after 20 s."""
    seed = sum(map(ord, c["id"]))
    wave = math.sin(t / 6 + seed) * 0.6 + math.sin(t / 1.7 + seed * 3) * 0.4
    if c["kind"] == "ping":
        return True, None, "answered in %d ms" % (60 + 25 * (1 + wave))
    if "max" in c:
        value = c["max"] * (0.36 + 0.13 * wave)
        if scenario == "fail" and c.get("critical") and t - started > 20:
            value = c["max"] * (1.9 + 0.2 * wave)
    else:
        value = c["min"] * (1.3 + 0.06 * wave)
    return None, round(value, 2 if value < 10 else 0), ""


class Monitor:
    def __init__(self, cfg, path, demo=None):
        self.cfg, self.path, self.demo = cfg, Path(path).resolve(), demo
        self.change_file = self.path.parent / cfg.get("change", "change.json")
        try:                                   # commands run from "cwd" in the config, else from where serve was started
            self.cwd = (self.path.parent / cfg["cwd"]).resolve() if cfg.get("cwd") else Path.cwd()
        except OSError:
            self.cwd = self.path.parent
        self.started = time.time()
        self.lock = threading.Lock()
        self.events = deque(maxlen=300)
        self.state = {c["id"]: {"status": "waiting", "running": False, "value": None, "text": "", "at": None,
                                "last_start": 0, "history": deque(maxlen=60)} for c in cfg["checks"]}
        self.url = ""
        self.event("info", f"Monitor started with {len(cfg['checks'])} checks" + (" (demo: invented readings)" if demo else ""))

    def event(self, level, text, source="monitor"):
        self.events.append({"at": time.time(), "source": source, "level": level, "text": text})

    def limit(self, c):
        return " and ".join(f"{k} {c[k]} {c.get('unit', '')}".strip() for k in ("min", "max") if k in c)

    def run(self, c, by="monitor"):
        st = self.state[c["id"]]
        with self.lock:
            if st["running"]:
                return st
            st["running"], st["last_start"] = True, time.time()
        t0 = time.time()
        ok, value, text = None, None, ""
        if self.demo:
            time.sleep(0.25)
            ok, value, text = demo_reading(c, t0, self.demo, self.started)
            critical = [x["id"] for x in self.cfg["checks"] if x.get("on_demand") and x.get("critical")]
            if self.demo == "fail" and critical[:1] == [c["id"]]:
                ok, text = False, "made to fail by the demo"
        else:
            try:
                p = subprocess.run(c["cmd"], shell=True, cwd=str(self.cwd), capture_output=True, text=True, timeout=c.get("timeout", 20))
                out = (p.stdout.strip() or p.stderr.strip())
                ok, text = p.returncode == 0, (out.splitlines() or [""])[-1][:200]
                if c["kind"] == "chart":
                    m = re.search(c.get("value") or r"(-?\d+(?:\.\d+)?)", out)
                    value = float(m.group(1)) if m else None
                    if value is None:
                        ok, text = False, "no number in the output: " + text
            except subprocess.TimeoutExpired:
                ok, text = False, f"no answer within {c.get('timeout', 20)} s"
        if c["kind"] == "chart" and value is not None:
            inside = ("min" not in c or value >= c["min"]) and ("max" not in c or value <= c["max"])
            ok = inside if ok is None else ok and inside
        status = "ok" if ok else "fail"
        shown = f"{value:g} {c.get('unit', '')}".strip() if value is not None else text
        with self.lock:
            was = st["status"]
            st.update(status=status, running=False, value=value, text=text, at=time.time())
            st["history"].append([round(st["at"], 1), value if c["kind"] == "chart" else (1 if ok else 0)])
            name = f"{c['id']} {c['label']}"
            if c.get("on_demand"):
                self.event("ok" if ok else "bad", f"{name}: passed" if ok else f"{name}: FAILED" + (f". {shown}" if shown else ""))
            elif was == "waiting":
                if not ok:
                    self.event("bad", f"{name}: RED on its first reading" + (f", {shown}" if shown else ""))
            elif was != status:
                limit = f" (limit: {self.limit(c)})" if c["kind"] == "chart" else ""
                self.event("ok" if ok else "bad", f"{name} {'is green again' if ok else 'went RED'}: {shown}{limit}")
        return st

    def verdict(self):
        live = [c for c in self.cfg["checks"] if c.get("every")]
        red = [c for c in self.cfg["checks"] if self.state[c["id"]]["status"] == "fail"]
        crit = [c["id"] for c in red if c.get("critical")]
        if crit:
            return "bad", f"STOP: critical check {', '.join(crit)} is red"
        if red:
            return "warn", f"{', '.join(c['id'] for c in red)} red, not critical"
        if any(self.state[c["id"]]["status"] == "waiting" for c in live):
            return "waiting", "Waiting for the first readings"
        return "ok", f"All {len(live)} live checks green" if live else "Monitor up"

    def loop(self):
        last_write = 0
        while True:
            now = time.time()
            for c in self.cfg["checks"]:
                st = self.state[c["id"]]
                if c.get("every") and not st["running"] and now - st["last_start"] >= c["every"]:
                    threading.Thread(target=self.run, args=(c,), daemon=True).start()
            if self.demo:                                   # on-demand checks play themselves, 12 s apart, last one never
                waiting = [c for c in self.cfg["checks"] if c.get("on_demand")][:-1]
                for i, c in enumerate(waiting):
                    st = self.state[c["id"]]
                    if st["status"] == "waiting" and not st["running"] and now - self.started >= DEMO_SMOKE + 12 * i:
                        threading.Thread(target=self.run, args=(c,), daemon=True).start()
            if now - last_write >= 2:
                last_write = now
                state, text = self.verdict()
                idle = [c["id"] for c in self.cfg["checks"] if c.get("on_demand") and self.state[c["id"]]["status"] == "waiting"]
                tmp = change.monitor_state_file(self.path).with_suffix(".tmp")
                tmp.write_text(json.dumps({"updated": now, "url": self.url, "pid": os.getpid(), "state": state, "text": text,
                                           "not_run": idle, "demo": bool(self.demo)}))
                tmp.replace(change.monitor_state_file(self.path))
            time.sleep(0.25)

    def change_view(self):
        try:
            doc = json.loads(self.change_file.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            return {"title": "Change document unreadable", "line": str(err), "stages": [], "smoke": []}, []
        if self.demo:
            doc = demo_change(doc, self.started)
        log = []
        for x in change.rows(doc, "log"):
            try:
                at = datetime.strptime(str(x.get("at")), "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc).timestamp()
            except ValueError:
                continue
            log.append({"at": at, "source": "agent", "level": "bad" if re.search(r"\b(fail|failed|reverted)\b", str(x.get("event"))) else "info",
                        "text": str(x.get("event"))})
        return {"title": doc.get("title", ""), "line": change.brief(doc),
                "stages": [{"name": n, "state": s} for n, s in change.stage_states(doc)],
                "smoke": [{"id": s.get("id"), "check": s.get("check", ""), "critical": bool(s.get("critical")), "manual": bool(s.get("manual")),
                           "recorded": s.get("status") if s.get("status") in ("pass", "fail") else None} for s in change.rows(doc, "smoke")]}, log

    def snapshot(self):
        view, agent_log = self.change_view()
        state, text = self.verdict()
        with self.lock:
            checks = [{**{k: c.get(k) for k in ("id", "label", "kind", "unit", "min", "max", "critical", "every")},
                       **{k: self.state[c["id"]][k] for k in ("status", "running", "value", "text", "at")},
                       "history": list(self.state[c["id"]]["history"])} for c in self.cfg["checks"]]
            log = sorted(list(self.events) + agent_log, key=lambda x: x["at"])[-120:]
        return {"now": time.time(), "started": self.started, "demo": bool(self.demo), "change": view,
                "verdict": {"state": state, "text": text}, "checks": checks, "log": log}


def demo_change(doc, started):
    """For --demo only: show the example change as if it were being executed. Nothing is written."""
    doc = copy.deepcopy(doc)
    stamp = lambda ago: datetime.fromtimestamp(started - ago, timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    for x in change.rows(doc, "prep"):
        x["status"] = "done"
    for x in change.rows(doc, "unknowns"):
        x.setdefault("accepted_by", "Ada") if x.get("status") == "open" else None
    steps, smoke, elapsed = change.rows(doc, "steps"), change.rows(doc, "smoke"), time.time() - started
    doc["approvals"] = {"plan": {"by": "Ada"}, "execute": {"by": "Ada", "hash": change.plan_hash(doc)}}
    doc["log"] = [{"at": stamp(95), "event": "execute approved by Ada"}]
    for i, s in enumerate(steps):                      # first step done before the start, one more every 15 s
        if elapsed >= 15 * i:
            s["status"] = "done"
            doc["log"].append({"at": stamp(40 - 55 * min(i, 1) - 15 * max(i - 1, 0)), "event": f"{s.get('id')} done"})
    if smoke and elapsed >= DEMO_SMOKE + 8:
        smoke[0]["status"] = "pass"
        doc["log"].append({"at": started + DEMO_SMOKE + 8, "event": f"{smoke[0].get('id')} pass"})
    for x in doc["log"]:
        if not isinstance(x["at"], str):
            x["at"] = datetime.fromtimestamp(x["at"], timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return doc


def handler(mon):
    class H(BaseHTTPRequestHandler):
        def send(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind + "; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path in ("/", "/index.html"):
                self.send(200, PAGE.read_bytes(), "text/html")
            elif self.path == "/state":
                self.send(200, mon.snapshot())
            else:
                self.send(404, {"error": "not found"})

        def do_POST(self):
            if not self.path.startswith("/run"):
                return self.send(404, {"error": "not found"})
            ids = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"[]")
            by_id = {c["id"]: c for c in mon.cfg["checks"]}
            unknown = [i for i in ids if i not in by_id]
            if unknown:
                return self.send(400, {"error": f"no check {', '.join(unknown)} in this monitor"})
            mon.event("info", f"Asked the monitor to run {', '.join(ids)}", source="agent")
            out = []
            for i in ids:
                st = mon.run(by_id[i], by="agent")
                out.append({"id": i, "label": by_id[i]["label"], "critical": by_id[i].get("critical"), "status": st["status"], "text": st["text"]})
            self.send(200, out)

        def log_message(self, *args):
            pass
    return H


def need_config(path):
    cfg, errs = read_config(path)
    if errs:
        print("The monitor config has holes:")
        for x in errs:
            print(f"  - {x}")
        sys.exit(1)
    return cfg


def cmd_check(a):
    cfg = need_config(a.config)
    live = [c["id"] for c in cfg["checks"] if c.get("every")]
    demand = [c["id"] for c in cfg["checks"] if c.get("on_demand")]
    print("Config is complete. " + (f"Live: {', '.join(live)}. " if live else "No live checks. ")
          + (f"On demand: {', '.join(demand)}." if demand else "Nothing on demand."))


def cmd_serve(a):
    cfg = need_config(a.config)
    mon = Monitor(cfg, a.config, a.demo)
    port = a.port or cfg.get("port") or 4173
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), handler(mon))
    except OSError as err:
        sys.exit(f"error: cannot listen on port {port}: {err}. Pass --port with a free one.")
    mon.url = f"http://127.0.0.1:{port}"
    threading.Thread(target=mon.loop, daemon=True).start()
    print(f"Dashboard: {mon.url}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def read_state(config):
    try:
        st = json.loads(change.monitor_state_file(config).read_text())
    except (OSError, ValueError):
        return None
    return st if time.time() - st.get("updated", 0) <= STALE else None


def cmd_status(a):
    st = read_state(a.config)
    if not st:
        print("The monitor is not running: no signal. Start it with: monitor.py serve CONFIG")
        sys.exit(1)
    idle = f" On demand, not run yet: {', '.join(st['not_run'])}." if st.get("not_run") else ""
    print(f"{st['text']}.{idle} Dashboard: {st['url']}" + (" (demo)" if st.get("demo") else ""))
    sys.exit(1 if st["state"] == "bad" else 0)


def cmd_run(a):
    st = read_state(a.config)
    if not st:
        print("The monitor is not running, so nothing was run. Start it with: monitor.py serve CONFIG")
        sys.exit(1)
    req = urllib.request.Request(st["url"] + "/run", data=json.dumps(a.ids).encode(), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            results = json.loads(r.read())
    except urllib.error.HTTPError as err:
        sys.exit("error: " + json.loads(err.read()).get("error", str(err)))
    except OSError as err:
        sys.exit(f"error: the monitor did not answer: {err}")
    bad = [x for x in results if x["status"] != "ok"]
    print(", ".join(f"{x['id']} {'passed' if x['status'] == 'ok' else 'FAILED'}" for x in results) + ".")
    for x in bad:
        print(f"  - {x['id']} {x['label']}{' (critical)' if x['critical'] else ''}: {x['text']}")
    sys.exit(1 if any(x["critical"] for x in bad) else 0)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check"); c.add_argument("config"); c.set_defaults(fn=cmd_check)
    c = sub.add_parser("serve"); c.add_argument("config"); c.add_argument("--port", type=int)
    c.add_argument("--demo", nargs="?", const="ok", choices=("ok", "fail")); c.set_defaults(fn=cmd_serve)
    c = sub.add_parser("status"); c.add_argument("config"); c.set_defaults(fn=cmd_status)
    c = sub.add_parser("run"); c.add_argument("config"); c.add_argument("ids", nargs="+"); c.set_defaults(fn=cmd_run)
    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
