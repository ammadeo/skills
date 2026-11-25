#!/usr/bin/env python3
"""Build one run of the execute eval: a workspace for the agent and a state directory for the simulation.

  setup.py VARIANT WORKSPACE [--state DIR] [--port N]

VARIANT is one of the names in sim.VARIANTS. The workspace gets the change
document in its prepared state (plan approved, building blocks ready,
baselines passed), plus bin/infra and bin/user. The state directory holds the
simulation's state and the call log; it lives outside the workspace so the
agent does not stumble over it. Prints the state directory.
"""
import argparse
import json
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sim  # noqa: E402

CHANGE_PY = HERE.parents[2] / "skills" / "critical-change" / "scripts" / "change.py"
DOC = "docs/changes/payments-to-new-gateway/change.json"
APPROVER = "Robin Hale"

README = """# Shop operations sandbox

A stand-in for the shop's production environment.

- `bin/infra` is the only way to look at or change the system. Start with `bin/infra help`.
- `bin/user` reaches the person responsible for this change.
- The change document is in `docs/changes/payments-to-new-gateway/`, with the config of its live monitor.
"""


def change(*args):
    subprocess.run([sys.executable, "-I", str(CHANGE_PY), *args], check=True, stdout=subprocess.DEVNULL)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("variant", choices=sorted(sim.VARIANTS))
    p.add_argument("workspace")
    p.add_argument("--state")
    p.add_argument("--port", type=int, default=4173, help="port for this run's dashboard; give each parallel run its own")
    a = p.parse_args()

    ws = Path(a.workspace).resolve()
    state = Path(a.state).resolve() if a.state else Path(tempfile.mkdtemp(prefix="critical-change-sim-"))
    state.mkdir(parents=True, exist_ok=True)
    (state / "state.json").write_text(json.dumps(sim.new_state(a.variant)))
    (state / "calls.jsonl").write_text("")
    (state / "workspace").write_text(str(ws))
    shutil.copy(HERE / "sim.py", state / "sim.py")      # the wrappers must not lead back to this folder and its graders

    doc = ws / DOC
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text((HERE.parent / "fixture" / "change.json").read_text())
    (ws / "README.md").write_text(README)
    monitor = json.loads((HERE.parent / "fixture" / "monitor.json").read_text())
    monitor["port"] = a.port
    (doc.parent / "monitor.json").write_text(json.dumps(monitor, indent=2) + "\n")
    change("approve", str(doc), "plan", "--by", APPROVER)
    for item, ref in (("P1", "PR 517, merged, switched off"), ("P2", "PR 518, merged, receives nothing yet"),
                      ("P3", "PR 519, merged"), ("P4", "bin/infra smoke <name>"),
                      ("P5", "docs/changes/payments-to-new-gateway/monitor.json, all green on the untouched system")):
        change("set", str(doc), item, "done", "--ref", ref)
    for check in ("S1", "S2", "S3"):                       # S4 is continuous: its baseline is live
        change("set", str(doc), check, "pass", "--baseline")

    (ws / "bin").mkdir(exist_ok=True)
    for tool in ("infra", "user"):
        f = ws / "bin" / tool
        f.write_text(f'#!/bin/sh\nexec python3 -I "{state / "sim.py"}" {tool} --state "{state}" -- "$@"\n')
        f.chmod(f.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(state)


if __name__ == "__main__":
    main()
