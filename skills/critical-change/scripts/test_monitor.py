"""The monitor, with real commands that are harmless. Run: python3 -m unittest -v test_monitor.py"""
import contextlib
import io
import json
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import change
import monitor

ASSETS = Path(__file__).resolve().parent.parent / "assets"
CHECKS = [
    {"id": "H1", "label": "Up", "kind": "ping", "cmd": "true", "every": 2, "critical": True},
    {"id": "H2", "label": "Error rate", "kind": "chart", "cmd": "echo rate=0.4", "unit": "%", "max": 1, "every": 2, "critical": True},
    {"id": "S1", "label": "Old session works", "kind": "ping", "cmd": "echo fine", "on_demand": True, "critical": True},
    {"id": "S2", "label": "New login works", "kind": "ping", "cmd": "true", "on_demand": True, "critical": True},
    {"id": "S4", "label": "As fast as before", "kind": "ping", "cmd": "true", "on_demand": True, "critical": False},
]
SMOKE = CHECKS[2:]          # what the example plan gives to a script: S1, S2, S4


class MonitorTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        shutil.copy(ASSETS / "example.json", self.dir / "change.json")
        self.config = self.dir / "monitor.json"
        self.write(CHECKS)
        self.addCleanup(lambda: change.monitor_state_file(self.config).unlink() if change.monitor_state_file(self.config).exists() else None)

    def write(self, checks):
        self.config.write_text(json.dumps({"checks": checks}))

    def monitor(self, checks=None, demo=None):
        if checks:
            self.write(checks)
        cfg, errs = monitor.read_config(self.config)
        self.assertEqual(errs, [])
        return monitor.Monitor(cfg, self.config, demo)

    def run_all(self, m):
        for c in m.cfg["checks"]:
            m.run(c)

    def call(self, fn, *args):
        out, code = io.StringIO(), 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                fn(*args)
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                out.write(e.code if isinstance(e.code, str) else "")
        return code, out.getvalue()

    def test_shipped_examples_are_valid_configs(self):
        default, errs = monitor.read_config(ASSETS / "dashboard" / "monitor.example.json")
        self.assertEqual(errs, [])
        self.assertFalse(any(c.get("every") for c in default["checks"]), "the default runs nothing by itself")
        self.assertEqual(monitor.read_config(ASSETS / "dashboard" / "monitor.heartbeats.example.json")[1], [])

    def test_config_holes_are_named(self):
        self.write([{"id": "H1", "label": "Up", "kind": "ping", "cmd": "true", "critical": True},
                    {"id": "H2", "label": "Rate", "kind": "chart", "cmd": "x", "every": 1, "critical": "yes"},
                    {"id": "x", "label": "", "kind": "gauge"}])
        errs = "\n".join(monitor.read_config(self.config)[1])
        for needle in ("H1: give every", "H2: every must be 2 seconds or more", "H2: critical must be true or false",
                       "H2: a chart needs a unit", "H2: a chart needs min or max", "checks[2]: id must look like"):
            self.assertIn(needle, errs)

    def test_the_default_monitor_runs_nothing_until_asked(self):
        marker = self.dir / "ran"
        m = self.monitor([dict(SMOKE[0], cmd=f"touch '{marker}'"), *SMOKE[1:]])
        self.assertEqual(m.verdict(), ("ok", "Monitor up"))
        threading.Thread(target=m.loop, daemon=True).start()
        time.sleep(1)
        self.assertFalse(marker.exists())
        m.run(m.cfg["checks"][0])
        self.assertTrue(marker.exists())

    def test_demo_fail_breaks_the_first_critical_smoke_test(self):
        m = self.monitor(demo="fail")
        m.run(m.cfg["checks"][2])
        self.assertEqual(m.verdict(), ("bad", "STOP: critical check S1 is red"))

    def test_config_and_plan_must_agree_on_what_a_script_runs(self):
        s3 = {"id": "S3", "label": "Export sees sessions", "kind": "ping", "cmd": "true", "on_demand": True, "critical": False}
        self.write([CHECKS[0], SMOKE[0], SMOKE[1], s3])
        errs = "\n".join(monitor.read_config(self.config)[1])
        self.assertIn("S4: the plan says a script runs this smoke test, but it is not in the monitor config", errs)
        self.assertIn("S3: the monitor would run this smoke test, but the plan says the agent runs it", errs)

    def test_green_readings(self):
        m = self.monitor()
        self.assertEqual(m.verdict(), ("waiting", "Waiting for the first readings"))
        self.run_all(m)
        self.assertEqual(m.verdict(), ("ok", "All 2 live checks green"))
        self.assertEqual(m.state["H2"]["value"], 0.4)
        self.assertEqual(m.state["S1"]["text"], "fine")

    def test_a_number_past_its_limit_is_red_even_when_the_command_succeeds(self):
        checks = [dict(c) for c in CHECKS]
        checks[1]["cmd"] = "echo rate=3.2"
        m = self.monitor(checks)
        self.run_all(m)
        self.assertEqual(m.verdict(), ("bad", "STOP: critical check H2 is red"))
        self.assertTrue(any(e["level"] == "bad" and "H2" in e["text"] for e in m.events))

    def test_a_failing_command_and_a_missing_number_are_red(self):
        checks = [dict(c) for c in CHECKS]
        checks[0].update(cmd="false", critical=False)
        checks[1]["cmd"] = "echo no figure here"
        m = self.monitor(checks)
        self.run_all(m)
        self.assertEqual(m.state["H1"]["status"], "fail")
        self.assertIn("no number in the output", m.state["H2"]["text"])
        self.assertEqual(m.verdict()[0], "bad")

    def test_going_red_and_back_is_logged_once_each(self):
        flag = self.dir / "down"
        checks = [dict(c) for c in CHECKS]
        checks[0]["cmd"] = f"test ! -e '{flag}'"
        m = self.monitor(checks)
        m.run(checks[0]); m.run(checks[0])                 # green from the start: nothing worth a log line
        flag.write_text("")
        m.run(checks[0]); m.run(checks[0])
        flag.unlink()
        m.run(checks[0])
        texts = [e["text"] for e in m.events if "H1" in e["text"]]
        self.assertEqual(len(texts), 2)
        self.assertIn("went RED", texts[0])
        self.assertIn("is green again", texts[1])

    def test_snapshot_joins_the_change_and_marks_who_said_what(self):
        self.call(change.main, ["approve", str(self.dir / "change.json"), "plan", "--by", "Ada"])
        m = self.monitor()
        self.run_all(m)
        snap = m.snapshot()
        self.assertEqual(snap["change"]["title"], "Move login sessions to the managed Redis")
        self.assertEqual([s["state"] for s in snap["change"]["stages"]], ["done", "now", "todo", "todo", "todo"])
        self.assertEqual([(s["id"], s["owner"]) for s in snap["change"]["smoke"]],
                         [("S1", "the script"), ("S2", "the script"), ("S3", "the agent"), ("S4", "the script"), ("S5", "Ada")])
        self.assertEqual({e["source"] for e in snap["log"]}, {"monitor", "agent"})
        self.assertEqual(len(snap["checks"][1]["history"]), 1)

    def test_the_monitor_never_writes_to_the_change_document(self):
        before = (self.dir / "change.json").read_bytes()
        m = self.monitor()
        self.run_all(m)
        m.snapshot()
        self.assertEqual((self.dir / "change.json").read_bytes(), before)

    def test_demo_runs_no_command(self):
        marker = self.dir / "ran"
        checks = [dict(c) for c in CHECKS]
        checks[0]["cmd"] = f"touch '{marker}'"
        m = self.monitor(checks, demo="ok")
        self.run_all(m)
        self.assertFalse(marker.exists())
        self.assertTrue(m.snapshot()["demo"])

    def serve(self, m):
        server = ThreadingHTTPServer(("127.0.0.1", 0), monitor.handler(m))
        m.url = f"http://127.0.0.1:{server.server_address[1]}"
        threading.Thread(target=server.serve_forever, daemon=True).start()
        threading.Thread(target=m.loop, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        deadline = time.time() + 10
        while monitor.read_state(self.config) is None or m.verdict()[0] == "waiting":
            self.assertLess(time.time(), deadline, "the monitor never reported")
            time.sleep(0.2)
        time.sleep(2.2)                                    # one more state file write, now with the readings
        return m.url

    def test_served_page_status_and_run(self):
        url = self.serve(self.monitor())
        self.assertIn(b"<title>Change dashboard</title>", urllib.request.urlopen(url + "/").read())
        self.assertEqual(json.loads(urllib.request.urlopen(url + "/state").read())["verdict"]["state"], "ok")
        args = lambda **kw: type("A", (), {"config": str(self.config), **kw})()
        code, out = self.call(monitor.cmd_status, args())
        self.assertEqual(code, 0, out)
        self.assertIn("All 2 live checks green. Waiting for the script, on your word: S1, S2, S4.", out)
        code, out = self.call(monitor.cmd_run, args(ids=["S1"]))
        self.assertEqual((code, out.strip()), (0, "S1 passed."))
        code, out = self.call(monitor.cmd_run, args(ids=[]))             # no ID: everything on demand
        self.assertEqual((code, out.strip()), (0, "S1 passed, S2 passed, S4 passed."))
        code, out = self.call(monitor.cmd_run, args(ids=["S9"]))
        self.assertIn("no check S9", out)

    def post(self, url, path, body, header=True):
        req = urllib.request.Request(url + path, data=json.dumps(body).encode(), method="POST",
                                     headers={"X-Change-Dashboard": "1"} if header else {})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    def test_a_person_gives_their_verdict_on_the_dashboard(self):
        m = self.monitor()
        url = self.serve(m)
        self.assertEqual(self.post(url, "/verdict", {"id": "S5", "result": "pass"})[0], 200)
        row = next(s for s in m.snapshot()["change"]["smoke"] if s["id"] == "S5")
        self.assertEqual((row["by"], row["owner"], row["marked"], row["recorded"]), ("human", "Ada", "pass", None))
        self.assertTrue(any(e["source"] == "human" and "Ada marked S5 passed" in e["text"] for e in m.events))
        time.sleep(2.2)
        self.assertIn("Ada marked S5 passed on the dashboard: record it.", self.call(monitor.cmd_status, type("A", (), {"config": str(self.config)})())[1])
        self.assertEqual(self.post(url, "/verdict", {"id": "S5", "result": "fail"})[0], 200)          # they may change their mind
        self.assertEqual(m.human["S5"]["result"], "fail")
        self.assertIn("not a smoke test a person runs", self.post(url, "/verdict", {"id": "S1", "result": "pass"})[1]["error"])
        self.assertIn("pass or fail", self.post(url, "/verdict", {"id": "S5", "result": "maybe"})[1]["error"])

    def test_the_document_speaks_once_the_agent_has_recorded_it(self):
        m = self.monitor()
        self.assertIsNone(m.mark("S5", "fail"))
        d = json.loads((self.dir / "change.json").read_text())
        d["smoke"][4]["status"] = "pass"                    # the agent recorded what the person then said in the conversation
        (self.dir / "change.json").write_text(json.dumps(d))
        row = next(s for s in m.snapshot()["change"]["smoke"] if s["id"] == "S5")
        self.assertEqual((row["recorded"], row["marked"]), ("pass", None))
        self.assertIn("already recorded", m.mark("S5", "fail"))

    def test_a_critical_test_failed_by_a_person_is_a_stop(self):
        d = json.loads((self.dir / "change.json").read_text())
        d["smoke"][4]["critical"] = True
        (self.dir / "change.json").write_text(json.dumps(d))
        m = self.monitor()
        m.mark("S5", "fail")
        self.assertEqual(m.verdict(), ("bad", "STOP: critical check S5 is red"))

    def test_another_site_cannot_start_a_check_or_give_a_verdict(self):
        url = self.serve(self.monitor())
        self.assertEqual(self.post(url, "/run", ["S1"], header=False)[0], 403)
        self.assertEqual(self.post(url, "/verdict", {"id": "S5", "result": "pass"}, header=False)[0], 403)

    def test_status_without_a_monitor_says_so(self):
        code, out = self.call(monitor.cmd_status, type("A", (), {"config": str(self.config)})())
        self.assertEqual(code, 1)
        self.assertIn("not running", out)

    def test_first_step_waits_for_a_real_green_monitor(self):
        doc = str(self.dir / "change.json")
        for args in (["approve", doc, "plan", "--by", "Ada"], ["set", doc, "P1", "done", "P2", "done", "P3", "done", "P4", "done"]):
            self.call(change.main, args)
        d = json.loads(Path(doc).read_text())
        d["unknowns"][1]["accepted_by"] = "Ada"
        Path(doc).write_text(json.dumps(d))
        self.call(change.main, ["approve", doc, "execute", "--by", "Ada"])
        code, out = self.call(change.main, ["set", doc, "E1", "done"])
        self.assertIn("the monitor is not running", out)
        state = change.monitor_state_file(self.config)
        state.write_text(json.dumps({"updated": time.time(), "state": "ok", "text": "All 2 live checks green", "demo": True}))
        self.assertIn("demo mode", self.call(change.main, ["set", doc, "E1", "done"])[1])
        state.write_text(json.dumps({"updated": time.time(), "state": "bad", "text": "STOP: critical check H2 is red"}))
        self.assertIn("not green before the first step", self.call(change.main, ["set", doc, "E1", "done"])[1])
        state.write_text(json.dumps({"updated": time.time(), "state": "ok", "text": "All 2 live checks green"}))
        code, out = self.call(change.main, ["set", doc, "E1", "done"])
        self.assertEqual(code, 0, out)
        state.unlink()                                     # later steps are recorded even if the monitor has died
        self.assertEqual(self.call(change.main, ["set", doc, "E2", "done"])[0], 0)


if __name__ == "__main__":
    unittest.main()
