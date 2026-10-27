"""Fresh local fixtures around the existing WorkLedger; never a second ledger.

Source and code fixtures are portable. Existing native journals remain bound to
their original host path: relocation is a HOLD, never a silent rebind.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import importlib
import json
import os
from pathlib import Path
import sys
import uuid
from adapters.portable_io import safe_read,admit_path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PAYLOAD = HERE / "payload"
MANIFEST_SHA256 = "7412bd44746d3e38146d5ba59186e940eb312ba23f052efcd8e44d49eb3b594f"
IMPORT_PINS_SHA256 = "b1be7aabce2903d9622e57a978a6a9bea21a9950e7c29cd6aff780318e5cf0ba"
NATIVE_PARENT = "16404870b12c375d3c899113cce46f087e3b1546"
R007_AUTHORITY = {'source': 'PUBLIC_REVIEWER_FIXED_LOCAL_FIXTURE_ORDER', 'policy': 'setup/YR_JUDGE_WINDOWS_MOOT_BOOTSTRAP_R001.yaml', 'scope': 'LOCAL_FIXED_DEMOS_ONLY', 'owner_authority_exported': False, 'commit': 'LOCAL_FIXED_MANIFEST_SHA256:7412bd44746d3e38146d5ba59186e940eb312ba23f052efcd8e44d49eb3b594f', 'commit_field_semantics': 'Legacy schema field binds the local fixed manifest; it is not a Git commit or a remote storage claim'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_native():
    raw = safe_read(PAYLOAD, "BUILD_MANIFEST.json")
    if sha(raw) != MANIFEST_SHA256:
        raise RuntimeError("HOLD_NATIVE_SOURCE_MANIFEST_PIN")
    manifest = json.loads(raw)
    for relative, expected in manifest["files"].items():
        if sha(safe_read(PAYLOAD,relative)) != expected:
            raise RuntimeError("HOLD_NATIVE_SOURCE_HASH:" + relative)
    expected_python = {relative for relative in manifest["files"] if relative.endswith(".py")}
    actual_python = {path.relative_to(PAYLOAD).as_posix() for path in PAYLOAD.rglob("*.py")}
    if actual_python != expected_python:
        raise RuntimeError("HOLD_NATIVE_EXECUTABLE_INVENTORY")
    for name in ("implementation", "yr_tools"):
        existing = sys.modules.get(name)
        if existing is not None and not Path(existing.__file__).resolve().is_relative_to(PAYLOAD.resolve()):
            raise RuntimeError("HOLD_NATIVE_MODULE_NAMESPACE:" + name)
    location = str(PAYLOAD)
    if location not in sys.path:
        sys.path.insert(0, location)
    workstate = importlib.import_module("implementation.workstate")
    guard = importlib.import_module("implementation.intent_budget")
    shelf = importlib.import_module("implementation.shelf_witness")
    binder = importlib.import_module("implementation.reused.binder")
    return workstate, guard, shelf.EvidenceShelfWitness, binder.canonical, binder.digest, binder.ContractError


def identity(label):
    _, guard, _, _, _, _ = load_native()
    return {name: ["code-cli/synthetic/" + label + "/" + name] for name in guard.IDENTITY_FIELDS}

def _source_inventory(directory,relative_to):
    admit_path(directory);files=set()
    for folder,dirs,names in os.walk(directory,followlinks=False):
        for d in dirs:admit_path(Path(folder)/d)
        for name in names:
            path=admit_path(Path(folder)/name)
            if not path.is_file():raise RuntimeError("HOLD_NONREGULAR_SOURCE_INVENTORY")
            files.add(path.relative_to(relative_to).as_posix())
    return files


def verify_code_fixture(name, *, auxiliary=False):
    """Verify a code-only input before execution, against the imported pins."""
    raw=safe_read(HERE,"IMPORT_PINS.json")
    if sha(raw)!=IMPORT_PINS_SHA256:
        raise RuntimeError("HOLD_CODE_FIXTURE_PIN_MANIFEST_ANCHOR")
    pins = json.loads(raw)
    group = "auxiliary" if auxiliary else "fixtures"
    if name not in pins.get(group, {}):
        raise RuntimeError("HOLD_UNREGISTERED_CODE_FIXTURE:" + name)
    directory = HERE if auxiliary else HERE / "fixtures"
    if not auxiliary:
        actual=_source_inventory(directory,directory)
        if actual!=set(pins['fixtures']):raise RuntimeError("HOLD_CODE_FIXTURE_EXACT_INVENTORY")
    elif name.startswith('meterless/'):
        expected={p for p in pins['auxiliary'] if p.startswith('meterless/')}
        actual=_source_inventory(HERE/'meterless',HERE)
        if actual!=expected:raise RuntimeError("HOLD_AUXILIARY_EXECUTABLE_INVENTORY")
    path=admit_path(directory/name)
    if sha(safe_read(directory,name)) != pins[group][name]:
        raise RuntimeError("HOLD_CODE_FIXTURE_HASH:" + name)
    return path


def _context(base, worker=None):
    _, guard, Witness, _, _, _ = load_native()
    metadata = json.loads((base / "RUN_METADATA.json").read_bytes())
    if not isinstance(metadata, dict) or metadata.get("schema") != "code-cli.fresh-native-work-order/1" or metadata.get("data_origin") != "FRESH_LOCAL_SYNTHETIC_RUNTIME_STATE":
        raise ValueError("HOLD_NOT_CURRENT_LOCAL_NATIVE_STATE")
    worker = worker or metadata["workers"][0]
    witness = Witness(base / "evidence_shelf", metadata["ledger_id"])
    if witness.root.exists():
        # The retained native genesis records ledger_root but its read-only
        # verifier does not compare that field. Enforce the R007 host boundary
        # here without changing/rebinding the retained native shelf bytes.
        shelf = importlib.import_module("implementation.shelf_witness")
        genesis = witness.records()[0]
        if shelf.path_key(genesis.get("ledger_root", "")) != shelf.path_key(base / "ledger"):
            raise ValueError("HOLD_SHELF_NATIVE_JOURNAL_RELOCATED_FRESH_RUN_REQUIRED")
    return guard.Context(metadata["ledger_id"], base / "ledger", (base / "ROOT_POLICY.json").read_bytes(), worker,
                         witness, {},
                         lambda: {"state": "CURRENT", "key_ids": [], "approval_ids": []}, now,
                         environment="SYNTHETIC_FIXTURE")


def create_case(base, *, roots=("ROOT_A", "ROOT_B", "ROOT_C"), workers=("W1", "W2", "W3"),
                work_order_id="CODE-CLI-R007-SYNTHETIC-DEMO", stage_id="LOCAL_COUNTEREXAMPLE", required_stage=False):
    base = Path(base).resolve()
    base.mkdir(parents=True, exist_ok=False)
    W, _, _, canonical, digest, _ = load_native()
    workers = tuple(workers)
    metadata = {"schema": "code-cli.fresh-native-work-order/1", "ledger_id": "CODECLI_" + uuid.uuid4().hex,
                "work_order_id": work_order_id, "data_origin": "FRESH_LOCAL_SYNTHETIC_RUNTIME_STATE",
                "workers": list(workers), "created_utc": now(), "archived_private_ledger_imported": False,
                "host_bound_native_journal": True, "relocation": "RELOCATED_EXISTING_JOURNAL_MUST_HOLD; RUN_A_NEW_WORK_ORDER"}
    save(base / "RUN_METADATA.json", metadata)
    registry = {"schema": "yr.intent-root-registry/3", "environment": "SYNTHETIC_FIXTURE", "host_workers": list(workers),
                "roots": {root: {"identity": identity(root), "max_attempts": 3, "max_cost_minor": 100,
                                  "currency": "USD", "minor_exponent": 6, "workers": list(workers),
                                  "operations": {"LOCAL": {"upper_cost_minor": 30, "effect_revision": "CODE_CLI_LOCAL_OFFLINE_R007"}}}
                          for root in roots}}
    (base / "ROOT_POLICY.json").write_bytes(canonical(registry))
    authority = {"source": "REVIEWER_LOCAL_FIXED_FIXTURE_ENVELOPE", "parent_order": R007_AUTHORITY,
                 "local_work_order_id": work_order_id, "new_local_subjob_remote_stored": False,
                 "allowed": "LOCAL_SYNTHETIC_OFFLINE_TOOL_EXECUTION", "authority_effect": "NONE",
                 "human_signature": "NOT_PRESENT_NOT_FABRICATED", "canonical_promotion": False,
                 "external_submission": False, "paid_provider_authority": "NOT_GRANTED"}
    save(base / "AUTHORITY.json", authority)
    (base / "HOST_IMPLEMENTATION.py").write_bytes(Path(__file__).read_bytes())
    ref = W.evidence_ref(base, "AUTHORITY.json", "AUTHORITY", "CODE_CLI_R007", metadata["ledger_id"])
    implementation = W.evidence_ref(base, "HOST_IMPLEMENTATION.py", "SOURCE", "CODE_CLI_R007", "HOST_BINDING")
    plan = {"schema": "ingridge.workplan/1", "subject": metadata["ledger_id"], "subject_revision": "CODE_CLI_R007",
            "incoming_revision": "PUBLIC_LOCAL_FIXED_FIXTURE_ORDER", "parent_commit": NATIVE_PARENT,
            "authority_digest": digest(authority), "authority_effect": "NONE",
            "intent_budget": {"schema": "yr.intent-budget/3", "ledger_id": metadata["ledger_id"], "policy_sha256": sha(canonical(registry))},
            "stages": [{"id": stage_id, "scope": ["INTENT_ROOT:" + root for root in roots], "dependencies": [],
                        "inputs": [ref], "outputs": [], "joints": {}, "required_joints": [], "implementation": [implementation],
                        "exit_criterion": "HOST_LOCAL_RUNNER_RETURNED_WITH_RETAINED_BYTES", "next_if_hold": "PRESERVE_BYTES_NO_AUTOMATIC_RETRY",
                        "disposition": "IMPLEMENTED", "required_for_delivery": required_stage,
                        "output_contracts": [{"locator": "STAGE_RESULT.json", "subject": stage_id, "revision": "CODE_CLI_R007",
                                              "record_class": "RECEIPT", "required_result_fields": {"runner_returned": True, "operation_class": "LOCAL_SYNTHETIC_OFFLINE"}}]}]}
    save(base / "PLAN.json", plan)
    ledger = W.WorkLedger(base, plan, base / "ledger", _context(base))
    ledger.append("RESUME", {"presence": "CURRENT_CONFIRMED", "authority_digest": plan["authority_digest"]}, [ref])
    return ledger, ref


def open_case(base, worker=None):
    base = Path(base).resolve()
    W, _, _, _, _, _ = load_native()
    return W.WorkLedger.open_existing(base, json.loads((base / "PLAN.json").read_bytes()), base / "ledger", _context(base, worker))


def authority_ref(base):
    W, _, _, _, _, _ = load_native()
    metadata = json.loads((Path(base) / "RUN_METADATA.json").read_bytes())
    return W.evidence_ref(base, "AUTHORITY.json", "AUTHORITY", "CODE_CLI_R007", metadata["ledger_id"])


def snapshot(ledger):
    _, guard, _, _, _, _ = load_native()
    return {"root_buckets": guard.projection(ledger.state, ledger.intent_context), "active": ledger.state["active"],
            "epoch": ledger.state["epoch"], "holds": ledger.state["holds"], "pending": ledger.state["pending"],
            "purposes": guard.intent_bindings(ledger.state), "checkpoint": ledger.checkpoint,
            "stages": ledger.state["stages"], "native_revision": ledger.state["revision"],
            "traces": ledger.state["traces"]}


def settle(ledger, attempt, amount=0):
    W, _, _, _, _, _ = load_native()
    pending = ledger.state["pending"][attempt]
    receipt = {"id": attempt, "origin_epoch": pending["origin_epoch"], "effect_revision": pending["effect_revision"],
               "scope": pending["scope"], "actual_minor": amount, "currency": "USD", "minor_exponent": 6, "completion": "OBSERVED"}
    filename = "receipt-" + attempt + ".json"
    save(ledger.base / filename, receipt)
    ref = W.evidence_ref(ledger.base, filename, "RECEIPT", "CODE_CLI_LOCAL_OFFLINE_R007", attempt)
    ledger.observe_actual_cost(receipt, [ref], observer_class="SYNTHETIC_FIXTURE")
    ledger.settle_attempt(attempt, amount, "USD", receipt, [ref])
    return ref


def refused(function, expected):
    *_, ContractError = load_native()
    try:
        function()
    except ContractError as error:
        if expected not in str(error):
            raise AssertionError((expected, str(error))) from error
        return str(error)
    raise AssertionError("Expected refusal: " + expected)
