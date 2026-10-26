#!/usr/bin/env python3
"""
YamRail A/B Typed Graph Evaluator prototype.

A = Authority / Jurisdiction / Temporal-validity
B = Identity / Lifecycle / Material-lineage

The evaluator is deterministic and non-adjudicative. It detects known unsafe
edge substitutions and closure collapses; it does not decide legal rightness,
object identity, or domain acceptance.
"""

from datetime import date, datetime


VERSION = "0.1.0"
UNKNOWNISH = {"UNKNOWN", "HOLD", "NOT_FOUND", "UNREACHABLE", "OPEN", "MIXED_OR_OPEN", "INTERVAL_ONLY", "UNRESOLVED", "UNRESOLVED_SUCCESSOR_OR_ESTATE", "NONE", ""}
EXACT_OR_CLOSED = {"OBSERVED", "CLOSED", "EXACT", "PASS", "KNOWN"}

# Typed edge substitution registry. If the target edge is asserted solely from
# one of these edge families, the graph is structurally under-supported.
FORBIDDEN_DERIVATIONS = {
    # Lane A
    "SHIP_REGISTRY": {"STATE_CONTINUATION"},
    "PROPERTY_TITLE": {"PORT_CONTROL", "PORT_ENTRY", "OWNER_EXTINCTION", "CUSTODY", "REMOVAL_POWER"},
    "DISPOSAL_POWER": {"PORT_CONTROL", "REMOVAL_POWER", "CUSTODY"},
    "ABANDONMENT": {"OWNER_EXTINCTION"},
    "PHYSICAL_STATE": {"STATE_CONTINUATION", "SHIP_REGISTRY", "FLAG_TERMINATION"},
    "CAUSAL_SUCCESSION": {"TIME_ORDER", "TEMPORAL_OVERLAP"},
    # Lane B
    "HULL_IDENTITY": {"NAME_IDENTITY", "CLASSIFICATION", "SERVICE_IDENTITY", "ORIGINAL_MATERIAL_FRACTION"},
    "COMMISSION_EVENT": {"LAUNCH_EVENT", "TRANSFER_EVENT"},
    "PHYSICAL_END": {"DECOMMISSION_EVENT", "RETURN_EVENT", "SERVICE_END"},
    "VESSEL_ALLOCATION": {"PROGRAM_BUDGET"},
    "EVENT_TIME": {"DOCUMENT_DATE"},
}

LANE_A_EDGE_TYPES = {
    "STATE_CONTINUATION", "SHIP_REGISTRY", "PROPERTY_TITLE", "PORT_CONTROL",
    "CUSTODY", "REMOVAL_POWER", "DISPOSAL_POWER", "LAW_VALIDITY",
    "ABANDONMENT", "PHYSICAL_STATE", "TIME_ORDER", "TEMPORAL_OVERLAP",
    "CAUSAL_SUCCESSION", "PORT_ENTRY",
}
LANE_B_EDGE_TYPES = {
    "HULL_IDENTITY", "SERVICE_IDENTITY", "NAME_IDENTITY", "CLASSIFICATION",
    "LIFECYCLE_EVENT", "LAUNCH_EVENT", "COMMISSION_EVENT", "TRANSFER_EVENT",
    "DECOMMISSION_EVENT", "RETURN_EVENT", "PHYSICAL_END", "MATERIAL_LINEAGE",
    "DERIVED_ASSET", "PROGRAM_BUDGET", "VESSEL_ALLOCATION", "DOCUMENT_DATE",
    "EVENT_TIME", "ORIGINAL_MATERIAL_FRACTION",
}


def _upper(v):
    return str(v).upper() if v is not None else ""


def _walk(value, path=()):
    if isinstance(value, dict):
        yield path, value
        for key in sorted(value):
            yield from _walk(value[key], path + (str(key),))
    elif isinstance(value, list):
        for i, item in enumerate(value):
            yield from _walk(item, path + (str(i),))


def _path(path):
    return "$" if not path else "$." + ".".join(path)


def _violation(rule_id, lane, kind, path, message, details=None):
    return {
        "rule_id": rule_id,
        "lane": lane,
        "kind": kind,
        "path": _path(path),
        "message": message,
        "details": details or {},
        "probe": {
            "axis": rule_id,
            "group": "typed_graph_" + lane.lower(),
            "to": "B_TYPED_GRAPH_" + lane,
            "method": "TYPED_GRAPH_TRACE",
            "rule_id": rule_id,
        },
    }


