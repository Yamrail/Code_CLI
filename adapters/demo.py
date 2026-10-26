"""Portable local counterexamples using the retained native guard and ledger.

Inputs and cost units are synthetic; the Python subprocesses, crash, durable
replay, graph evaluation and optional Meterless reference execution are real.
No provider or subscription CLI is called by this module.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))
sys.dont_write_bytecode = True
from native_runtime.core import (HERE, authority_ref, create_case, identity, load_native,
                                 now, open_case, refused, save, settle, sha, snapshot,
                                 verify_code_fixture)


def clean_environment():
    # Minimize credentials; this is not an OS or process-tree sandbox.
    keep = {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "PATH", "COMSPEC", "PATHEXT", "SYSTEMDRIVE"}
    return {**{k: v for k, v in os.environ.items() if k.upper() in keep},
            "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}


def run_process(command, folder, name, *, expected_exit=0, timeout=30, cwd=None):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tick, started = time.monotonic(), now()
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, cwd=str(cwd or PACKAGE), env=clean_environment())
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    (folder / (name + ".stdout")).write_bytes(stdout)
    (folder / (name + ".stderr")).write_bytes(stderr)
    receipt = {"schema": "code-cli.actual-fixed-process/1", "command": command,
               "pid": process.pid, "started_utc": started, "ended_utc": now(),
               "elapsed_ms": round((time.monotonic() - tick) * 1000, 3),
               "exit_code": process.returncode, "expected_exit_code": expected_exit,
               "timed_out": timed_out, "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr),
               "stdout_bytes": len(stdout), "stderr_bytes": len(stderr), "evidence_class": "LOCAL_EXECUTED",
               "environment": "CREDENTIAL_MINIMIZED_FIXED_PROCESS_NOT_OS_SANDBOX",
               "process_tree_isolation": "NOT_CLAIMED"}
    save(folder / (name + ".process.json"), receipt)
    if timed_out or process.returncode != expected_exit:
        raise RuntimeError("PROCESS_FAILED:" + name + ":" + str(process.returncode) + ":" + stderr.decode("utf-8", "replace")[:1500])
    return receipt, stdout


def _worker(base, action, worker_id):
    def no_network(event, _args):
        if event.startswith("socket."):
            raise RuntimeError("HOLD_FIXED_OFFLINE_WORKER_SOCKET_DENIED")
    sys.addaudithook(no_network)
    W, _, _, _, _, _ = load_native()
    base = Path(base).resolve()
    if action == "init":
        ledger, ref = create_case(base)
        ledger.bind_purpose("ROOT_A", "ROOT_A", identity("ROOT_A"), [ref])
        ledger.bind_purpose("CHILD", "ROOT_A", identity("ROOT_A"), [ref], "ROOT_A")
        ledger.bind_purpose("GRANDCHILD", "ROOT_A", identity("ROOT_A"), [ref], "CHILD")
        result = {"work_order": "CODE-CLI-R007-SYNTHETIC-DEMO", "root": "ROOT_A"}
    else:
        ledger, ref = open_case(base, worker_id), authority_ref(base)
        result = {}
        if action in {"parent", "child", "grandchild", "independent"}:
            table = {"parent": ("A1", "ROOT_A", "ROOT_A"), "child": ("A2", "CHILD", "ROOT_A"),
                     "grandchild": ("A3", "GRANDCHILD", "ROOT_A"), "independent": ("C1", "ROOT_C", "ROOT_C")}
            attempt, purpose, root = table[action]
            if action == "independent":
                ledger.bind_purpose(root, root, identity(root), [ref])
            ledger.reserve_attempt(attempt, purpose, root, "LOCAL", 30, [ref])
            fixture_raw = (base.parent / "WORK_ORDER.json").read_bytes()
            fixture = json.loads(fixture_raw)
            counts = {state: sum(row["state"] == state for row in fixture["checklist"]) for state in ("KNOWN", "UNKNOWN")}
            task_result = {"state": "PASS_LOCAL_TRANSFORM", "evidence_class": "LOCAL_EXECUTED",
                           "input_class": "SYNTHETIC_FIXTURE", "attempt_id": attempt, "worker_pid": os.getpid(),
                           "source_sha256": sha(fixture_raw), "check_counts": counts, "real_provider_calls": 0}
            save(base / ("result-" + attempt + ".json"), task_result)
            observed = W.evidence_ref(base, "result-" + attempt + ".json", "EXECUTION", "CODE_CLI_LOCAL_OFFLINE_R007", attempt)
            cost_ref = settle(ledger, attempt, 25)
            trace_id = "LOCAL_EXECUTION:" + attempt
            ledger.append("TRACE", {"id": trace_id, "trace_class": "OBSERVED", "source_cases": [observed["locator"]],
                                    "parent_trace_ids": ["PURPOSE:" + purpose], "reason_status": "CONTEMPORARY_RECORDED",
                                    "reason": "ACTUAL_FIXED_LOCAL_TASK_WITH_SYNTHETIC_INPUT_AND_COST",
                                    "worker_id": worker_id, "pid": os.getpid(), "attempt_id": attempt}, [observed, cost_ref])
            result = {"attempt_id": attempt, "trace_id": trace_id, "result": task_result,
                      "result_sha256": observed["sha256"], "synthetic_cost_minor": 25}
        elif action == "stop":
            ledger.append("STOP", {"reason": "CONTROLLED_OPERATOR_STOP"}, [ref])
            result = {"reason": "CONTROLLED_OPERATOR_STOP"}
        elif action == "resume":
            before = snapshot(ledger)
            if before["active"]:
                raise AssertionError("Expected stopped native ledger")
            ledger.append("RESUME", {"presence": "CURRENT_CONFIRMED", "authority_digest": ledger.plan["authority_digest"]}, [ref])
            result = {"restored_attempts": before["root_buckets"]["ROOT_A"]["attempts_used"],
                      "was_stopped": True, "prior_checkpoint": before["checkpoint"]}
        elif action == "fourth":
            result = {"refusal": refused(lambda: ledger.reserve_attempt("A4", "GRANDCHILD", "ROOT_A", "LOCAL", 30, [ref]), "ATTEMPT_LIMIT"),
                      "operation_dispatched": False}
        elif action == "alias":
            result = {"refusal": refused(lambda: ledger.bind_purpose("RENAMED", "RENAMED", identity("ROOT_A"), [ref]), "ALIAS_DENY"),
                      "new_budget_created": False}
        elif action == "crash":
            ledger.bind_purpose("ROOT_B", "ROOT_B", identity("ROOT_B"), [ref])
            ledger.reserve_attempt("B1", "ROOT_B", "ROOT_B", "LOCAL", 30, [ref])
            print(json.dumps({"state": "CONTROLLED_CRASH_AFTER_DURABLE_RESERVATION", "pid": os.getpid(),
                              "external_effect": "SYNTHETIC_NOT_DISPATCHED", "snapshot": snapshot(ledger)}), flush=True)
            os._exit(23)
        elif action == "recover":
            before = ledger.state["pending"]["B1"]["state"]
            ledger.append("STOP", {"reason": "OWNER_RESTART_WITH_UNSETTLED_SYNTHETIC_EFFECT"}, [ref])
            ledger.append("RESUME", {"presence": "CURRENT_CONFIRMED", "authority_digest": ledger.plan["authority_digest"]}, [ref])
            result = {"before": before, "after": ledger.state["pending"]["B1"]["state"], "automatic_retry": False,
                      "refusal": refused(lambda: ledger.reserve_attempt("B2", "ROOT_B", "ROOT_B", "LOCAL", 30, [ref]), "LATCHED")}
        elif action != "status":
            raise ValueError("Unknown fixed action")
    print(json.dumps({"schema": "code-cli.native-worker-receipt/1", "action": action, "worker_id": worker_id,
                      "pid": os.getpid(), "observed_utc": now(), "engine_class": "LOCAL_EXECUTED",
                      "domain_and_cost_class": "SYNTHETIC_FIXTURE", "real_provider_calls": 0,
                      "result": result, "snapshot": snapshot(ledger)}, ensure_ascii=False), flush=True)


def _graph(final):
    path = verify_code_fixture("typed_graph_ab.py", auxiliary=True)
    spec = importlib.util.spec_from_file_location("code_cli_pinned_typed_graph", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    purposes = final["purposes"]
    edges = [{"source": p["parent_purpose_id"], "target": p["purpose_id"], "edge_type": "MATERIAL_LINEAGE",
              "source_evidence_state": "OBSERVED", "target_state": "OBSERVED", "dependency_class": "CURRENT_ROUTE_ONLY"}
             for p in purposes.values() if p.get("parent_purpose_id")]
    accepted = module.evaluate_typed_graph({"typed_graph": {"edges": edges}})
    rejected = module.evaluate_typed_graph({"typed_graph": {"edges": [
        {"source": "UNKNOWN_PROVIDER_RESULT", "target": "ACCEPTED_COMPLETION", "edge_type": "MATERIAL_LINEAGE",
         "source_evidence_state": "UNKNOWN", "target_state": "EXACT"}]}})
    if accepted or not any(item["rule_id"] == "AB_UNKNOWN_TO_EXACT" for item in rejected):
        raise AssertionError("Pinned Typed Graph acceptance changed")
    return {"evidence_class": "LOCAL_EXECUTED", "source": "NATIVE_WORKLEDGER_READONLY_PROJECTION",
            "nodes": [{"id": key, **value} for key, value in purposes.items()], "edges": edges,
            "valid_projection_violations": accepted, "synthetic_invalid_graph_violations": rejected,
            "evaluator_sha256": sha(path.read_bytes()), "state_writes": 0}


def _world_model(output, final):
    # Only explicit configuration/PATH discovery, never author's runtime paths.
    configured = os.environ.get("RTA_NODE")
    node = configured if configured and Path(configured).is_file() else shutil.which("node")
    if not node:
        return {"state": "HOLD_OPTIONAL_NODE_RUNTIME", "evidence_class": "UNKNOWN", "executed": False,
                "canonical_writes": 0, "reason": "Set RTA_NODE to a compatible Node executable or put node on PATH"}
    names = ("world_model_bridge.js", "meterless-world-model-reference.js")
    for name in names:
        verify_code_fixture("meterless/" + name, auxiliary=True)
    source = {"kind": "fresh-native-workledger-replay", "at": now(), "by": "code-cli-local-host",
              "journal_sha256": sha((output / "worksite/ledger/events.jsonl").read_bytes()), "checkpoint": final["checkpoint"]}
    data = {"source": source, "evidence_class": "SYNTHETIC_FIXTURE", **final}
    data["purposes"] = {k: {**v, "root_id": v["root_purpose_id"], "parent_id": v.get("parent_purpose_id")} for k, v in final["purposes"].items()}
    save(output / "WORLD_MODEL_INPUT.json", data)
    process, raw = run_process([node, str(HERE / "meterless/world_model_bridge.js"), str(output / "WORLD_MODEL_INPUT.json")],
                               output / "processes", "world_model")
    result = json.loads(raw)
    if result.get("source_of_truth") != "NATIVE_WORKLEDGER_ONLY" or result.get("canonical_writes") != 0:
        raise AssertionError("World Model source-of-truth contract")
    if not any(x["purpose_id"] == "GRANDCHILD" and set(x["ancestors"]) == {"ROOT_A", "CHILD"} for x in result["lineage"]):
        raise AssertionError("World Model lineage contract")
    save(output / "WORLD_MODEL.json", result)
    return {"state": "PASS_LOCAL_UPSTREAM_ENGINE", "evidence_class": "LOCAL_EXECUTED", "executed": True,
            "input_class": "SYNTHETIC_FIXTURE", "entity_count": len(result["entities"]),
            "relationship_count": len(result["relationships"]), "derived_state_sha256": result["derived_state_sha256"],
            "canonical_writes": 0, "provider_calls": 0, "license": "Apache-2.0", "process": process}


def _derived_code_runner(stage_dir):
    hashes = {}
    for name in ("hold_report.py", "test_hold_report.py"):
        source = verify_code_fixture(name)
        raw = source.read_bytes()
        (stage_dir / name).write_bytes(raw)
        hashes[name] = sha(raw)
    receipt, _ = run_process([sys.executable, "-I", "-S", "-B", "-c",
                             "import sys,unittest;sys.path.insert(0,'.');import test_hold_report;"
                             "r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_hold_report));"
                             "sys.exit(0 if r.wasSuccessful() else 1)"], stage_dir / "processes", "safe_code_tests", cwd=stage_dir)
    return {"state": "PASS_DERIVED_CODE_FIXTURE_TESTS", "evidence_class": "LOCAL_EXECUTED",
            "origin": "CODE_ONLY_DERIVED_FROM_PINNED_PRIOR_CODING_TASK", "source_commit": "95322eb461cb251c6ed6c837bbb1f3e0d34c69e1",
            "source_sha256": hashes, "test_count": 4, "current_model_generation": False,
            "original_live_receipt_imported": False, "provider_calls": 0, "process": receipt}


def _render(output, report):
    import html
    final = report["final_native_state"]
    lines = ["# Code CLI local execution", "", "Engine: LOCAL_EXECUTED. Inputs, costs and counterexamples: SYNTHETIC_FIXTURE.", "",
             "```mermaid", "graph LR"]
    for node in report["typed_graph"]["nodes"]:
        identifier = node["id"]
        root = node["root_purpose_id"]
        bucket = final["root_buckets"][root]
        label = identifier + " | " + str(bucket["attempts_used"]) + "/3 root attempts"
        if bucket["unsettled"]:
            label += " | UNKNOWN/HOLD"
        lines.append('  ' + identifier + '["' + label + '"]')
    for edge in report["typed_graph"]["edges"]:
        lines.append("  " + edge["source"] + " -->|same root| " + edge["target"])
    lines += ["```", "", "Read-only projection of this run's native journal. Rendering class: STATIC_DIAGRAM.", "",
              "| Step | Observed result | PID |", "|---|---|---|"]
    for step in report["steps"]:
        value = step["result"].get("refusal", step["result"].get("after", step["title"]))
        lines.append("| " + step["action"] + " | " + str(value) + " | " + str(step["process"]["pid"]) + " |")
    lines += ["", "ROOT_B remains UNKNOWN/HOLD. ROOT_C continued. No external effect was dispatched or retried.", "",
              "Meterless World Model: " + report["world_model"]["state"] + ". Nightshift/Nemotron and Zetaris: HOLD, no live request.", "",
              "Raw journals are newly generated and host-bound. Ship sanitized summaries; relocated source supports a fresh run."]
    (output / "DEPENDENCY_GRAPH.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rows = "".join("<tr><td>" + html.escape(step["action"]) + "</td><td>" + html.escape(str(step["result"].get("refusal", step["title"]))) + "</td><td>" + str(step["process"]["pid"]) + "</td></tr>" for step in report["steps"])
    body = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Code CLI native execution</title><style>body{max-width:1050px;margin:40px auto;padding:20px;font:18px/1.6 system-ui;background:#0b1725;color:#e5edf4}h1{font-size:38px}td,th{padding:10px;border-bottom:1px solid #42526a;text-align:left}pre{white-space:pre-wrap}a{color:#8de0c6}</style><h1>Intent survives worker changes and process failure</h1><p>Three worker processes share one purpose budget. Attempt four and aliases are refused. Unknown completion stays on HOLD while an independent purpose continues.</p><p><strong>' + report["state"] + '</strong><br>Local engine executed; scenario and cost units are synthetic. No new model or sponsor request.</p><table><tr><th>Step</th><th>Observed result</th><th>PID</th></tr>' + rows + '</table><h2>Purpose lineage</h2><pre>ROOT_A (3/3) → CHILD → GRANDCHILD\nROOT_B: UNKNOWN / HOLD, no automatic retry\nROOT_C: independent work completed</pre><p>This static graph is derived from current native state.</p><p><a href="DEPENDENCY_GRAPH.md">Typed dependency graph</a> · <a href="RESULT.json">Exact local receipt</a></p><p>Meterless: ' + report["world_model"]["state"] + '. Nightshift/Nemotron and Zetaris live: HOLD.</p></html>'
    (output / "REPORT.html").write_text(body, encoding="utf-8")


def run_demo(output):
    """Create-only, one-command local demo; return retained current-run evidence."""
    from adapters.native_host import supervise_stage, read_native_state
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = {"schema": "code-cli.safe-synthetic-work-order/1", "work_order_id": "CODE-CLI-R007-SYNTHETIC-DEMO",
               "evidence_class": "SYNTHETIC_FIXTURE", "checklist": [{"id": "input-1", "state": "KNOWN"}, {"id": "input-2", "state": "UNKNOWN"}],
               "inference_fixture": {"state": "SYNTHETIC_FIXTURE", "text": "The fourth attempt shares the exhausted root. Keep ROOT_B on HOLD; ROOT_C is independent."}}
    save(output / "WORK_ORDER.json", fixture)
    steps = []
    try:
        coding = supervise_stage(output / "derived_code_task", "SAFE_CODE_TESTS", _derived_code_runner,
                                 work_order_id="CODE-CLI-R007-DERIVED-CODE-TESTS", root_purpose="SAFE_FIXTURE_TESTS")
        sequence = [("init", "W1", "Work order and explicit lineage registered", 0),
                    ("parent", "W1", "Parent executes first attempt", 0), ("child", "W2", "Child shares root budget", 0),
                    ("grandchild", "W3", "Grandchild consumes third attempt", 0), ("stop", "W1", "Operator stops", 0),
                    ("resume", "W2", "New process restores durable consumption", 0), ("fourth", "W2", "Fourth attempt refused before dispatch", 0),
                    ("alias", "W3", "Purpose alias cannot reset budget", 0), ("crash", "W1", "Actual controlled process crash", 23),
                    ("recover", "W3", "UNKNOWN retained; automatic retry refused", 0), ("independent", "W2", "Independent purpose continues", 0),
                    ("stop", "W3", "Final STOP preserves scoped HOLD", 0)]
        for index, (action, worker_id, title, expected) in enumerate(sequence, 1):
            process, raw = run_process([sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()), "worker",
                                        "--case", str(output / "worksite"), "--action", action, "--worker-id", worker_id],
                                       output / "processes", str(index).zfill(2) + "_" + action, expected_exit=expected)
            result = json.loads(raw)
            step = {"index": index, "action": action, "title": title, "process": process,
                    "result": result.get("result", {"state": result.get("state")}), "snapshot": result["snapshot"]}
            steps.append(step)
        final = steps[-1]["snapshot"]
        W, _, _, _, _, _ = load_native()
        probe = output / "tamper_probe"
        probe.mkdir()
        good = (output / "worksite/receipt-A1.json").read_bytes()
        (probe / "receipt.json").write_bytes(good)
        proof = W.evidence_ref(probe, "receipt.json", "RECEIPT", "CODE_CLI_R007_TAMPER_PROBE", "A1")
        (probe / "receipt.original.bytes").write_bytes(good)
        (probe / "receipt.json").write_bytes(good + b" ")
        tamper = {"state": refused(lambda: W.validate_evidence(probe, proof), "HOLD_EVIDENCE_BYTES"),
                  "good_sha256": sha(good), "tampered_sha256": sha(good + b" "), "original_and_failure_bytes_retained": True}
        graph = _graph(final)
        save(output / "TYPED_GRAPH.json", graph)
        # An optional sponsor runtime HOLD does not discard the native demo.
        try:
            world = _world_model(output, final)
        except Exception as error:
            world = {"state": "HOLD_OPTIONAL_WORLD_MODEL_EXECUTION", "evidence_class": "UNKNOWN", "executed": None,
                     "attempt_status": "PARTIAL_OR_UNKNOWN; SEE_RETAINED_PROCESS_RECEIPTS",
                     "error_type": type(error).__name__, "reason": str(error), "canonical_writes": 0, "provider_calls": 0}
        checks = {"parent_child_grandchild_shared_three": final["root_buckets"]["ROOT_A"]["attempts_used"] == 3,
                  "fourth_refused": steps[6]["result"]["refusal"] == "HOLD_ROOT_ATTEMPT_LIMIT",
                  "alias_refused": steps[7]["result"]["refusal"] == "ALIAS_DENY",
                  "stop_restore_preserves_consumption": steps[5]["result"]["was_stopped"] and steps[5]["result"]["restored_attempts"] == 3,
                  "actual_crash_exit_23": steps[8]["process"]["exit_code"] == 23,
                  "unknown_no_automatic_retry": final["pending"]["B1"]["state"] == "UNKNOWN_COMPLETION" and not steps[9]["result"]["automatic_retry"],
                  "local_hold_independent_work_continues": final["root_buckets"]["ROOT_C"]["attempts_used"] == 1,
                  "sha256_tamper_refused": tamper["state"] == "HOLD_EVIDENCE_BYTES",
                  "typed_graph_rejects_unknown_to_exact": bool(graph["synthetic_invalid_graph_violations"]),
                  "final_safe_stop": not final["active"],
                  "derived_code_fixture_reexecuted": coding["state"] == "PASS_NATIVE_HOST_STAGE" and coding["result"]["current_model_generation"] is False,
                  "durable_current_journal_readback": read_native_state(output)["state"] == "PASS_NATIVE_DURABLE_READBACK"}
        if not all(checks.values()):
            raise AssertionError(checks)
        report = {"schema": "code-cli.portable-native-demo/1", "state": "PASS_SCOPED_LOCAL_COUNTEREXAMPLES",
                  "observed_utc": now(), "command": "python yr_code.py demo", "engine_class": "LOCAL_EXECUTED",
                  "fixture_and_cost_class": "SYNTHETIC_FIXTURE", "checks": checks, "steps": steps,
                  "final_native_state": final, "coding_task": coding, "tamper": tamper, "typed_graph": graph,
                  "world_model": world, "inference_fixture": fixture["inference_fixture"],
                  "sponsors": {"nightshift_nemotron": "HOLD_NO_LIVE_RECEIPT_OR_PAID_AUTHORITY", "zetaris": "HOLD_NO_LIVE_RECEIPT_OR_SCOPE",
                               "meterless_world_model": world["state"], "real_provider_calls": 0},
                  "no_new_model_generation": True, "captured_model_execution_replayed": False,
                  "only_workflow_state_writer": "EXISTING_NATIVE_WORKLEDGER", "private_or_canonical_ledgers_imported": False,
                  "human_acceptance": "NOT_GRANTED", "submission": "SEPARATE_HUMAN_GATE_PENDING",
                  "journal_relocation": "HOLD_EXISTING_HOST_BOUND_JOURNAL; RELOCATE_SOURCE_AND_RUN_FRESH"}
        save(output / "RESULT.json", report)
        _render(output, report)
        return report
    except BaseException as error:
        save(output / "FAILURE.json", {"state": "FAIL_OBSERVED", "error_type": type(error).__name__, "error": str(error),
                                       "observed_utc": now(), "completed_steps": steps, "failure_evidence_retained": True})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    worker = sub.add_parser("worker")
    worker.add_argument("--case", required=True)
    worker.add_argument("--action", required=True)
    worker.add_argument("--worker-id", choices=["W1", "W2", "W3"], required=True)
    demo = sub.add_parser("demo")
    demo.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.command == "worker":
        _worker(args.case, args.action, args.worker_id)
    else:
        result = run_demo(Path(args.output))
        print(json.dumps({"state": result["state"], "checks": result["checks"], "world_model": result["world_model"]["state"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
