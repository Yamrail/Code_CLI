# YamRail/Code_CLI English demo script

176 seconds. Silent, with timed English captions. Edited replay from current local execution, not a real-time recording.

## 0–14 seconds: YamRail/Code_CLI: a transferable work surface

An agent handover can lose intent and sources. This package keeps scoped work and native evidence together.

Evidence class: LOCAL_EXECUTED / ACTUAL HOST METADATA; no provider invocation. Source `evidence/observed_and_labelled/CLI_WINDOWS_SCOPED.json`, SHA256 `6a08df61941f87465b1159d94e6a7f5d8cc181ed419da6b5c12c418ce6924727`.

```text
$ yr-code doctor --format json
status=PASS  pid=34048  exit=0
python.version = 3.12.10; host = Windows 11 AMD64
standard_library_core = true
tools: discovered does not mean invoked or licensed
credential_values_read = false
network_requests = 0; provider_invocations = 0
Optional Node was configured explicitly for this capture.
```

## 14–36 seconds: One root budget across worker processes

The fresh local run executes 12 scoped checks. Inputs and cost units are synthetic; the subprocesses and durable state are real.

Evidence class: LOCAL_EXECUTED / SYNTHETIC_FIXTURE inputs. Source `evidence/observed_and_labelled/CLI_WINDOWS_SCOPED.json`, SHA256 `6a08df61941f87465b1159d94e6a7f5d8cc181ed419da6b5c12c418ce6924727`.

```text
$ yr-code demo --evidence-mode replay --format json
status=PASS  pid=20812  exit=0
state = PASS_SCOPED_LOCAL_COUNTEREXAMPLES
parent_child_grandchild_shared_three = true
fourth_refused = true; alias_refused = true
derived_code_fixture_reexecuted = true
world_model = PASS_LOCAL_UPSTREAM_ENGINE
new_model_generation = false; sponsor_live_calls = 0
```

## 36–56 seconds: STOP and recovery preserve uncertainty

A controlled process crash leaves UNKNOWN. Recovery refuses an automatic retry while an independent purpose continues.

Evidence class: LOCAL_EXECUTED / SYNTHETIC_FIXTURE inputs. Source `evidence/observed_and_labelled/CLI_WINDOWS_SCOPED.json`, SHA256 `6a08df61941f87465b1159d94e6a7f5d8cc181ed419da6b5c12c418ce6924727`.

```text
actual_crash_exit_23 = true
stop_restore_preserves_consumption = true
root_A_used = 3
root_B_pending_state = UNKNOWN_COMPLETION
unknown_no_automatic_retry = true
local_hold_independent_work_continues = true
sha256_tamper_refused = true
typed_graph_rejects_unknown_to_exact = true
final_safe_stop = true; active = false
```

## 56–76 seconds: Read-only recon with source bytes

The scoped fixture read flags a deliberate eval call for review. It does not execute the target or prove an exploit.

Evidence class: LOCAL_EXECUTED / SYNTHETIC_FIXTURE inputs. Source `evidence/observed_and_labelled/CLI_WINDOWS_SCOPED.json`, SHA256 `6a08df61941f87465b1159d94e6a7f5d8cc181ed419da6b5c12c418ce6924727`.

```text
$ yr-code recon local
  --root fixtures/safe_public_or_synthetic --format json
status=PASS  pid=29392  exit=0
sources = README.md, dependencies.json, sample_app.py
Each source has observed UTC, original bytes and SHA256.
sample_app.py:3 = DYNAMIC_CODE_EXECUTION_CALL
scope = REVIEW_FINDING_NOT_EXPLOIT_PROOF
target_executed = false; network_requests = 0
```

## 76–94 seconds: Build and native readback stay separate

The captured local build reports scoped PASS. Status reads the current native journal without granting new execution authority.

Evidence class: LOCAL_EXECUTED / RETAINED SOURCE FIXTURE TESTS AND NATIVE READBACK. Source `evidence/observed_and_labelled/CLI_WINDOWS_SCOPED.json`, SHA256 `6a08df61941f87465b1159d94e6a7f5d8cc181ed419da6b5c12c418ce6924727`.

```text
$ yr-code build all --format json
status=PASS  pid=26648  exit=0
state = PASS_SCOPED_LOCAL_BUILD
$ yr-code status --format json
status=PASS  pid=32256  exit=0
state = OBSERVED_NATIVE_READBACK
last_command = build all
native_state = PASS_NATIVE_DURABLE_READBACK
sponsor_live_calls = 0
```

## 94–120 seconds: Source-linked A4 report and graph

The actual reused OSINT renderer keeps citation references and visible uncertainty. A shared source never establishes causality.