def _parse_date(v):
    if not isinstance(v, str):
        return None
    s = v.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        pass
    try:
        return date.fromisoformat(s[:10])
    except Exception:
        return None


def _unique(out):
    seen = set()
    result = []
    for v in out:
        key = (v["rule_id"], v["path"], repr(sorted(v.get("details", {}).items())))
        if key not in seen:
            seen.add(key)
            result.append(v)
    return sorted(result, key=lambda x: (x["lane"], x["rule_id"], x["path"]))


def evaluate_typed_graph(observation):
    graph = observation.get("typed_graph")
    if not isinstance(graph, dict):
        return []
    out = []
    edges = graph.get("edges", [])
    if not isinstance(edges, list):
        return [_violation(
            "AB_GRAPH_SCHEMA", "A", "GRAPH_SCHEMA", ("typed_graph", "edges"),
            "typed_graph.edges must be a list.",
        )]

    for i, edge in enumerate(edges):
        if not isinstance(edge, dict):
            continue
        p = ("typed_graph", "edges", str(i))
        target = _upper(edge.get("edge_type"))
        derived = edge.get("derived_from_edge_types", [])
        if isinstance(derived, str):
            derived = [derived]
        derived_u = {_upper(x) for x in derived}
        lane = "A" if target in LANE_A_EDGE_TYPES else ("B" if target in LANE_B_EDGE_TYPES else "A")

        forbidden = FORBIDDEN_DERIVATIONS.get(target, set())
        if derived_u and derived_u <= forbidden and edge.get("independent_evidence") is not True:
            out.append(_violation(
                "AB_EDGE_SUBSTITUTION", lane, "UNSUPPORTED_EDGE_SUBSTITUTION", p,
                "A typed relation was derived only from a non-equivalent relation family.",
                {"edge_type": target, "derived_from": sorted(derived_u)},
            ))

        scope_from = _upper(edge.get("source_scope"))
        scope_to = _upper(edge.get("target_scope"))
        if scope_from == "CLASS" and scope_to in {"HULL", "ASSET", "INSTANCE"} and edge.get("per_instance_evidence") is not True:
            out.append(_violation(
                "AB_SCOPE_DISTRIBUTION", "B", "CLASS_TO_INSTANCE_AUTO_PROPAGATION", p,
                "Class-level evidence must not auto-close instance-level lifecycle cells.",
                {"edge_type": target},
            ))

        event_time = _parse_date(edge.get("event_time"))
        valid_from = _parse_date(edge.get("rule_valid_from"))
        if event_time and valid_from and event_time < valid_from and edge.get("retroactive") is not True:
            out.append(_violation(
                "AB_TEMPORAL_VALIDITY", "A", "PRESENTISM", p,
                "A rule was applied before its validity epoch.",
                {"event_time": str(event_time), "rule_valid_from": str(valid_from), "edge_type": target},
            ))

        source_state = _upper(edge.get("source_evidence_state"))
        target_state = _upper(edge.get("target_state"))
        if source_state in UNKNOWNISH and target_state in EXACT_OR_CLOSED:
            out.append(_violation(
                "AB_UNKNOWN_TO_EXACT", lane, "UNKNOWN_TO_EXACT_CLOSURE", p,
                "Unknown/open source evidence must not auto-close an exact downstream relation.",
                {"source_evidence_state": source_state, "target_state": target_state, "edge_type": target},
            ))

        if edge.get("same_event_assumed") is True and target in {"COMMISSION_EVENT", "PHYSICAL_END", "PROPERTY_TITLE"}:
            out.append(_violation(
                "AB_DISTINCT_EVENT_COLLAPSE", lane, "DISTINCT_EVENTS_COLLAPSED", p,
                "Distinct lifecycle/authority events must not be collapsed solely by adjacency or convenience.",
                {"edge_type": target},
            ))

        if edge.get("chronology_only") is True and target in {"CAUSAL_SUCCESSION", "PROPERTY_TITLE", "HULL_IDENTITY"}:
            out.append(_violation(
                "AB_TIME_NOT_CAUSAL", lane, "CHRONOLOGY_AS_CAUSAL_EDGE", p,
                "Temporal order alone does not establish the asserted causal/identity/legal edge.",
                {"edge_type": target},
            ))

    # Cross-edge consistency checks.
    edge_types = {_upper(e.get("edge_type")) for e in edges if isinstance(e, dict)}
    if "PHYSICAL_END" in edge_types and ({"MATERIAL_LINEAGE", "DERIVED_ASSET"} & edge_types):
        physical_end_edges = [e for e in edges if isinstance(e, dict) and _upper(e.get("edge_type")) == "PHYSICAL_END"]
        survivor_edges = [e for e in edges if isinstance(e, dict) and _upper(e.get("edge_type")) in {"MATERIAL_LINEAGE", "DERIVED_ASSET"}]
        if any(_upper(e.get("target_state")) in {"DESTROYED", "NONEXISTENT", "SCRAPPED_ALL"} for e in physical_end_edges) and any(
            _upper(e.get("target_state")) in {"ACTIVE", "EXISTS", "REUSED", "HOLD", "OPEN"} for e in survivor_edges
        ):
            out.append(_violation(
                "AB_MATERIAL_AFTERLIFE", "B", "HULL_END_ERASES_MATERIAL_LINEAGE", ("typed_graph",),
                "Hull/service terminal state must not erase surviving material or derived-asset lineage.",
            ))

    return _unique(out)


