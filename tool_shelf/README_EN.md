# Tool shelf and release profiles

Run `python tool_shelf/shelf_tools.py list` or `python tool_shelf/shelf_tools.py verify` from the package root. These commands use Python's standard library, run offline, and do not import recovered tools. They inspect inventory and packaged bytes only; they do not replace unavailable tools' behavior.

`TOOLS.json` indexes all 289 recovered source families and 32 overlapping named capability aliases, preserving original maturity. These are source candidates, not an installation count. An additional locally authored inventory/verifier is distinguished as an implemented adapter. Source-only, design-only and unknown entries retain their HOLDs regardless of previous PASS, FAIL or merge status.

The **hackathon_judge** candidate contains sanitized provenance/status, the inspection helper, and the specifically reviewed R008 native OSINT renderer described in `osint_runtime/README.md`. R005's unreviewed recovered objects are not included. The R008 native code remains `OWNER_RELEASE_PENDING`; its Noto-derived font has an adjacent OFL license. No private GitHub login, builder archive, author home directory or proprietary application is needed at runtime. Root's separately packaged native core provides only capabilities its own receipts establish. Missing tools remain visible; the inspection helper is an integrity/provenance alternative, not a functional substitute for them.

The **full_authorized_handoff** source set is staged separately in builder-only private storage. It contains reviewed native sources, exact SHA256/object pins and per-position origins. Unknown third-party rights, dependency/environment files, secret-like literals, private/canonical ledger instances, and author-specific absolute paths are excluded. Every omitted family retains a disposition and retrieval pins. The untouched R005 archive is outside both release profiles and is not an approved source payload.

YamRail native sources are `OWNER_RELEASE_PENDING`, not silently assigned an open-source license. A named collaborator scope and owner release authority are still required before transfer. Unknown license metadata never grants redistribution. No new source or test result promotes historical maturity, no copied tool grants execution/network authority, and no worker signature is Human approval.

See `../LICENSES_AND_PROVENANCE.csv`, `../SBOM.json`, and `profiles/`. The builder's detailed transfer report is for the private assembler and is not required at runtime.
