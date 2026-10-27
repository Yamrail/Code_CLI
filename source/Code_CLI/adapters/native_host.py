"""Actual local stage execution through existing native WorkLedger only."""
from __future__ import annotations
import json
from pathlib import Path
import re
from native_runtime.core import authority_ref, create_case, identity, load_native, now, open_case, save, settle, sha, snapshot, R007_AUTHORITY


def read_native_state(output_dir):
    """Derive status from the current journal; readback never grants execution."""
    directory = Path(output_dir).resolve()
    candidates = [directory / "native", directory / "worksite", directory]
    base = next((path for path in candidates if (path / "RUN_METADATA.json").is_file()), None)
    if base is None:
        return {"state": "HOLD_NO_CURRENT_NATIVE_JOURNAL", "archived_evidence_is_active_state": False,
                "execution_authority_granted_by_readback": False}
    try:
        ledger = open_case(base)
        data = snapshot(ledger)
        W, _, _, _, _, _ = load_native()
        reconstruction = W.reconstruction(base, ledger.plan, ledger.journal, ledger.checkpoint, ledger.intent_context)
        return {"state": "PASS_NATIVE_DURABLE_READBACK", "evidence_class": "LOCAL_EXECUTED", "snapshot": data,
                "native_revision": W.REVISION, "journal_sha256": sha(ledger.journal.read_bytes()),
                "checkpoint": ledger.checkpoint, "reconstruction": reconstruction,
                "only_workflow_state_writer": "EXISTING_NATIVE_WORKLEDGER", "private_ledger_imported": False,
                "archived_evidence_is_active_state": False, "execution_authority_granted_by_readback": False,
                "relocation_contract": "SOURCE_RELOCATION_SUPPORTS_FRESH_RUN; MOVED_JOURNAL_MUST_HOLD"}
    except (ValueError, RuntimeError, OSError, KeyError) as error:
        return {"state": "HOLD_NATIVE_READBACK", "reason": str(error), "error_type": type(error).__name__,
                "source_bytes_rewritten": False, "execution_authority_granted_by_readback": False}


def _milestones(ledger, ref):
    W, _, _, _, digest, _ = load_native()
    for name, extra in [
        ("ISSUE_REGISTERED", {"origin": "PUBLIC_REVIEWER_LOCAL_FIXED_FIXTURE_ORDER"}),
        ("GITHUB_STORED", {"origin": "SYNTHETIC_TRANSPORT_MILESTONE_LOCAL_MANIFEST_ONLY", "immutable_commit": R007_AUTHORITY["commit"], "generated_local_subjob_separately_remote_stored": False}),
        ("PC_RECEIVED", {"origin": "RECEIVER", "members_match": True, "immutable_commit": R007_AUTHORITY["commit"], "manifest_digest": digest(R007_AUTHORITY), "parent_order_only": True}),
        ("SOL_ACK", {"origin": "SOL", "actor_type": "DETERMINISTIC_LOCAL_HOST_ROLE_LABEL", "reconstruction_digest": digest(ledger.state)}),
        ("WORK_STARTED", {"origin": "HOST_NATIVE_WORKLEDGER"}),
    ]:
        data = {"fixture_milestone": True, "actual_remote_delivery": False, "legacy_event_name_semantics": "Synthetic local fixture milestone; no GitHub delivery is claimed", "name": name, "receipt_subject": ledger.plan["subject"], "payload_revision": ledger.plan["incoming_revision"], **extra}
        filename = "milestones/" + name + ".json"
        save(ledger.base / filename, {"milestone": name, "binding": data, "authority_effect": "NONE"})
        receipt = W.evidence_ref(ledger.base, filename, "RECEIPT", "PUBLIC_LOCAL_FIXED_FIXTURE_ORDER", ledger.plan["subject"])
        ledger.append("MILESTONE", data, [ref, receipt])