Evidence class: LOCAL_EXECUTED / SYNTHETIC_FIXTURE inputs. Source `media/source_evidence/R008_RENDERER_RECEIPT.json`, SHA256 `442e2e6d611ae54e5e963fd26af079440c8734200937876151eac35a916b47c8`.

## 120–138 seconds: Verify the captured manifest scope

Byte verification confirms the captured file set. It does not establish semantic correctness, license entitlement or Human approval.

Evidence class: LOCAL_EXECUTED / ACTUAL PACKAGE BYTE VERIFICATION. Source `media/source_evidence/SOURCE_CHECKPOINT_VERIFICATION.json`, SHA256 `78c7d71235955180dc5e9d4ed536d358c58c744485fc533bb62cba4a194d9dcc`.

```text
$ yr-code evidence verify --manifest MANIFEST.json
status = PASS
verified_files = 199; verified_bytes = 45965321
manifest SHA256 = 01c9b9c852d453cae189e12e030880bc8e042ac9...
exact_inventory = true; sha256_index_verified = true
Scope: PRE-MEDIA SOURCE CHECKPOINT, not final ZIP/security cert.
Original concurrent-snapshot failure is retained by the builder.
semantic_acceptance = NOT_INFERRED; authority_effect = NONE
```

## 138–160 seconds: Live sponsor and AutoCAD limits remain explicit

World Model ran locally. Real Nightshift/NVIDIA and Zetaris requests remain unexecuted. Unverified CAD entitlement stops launch.

Evidence class: LOCAL_EXECUTED / CAPABILITY AND HOLD STATUS; live sponsor calls UNEXECUTED. Source `evidence/observed_and_labelled/CLI_WINDOWS_SCOPED.json`, SHA256 `6a08df61941f87465b1159d94e6a7f5d8cc181ed419da6b5c12c418ce6924727`.

```text
$ yr-code sponsor doctor --format json
status=HOLD  pid=31324  exit=2
nightshift_nemotron = LIVE_UNEXECUTED; zetaris = LIVE_UNEXECUTED
$ yr-code cad doctor --local-only
status=HOLD  pid=14712  exit=2
actual_product_entitlement = UNVERIFIED
autocad_launched = false; com_activated = false
cloud_fallback = false
Policy: server/cloud AutoCAD denied; no fallback/test bypass.
```

## 160–176 seconds: The package is the handoff

Transfer source, safe fixtures and labelled evidence for a fresh run. Another-machine proof and mandatory live sponsor closure remain open.

Evidence class: LOCAL_EXECUTED / SYNTHETIC_FIXTURE inputs. Source `evidence/observed_and_labelled/CLI_WINDOWS_SCOPED.json`, SHA256 `6a08df61941f87465b1159d94e6a7f5d8cc181ed419da6b5c12c418ce6924727`.

```text
Use START_HERE.md and INSTALL.md in the package.
Observed: Windows 11 / Python 3.12.10; not unrelated-machine proof
Move source and evidence; do not silently rebind active journals.
RAM/encryption and complete Agent-to-yard route: HOLD
Nightshift/NVIDIA real request and Zetaris data: HOLD
External submission and public disclosure: HUMAN_GATE_PENDING
Private construction is not Human submission approval.
```

## Claim boundary

Observed scope: Windows 11 / Python 3.12.10. This capture is not another-machine or VM proof.

Meterless upstream World Model actually ran locally. Nightshift/NVIDIA and Zetaris live requests remain UNEXECUTED/HOLD, with zero new model/provider calls in the captured journey. Current Academy rules require the actual provider/data integrations and a real Nightshift request in the demo; this offline package does not establish full contest eligibility. Cursor was not used; actual Codex construction is declared separately from product runtime.

The fresh offline workflow executes native Python processes, a controlled exit23 crash, durable STOP/RESUME and current tests of retained code fixtures. Domain inputs and cost units are synthetic. No new model generation or original model-execution receipt is imported. Only the reused WorkLedger writes local workflow state. No private/canonical ledger is imported. Source relocation supports a fresh run; relocated active journals remain HOLD pending reconciliation. This is outer task supervision, not proof of full Agent-to-yard isolation. This Windows capture explicitly configured an optional Node runtime via RTA_NODE. Doctor correctly reported Node absent from PATH; no default Node installation is claimed. The raw author path remains outside the package.

Other-machine / VM proof, RAM / encryption and full agent-to-yard routing remain HOLD.
Moved active journals stay HOLD; transfer source and evidence for a fresh run.

Optional AutoCAD is limited to user-initiated execution on the user’s own licensed interactive workstation with verified license, session and scope. Unknown means HOLD and no launch. Server/cloud execution, proxy operation, fallback and test bypass remain prohibited. Local graph/report rendering requires no AutoCAD application.
