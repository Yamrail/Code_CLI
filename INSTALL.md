# Install and uninstall

## Supported baseline

- Core: Python 3.11+ and its standard library.
- Full local A4 report/graph: CPython 3.12 x64 on Windows x64 or Linux glibc
  x86_64 2.28+. The frozen wheelhouse includes both platforms.
- Optional Meterless World Model: Node on PATH, or an explicit `RTA_NODE`
  executable supplied by the operator. No Node binary is bundled.

The Python interpreter is a host prerequisite. All full-package Python
dependencies, their hashes, original licenses and the LGPL svglib source
archive are included. `DEPENDENCIES.json` records actual origins. Other OS,
CPU or Python ABIs require a separately reviewed dependency preparation;
the installer does not silently fetch replacements.

## Offline installation

Open a terminal in this directory:

```text
python yr_code.py evidence verify --manifest MANIFEST.json
python install.py
```

Use `python3` on Linux. Installation creates `.venv` only, disables pip indexes
and caches, verifies wheel hashes, and modifies no system Python packages.
No provider, GitHub or Autodesk key is required. Keep interrupted installation
evidence; an existing `.venv` is not automatically overwritten or retried.

The command launchers select this `.venv` when it exists. Otherwise they use
the host Python for core-only commands. On Linux a ZIP extractor should retain
the launcher executable mode; if needed run `chmod +x yr-code.sh`.

## Uninstall

```text
python uninstall.py --venv
```

This removes only the package's local `.venv` after checking the resolved
workspace boundary. Sources and `.yr-code/` / `out/` evidence remain. Archive
any wanted results before deleting an entire unpacked package yourself.

## State relocation

Move sources and frozen fixtures freely within the authorized handoff scope.
Create new journals after moving. An existing native journal is bound to its
creation location and must HOLD if moved. A hash-bound handover receipt links
prior evidence to a new work order without granting execution authority.