def evaluate_legacy_ab(observation):
    """Compatibility adapter for the existing A/B destruction fixtures."""
    out = []
    observed = observation.get("observed") if isinstance(observation.get("observed"), dict) else {}
    objects = list(_walk(observed))

    def add(rule_id, lane, kind, path, message, details=None):
        out.append(_violation(rule_id, lane, kind, path, message, details))

    for path, obj in objects:
        lower = {str(k).lower(): v for k, v in obj.items()}
        vals_u = {_upper(v) for v in obj.values() if isinstance(v, (str, int, float, bool))}

        # -------- Lane A: Authority / Jurisdiction / Temporal-validity --------
        if lower.get("automatic_mutation") is True and "ship_registry_transfer_event" in lower:
            if _upper(lower.get("ship_registry_transfer_event")) in {"NONE", "UNKNOWN", ""}:
                add("A_STATE_SUCCESSION_NOT_REGISTRY", "A", "EDGE_SUBSTITUTION", path,
                    "State continuation must not auto-create vessel-specific registry succession.")

        if lower.get("derived_automatically_from_extinction") is True and _upper(lower.get("property_status")) == "OWNERLESS":
            add("A_ENTITY_EXTINCTION_NOT_OWNERLESS", "A", "EDGE_SUBSTITUTION", path,
                "Legal-entity extinction does not establish ownerless property.")

        if lower.get("collapsed_authority_and_title") is True:
            add("A_CONTROL_NOT_TITLE", "A", "EDGE_SUBSTITUTION", path,
                "Operational/port control must remain separate from property title.")

        if lower.get("unlimited_disposal_authority") is True and _upper(lower.get("foreign_property_title")) in UNKNOWNISH:
            add("A_REMOVAL_NOT_DISPOSAL", "A", "EDGE_SUBSTITUTION", path,
                "Removal/control power must not silently become unlimited disposal authority.")

        if lower.get("retroactive_application") is True:
            add("A_LAW_VALIDITY_EPOCH", "A", "PRESENTISM", path,
                "Later legal regime must not be projected backward without an explicit retroactivity basis.")

        if "actual_scope" in lower and "used_as" in lower and _upper(lower.get("actual_scope")) != _upper(lower.get("used_as")):
            add("A_RULE_SCOPE_NOT_POWER", "A", "SCOPE_SUBSTITUTION", path,
                "A legal/source scope must not be silently substituted for a different operational power.",
                {"actual_scope": lower.get("actual_scope"), "used_as": lower.get("used_as")})

        if lower.get("derived_from_flag_termination") is True:
            add("A_FLAG_NOT_PHYSICAL_END", "A", "CROSS_LAYER_SUBSTITUTION", path,
                "Registry/state termination does not establish physical destruction.")

        if _upper(lower.get("legal_entity")) == "EXTINCT" and _upper(lower.get("abandonment_state")) == "ABANDONED":
            if _upper(lower.get("abandonment_evidence")) in {"NONE", "UNKNOWN", ""}:
                add("A_EXTINCTION_NOT_ABANDONMENT", "A", "UNSUPPORTED_EDGE", path,
                    "Abandonment requires its own evidence; entity extinction is insufficient.")

        if lower.get("causal_registry_transfer_inferred") is True:
            add("A_TIME_ORDER_NOT_CAUSAL", "A", "CHRONOLOGY_AS_CAUSAL_EDGE", path,
                "Temporal overlap/order does not establish vessel-specific registry succession.")

        if _upper(lower.get("state")) == "AUTO_FILLED" and "flag" in lower:
            add("A_REGISTRY_GAP_PRESERVE", "A", "GAP_AUTO_FILLED", path,
                "Registry gaps must remain open absent a transfer/registration edge.")

        if "transfer_event" in lower and _upper(lower.get("transfer_event")) in {"NONE", "UNKNOWN", ""}:
            keys = [k for k in lower if k[:4].isdigit()]
            if len(keys) >= 2 and any(_upper(lower[k]) not in UNKNOWNISH for k in keys):
                add("A_TITLE_TRANSFER_REQUIRES_EDGE", "A", "UNSUPPORTED_EDGE", path,
                    "Property-title mutation requires an explicit transfer/succession edge.")

        if "collapsed_to_single_authority" in lower:
            add("A_DEADLOCK_NOT_WINNER", "A", "AUTHORITY_GRAPH_COLLAPSE", path,
                "Competing authority claims/deadlock must not be collapsed to one machine-selected authority.")

        if _upper(lower.get("causal_basis")) in {"EARLIER_PORT_ENTRY", "TIME_ORDER", "TEMPORAL_OVERLAP"}:
            add("A_CHRONOLOGY_NOT_TITLE", "A", "CHRONOLOGY_AS_CAUSAL_EDGE", path,
                "Earlier presence/chronology does not establish later property title.")

        # -------- Lane B: Identity / Lifecycle / Material-lineage --------
        if _upper(lower.get("physical_continuity")) == "SALVAGED_HULL" and lower.get("treated_as_new_unrelated_hull") is True:
            add("B_PHYSICAL_CONTINUITY_NOT_SPLIT", "B", "IDENTITY_SPLIT", path,
                "Observed physical hull continuity must not be silently split into unrelated hulls.")

        if lower.get("sunk") is True and lower.get("salvaged") is True and _upper(lower.get("identity_decision")) == "NEW_BUILD":
            add("B_SALVAGE_NOT_NEW_BUILD", "B", "IDENTITY_SUBSTITUTION", path,
                "Salvage/reconstruction does not automatically create a new hull identity.")

        if lower.get("collapsed_to_one_service_identity") is True:
            add("B_HULL_NOT_SERVICE_IDENTITY", "B", "IDENTITY_LAYER_COLLAPSE", path,
                "One physical hull may carry multiple service identities; they must remain typed separately.")

        if "legal_owner" in lower and "operator" in lower:
            if lower.get("loan") is True and (
                lower.get("collapsed_owner_operator") is True or
                _upper(lower.get("collapsed_owner_operator")) == _upper(lower.get("operator"))
            ):
                add("B_OWNER_NOT_OPERATOR", "B", "AUTHORITY_IDENTITY_COLLAPSE", path,
                    "Loaned operation must not collapse legal owner and operator.")

        if "loan_event" in lower and lower.get("treated_as_same_event") is True:
            add("B_LOAN_NOT_GRANT", "B", "DISTINCT_EVENT_COLLAPSE", path,
                "Loan and grant/title-change events are distinct.")

        if lower.get("applied_to_all_hulls") is True:
            add("B_CLASS_NOT_INSTANCE_TRUTH", "B", "CLASS_TO_HULL_PROPAGATION", path,
                "Class-level dates or terminal states must not auto-close per-hull facts.")

        if lower.get("returned_to_former_owner") is True and _upper(lower.get("physical_end")) in {"SAME_DATE", "RETURN_DATE"}:
            add("B_RETURN_NOT_PHYSICAL_END", "B", "DISTINCT_EVENT_COLLAPSE", path,
                "Return from service is not physical terminal disposition.")

        if lower.get("new_hull_on_class_change") is True:
            add("B_CLASS_CHANGE_NOT_NEW_HULL", "B", "IDENTITY_SUBSTITUTION", path,
                "Classification change does not create a new hull.")

        if lower.get("assumed_identical_lifecycle") is True:
            add("B_CLASS_NOT_SAME_LIFECYCLE", "B", "CLASS_TO_HULL_PROPAGATION", path,
                "Class membership does not imply identical lifecycle.")

        if lower.get("treated_as_two_unrelated_hulls") is True and _upper(lower.get("physical_continuity")) == "SALVAGED_HULL":
            add("B_SAME_HULL_CROSS_SERVICE", "B", "IDENTITY_SPLIT", path,
                "Cross-service identity change must not sever observed hull continuity.")

        if lower.get("treated_as_same_event") is True and (
            "recipient_commission_date" in lower or
            {"launch", "commission"} <= {k.split("_")[-1] for k in lower}
        ):
            add("B_TRANSFER_NOT_COMMISSION", "B", "DISTINCT_EVENT_COLLAPSE", path,
                "Transfer/launch must not auto-close recipient commission.")

        if _upper(lower.get("primary_key")) == "NAME" and lower.get("collapsed_to_one_hull") is True:
            add("B_NAME_NOT_HULL_ID", "B", "IDENTITY_KEY_COLLAPSE", path,
                "Name is not a safe primary key for hull identity.")

        if lower.get("new_hull_on_reclassification") is True:
            add("B_RECLASS_NOT_NEW_HULL", "B", "IDENTITY_SUBSTITUTION", path,
                "Reclassification does not create a new physical hull.")

        if lower.get("commission_inferred_from_launch") is True:
            add("B_LAUNCH_NOT_COMMISSION", "B", "DISTINCT_EVENT_COLLAPSE", path,
                "Launch is not commission.")

        if _upper(lower.get("vessel_allocation_evidence")) in UNKNOWNISH and _upper(lower.get("hull_budget_state")) == "CLOSED":
            add("B_PROGRAM_NOT_HULL_ALLOCATION", "B", "SCOPE_PROMOTION", path,
                "Program-level appropriation must not auto-close vessel-specific allocation.")

        if lower.get("copied_document_date_to_event") is True and _upper(lower.get("historical_event_date")) in UNKNOWNISH:
            add("B_DOCUMENT_DATE_NOT_EVENT_DATE", "B", "TEMPORAL_SUBSTITUTION", path,
                "Document date is not automatically the historical event date.")

        if lower.get("collapsed_terminal_events") is True:
            add("B_TERMINAL_EVENTS_DISTINCT", "B", "DISTINCT_EVENT_COLLAPSE", path,
                "Loss, administrative strike, salvage, and later disposition must remain distinct events.")

        if lower.get("decided_from_original_material_fraction_only") is True:
            add("B_NO_SCALAR_IDENTITY_VERDICT", "B", "IDENTITY_SCALARIZATION", path,
                "Object identity must not be machine-decided from original-material fraction alone.")

        if lower.get("all_material_destroyed") is True:
            # Parent object may carry surviving/uncertain material fragments elsewhere.
            add("B_HULL_END_NOT_MATERIAL_END", "B", "MATERIAL_LINEAGE_ERASURE", path,
                "Hull cancellation/scrap must not imply all material lineage ended.")

        if _upper(lower.get("state")) in {"SUNK_WRECK", "SCRAPPED"} and "time" in lower:
            # We only flag exact terminal closure when adjacent evidence explicitly says UNKNOWN/open.
            root_text = repr(observed)
            if "physical_sinking_time" in root_text and "UNKNOWN" in root_text:
                add("B_LOSS_WINDOW_NOT_EXACT", "B", "UNKNOWN_TO_EXACT_CLOSURE", path,
                    "Open physical-loss window must not be collapsed to an exact terminal time.")
            if "commissioned" in root_text and "snapshot" in root_text and "SCRAPPED" in root_text:
                add("B_OPEN_LIFECYCLE_NOT_TERMINAL", "B", "OPEN_LIFECYCLE_CLOSED", path,
                    "Current commissioned/open lifecycle must not auto-complete as scrapped.")

        if _upper(lower.get("state")) == "SCRAPPED" and _upper(lower.get("time")) == "DECOMMISSION_DATE":
            if "CIVIC_FACILITY_ACTIVE" in repr(observed):
                add("B_SERVICE_END_NOT_ASSET_END", "B", "AFTERLIFE_ERASURE", path,
                    "Naval decommission must not erase later civic-asset service.")

        if _upper(lower.get("state")) == "SCRAPPED" and _upper(lower.get("time")) == "NAVAL_SERVICE_END":
            if "BREAKWATER" in repr(observed):
                add("B_SERVICE_END_NOT_DERIVED_ASSET_END", "B", "AFTERLIFE_ERASURE", path,
                    "Naval terminal state must not erase whole-hull derived-asset afterlife.")

        if lower.get("physical_nonexistence") is True and "material_fragments" in observed:
            frags = observed.get("material_fragments")
            if isinstance(frags, list) and any(_upper(x.get("current_state")) == "ACTIVE" for x in frags if isinstance(x, dict)):
                add("B_FRAGMENT_SURVIVES_HULL_END", "B", "MATERIAL_LINEAGE_CONFLICT", path,
                    "Active surviving material fragment conflicts with global material nonexistence.")

    # Cross-object A checks that need sibling context.
    flag_registry = observed.get("flag_registry")
    succession_chain = observed.get("succession_chain")
    if isinstance(flag_registry, dict) and isinstance(succession_chain, dict):
        if flag_registry.get("automatic_mutation") is True and _upper(succession_chain.get("ship_registry_transfer_event")) in {"NONE", "UNKNOWN", ""}:
            add("A_STATE_SUCCESSION_NOT_REGISTRY", "A", "EDGE_SUBSTITUTION", ("flag_registry",),
                "State continuation must not auto-create vessel-specific registry succession without a registry edge.")

    # Cross-object B checks that need sibling context.
    lr = observed.get("loss_resolution")
    td = observed.get("terminal_disposition")
    if isinstance(lr, dict) and isinstance(td, dict):
        if _upper(lr.get("physical_sinking_time")) in UNKNOWNISH and _upper(td.get("evidence_state")) in EXACT_OR_CLOSED:
            add("B_LOSS_WINDOW_NOT_EXACT", "B", "UNKNOWN_TO_EXACT_CLOSURE", ("terminal_disposition",),
                "Unknown physical-sinking time must not auto-close to an exact terminal date.")

    fs = observed.get("foreign_service")
    if isinstance(fs, dict) and fs.get("treated_as_same_event") is True and _upper(fs.get("recipient_side_evidence")) in UNKNOWNISH:
        add("B_TRANSFER_NOT_COMMISSION", "B", "UNKNOWN_TO_EXACT_CLOSURE", ("foreign_service",),
            "Recipient commission requires recipient-side evidence; donor transfer is not enough.")

    nh = observed.get("name_history")
    ident = observed.get("identity_summary")
    if isinstance(nh, list) and isinstance(ident, dict) and _upper(ident.get("primary_key")) == "NAME":
        names = {}
        for item in nh:
            if isinstance(item, dict) and item.get("name") is not None:
                names.setdefault(item.get("name"), set()).add(item.get("hull_id"))
        if any(len(v) > 1 for v in names.values()):
            add("B_NAME_NOT_HULL_ID", "B", "IDENTITY_KEY_COLLAPSE", ("identity_summary",),
                "A repeated name across distinct hull IDs cannot serve as the hull primary key.")

    le = observed.get("lifecycle_events")
    if isinstance(le, list) and all(isinstance(x, str) for x in le):
        u = {_upper(x) for x in le}
        if {"LAUNCHED", "CANCELLED", "COMMISSIONED"} <= u and isinstance(ident, dict) and ident.get("commission_inferred_from_launch") is True:
            add("B_LAUNCH_NOT_COMMISSION", "B", "DISTINCT_EVENT_COLLAPSE", ("identity_summary",),
                "Launch is not commission, especially across cancellation.")

    # Material/derived asset branch after terminal.
    derived = observed.get("derived_assets")
    if isinstance(td, dict) and isinstance(derived, list):
        if _upper(td.get("state")) == "SCRAPPED" and any(_upper(x.get("current_state")) in {"ACTIVE", "BURIED_OR_REMAINING", "REUSED"} for x in derived if isinstance(x, dict)):
            add("B_HULL_END_NOT_DERIVED_ASSET_END", "B", "AFTERLIFE_ERASURE", ("derived_assets",),
                "Hull terminal state does not erase a surviving derived asset.")

    frags = observed.get("material_fragments")
    if isinstance(td, dict) and isinstance(frags, list):
        if td.get("all_material_destroyed") is True and any(_upper(x.get("evidence_state")) in {"HOLD", "UNKNOWN"} for x in frags if isinstance(x, dict)):
            add("B_HULL_END_NOT_MATERIAL_END", "B", "UNKNOWN_TO_EXACT_CLOSURE", ("material_fragments",),
                "Unresolved surviving fragment evidence prevents an all-material-destroyed closure.")

    return _unique(out)


def evaluate(observation):
    return _unique(evaluate_typed_graph(observation) + evaluate_legacy_ab(observation))