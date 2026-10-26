# Start here

1. Unpack or clone the whole `Code_CLI` directory. Keep its source layout.
2. Run `python yr_code.py doctor --format json`. No key is needed.
3. Run `python yr_code.py evidence verify --manifest MANIFEST.json`.
4. For full report/graph support, run `python install.py` with CPython 3.12 x64.
   It installs only the bundled hash-pinned OSS wheels into a local `.venv`.
5. Run `yr-code.cmd demo` on Windows, or `./yr-code.sh demo` on Linux.
6. Run local recon and render the synthetic case using the README commands.

Read the generated run receipt and its native trace. Expected UNKNOWN/HOLD
counterexamples are retained. A local PASS does not clear sponsor, AutoCAD,
storage, release or external-submission HOLDs.

The default fixture never sends a provider request, accesses Private GitHub,
scans a network target or executes code found by recon. Optional model workers,
Node and commercial desktop applications are host dependencies, not bundled
applications. No Microsoft Office or AutoCAD license is assumed.
