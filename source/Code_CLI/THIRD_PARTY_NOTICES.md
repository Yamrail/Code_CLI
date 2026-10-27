# Third-party notices

YamRail-owned code is under A_PLUS. Third-party rights remain unchanged.

* prompt_toolkit 3.0.52  -  BSD-3-Clause, Jonathan Slenders and contributors. Exact LICENSE and AUTHORS: dependency_licenses/prompt_toolkit/.
* wcwidth 0.2.13  -  MIT, Jeff Quast and contributors. Exact LICENSE: dependency_licenses/wcwidth/.
* Meterless World Model, upstream commit 1742dec56a66e58eef9dda2d2b865823758ca8cd  -  Apache-2.0, Meterless contributors. Exact source extract, provenance and license retained in native_runtime/meterless/. A complete upstream tree inspection found no NOTICE file at that pin; the existing LICENSE is retained.

CPython and Node are host prerequisites and are not redistributed. EEA uses custom publisher terms; the GPL Core specification is an independently licensed public reference. Only pinned links are provided; no full snapshots, prompt injection or runtime adoption is performed. The owner renderer, proprietary apps, service SDKs, model binaries, and original private ledgers are not in this tree.


The stdlib Python fallback in adapters/reasoning_world_model.py derives the fixed upsert, relation, fact-conflict and canonical-state operations from the pinned Meterless reference under Apache-2.0. Its projection contract matches the unchanged JS adapter; it is not an execution of that JavaScript runtime. The original Apache license remains in native_runtime/meterless/LICENSE-Meterless.txt.
