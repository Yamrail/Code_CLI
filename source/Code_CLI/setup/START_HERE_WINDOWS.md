# YamRail/Code_CLI R010 - Windows judge first-run guide

## Judge Zero-Credential Quickstart (SAMPLE_MODE=true)

Judges need no API keys or paid credentials. From this unpacked profile root in PowerShell:

```powershell
Copy-Item .env.example .env
cd .\source\Code_CLI
py -3.12 -B yr_code.py evidence verify --manifest MANIFEST.json
py -3.12 -B install.py
.\yr-code.cmd doctor
.\yr-code.cmd sample --all
.\yr-code.cmd ui
```

The CLI loads `.env` from the current directory, profile root or Code_CLI directory. Existing process variables take precedence. Without `.env`, only `SAMPLE_MODE=true` is read from `.env.example`. Explicit `sample` and console `demo` requests always select the fixed offline fixtures.

Node is preferred and is discovered on PATH, standard Windows install paths or the local runtime cache. If no Node executable is available, a stdlib-only Python projection implements the same fixed-case JSON contract. Byte, structure and SHA256 equivalence are tested against the unchanged JavaScript adapter; the actual backend is recorded in doctor and process receipts. No live provider is invoked by these commands.

Optional gateway variables are configuration examples, not new service connections or proof of a qualified Zetaris REST route. The optional judge probe remains NOT_EXECUTED unless separately requested. Existing owner-authenticated SOL selection is unchanged.

## Original guide with current R010 overrides

**Purpose:** A reviewer can install and run three deterministic, credential-free Track 3 fixtures before seeing the already-sealed real NVIDIA, Nightshift and Zetaris evidence. The installation itself becomes the first auditable work order.

This is the R010 Public setup derivative of the original R009 supplement. The current R010 archive and source manifest govern installation. Original supplements remain byte-exact in the owner handoff. This guide does not grant publication authority.

## 1. For a reviewer using Codex CLI or Claude Code

Extract the **authorized** `Code_CLI_R010_PUBLIC_MINIMALLY_WIRED.zip` to a new short, writable Windows path. Place this supplement at the extracted package root.

Give the assistant this instruction:

> Read `YR_JUDGE_WINDOWS_MOOT_BOOTSTRAP_R001.yaml`. Inspect this Windows host and execute W00 through W07, keeping a noncanonical `INSTALL_MOOT_RESULT.json` with dependencies, measured facts, failures and closure conditions. Install only missing prerequisites using standard, verified tools. Do not modify existing CAD applications or projects. Run the three credential-free Code_CLI fixtures. Treat EEA and GPL Core as separately pinned read-only public references; keep the main demo usable if those references are unavailable. Do not request API keys or make paid calls during setup. Show the resulting STOP/resume and evidence receipts. Any live API test requires an explicit separate human action.

Codex CLI and Claude Code are *installation assistants*, not required vendor dependencies of Code_CLI. If neither is present, use the following PowerShell steps directly.

## 2. Requirements and preflight

- Windows x64 (record actual build; do not assume compatibility).
- CPython **3.12 x64** for the complete bundled offline install. Python 3.11+ is enough only for the small core CLI.
- Node.js available on `PATH` for the Meterless World Model. Qualified baseline: Node **24.19.0**; other versions require a fresh compatibility check.
- No API key, GitHub access, AutoCAD license, Codex subscription or CUDA hardware is needed to run the default offline fixture set after acquiring the package.
- Avoid Windows paths of excessive length. Never extract over an existing CAD project or previous run.

Run in PowerShell:

```powershell
[Environment]::Is64BitOperatingSystem
py -3.12 --version
node --version
Get-Command git,codex,claude -ErrorAction SilentlyContinue | Select-Object Name,Source
```

Missing optional tools should become **scoped Moot HOLDs**, not a reason to abort a working offline route.

## 3. Verify, install and start the demonstration

From the extracted **judge package root**:

```powershell
cd .\source\Code_CLI
py -3.12 -B yr_code.py evidence verify --manifest MANIFEST.json
py -3.12 -B install.py
.\yr-code.cmd doctor --format json
$env:SAMPLE_MODE = 'true'
.\yr-code.cmd sample --all
.\yr-code.cmd status --format json
```

The package installer uses its included offline wheelhouse and creates a *local* `.venv`. It does not install Python itself, replace system packages or call a model provider. If `py -3.12` is absent, acquire/verify Python 3.12 using an existing trusted COTS installation channel; do not silently install an arbitrary runtime.

Expected fixture cases:

