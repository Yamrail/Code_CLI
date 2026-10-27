"use strict";
// YamRail RTA integration glue. Meterless reference remains byte-identical.
// The only durable source is the caller's native WorkLedger journal.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");
const { TextEncoder } = require("node:util");

function loadReference() {
  const code = fs.readFileSync(path.join(__dirname, "meterless-world-model-reference.js"), "utf8");
  const scope = { TextEncoder, structuredClone };
  vm.runInNewContext(code + "\n;globalThis.referenceExports=MeterlessWorldModel;", scope, { timeout: 3000 });
  return scope.referenceExports;
}

function canonical(value) {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (value && typeof value === "object") return "{" + Object.keys(value).sort().map(k => JSON.stringify(k) + ":" + canonical(value[k])).join(",") + "}";
  return JSON.stringify(value);
}

function rows(collection) {
  if (collection == null) return [];
  if (Array.isArray(collection)) return collection.map(row => {
    const item = row && typeof row === "object" ? row : { value: row };
    const key = item.id ?? item.purpose_id ?? item.root_purpose_id ?? item.root_id ?? item.event_id ?? item.seq;
    return [key == null ? crypto.createHash("sha256").update(canonical(item)).digest("hex") : String(key), item];
  });
  if (typeof collection === "object") return Object.entries(collection).sort(([a], [b]) => a.localeCompare(b)).map(([key, row]) => [key, row && typeof row === "object" ? row : { value: row }]);
  throw new Error("World Model bridge: collections must be arrays or keyed objects");
}

async function project(input) {
  if (!input || !input.source || typeof input.source.kind !== "string" || !input.source.kind || typeof input.source.at !== "string" || !Number.isFinite(Date.parse(input.source.at))) {
    throw new Error("World Model bridge: source.kind and valid source.at are required; provenance cannot be fabricated");
  }
  const source = { ...input.source, by: input.source.by ?? "yamrail-readonly-bridge" };
  const { WorldModel } = loadReference();
  const world = new WorldModel({ storage: "memory", namespace: "yamrail-workledger-derived", clock: () => new Date(source.at) });
  const index = new Map(), facts = [];
  const groups = [["root-bucket", input.root_buckets], ["purpose", input.purposes], ["hold", input.holds], ["pending", input.pending], ["native-event", input.events]];
  if (input.checkpoint != null) groups.push(["checkpoint", { checkpoint: input.checkpoint }]);
  const sourceRecords = [];
  for (const [type, collection] of groups) {
    for (const [key, row] of rows(collection)) {
      const attrs = { native_key: key, native_record: row };
      const entity = await world.upsertEntity({ type, externalKey: { system: "workledger", id: key }, attrs, source });
      index.set(type + "\0" + key, entity.id);
      sourceRecords.push({ type, key, row, id: entity.id });
      facts.push(await world.assertFact({ about: entity.id, predicate: "native-record-observed", value: row, source }));
    }
  }
  const relationships = [], unresolved = [];
  async function link(from, type, to, nativeTarget) {
    if (!to) { unresolved.push({ from, type, native_target: nativeTarget, state: "UNKNOWN_UNRESOLVED_REFERENCE" }); return; }
    relationships.push(await world.relate({ from, type, to, source, validFrom: source.at }));
  }
  for (const record of sourceRecords) {
    const { type, row, id } = record;
    // Only explicit IDs create edges. Names and worker labels cannot merge budgets.
    const root = row.root_id ?? row.root_purpose_id ?? row.root_intent_id;
    if (root != null && type !== "root-bucket") await link(id, "shares-root-budget", index.get("root-bucket\0" + root), String(root));
    const parent = row.parent_id ?? row.parent_purpose_id;
    if (parent != null && type === "purpose") await link(id, "child-of", index.get("purpose\0" + parent), String(parent));
  }
  const graph = world.view("graph");
  const lineage = sourceRecords.filter(r => r.type === "purpose").map(r => ({
    purpose_id: r.key,
    entity_id: r.id,
    ancestors: graph.traverse(r.id, { via: "child-of", direction: "ancestors", maxDepth: sourceRecords.length + 1 }).map(e => e.attrs.native_key),
    root_buckets: graph.neighborsOf(r.id, { via: "shares-root-budget" }).map(e => e.attrs.native_key),
  }));
  const shape = world.stateShape();
  // Cross-realm reference objects become an ordinary JSON transport contract.
  return JSON.parse(JSON.stringify({
    schema: "yamrail.meterless-world-model-derived-view/1",
    engine: "Meterless World Model upstream browser reference",
    upstream_commit: "1742dec56a66e58eef9dda2d2b865823758ca8cd",
    evidence_class: "LOCAL_EXECUTED",
    input_evidence_class: input.evidence_class ?? "UNKNOWN",
    source_of_truth: "NATIVE_WORKLEDGER_ONLY",
    ephemeral_derived_view: true,
    canonical_writes: 0,
    source,
    source_input_sha256: crypto.createHash("sha256").update(canonical(input)).digest("hex"),
    entities: graph.query({}), facts, relationships, lineage, unresolved,
    audit: world.audit(),
    derived_state_sha256: crypto.createHash("sha256").update(world.stateShapeCanonical()).digest("hex"),
    derived_state: shape,
    assertion_semantics: "Copied native observations; no Human approval, truth judgment, provider execution, or sponsor eligibility inferred",
  }));
}

module.exports = { loadReference, project };
if (require.main === module) {
  const raw = process.argv[2] ? fs.readFileSync(process.argv[2], "utf8") : fs.readFileSync(0, "utf8");
  project(JSON.parse(raw)).then(result => process.stdout.write(JSON.stringify(result, null, 2) + "\n")).catch(error => { process.stderr.write(error.message + "\n"); process.exitCode = 1; });
}
