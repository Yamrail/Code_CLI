"""Adversarial local checks for actual retained guard/ledger behavior."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))
sys.dont_write_bytecode = True
from adapters.native_host import read_native_state, supervise_stage
from native_runtime.core import load_native, sha


class NativeRuntimeTests(unittest.TestCase):
    def test_actual_counterexamples_and_optional_sponsor_boundary(self):
        from adapters.demo import run_demo
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "demo"
            result = run_demo(out)
            self.assertTrue(all(result["checks"].values()))
            self.assertEqual(result["final_native_state"]["pending"]["B1"]["state"], "UNKNOWN_COMPLETION")
            self.assertTrue(any(h["state"] in {"HOLD", "UNKNOWN"} and "INTENT_ROOT:ROOT_B" in h["scope"]
                                for h in result["final_native_state"]["holds"].values()))
            self.assertEqual(result["sponsors"]["real_provider_calls"], 0)
            self.assertFalse(result["captured_model_execution_replayed"])
            self.assertFalse(result["coding_task"]["result"]["current_model_generation"])
            crash = next(step for step in result["steps"] if step["action"] == "crash")
            self.assertEqual(crash["process"]["exit_code"], 23)
            self.assertFalse(crash["process"]["timed_out"])
            self.assertIn(result["world_model"]["state"], {"PASS_LOCAL_UPSTREAM_ENGINE", "HOLD_OPTIONAL_NODE_RUNTIME"})
            self.assertTrue((out / "REPORT.html").is_file())
            self.assertTrue((out / "DEPENDENCY_GRAPH.md").is_file())

    def test_host_runner_once_stage_done_and_hold_payload_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            count = []
            def runner(stage):
                count.append(stage)
                (stage / "fixture.txt").write_text("safe fixture", encoding="utf-8")
                return {"state": "HOLD_DOMAIN_SOURCE_UNVERIFIED", "authority_effect": "NONE"}
            out = Path(directory) / "run"
            result = supervise_stage(out, "OFFLINE_RENDER", runner)
            self.assertEqual(len(count), 1)
            self.assertEqual(result["state"], "PASS_NATIVE_HOST_STAGE")
            self.assertEqual(result["result"]["state"], "HOLD_DOMAIN_SOURCE_UNVERIFIED")
            self.assertEqual(result["domain_hold_closure"], "NOT_INFERRED")
            readback = read_native_state(out)
            self.assertEqual(readback["snapshot"]["stages"]["OFFLINE_RENDER"]["state"], "DONE")
            self.assertFalse(readback["snapshot"]["active"])
            self.assertFalse(readback["execution_authority_granted_by_readback"])
            self.assertEqual(readback["snapshot"]["root_buckets"]["LOCAL_TOOL"]["attempts_used"], 1)
            self.assertFalse(supervise_stage(out, "OFFLINE_RENDER", runner)["runner_invoked"])
            self.assertEqual(len(count), 1)

    def test_unknown_runner_is_not_retried_or_silently_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            calls = []
            def fails(stage):
                calls.append(stage)
                (stage / "before_failure.txt").write_text("effect may have started", encoding="utf-8")
                raise RuntimeError("controlled host failure")
            out = Path(directory) / "failed"
            result = supervise_stage(out, "UNKNOWN_TEST", fails, root_purpose="FAILED_LOCAL_TOOL")
            self.assertEqual(result["state"], "HOLD_NATIVE_RUNNER_OUTCOME_UNKNOWN")
            state = read_native_state(out)["snapshot"]
            self.assertEqual(state["pending"]["LOCAL_1"]["state"], "UNKNOWN_COMPLETION")
            self.assertEqual(state["stages"]["UNKNOWN_TEST"]["state"], "STOPPED")
            self.assertIn("RUNNER_OUTCOME_UNKNOWN", state["holds"])
            self.assertTrue(result["controlled_stop_resume"]["unresolved_pending_preserved"])
            self.assertFalse(supervise_stage(out, "UNKNOWN_TEST", fails)["runner_invoked"])
            self.assertEqual(len(calls), 1)

    def test_relocated_existing_journal_holds_and_bytes_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            original = root / "original"
            supervise_stage(original, "LOCAL", lambda _: {"state": "LOCAL_EXECUTED"})
            moved = root / "moved"
            shutil.copytree(original, moved)
            files = [path for path in moved.rglob("*") if path.is_file()]
            before = {p.relative_to(moved).as_posix(): sha(p.read_bytes()) for p in files}
            observed = read_native_state(moved)
            self.assertEqual(observed["state"], "HOLD_NATIVE_READBACK")
            self.assertIn("SHELF", observed["reason"])
            self.assertFalse(observed["source_bytes_rewritten"])
            after = {p.relative_to(moved).as_posix(): sha(p.read_bytes()) for p in files}
            self.assertEqual(before, after)

    def test_archived_summary_does_not_activate_state(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            (out / "RESULT.json").write_text(json.dumps({"state": "PASS", "active": True}), encoding="utf-8")
            state = read_native_state(out)
            self.assertEqual(state["state"], "HOLD_NO_CURRENT_NATIVE_JOURNAL")
            self.assertFalse(state["archived_evidence_is_active_state"])
            (out / "RUN_METADATA.json").write_text("[]", encoding="utf-8")
            (out / "PLAN.json").write_text("{}", encoding="utf-8")
            malformed = read_native_state(out)
            self.assertEqual(malformed["state"], "HOLD_NATIVE_READBACK")
            self.assertIn("HOLD_NOT_CURRENT_LOCAL_NATIVE_STATE", malformed["reason"])

    def test_native_source_tamper_refused_in_isolated_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(PACKAGE / "native_runtime", root / "native_runtime",
                            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            source = root / "native_runtime/payload/implementation/intent_budget.py"
            source.write_bytes(source.read_bytes() + b"\n# controlled corruption\n")
            proc = subprocess.run([sys.executable, "-I", "-S", "-B", "-c",
                                   "import sys;sys.path.insert(0,sys.argv[1]);from native_runtime.core import load_native;load_native()", str(root)],
                                  capture_output=True, timeout=15)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn(b"HOLD_NATIVE_SOURCE_HASH:implementation/intent_budget.py", proc.stderr)

    def test_world_model_absent_node_is_hold_without_process_or_provider(self):
        from adapters.demo import _world_model
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"PATH": ""}, clear=True):
                result = _world_model(Path(directory), {})
            self.assertEqual(result["state"], "HOLD_OPTIONAL_NODE_RUNTIME")
            self.assertFalse(result["executed"])
            self.assertEqual(result["canonical_writes"], 0)

    def test_ooxml_break_markers_and_external_member_denials(self):
        from adapters.build_pipeline import _office_fixture, admit_ooxml
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            fixture = _office_fixture(out / "safe_markers")
            self.assertEqual(fixture["state"], "PASS_SCOPED_OOXML_ADMISSION_BREAK_TESTS")
            cases = {
                "windows_drive.zip": ("C:/unsafe.xml", "<data/>"),
                "ads.zip": ("word/safe.xml:alternate", "<data/>"),
                "traversal.zip": ("word/../unsafe.xml", "<data/>"),
                "external.zip": ("_rels/.rels", '<Relationships><Relationship TargetMode="External" Target="https://example.invalid/"/></Relationships>'),
            }
            for name, (member, data) in cases.items():
                path = out / name
                with zipfile.ZipFile(path, "x") as archive:
                    archive.writestr(member, data)
                with self.subTest(name=name):
                    with self.assertRaises(ValueError):
                        admit_ooxml(path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
