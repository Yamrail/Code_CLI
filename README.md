# YamRail/Code_CLI

A transferable local research and coding workyard for a technical operator.
Receive a scoped work order, inspect source evidence, run the existing Ingridge
WorkLedger/Intent Guard, render a source-linked A4 graph, and hand the result to
the next operator. The native WorkLedger is the only workflow state writer.

This is a **Private release candidate**, with explicit sponsor, license,
isolation and external-submission HOLDs. It is not a production qualification.

## Start without keys

Unpack or clone this directory. No access to the author's Private repositories,
home directory, account or credentials is needed to execute the packaged code.
Python 3.11+ runs the standard-library core. CPython 3.12 x64 runs the included
offline graph dependency wheelhouse on Windows x64 or Linux glibc x86_64.

```powershell
python yr_code.py doctor --format json
python yr_code.py evidence verify --manifest MANIFEST.json
python install.py
.\yr-code.cmd demo --evidence-mode replay
.\yr-code.cmd recon local --root fixtures/safe_public_or_synthetic
.\yr-code.cmd graph render --input fixtures/osint_case.json --type content --paper a4-landscape --out out/graph
.\yr-code.cmd report make --input fixtures/osint_case.json --paper a4-landscape --out out/report
.\yr-code.cmd status --format json
```

On Linux use `python3` and `./yr-code.sh`. See [INSTALL.md](INSTALL.md) and
[START_HERE.md](START_HERE.md). Every run uses a fresh directory. Existing runs
are not automatically retried. Use `work_handover --run <local-run-directory>`
to create a next-worker receipt after native readback.

## Observed behavior

- Existing R003 parent/child/grandchild admission consumes one three-attempt
  root. A fourth request and an alias are denied. Synthetic worker roles and
  budget units are labelled.
- A real controlled process exit after reservation restores UNKNOWN/HOLD.
  An independent purpose continues; unknown external completion is not retried.
- Recovered safe code is tested locally. Default replay generates no new model
  output and imports no original private/canonical ledger.
- Local recon hashes a packaged synthetic target and reports static findings
  without running its code or sending network requests.
- The report/graph path reuses pinned YamRail/OSINT renderers. A4 landscape
  SVG/PNG/PDF, source bindings and receipts are local outputs. UNKNOWN/HOLD and
  relation types remain visible; reference relations do not prove causation.

The independently operated fresh Linux/WSL2 guest also completed the
offline installation and 18 scoped function checks, including the 12 core
counterexamples, graph/report generation and handover. It used the same
physical host; isolation limitations and retained failures are explicit.
See [REPRODUCTION.md](REPRODUCTION.md) and the hash-bound first-boot receipt.

## Sponsor and CAD boundaries

Meterless's pinned upstream World Model can execute locally when Node is
available on PATH or explicitly configured as `RTA_NODE`. Native WorkLedger
events remain authoritative; the World Model is a derived read projection.
Nightshift/NVIDIA Nemotron and Zetaris **lack live request/query receipts**.
Adapters, offline output and loopback tests do not establish contest eligibility.
`sponsor doctor` makes no provider call and emits no credential values.

AutoCAD is **OFF by default**. `cad doctor --local-only` is a read-only admission
check. Actual local product entitlement and the interactive user broker remain
unqualified, so `cad open/export` hold without launching AutoCAD. Server/cloud,
remote automation and AutoLISP/script autoload are denied with no fallback.
Graph/report generation needs no AutoCAD or Autodesk account.

## Sources and extension

R005 fixed closing commit `95322eb461cb251c6ed6c837bbb1f3e0d34c69e1`, received
R006/R007/R008 orders, native runtime imports, OSINT source locks, dependency
licenses and per-tool maturity are preserved in the package's provenance files.
Existing YamRail code and this competition's adapters are declared separately.
Unknown or unreviewed third-party redistribution rights exclude recovered code
from the judge payload; every omitted family has a disposition and alternative.
Tool import is not installation, execution or egress authority.

Add a deterministic host runner using `adapters.native_host.supervise_stage`.
Keep source evidence immutable, add tests for the relevant boundary, then start
a fresh scoped work order. Read [AGENT_BOUNDARY.md](AGENT_BOUNDARY.md) before
attaching a model worker. Unimplemented command vocabulary returns
`NOT_EXECUTED`/HOLD and dispatches nothing.

## Candidate delivery

`MANIFEST.json` and `SHA256SUMS.txt` bind finite package bytes. Runtime `.yr-code/`,
`out/`, `.venv/`, cache directories and Git metadata are outside that seal.
`media/demo.mp4` and `media/slides.pptx` describe the measured current scope.
Hash agreement is not Human approval, source-release authority or semantic
acceptance. Separate Human artifacts are required for external submission,
public push, Private-source disclosure, new paid calls and canonical promotion.
