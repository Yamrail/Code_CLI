"""Search existing drawings and return one review workface; never send messages."""
from .binder import need,text,digest,result,guarded,validate,strict_int,sha,retained
import json
from .execution_receipt import validate as validate_execution
REVISION='PROTOTYPE_DRAWING_SOL_COMPLETION_INTAKE_R004_PRIVATE'
STAGES=('S01_PARENT_READBACK','S02_DRAWING_INSPECTION','S03_DEPENDENCY_BINDING','S04_FIXTURE_CONSTRUCTION','S05_IMPLEMENTATION','S06_SELF_TEST','S07_DESTRUCTIVE_TEST','S08_REPAIR_AND_FULL_RERUN','S09_CROSS_HANDOFF_TEST','S10_HUMAN_BOUNDARY_EXTRACTION')
HUMAN={'H01_VALUE_JUDGMENT','H02_AUTHORITY','H03_MATERIAL_TOLERANCE_CHANGE','H04_IRREVERSIBLE_EFFECT','H05_CANONICAL_PROMOTION','H06_UNRESOLVABLE_SOURCE_CONFLICT'}
def intake(d,pin,base):return guarded(_intake,d,pin,base)
def _intake(d,pin,base):
    need(d.get('event')=='NEW_WORK_TURN_START' and text(d.get('requested_capability_id')),'HOLD_INTAKE_IDENTITY')
    need(pin.get('input_digest')==digest(d) and d['search_coverage_complete'] is True and set(d['searched_surfaces'])=={'03_operations/architecture/','03_operations/prototypes/','03_operations/tools/','03_operations/indexes/','03_operations/governance/'},'HOLD_DRAWING_SEARCH_UNPROVEN')
    ref=d['inventory_ref'];validate(ref,pin['inventory_pin'],base,pin['inventory_subject'],{'inventory_members':d['inventory_members']})
    matches=[m for m in d['inventory_members'] if d['requested_capability_id'] in m['declared_capability_ids']]
    if not matches:return result('DRAWING_REQUIRED',tool_revision=REVISION,next_workface='DRAWING_REQUIRED',external_mutation='PROHIBITED')
    by={m['drawing_id']:m for m in matches};superseded={i for m in matches for i in m['supersedes']};baselines=[m for m in matches if m['drawing_id'] not in superseded]
    need(len(baselines)==1,'HOLD_BASELINE_SELECTION_REQUIRES_HUMAN');baseline=baselines[0]
    for drawing in matches:validate(drawing['ref'],pin['drawing_pins'][drawing['ref']['artifact_id']],base)
    need(baseline['ref']['parent_commit']==d['parent_commit'],'HOLD_PARENT_REVISION_UNKNOWN')
    need(len(d['stage_receipts'])<=len(STAGES) and [s['stage'] for s in d['stage_receipts']]==list(STAGES[:len(d['stage_receipts'])]),'HOLD_STAGE_RECEIPT_ORDER')
    done=[];failed=[];implementation=None
    for s in d['stage_receipts']:
        need(s['stage'] in STAGES and s['stage'] not in done,'HOLD_STAGE_RECEIPT_IDENTITY');bound=validate(s['ref'],pin['stage_pins'][s['ref']['artifact_id']],base,pin['stage_subjects'][s['ref']['artifact_id']],{'stage':s['stage'],'status':s['status'],'drawing_revision':baseline['ref']['revision']})
        need(s['status'] in {'PASS','FAIL','HOLD'},'HOLD_UNKNOWN_STAGE_VERDICT')
        if s['status']=='PASS':
            record=bound['record']
            if s['stage']=='S05_IMPLEMENTATION':implementation=record
            if s['stage'] in {'S06_SELF_TEST','S07_DESTRUCTIVE_TEST','S08_REPAIR_AND_FULL_RERUN','S09_CROSS_HANDOFF_TEST'}:
                need(s['ref']['record_class'] in {'EXECUTION','RECEIPT'},'HOLD_STAGE_EXECUTION_CLASS')
                ep=pin['stage_execution_pins'][s['stage']]
                _,b=retained(base,record['execution_receipt_locator'])
                need(sha(b)==record['execution_receipt_sha256']==ep['receipt_sha256'],'HOLD_STAGE_EXECUTION_RECEIPT_UNBOUND')
                er=json.loads(b);validate_execution(er,ep,base)
                need(implementation is not None and er['tool_revision']==implementation['tool_revision'] and er['source_sha256']==implementation['source_sha256'],'HOLD_STAGE_IMPLEMENTATION_EXECUTION_MISMATCH')
                need(ep['drawing_revision']==baseline['ref']['revision'],'HOLD_STAGE_EXECUTION_DRAWING_REVISION')
                _,fixture=retained(base,ep['fixture_locator']);fixture=json.loads(fixture)
                expected={'artifact_id':baseline['ref']['artifact_id'],'revision':baseline['ref']['revision'],'sha256':baseline['ref']['sha256']}
                paths=ep['fixture_drawing_json_paths'];need(set(paths)==set(expected),'HOLD_FIXTURE_DRAWING_BINDING_PATHS')
                for key,wanted in expected.items():
                    value=fixture;need(isinstance(paths[key],list) and paths[key],'HOLD_FIXTURE_DRAWING_BINDING_PATHS')
                    for part in paths[key]:value=value[part]
                    need(value==wanted,'HOLD_EXECUTION_FIXTURE_DRAWING_MISMATCH_'+key)
            done.append(s['stage'])
        else:failed.append(s)
    need(all(d['human_questions'][i]['class'] in HUMAN for i in range(len(d['human_questions']))),'HOLD_TECHNICAL_UNFINISHED_WORK_IS_NOT_HUMAN_JUDGMENT')
    if failed:return result('LIMITED_REWORK',tool_revision=REVISION,baseline=baseline,next_workface=failed[0]['stage'],local_holds=failed,whole_workface_hold=False)
    missing=[s for s in STAGES if s not in done]
    if missing:return result('READY_FOR_SOL_REVIEW',tool_revision=REVISION,baseline=baseline,next_workface=missing[0],must_review_before_redraw=True,external_mutation='PROHIBITED')
    need(d['all_runnable_fixtures_executed'] is True and d['false_pass_register_reviewed'] is True and d['false_hold_register_reviewed'] is True,'HOLD_COMPLETION_EVIDENCE_INCOMPLETE')
    return result('READY_FOR_HUMAN_JUDGMENT',tool_revision=REVISION,baseline=baseline,next_workface='HUMAN_JUDGMENT_BOUNDARY',human_questions=d['human_questions'],external_mutation='PROHIBITED',canonical_promotion='NOT_PERFORMED')
