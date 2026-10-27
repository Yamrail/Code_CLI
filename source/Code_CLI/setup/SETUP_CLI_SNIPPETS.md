# Current zero-credential snippets

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

## Earlier setup snippets (retained for reference)

# Verified Windows setup route

Policy source: `YR_JUDGE_WINDOWS_MOOT_BOOTSTRAP_R001.yaml`. Originals are retained unchanged. R010 binding: `R010_SETUP_BINDING.json`.

Use a new short writable path, existing CPython 3.12 x64 and a compatible Node runtime. Set `RTA_NODE` explicitly if that existing runtime is outside PATH. Never replace system runtimes or existing projects.

```powershell
cd .\source\Code_CLI
py -3.12 -B yr_code.py evidence verify --manifest MANIFEST.json
py -3.12 -B install.py
.\yr-code.cmd doctor --format json
$env:SAMPLE_MODE = "true"
.\yr-code.cmd sample --all
.\yr-code.cmd status --format json
.\yr-code.cmd moot check --format json
.\yr-code.cmd ui
```

In the console: `demo confirmed`, `demo insufficient`, `demo stop`, `moot status`, `evidence`, `manifest`, `sha256`, `tools`, `blueprint`. Enter submits; Alt+Enter adds a newline; Ctrl+C requests a controlled STOP at the next completed tool boundary. `resume` restarts only a cooperatively suspended in-process rail. A killed or unknown run is never replayed automatically.

Codex CLI / Claude Code instruction: "Read the bootstrap YAML and binding; inspect this host, execute W00-W07 and retain actual results in INSTALL_MOOT_RESULT.json. Run three credential-free fixtures, preserve failed results, and show STOP/RESUME evidence. Do not copy credentials, overwrite global agent configuration, or request a live API call during setup."

The optional original API probe defaults to NOT_EXECUTED. Owner CAD verification uses the separately authorized authenticated Codex CLI route; the judge probe remains optional.
