"""Deterministic sector sweep over a revision/epoch-qualified mutable graph."""
from .binder import need,digest,text,strict_int,result,guarded,validate
REVISION='PLASMA_CIRCUMNAVIGATION_GUARD_R002_PRIVATE'
CORE=('EVIDENCE','TOPOLOGY','STATE','AUTHORITY','TEMPORAL_LIFECYCLE','RECOVERY_RETRY')
TAGS={'AUTH':'AUTH','ROUTING':'ROUTING_TRANSPORT','PROJECTION':'PROJECTION_UI','SURFACE':'SURFACE_CLIENT','BILLING':'BILLING_METERING','COST':'COST_LOSS','SAFETY':'SAFETY','CANONICAL':'CANONICAL_AUTHORITY'}
TERMINAL={'OBSERVED','CONTRADICTED','UNKNOWN','HOLD','NOT_APPLICABLE'}
PROBES=TERMINAL|{'UNINSPECTED','INSPECTING','INVALIDATED_BY_GRAPH_CHANGE'}
def assess(d,pin,base):return guarded(_assess,d,pin,base)
def _assess(d,pin,base):
    need(pin.get('input_digest')==digest(d) and pin.get('registry_order')==d['registry_order'],'HOLD_SWEEP_REGISTRY_PIN')
    order=d['registry_order'];need(order==list(CORE)+list(TAGS.values()),'HOLD_REGISTRY_ORDER_UNKNOWN')
    for k in ('sweep_generations','new_frontiers_this_generation','wall_budget_used_ms'):need(strict_int(d[k]),'HOLD_BUDGET_UNKNOWN')
    for k in ('max_sweep_generations','max_new_frontiers_per_generation','max_wall_budget_ms'):need(strict_int(d['limits'][k],1),'HOLD_BOUND_UNKNOWN')
    if d['sweep_generations']>d['limits']['max_sweep_generations'] or d['new_frontiers_this_generation']>d['limits']['max_new_frontiers_per_generation'] or d['wall_budget_used_ms']>d['limits']['max_wall_budget_ms']:return result('HOLD_NONCONVERGENT',tool_revision=REVISION)
    targets=d['material_targets'];need(len({t['id'] for t in targets})==len(targets),'HOLD_TARGET_DUPLICATE');probes=d['probes'];known={};pending=[];terminal=[]
    for p in probes:
        need(p['state'] in PROBES,'HOLD_UNKNOWN_PROBE_ENUM');key=(p['target_id'],p['sector'],p['direction'],p['epoch']);need(key not in known,'HOLD_PROBE_DUPLICATE');known[key]=p
    for target in targets:
        need(set(target['tags'])<=set(TAGS),'HOLD_EXTENSION_UNREGISTERED_SECTOR');required=set(CORE)|{TAGS[x] for x in target['tags']}|set(d['human_fixed_sectors']);need(required<=set(order),'HOLD_SECTOR_UNKNOWN')
        for sector in required:
            key=(target['id'],sector,'NODE',target['epoch']);probe=known.get(key)
            if probe is None or probe['state'] not in TERMINAL:pending.append((target['frontier_order'],target['id'],order.index(sector),'NODE',target['epoch']))
            else:
                ref=probe['evidence_ref'];validate(ref,pin['evidence_pins'][ref['artifact_id']],base,pin['evidence_subjects'][ref['artifact_id']],{'probe_observation':{'target_id':target['id'],'sector':sector,'direction':'NODE','epoch':target['epoch'],'state':probe['state']}});terminal.append(probe)
    for edge in d['material_edges']:
        need(edge['from'] in {t['id'] for t in targets} and edge['to'] in {t['id'] for t in targets} and text(edge['authority_direction']),'HOLD_EDGE_BINDING')
        for direction in ('FORWARD','REVERSE'):
            probe=known.get((edge['id'],'TOPOLOGY',direction,edge['epoch']))
            if probe is None or probe['state'] not in TERMINAL:pending.append((edge['frontier_order'],edge['id'],order.index('TOPOLOGY'),direction,edge['epoch']))
            else:
                ref=probe['evidence_ref'];validate(ref,pin['evidence_pins'][ref['artifact_id']],base,pin['evidence_subjects'][ref['artifact_id']],{'probe_observation':{'target_id':edge['id'],'sector':'TOPOLOGY','direction':direction,'epoch':edge['epoch'],'state':probe['state']}});terminal.append(probe)
    pending.sort()
    if d['unprocessed_delta_graph']:return result('HOLD_LOCAL_RESWEEP_REQUIRED',tool_revision=REVISION,changed_frontiers=d['unprocessed_delta_graph'],pending=pending,retained_terminal_states=terminal)
    if pending:
        first=pending[0];return result('NEXT_PROBE_REQUIRED',tool_revision=REVISION,next_probe={'frontier_order':first[0],'target_id':first[1],'sector':order[first[2]],'direction':first[3],'epoch':first[4]},pending_count=len(pending),retained_terminal_states=terminal)
    return result('PASS_SURVEY_COVERAGE_ONLY',tool_revision=REVISION,survey_closed=True,root_cause=d['root_cause_state'],retained_terminal_states=terminal,causality='NOT_CERTIFIED',contradictions_preserved=[p for p in terminal if p['state']=='CONTRADICTED'])
