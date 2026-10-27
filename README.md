# YamRail Code_CLI R010

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

Primary submission: **Track 3  -  Reasoning Architecture**. Track 1 and Track 2 are supplemental evidence. License: **A_PLUS**, limited hackathon evaluation; third-party licenses remain unchanged.

This candidate demonstrates three deterministic offline rails: CONFIRMED_CONFIG, INSUFFICIENT_EVIDENCE, and STOP_AND_ALTERNATIVE. The roles use synthetic decisions. Python/Node processes, the pinned Meterless World Model projection, and native WorkLedger journals execute locally. General autonomous coding and external tool chaining are under design review.

Read START_HERE_WINDOWS.md and YR_JUDGE_WINDOWS_MOOT_BOOTSTRAP_R001.yaml. Verify the archive against its external SHA256 receipt, use a fresh short writable path, then execute the source manifest/installer/doctor/sample/status commands. Start the console with `source/Code_CLI/yr-code.cmd ui`.

Inside the console: `sample --all`, `demo confirmed`, `demo insufficient`, `demo stop`, `moot check`, `moot status`, `evidence verify`, `manifest`, `sha256`, `tools`, `blueprint`. Enter submits; Alt+Enter inserts a newline; Ctrl+C requests a controlled stop at a settled tool boundary; `resume` continues only that suspended in-process run; Ctrl+L redraws after terminal resizing. No authority is inferred from text input. Original output and errors are retained, and completion includes an SVG/HTML blueprint plus SHA256 seal.

Public push, HackOS submission, canonical promotion, and main merge remain separate Human decisions. Existing accepted R009 measurements are historical evidence; they are not executed again by the offline demos.
