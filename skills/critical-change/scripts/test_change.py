"""Gates of change.py, walked on the example change. Run: python3 -m unittest -v test_change.py"""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import change

EXAMPLE = Path(__file__).resolve().parent.parent / "assets" / "example.json"


class Lifecycle(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.dir)
        self.file = self.dir / "change.json"
        shutil.copy(EXAMPLE, self.file)

    def run_cmd(self, *args):
        """Returns (exit code, output)."""
        out = io.StringIO()
        code = 0
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                change.main([args[0], str(self.file), *args[1:]])
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                if isinstance(e.code, str):
                    out.write(e.code)
        return code, out.getvalue()

    def edit(self, fn):
        doc = json.loads(self.file.read_text())
        fn(doc)
        self.file.write_text(json.dumps(doc))

    def ok(self, *args):
        code, out = self.run_cmd(*args)
        self.assertEqual(code, 0, out)
        return out

    def refused(self, *args):
        code, out = self.run_cmd(*args)
        self.assertEqual(code, 1, out)
        return out

    def to_prepared(self):
        self.ok("approve", "plan", "--by", "Ada")
        for p in ("P1", "P2", "P3", "P4"):
            self.ok("set", p, "done")
        self.edit(lambda d: d["unknowns"][1].update(accepted_by="Ada"))

    def to_executed(self):
        self.to_prepared()
        self.ok("approve", "execute", "--by", "Ada")
        for s in ("E1", "E2", "E3"):
            self.ok("set", s, "done")

    def test_example_is_a_complete_plan_with_a_loud_unknown(self):
        out = self.ok("check")
        self.assertIn("Stage: Plan", out)
        self.assertIn("U2 (NOT ACCEPTED)", out)
        self.ok("render")
        page = self.file.with_suffix(".html").read_text()
        self.assertIn("Risks without mitigation", page)
        self.assertIn("What an admin can do to close it", page)
        self.assertIn("<svg", page)
        self.assertTrue(page.isascii())

    def test_holes_in_the_plan_stop_the_render(self):
        def holes(d):
            d["smoke"][0]["mitigates"] = []
            d["smoke"][1]["why"] = ""
            d["unknowns"][1]["admin_guide"] = []
            d["steps"][0]["revert"] = ""
            d["risks"][0]["mitigation"] = ""
        self.edit(holes)
        out = self.refused("render")
        for needle in ("S1: mitigates must name", "S2: why is missing", "U2: admin_guide is missing",
                       "E1: say how to revert", "R1: mitigation is missing"):
            self.assertIn(needle, out)
        self.assertFalse(self.file.with_suffix(".html").exists())

    def test_smoke_check_for_an_unknown_risk_is_refused(self):
        self.edit(lambda d: d["smoke"][0].update(mitigates=["R9"]))
        self.assertIn("mitigates R9", self.refused("check"))

    def test_no_critical_smoke_check_is_refused(self):
        self.edit(lambda d: [s.update(critical=False) for s in d["smoke"]])
        self.assertIn("nothing would trigger the reversal", self.refused("check"))

    def test_irreversible_without_replacement_is_loud(self):
        self.edit(lambda d: d["reversal"].update(possible=False, steps=[]))
        self.assertIn("reversal (NOT ACCEPTED)", self.ok("check"))
        self.edit(lambda d: d["reversal"].update(instead="Restore from the snapshot rehearsed on staging"))
        self.assertNotIn("reversal (NOT ACCEPTED)", self.ok("check"))

    def test_nothing_is_prepared_before_the_plan_is_approved(self):
        self.assertIn("has not approved the plan", self.refused("set", "P1", "done"))

    def test_open_decision_blocks_plan_approval(self):
        self.edit(lambda d: d["decisions"][0].update(status="open"))
        self.assertIn("decision still open", self.refused("approve", "plan", "--by", "Ada"))

    def test_final_approval_needs_prep_done_and_loud_risks_accepted(self):
        self.ok("approve", "plan", "--by", "Ada")
        out = self.refused("approve", "execute", "--by", "Ada")
        self.assertIn("P1 not ready", out)
        self.assertIn("U2 has no mitigation and nobody accepted it", out)

    def test_failing_baseline_blocks_execution(self):
        self.to_prepared()
        self.ok("set", "S1", "fail", "--baseline")
        self.assertIn("fails on the system as it is today", self.refused("approve", "execute", "--by", "Ada"))

    def test_steps_need_the_final_approval_and_run_in_order(self):
        self.to_prepared()
        self.assertIn("final approval", self.refused("set", "E1", "done"))
        self.ok("approve", "execute", "--by", "Ada")
        self.assertIn("in order", self.refused("set", "E2", "done"))
        self.ok("set", "E1", "done")

    def test_changing_a_step_voids_the_final_approval(self):
        self.to_prepared()
        self.ok("approve", "execute", "--by", "Ada")
        self.edit(lambda d: d["steps"][0].update(details="something else"))
        self.assertIn("changed after the final approval", self.refused("set", "E1", "done"))

    def test_smoke_result_before_the_change_must_be_a_baseline(self):
        self.to_prepared()
        self.assertIn("--baseline", self.refused("set", "S1", "pass"))
        self.ok("set", "S1", "pass", "--baseline")

    def test_completed_needs_every_smoke_check_in(self):
        self.to_executed()
        self.assertIn("S1 has not run", self.refused("finish", "completed"))
        for s in ("S1", "S2", "S3", "S5"):
            self.ok("set", s, "pass")
        self.ok("set", "S4", "fail", "--note", "p95 up 30%")
        out = self.ok("finish", "completed")
        self.assertIn("Completed.", out)
        self.assertIn("Non-critical smoke tests that failed", out)

    def test_critical_smoke_failure_calls_for_the_reversal(self):
        self.to_executed()
        out = self.ok("set", "S1", "fail")
        self.assertIn("Run the reversal path now", out)
        self.assertIn("V1", out)
        self.assertIn("S1 is critical and failed", self.refused("finish", "completed"))
        self.assertIn("Reversal steps left", self.refused("finish", "reverted"))
        self.ok("set", "V1", "done")
        self.ok("set", "V2", "done")
        self.assertIn("Stage: Reverted", self.ok("finish", "reverted", "--note", "S1 failed"))
        self.assertIn(">Reverted<", self.file.with_suffix(".html").read_text())

    def test_failed_step_calls_for_the_reversal(self):
        self.to_prepared()
        self.ok("approve", "execute", "--by", "Ada")
        self.assertIn("A step failed", self.ok("set", "E1", "failed"))


if __name__ == "__main__":
    unittest.main()
