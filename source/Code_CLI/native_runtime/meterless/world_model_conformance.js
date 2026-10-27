"use strict";
// Executes the byte-identical official eight-check runner against the actual
// byte-identical upstream browser reference through a four-export ESM shim.
const cp = require("node:child_process");
const path = require("node:path");
const fs = require("node:fs");
const result = cp.spawnSync(process.execPath, ["--experimental-strip-types", path.join(__dirname, "official_conformance_runner.ts")], {
  encoding: "utf8", timeout: 30000,
  env: { ...process.env, WORLD_MODEL_IMPL: path.join(__dirname, "bundle_exports.mjs") },
});
const stdout = result.stdout ?? "", stderr = result.stderr ?? "";
const cases = [...stdout.matchAll(/^\s+(PASS|FAIL) (\S+) (.*)$/gm)].map(m => ({ id: m[2], description: m[3], status: m[1] }));
const report = { schema: "yamrail.meterless-official-conformance/1", status: result.status === 0 && cases.length === 8 && cases.every(x => x.status === "PASS") ? "PASS" : "FAIL", evidence_class: "LOCAL_EXECUTED", actual_engine: "PINNED_UPSTREAM_BROWSER_REFERENCE", actual_runner: "BYTE_IDENTICAL_UPSTREAM_CONFORMANCE_RUNNER_TYPESCRIPT_ERASURE_ONLY", node: process.version, upstream_commit: "1742dec56a66e58eef9dda2d2b865823758ca8cd", inspected_utc: new Date().toISOString(), cases, stdout, stderr, exit_code: result.status, error: result.error?.message ?? null };
if (process.argv[2]) fs.writeFileSync(process.argv[2], JSON.stringify(report, null, 2) + "\n", "utf8");
process.stdout.write(JSON.stringify(report, null, 2) + "\n");
process.exitCode = report.status === "PASS" ? 0 : 1;