1. `CONFIRMED_CONFIG`: supported evidence proceeds through Plan, Execute and Evaluate.
2. `INSUFFICIENT_EVIDENCE`: an unsupported claim is rejected, then repaired using a different permitted source.
3. `STOP_AND_ALTERNATIVE`: STOP, WorkLedger readback, stage re-entry and retained attempt budget.

**The decisions in these cases are synthetic, but the local processes, shared World Model read projection and native journals are real executions.** Intentional UNKNOWN/HOLD inside a case is not a global installation failure. Fresh run-specific IDs, timestamps and PIDs will differ.

Original sponsor results are already in the delivered evidence; this sample does **not** make a new NVIDIA or Zetaris API request.

## 4. EEA public evaluation references

Pinned source: [Yamrail/EEA](https://github.com/Yamrail/EEA) commit `8cd2c0286213ff51b7e95587040aedef55c1181e`.

If a separately licensed snapshot is present under `reference/EEA`, inspect it. Otherwise the assistant may clone this **public** source into the reviewer workspace when network access is allowed, then check out that exact commit. To obtain both exact public commits using standard Git (optional), run `& .\FETCH_PUBLIC_REFERENCES.ps1` from the supplement directory. Preserve `LICENSE.md` and do not describe the October review as adopted normative EEA.

From the pinned `reference/EEA` directory:

```powershell
py -3.12 -B tools\yamrail_ai_work_ticket_gate.py --project-root . --run-fixtures --validate-exemplar
```

This runs 12 published test fixtures, including expected PASS, HOLD and BLOCKED decisions. It is **not** an end-to-end certification of the present judge host. EEA's published `LICENSE.md` is *not* a blanket GPL-style redistribution grant; check the right to include full EEA copies in any public judge ZIP.

## 5. GPL Core public specification reference

Pinned source: [Yamrail/Yamrail](https://github.com/Yamrail/Yamrail) commit `0d6f1532a496c2033502d11adbebdda18b11e963`.

Read (in order) the Guidebook, Core Lite v0.7.0 and Core Full v0.6.7 from `packages/core-engine/src/prompts/`. Preserve GPL-3.0 source and license notices if distributing any copy. This is a **separate public design reference**, not the current Code_CLI execution runtime and not a new authorization to change its system prompt.

EEA and GPL Core may be independently unavailable on an isolated Windows host; the main three-case Code_CLI demo must still run.

## 6. Optional live OpenAI API probe (NOT REQUIRED)

A judge never needs an API key to run the three fixtures. If an operator explicitly wants to test a live `gpt-6.1-sol` OpenAI Responses connection, use the accompanying `OPENAI_API_PROBE.py` from the package root:

```powershell
py -3.12 -B .\OPENAI_API_PROBE.py --live --out .\out\SOL_API_CONNECTIVITY_RECEIPT.json
```

The probe asks for an explicit human confirmation and accepts an existing `OPENAI_API_KEY` or a foreground masked key entry. It sends **one synthetic text request only**, with no automatic retry and no secret in the receipt. The model and project must actually be authorized; errors are not silently converted into other models. A `codex login status` showing OAuth or an authenticated session does **not** expose a reusable raw API secret to this Python probe. A Codex operator may instead use Codex's own authenticated CLI for a separate explicitly authorized live test.

Claude Code can perform the local installation but its own provider login is **not** an OpenAI API credential. Never request the judge to paste private project keys into an agent conversation.

## 7. Reviewer acceptance

The installer assistant should show these independently labeled observations: installed runtime versions; verified judge ZIP; Code_CLI Doctor; three new local fixture results and native readback; EEA's 12-case results (if inspected); GPL Core source commit and notices (if inspected); explicit optional API status; outstanding local HOLDs; and a path to the new `INSTALL_MOOT_RESULT.json`.

A reviewer can accept the **credential-free demonstration** while EEA public reference retrieval or a live paid API call remains NOT_EXECUTED. Public release, submission, canonical promotion and private-source disclosure require a separate Human Gate.

Current R009 Nightshift/Nemotron live result **supersedes older archived HOLD labels**. Use `CURRENT_NEMOTRON_CUDA_STATUS.json`, not historical archived notes, for the measured CUDA route.


R010 console: run `.\yr-code.cmd ui`. Public entry commands are `sample --all`, `evidence verify`, and `moot status`; `demo confirmed`, `demo insufficient`, and `demo stop` select individual fixed cases inside the console. Use Ctrl+L to redraw after a pseudoterminal resize. General execution and owner authentication routes are unconnected.
