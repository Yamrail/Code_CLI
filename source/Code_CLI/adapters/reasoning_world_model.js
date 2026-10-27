"use strict";
// R009 glue around the unchanged, pinned Meterless reference. No durable store.
const fs = require("node:fs");
const crypto = require("node:crypto");
const assert = require("node:assert/strict");
const { loadReference } = require("../native_runtime/meterless/world_model_bridge.js");
const { WorldModel } = loadReference();
const hash = value => crypto.createHash("sha256").update(value).digest("hex");

async function project(input) {
  assert.equal(input.source_of_truth, "EXISTING_NATIVE_WORKLEDGER");
  const world = new WorldModel({ storage: "memory", namespace: "code-cli-r009-derived", conflictPolicy: "most-recent-wins" });
  const source = {kind: "native-workledger-readback", at: input.observed_utc, by: "INGRIDGE_HOST", url: "workledger:sha256:" + input.journal_sha256};
  const work = await world.upsertEntity({type: "work-order", externalKey: {system: "workledger", id: input.case_id}, attrs: {native_checkpoint: input.checkpoint, budget: input.root_buckets}, source});
  const workerIds = {};
  for (const role of ["PLANNER", "EXECUTOR", "EVALUATOR"]) {
    workerIds[role] = (await world.upsertEntity({type: "worker-role", externalKey: {system: "workledger", id: role}, attrs: {execution: "DETERMINISTIC_SAMPLE_PROCESS"}, source})).id;
  }
  for (const record of input.records) {
    const origin = {kind: "native-recorded-worker-output", at: record.produced_utc, by: record.role, url: "workledger:trace:" + record.trace_id, runId: input.case_id};
    await world.upsertEntity({type: "work-order", externalKey: {system: "workledger", id: input.case_id}, attrs: {last_role: record.role, last_trace: record.trace_id}, source: origin});
    await world.relate({from: work.id, type: "delegated-to", to: workerIds[record.role], validFrom: record.produced_utc, source: origin});
    if (record.selected_source) await world.assertFact({about: work.id, predicate: "selected_source", value: record.selected_source, source: origin});
    if (record.assessment) await world.assertFact({about: work.id, predicate: "assessment", value: record.assessment, source: origin});
    if (record.critique) await world.assertFact({about: work.id, predicate: "critique", value: record.critique, source: origin});
  }
  const shape = world.stateShape();
  return {
    schema: "yamrail.r009.shared-world-model/1", engine: "Meterless World Model pinned upstream reference",
    upstream_commit: "1742dec56a66e58eef9dda2d2b865823758ca8cd", execution_class: "LOCAL_EXECUTED",
    input_class: "SYNTHETIC_FIXTURE", source_of_truth: "EXISTING_NATIVE_WORKLEDGER", canonical_writes: 0,
    derived_memory_only: true, source_journal_sha256: input.journal_sha256, native_checkpoint: input.checkpoint,
    case_state: world.view("graph").entity(work.id).attrs, facts: shape.facts,
    relationships: shape.relationships, audit: world.audit(),
    derived_state_sha256: hash(world.stateShapeCanonical()),
    authority_semantics: "Worker reports and supersession are observations, not Human approval or proof of claim truth."
  };
}

async function conformance() {
  const checks = {};
  const world = new WorldModel({storage: "memory", namespace: "r009-conformance", conflictPolicy: "most-recent-wins"});
  const s = (at, by) => ({kind: "SYNTHETIC_CONFORMANCE_FIXTURE", at, by});
  const t0 = "2026-10-22T00:00:00.000Z", t1 = "2026-10-22T00:00:01.000Z", t2 = "2026-10-22T00:00:02.000Z";
  let denied = false;
  try { await world.upsertEntity({type: "case", externalKey: {system: "fixture", id: "missing"}}); } catch (_) { denied = true; }
  checks.provenance_required = denied;
  const a = await world.upsertEntity({type: "case", externalKey: {system: "fixture", id: "A"}, name: "same label", attrs: {planned: true}, source: s(t0, "PLANNER")});
  const b = await world.upsertEntity({type: "case", externalKey: {system: "fixture", id: "B"}, name: "same label", source: s(t0, "PLANNER")});
  checks.explicit_identity_prevents_name_merge = a.id !== b.id;
  const updates = await Promise.all([
    world.upsertEntity({type: "case", externalKey: {system: "fixture", id: "A"}, attrs: {executed: true}, source: s(t1, "EXECUTOR")}),
    world.upsertEntity({type: "case", externalKey: {system: "fixture", id: "A"}, attrs: {evaluated: true}, source: s(t2, "EVALUATOR")})
  ]);
  checks.concurrent_updates_serialized = updates[0].id === a.id && updates[1].id === a.id && world.view("graph").entity(a.id).attrs.executed && world.view("graph").entity(a.id).attrs.evaluated;
  const first = await world.assertFact({about: a.id, predicate: "assessment", value: "UNSUPPORTED_READY_CLAIM", source: s(t1, "EXECUTOR")});
  const second = await world.assertFact({about: a.id, predicate: "assessment", value: "HOLD_MISSING_EVIDENCE", source: s(t2, "EVALUATOR")});
  const shape = world.stateShape();
  checks.conflicting_history_preserved = shape.facts.length === 2;
  checks.supersession_points_to_actual_fact = shape.facts.find(x => x.id === first.id).supersededBy === second.id;
  checks.critique_changes_shared_view = world.view("graph").entity(a.id).attrs.assessment === "HOLD_MISSING_EVIDENCE";
  await world.relate({from: b.id, type: "depends-on", to: a.id, source: s(t2, "PLANNER")});
  checks.typed_relation_resolves = world.view("graph").neighborsOf(b.id, {via: "depends-on"}).some(x => x.id === a.id);
  checks.canonical_shape_repeatable = world.stateShapeCanonical() === world.stateShapeCanonical();
  checks.audit_preserves_actor_provenance = world.audit().some(x => JSON.stringify(x).includes("EVALUATOR"));
  for (const [name, ok] of Object.entries(checks)) assert.ok(ok, name);
  return {schema: "yamrail.r009.world-model-scoped-conformance/1", state: "PASS_REFERENCE_API_CONFORMANCE", checks,
    scope: "R009-authored contract tests against the pinned upstream engine, not an organizer-issued certification suite",
    upstream_commit: "1742dec56a66e58eef9dda2d2b865823758ca8cd", execution_class: "LOCAL_EXECUTED", inputs: "SYNTHETIC_FIXTURE", provider_calls: 0, canonical_writes: 0};
}

module.exports = {project, conformance};
if (require.main === module) {
  const task = process.argv[2] === "--conformance" ? conformance() : project(JSON.parse(fs.readFileSync(process.argv[2], "utf8")));
  task.then(x => process.stdout.write(JSON.stringify(x) + "\n")).catch(error => {process.stderr.write(error.name + ": " + error.message + "\n"); process.exitCode = 1;});
}