def supervise_stage(output_dir, stage_id, runner, work_order_id="CODE-CLI-R007-LOCAL-WORK-ORDER", root_purpose="LOCAL_TOOL"):
    """Invoke a trusted host runner once; it must perform only offline local work.

    This records the outer invocation. It does not intercept proprietary agent
    internals, qualify a paid observer, or grant a sandbox/egress capability.
    """
    output = Path(output_dir).resolve()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,79}", str(stage_id)) or not callable(runner):
        raise ValueError("HOLD_INVALID_NATIVE_STAGE_CONTRACT")
    if output.exists():
        return {"state": "HOLD_EXISTING_WORK_ORDER_NO_AUTOMATIC_RETRY", "runner_invoked": False,
                "native_state": read_native_state(output), "new_ledger_created": False}
    output.mkdir(parents=True)
    native = output / "native"
    ledger, authority = create_case(native, roots=(root_purpose,), workers=("HOST_R007",),
                                     work_order_id=work_order_id, stage_id=stage_id, required_stage=True)
    W, _, _, _, _, _ = load_native()
    _milestones(ledger, authority)
    ledger.bind_purpose(root_purpose, root_purpose, identity(root_purpose), [authority])
    ledger.append("STAGE_ENTER", {"stage": stage_id}, [authority])
    ledger.reserve_attempt("LOCAL_1", root_purpose, root_purpose, "LOCAL", 30, [authority])
    stage_dir = output / "artifacts"
    stage_dir.mkdir()
    result = {"schema": "code-cli.native-host-stage/1", "stage_id": stage_id, "work_order_id": work_order_id,
              "root_purpose": root_purpose, "started_utc": now(), "evidence_class": "LOCAL_EXECUTED",
              "operation_class": "LOCAL_SYNTHETIC_OFFLINE", "budget_cost_class": "SYNTHETIC_FIXTURE",
              "only_workflow_state_writer": "EXISTING_NATIVE_WORKLEDGER", "runner_invoked": True,
              "internal_agent_control": "NOT_OBSERVED_NOT_CLAIMED", "human_signature": "NOT_PRESENT_NOT_FABRICATED"}
    try:
        payload = runner(stage_dir)
        if not isinstance(payload, dict):
            raise ValueError("HOLD_RUNNER_RESULT_MUST_BE_JSON_OBJECT")
        save(native / "STAGE_RESULT.json", {"runner_returned": True, "operation_class": "LOCAL_SYNTHETIC_OFFLINE", "result": payload})
        observed = W.evidence_ref(native, "STAGE_RESULT.json", "RECEIPT", "CODE_CLI_R007", stage_id)
        cost_ref = settle(ledger, "LOCAL_1", 0)
        ledger.append("TRACE", {"id": "HOST_RUNNER_RESULT", "trace_class": "OBSERVED", "source_cases": [observed["locator"]],
                                "parent_trace_ids": ["PURPOSE:" + root_purpose], "reason_status": "CONTEMPORARY_RECORDED",
                                "reason": "ACTUAL_FIXED_HOST_RUNNER_RETURNED_JSON; DOMAIN_HOLDS_NOT_RELEASED"}, [observed, cost_ref])
        ledger.append("STAGE_DONE", {"stage": stage_id, "passed": True, "exit_criterion": ledger.plan["stages"][0]["exit_criterion"]}, [observed])
        result.update(state="PASS_NATIVE_HOST_STAGE", runner_returned=True, result=payload, domain_hold_closure="NOT_INFERRED")
    except Exception as error:
        failure = {"runner_returned": False, "operation_class": "LOCAL_SYNTHETIC_OFFLINE", "error_type": type(error).__name__, "error": str(error), "automatic_retry": False}
        save(native / "STAGE_FAILURE.json", failure)
        observed = W.evidence_ref(native, "STAGE_FAILURE.json", "OBSERVATION", "CODE_CLI_R007", stage_id)
        ledger.append("HOLD", {"id": "RUNNER_OUTCOME_UNKNOWN", "state": "HOLD", "scope": ["INTENT_ROOT:" + root_purpose],
                               "reason": "RUNNER_DID_NOT_COMPLETE_WITH_RETAINED_RESULT", "next": "PRESERVE_BYTES_REVIEW_NO_AUTO_RETRY", "global_stop": False}, [observed])
        result.update(state="HOLD_NATIVE_RUNNER_OUTCOME_UNKNOWN", runner_returned=False, failure=failure)
    ledger.append("STOP", {"reason": "LOCAL_HOST_STAGE_SAFE_STOP"}, [observed])
    # Controlled resume is presence restoration only: no runner retry or HOLD release.
    stopped = snapshot(open_case(native))
    resumed = open_case(native)
    resumed.append("RESUME", {"presence": "CURRENT_CONFIRMED", "authority_digest": resumed.plan["authority_digest"]}, [authority_ref(native)])
    restored = snapshot(resumed)
    resumed.append("STOP", {"reason": "CONTROLLED_READBACK_COMPLETE_NO_NEW_EXECUTION"}, [authority_ref(native)])
    result["controlled_stop_resume"] = {"was_stopped": not stopped["active"], "presence_restored": restored["active"],
                                         "root_consumption_preserved": stopped["root_buckets"] == restored["root_buckets"],
                                         "unresolved_pending_preserved": stopped["pending"] == restored["pending"], "runner_retried": False}
    result["native_state"] = read_native_state(output)
    result["ended_utc"] = now()
    save(output / "NATIVE_HOST_RESULT.json", result)
    return result
