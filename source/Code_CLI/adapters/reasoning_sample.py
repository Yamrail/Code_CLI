"""Track 3 offline feedback loop using actual workers and the existing ledger.

Role decisions and domain inputs are deterministic synthetic fixtures. The
Python processes, Meterless engine, native events and restart readback execute
locally. No model worker, live sponsor call or OS sandbox is simulated as real.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import shutil
import sys

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.dont_write_bytecode = True
from native_runtime.core import (authority_ref, create_case, identity, load_native,
                                 now, open_case, save, settle, sha, snapshot, verify_code_fixture)
from adapters.demo import run_process
from adapters.native_host import _milestones
from runtime_support import discover_node,sample_environment


def worker(role, input_file):
    def offline(event, _args):
        if event.startswith("socket."):
            raise RuntimeError("HOLD_SAMPLE_WORKER_NETWORK_DENIED")
    sys.addaudithook(offline)
    data = json.loads(Path(input_file).read_bytes())
    case, view = data["case"], data["world_model"]
    state = view["case_state"]
    result = {"role": role, "pid": os.getpid(), "produced_utc": now(),
              "consumed_world_model_sha256": data["world_model_sha256"],
              "consumed_native_checkpoint": view["native_checkpoint"],
              "execution_class": "LOCAL_EXECUTED", "reasoning_mode": "DETERMINISTIC_SYNTHETIC_ROLE", "model_calls": 0}
    if role == "PLANNER":
        repairing = state.get("assessment") == "HOLD_MISSING_EVIDENCE"
        result.update(selected_source=case["fallback_source"] if repairing else case["primary_source"],
                      plan="REPAIR_USING_AUTHORIZED_ALTERNATIVE" if repairing else "INSPECT_PRIMARY_SOURCE",
                      critique_received=state.get("critique"), assessment="REPAIR_PLANNED" if repairing else "PLANNED")
    elif role == "EXECUTOR":
        source_id = state["selected_source"]
        source = next(x for x in case["sources"] if x["source_id"] == source_id)
        # This unsupported first claim is an explicit counterexample, never a real finding.
        forced = case.get("unsupported_first_claim", False) and not data["attempt"] > 1
        result.update(selected_source=source_id, source_sha256=source["original_byte_sha256"],
                      assessment="READY" if forced or source["evidence_state"] == "CONFIRMED_FIXTURE" else "HOLD_MISSING_EVIDENCE",
                      finding={"source_id": source_id, "source_sha256": source["original_byte_sha256"],
                               "observation": source["observation"], "evidence_state": source["evidence_state"],
                               "real_world_security_verdict": "UNKNOWN_SYNTHETIC_CASE_ONLY"})
    elif role == "EVALUATOR":
        prior = data["executor"]
        source = next(x for x in case["sources"] if x["source_id"] == prior["selected_source"])
        actual_source_digest = sha(source["fixture_original_text"].encode("utf-8"))
        valid = source["evidence_state"] == "CONFIRMED_FIXTURE" and prior["source_sha256"] == actual_source_digest == source["original_byte_sha256"]
        result.update(selected_source=source["source_id"], assessment="ACCEPTED_SCOPED_FIXTURE" if valid else "HOLD_MISSING_EVIDENCE",
                      critique="SOURCE_BYTES_AND_SCOPE_RECONCILE" if valid else "CLAIM_LACKS_CONFIRMED_SOURCE; SELECT_AUTHORIZED_ALTERNATIVE",
                      accepted=valid, source_sha256=source["original_byte_sha256"])
    else:
        raise ValueError("Unknown fixed sample role")
    print(json.dumps(result, ensure_ascii=False))


def _node():
    result = discover_node()
    for name in ("world_model_bridge.js", "meterless-world-model-reference.js"):
        verify_code_fixture("meterless/" + name, auxiliary=True)
    return result


def run_case(output, case_file):
    sample_environment()
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    case_file = Path(case_file).resolve()
    fixture_root = (PACKAGE / "fixtures/safe_public_or_synthetic/reasoning").resolve()
    if not case_file.is_relative_to(fixture_root) or case_file.is_symlink():
        raise ValueError("HOLD_SAMPLE_SCOPE_REQUIRES_PACKAGED_SAFE_FIXTURE")
    case = json.loads(case_file.read_bytes())
    for source in case["sources"]:
        raw = source["fixture_original_text"].encode("utf-8")
        source["original_byte_sha256"] = sha(raw)
    node = _node()
    native = output / "native"
    root = "SAMPLE_" + case["case_id"]
    ledger, authority = create_case(native, roots=(root,), workers=("PLANNER", "EXECUTOR", "EVALUATOR"),
                                    work_order_id="R009_SAMPLE_" + case["case_id"], stage_id="REASONING_SAMPLE", required_stage=True)
    W, *_ = load_native()
    _milestones(ledger, authority)
    ledger.bind_purpose(root, root, identity(root), [authority])
    ledger.append("STAGE_ENTER", {"stage": "REASONING_SAMPLE"}, [authority])
    print("WORK_ORDER " + case["case_id"] + " | Ingridge stage REASONING_SAMPLE | LOCAL_EXECUTED, SYNTHETIC role reasoning | live sponsor calls: 0", file=sys.stderr, flush=True)
    save(native / "CASE.json", case)
    records, processes, views, stop_receipt = [], [], [], None

    def view_for(role, attempt):
        restored = open_case(native)
        snap = snapshot(restored)
        replayed_records = []
        for line in restored.journal.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event["kind"] != "TRACE" or not event["data"].get("id", "").startswith("ROLE_"):
                continue
            evidence = next(e for e in event["evidence"] if e["record_class"] == "EXECUTION")
            raw_record = (native / evidence["locator"]).read_bytes()
            if sha(raw_record) != evidence["sha256"]:
                raise AssertionError("Native worker record source bytes changed")
            record = json.loads(raw_record)
            record["trace_id"] = event["id"]
            replayed_records.append(record)
        name = str(len(views)).zfill(2)
        payload = {"source_of_truth": "EXISTING_NATIVE_WORKLEDGER", "observed_utc": now(),
                   "case_id": case["case_id"], "journal_sha256": sha(restored.journal.read_bytes()),
                   "checkpoint": snap["checkpoint"], "root_buckets": snap["root_buckets"], "records": replayed_records}
        input_path = native / "projections" / (name + "-input.json")
        save(input_path, payload)
        command=([node,str(PACKAGE/'adapters/reasoning_world_model.js'),str(input_path)] if node else
                 [sys.executable,'-I','-S','-B',str(PACKAGE/'adapters/reasoning_world_model.py'),str(input_path)])
        proc, raw = run_process(command,
                                output / "processes", "world-" + name)
        result = json.loads(raw)
        if result["source_journal_sha256"] != payload["journal_sha256"] or result["canonical_writes"] != 0:
            raise AssertionError("World Model native source binding")
        path = native / "projections" / (name + "-view.json")
        path.write_bytes(raw)
        views.append({"role": role, "native_checkpoint": result["native_checkpoint"], "sha256": sha(raw),
                      "fact_count": len(result["facts"]), "superseded_facts": sum(bool(f.get("supersededBy")) for f in result["facts"]),
                      "process": proc,"backend":"NODE_PINNED_METERLESS_REFERENCE" if node else "PYTHON_EQUIVALENT_PROJECTION"})
        return result, path, sha(raw)

    def invoke(role, attempt, executor=None):
        view, view_path, view_digest = view_for(role, attempt)
        step = str(len(records)).zfill(2) + "-" + role.lower()
        input_path = native / "records" / (step + "-input.json")
        save(input_path, {"case": case, "world_model": view, "world_model_sha256": view_digest,
                          "attempt": attempt, "executor": executor})
        proc, raw = run_process([sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                                 "--worker", role, "--input", str(input_path)], output / "processes", step)
        result = json.loads(raw)
        if result["consumed_world_model_sha256"] != view_digest:
            raise AssertionError("Worker did not consume shared view")
        path = native / "records" / (step + "-output.json")
        path.write_bytes(raw)
        live = open_case(native, role)
        observed = W.evidence_ref(native, path.relative_to(native).as_posix(), "EXECUTION", "R009_SAMPLE", role)
        projection = W.evidence_ref(native, view_path.relative_to(native).as_posix(), "OBSERVATION", "R009_SAMPLE", role)
        trace = live.append("TRACE", {"id": "ROLE_" + step, "trace_class": "OBSERVED",
                                      "source_cases": [observed["locator"], projection["locator"]],
                                      "parent_trace_ids": ["PURPOSE:" + root], "reason_status": "CONTEMPORARY_RECORDED",
                                      "reason": "ACTUAL_PROCESS_CONSUMED_METERLESS_NATIVE_DERIVED_VIEW", "worker_id": role, "pid": result["pid"]},
                            [observed, projection])
        result["trace_id"] = trace
        records.append(result)
        processes.append(proc)
        print(case["case_id"] + " " + role + " | " + result.get("assessment", "OBSERVED") + " | trace " + trace, file=sys.stderr, flush=True)
        return result

    final = None
    for attempt in (1, 2):
        invoke("PLANNER", attempt)
        execution_ledger = open_case(native, "EXECUTOR")
        execution_ledger.reserve_attempt("E" + str(attempt), root, root, "LOCAL", 30, [authority_ref(native)])
        execution = invoke("EXECUTOR", attempt)
        settle(open_case(native, "EXECUTOR"), "E" + str(attempt), 0)
        if attempt == 1 and case.get("stop_before_evaluation"):
            live = open_case(native)
            before = snapshot(live)
            live.append("STOP", {"reason": "CONTROLLED_SAMPLE_STOP_BEFORE_EVALUATOR"}, [authority_ref(native)])
            restored = open_case(native)
            stopped = snapshot(restored)
            restored.append("RESUME", {"presence": "CURRENT_CONFIRMED", "authority_digest": restored.plan["authority_digest"]}, [authority_ref(native)])
            restored.append("STAGE_ENTER", {"stage": "REASONING_SAMPLE"}, [authority_ref(native)])
            after = snapshot(open_case(native))
            stop_receipt = {"stopped": not stopped["active"], "resumed": after["active"],
                            "budget_preserved": before["root_buckets"] == after["root_buckets"], "replayed_execution": False}
            print(case["case_id"] + " STOP / RESUME | budget preserved, no execution replay", file=sys.stderr, flush=True)
        evaluated = invoke("EVALUATOR", attempt, execution)
        if evaluated["accepted"]:
            final = execution["finding"]
            break
    if final is None:
        raise AssertionError("Safe fixture failed to repair within two executor attempts")
    final_view, _, _ = view_for("FINAL", attempt)
    live = open_case(native)
    save(native / "STAGE_RESULT.json", {"runner_returned": True, "operation_class": "LOCAL_SYNTHETIC_OFFLINE",
                                        "result": {"case_id": case["case_id"], "assessment": "ACCEPTED_SCOPED_FIXTURE",
                                                   "executor_attempts": attempt, "finding": final}})
    ref = W.evidence_ref(native, "STAGE_RESULT.json", "RECEIPT", "CODE_CLI_R007", "REASONING_SAMPLE")
    live.append("STAGE_DONE", {"stage": "REASONING_SAMPLE", "passed": True,
                               "exit_criterion": live.plan["stages"][0]["exit_criterion"]}, [ref])
    live.append("STOP", {"reason": "OFFLINE_SAMPLE_FINISHED_NO_PROVIDER_CALL"}, [ref])
    restored = snapshot(open_case(native))
    checks = {"three_actual_roles": {r["role"] for r in records} == {"PLANNER", "EXECUTOR", "EVALUATOR"},
              "all_workers_consumed_world_model": all(r["consumed_world_model_sha256"] for r in records),
              "native_trace_readback": restored["checkpoint"] == live.checkpoint,
              "world_model_used_by_next_worker": any(v["fact_count"] > 0 for v in views[1:]),
              "critique_and_repair": not case.get("expect_repair") or any(r.get("plan") == "REPAIR_USING_AUTHORIZED_ALTERNATIVE" for r in records),
              "conflict_history_retained": not case.get("expect_repair") or any(v["superseded_facts"] > 0 for v in views),
              "stop_resume": not case.get("stop_before_evaluation") or all(stop_receipt[k] for k in ("stopped", "resumed", "budget_preserved")),
              "no_live_provider_calls": all(r["model_calls"] == 0 for r in records)}
    if not all(checks.values()):
        raise AssertionError("Sample acceptance failed")
    report = {"schema": "yamrail.r009.reasoning-sample/1", "state": "PASS_OFFLINE_REASONING_SAMPLE", "case_id": case["case_id"],
              "execution_class": "LOCAL_EXECUTED", "domain_inputs_and_role_decisions": "SYNTHETIC_FIXTURE",
              "actual_model_calls": 0, "checks": checks, "finding": final, "records": records,
              "world_model_views": views, "final_shared_state": final_view["case_state"], "stop_resume": stop_receipt,
              "executor_attempts": attempt, "native_checkpoint": restored["checkpoint"],
              "native_journal_sha256": sha(open_case(native).journal.read_bytes()), "only_authoritative_workflow_writer": "EXISTING_NATIVE_WORKLEDGER"}
    save(output / "RESULT.json", report)
    (output / "report.md").write_text("# Evidence-backed local sample\n\nCase: " + case["case_id"] + "\n\n" +
        "Execution: LOCAL_EXECUTED. Domain and role reasoning: SYNTHETIC_FIXTURE.\n\n" +
        "Source: " + final["source_id"] + "\n\n" + final["observation"] + "\n\n" +
        "Original fixture bytes SHA256: `" + final["source_sha256"] + "`\n\nReal-world security conclusion: UNKNOWN.\n", encoding="utf-8")
    return report


def run_samples(output, selected=None):
    sample_environment()
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    files = [Path(selected)] if selected else sorted((PACKAGE / "fixtures/safe_public_or_synthetic/reasoning").glob("*.json"))
    results = []
    for path in files:
        try:
            results.append(run_case(root / path.stem, path))
        except Exception as error:
            native = root / path.stem / 'native'
            if (native / 'ledger/events.jsonl').is_file():
                ledger = open_case(native)
                if ledger.state['active']:
                    save(native / 'UNFINISHED_SAMPLE.json', {'state': 'HOLD_UNFINISHED_SYNTHETIC_SAMPLE', 'exception_type': type(error).__name__, 'automatic_retry': False})
                    W, *_ = load_native()
                    ref = W.evidence_ref(native, 'UNFINISHED_SAMPLE.json', 'OBSERVATION', 'R009_SAMPLE', 'UNFINISHED')
                    ledger.append('HOLD', {'id':'UNFINISHED_SAMPLE','state':'UNKNOWN','scope':['INTENT_ROOT:'+name for name in snapshot(ledger)['root_buckets']],
                                          'reason':'LOCAL_RUNNER_DID_NOT_COMPLETE; preserve original evidence','next':'Inspect retained failure before a new decision','global_stop':False}, [ref])
                    ledger.append('STOP', {'reason':'UNFINISHED_SAMPLE_NO_AUTOMATIC_RETRY'}, [ref])
            raise
    return {"state": "PASS_OFFLINE_REASONING_SAMPLES", "sample_count": len(results), "samples": results,
            "world_model": "LOCAL_PINNED_METERLESS_ENGINE_EXECUTED" if all(v['backend']=='NODE_PINNED_METERLESS_REFERENCE' for r in results for v in r['world_model_views']) else "LOCAL_PYTHON_METERLESS_EQUIVALENT_PROJECTION_EXECUTED", "live_provider_calls": 0,
            "projection_contract":"Unchanged reasoning_world_model.js JSON contract; actual backend is recorded for every projection process",
            "multi_model_execution": "NOT_CLAIMED_DETERMINISTIC_ROLE_PROCESSES", "checks": {"all_samples_pass": all(all(x["checks"].values()) for x in results)}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", required=True, choices=["PLANNER", "EXECUTOR", "EVALUATOR"])
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    worker(args.worker, args.input)
