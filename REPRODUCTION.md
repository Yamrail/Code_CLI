# Reproduction and scope of the observation

The independent operator started the sealed boot candidate in a fresh WSL2
Linux guest on the same physical Windows host. This is a fresh guest test,
not evidence of an unrelated physical machine, RAM-backed storage, encrypted
scratch, zeroization, or a complete hostile-worker sandbox.

The actual boot input was Code_CLI commit
`7b0551c703aadf5da385c1ea33b24cfc6a6035f1`. Its 232-file payload manifest was
`85db5151293a5d2864a2e371dae79e487554a03e266130036a015b7486a11343`.
The input ZIP SHA256 was
`28307aa49fb5ab425306a9c412564d65a41860c5b0d7d320a5d46d29966a3570`.
The later final profile assembly adds observation/profile metadata; it does
not change the runtime code that was tested. The assembly receipts record
those exact inputs and output hashes separately.

See `evidence/observed_and_labelled/FIRST_BOOT_SUMMARY.json` for the observed
commands, individual outcomes, original receipt hashes, failures and limits.
The original full guest evidence archive remains on the trusted host and is
not imported as a current WorkLedger or shipped as author-machine journals.

Content SVG/PDF and the report PDF matched the packaged examples exactly.
The content PNG had different encoded bytes but identical decoded RGBA pixels
(2828 x 2000, zero changed pixels). Both byte hashes remain recorded; no
artifact was normalized or relabelled byte-identical. All six PDF pages and
the Japanese graph glyphs were visually checked in this observation.

Windows drives and the author's home were not mounted into the guest. The
operator ran as UID1000 with zero effective capabilities and a separate,
empty network namespace. The WSL configuration requested Windows interop OFF,
but the kernel registration was observed enabled. That mismatch remains an
explicit isolation HOLD; no global WSL/binfmt settings were changed.

The default demo executes pinned local code and current tests. It does not
generate new code with a model or control Codex internal calls. Native
WorkLedger events, real subprocess exits and byte hashes support the measured
tool/task-level supervision claim. Full Coding Agent yard routing remains
unproven.

## Reproduce on another authorized workstation

1. Unpack one profile into a new directory and read its `PACKAGE_PROFILE.json`.
2. Run `python yr_code.py evidence verify --manifest MANIFEST.json`.
3. Run `python install.py` with the supported CPython 3.12 platform.
4. Run `yr-code demo`, local recon, report and graph commands from `README.md`.
5. Keep generated `.yr-code/` and `out/` results. Use `work_handover` to bind
   prior evidence to the next operator; start a new work order after relocation.

On Linux use `python3` and `./yr-code.sh`; on Windows use `yr-code.cmd`.
The complete package is usable without GitHub or provider credentials. A Node
runtime is optional for the local Meterless World Model; missing Node is
reported rather than silently installed. The included dependency wheelhouse
does not bundle Python, Microsoft Office, AutoCAD, or model-provider access.

The media is a dated, edited capture of earlier actual local execution. Its
pre-media byte checkpoint is not the final ZIP seal. This document and the
first-boot receipt add the subsequent fresh-guest observation without
rewriting that earlier evidence.
