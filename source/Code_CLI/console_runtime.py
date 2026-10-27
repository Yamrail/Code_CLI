"""R010 observation/control layer over unchanged native WorkLedger semantics.

The three roles are deterministic fixture processes, not live AI models.
This module never accepts a shell command, a provider key, or an arbitrary tool.
"""
from __future__ import annotations
import argparse
import contextlib
import difflib
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import uuid

ROOT=Path(__file__).resolve().parent
from runtime_support import load_environment
load_environment()
CASES={
    'confirmed':('CONFIRMED_CONFIG','01_confirmed.json'),
    'insufficient':('INSUFFICIENT_EVIDENCE','02_insufficient.json'),
    'stop':('STOP_AND_ALTERNATIVE','03_stop_recover.json'),
}
PROFILE_PUBLIC='PUBLIC_MINIMALLY_WIRED'
INTERLOCK='[DETERMINISTIC RAIL INTERLOCK: ENGAGED | PROFILE: PUBLIC_MINIMALLY_WIRED | 3 VERIFIED RAILS ONLY]'
LOGO=r'''\ Y /    Y A M R A I L   C O D E _ C L I
 \\ /     === INTENT === EVIDENCE === SEAL ===
  ||      ||       DETERMINISTIC RAILS      ||
==||==    ||  PLAN -> CRITIQUE -> REPAIR    ||
  ||      === STOP / READBACK / RESUME ====='''
sha=lambda b:hashlib.sha256(b).hexdigest()

def save(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def profile():
    path=ROOT/'release_profile.json'
    if path.is_file():
        value=json.loads(path.read_bytes()).get('profile')
        if value in {PROFILE_PUBLIC,'OWNER_CONTROLLED_FULL'}:return value
    # Missing identity is never interpreted as the more capable owner profile.
    return PROFILE_PUBLIC

def public_denial(args):
    if profile()!=PROFILE_PUBLIC:return None
    cmd=args.command
    if cmd in {'doctor','status'}:return None
    if cmd=='sample' and not args.input and not args.output:return None
    if cmd=='evidence' and args.evidence_action=='verify' and args.manifest=='MANIFEST.json':return None
    if cmd=='evidence' and args.evidence_action=='list' and not args.run:return None
    if cmd=='tools':return None
    return 'R010-Sec04: the Public profile exposes three fixed credential-free rails and read-only setup/evidence inspection only.'

def intercept(text):
    return {'kind':'GOVERNANCE_INTERCEPT','clause':'R010-Sec04: Unbounded Autonomy Containment','requested_input':text[:512],
            'reason':'Unbounded autonomous tool chaining and CAD mutation are disabled in Public Profile. No arbitrary shell, external provider, or owner authority is connected to this console.',
            'allowed':['sample --all','evidence verify','moot status'],
            'individual_cases':['demo confirmed','demo insufficient','demo stop'],
            'operation_dispatched':False,'authority_escalated':False}

class ControlledCancel(Exception):pass

class RailControl:
    """In-process cooperative controls; no custom transport or remote endpoint."""
    def __init__(self):
        self.stop_requested=False;self.cancel_requested=False
        self.resume_event=threading.Event();self.resume_event.set()
    def stop(self):self.stop_requested=True;self.resume_event.clear()
    def resume(self):self.resume_event.set()
    def cancel(self):self.cancel_requested=True;self.resume_event.set()

def _safe_boundary(native,control,emit):
    from native_runtime.core import open_case,authority_ref,snapshot
    if control.cancel_requested:
        if (native/'RUN_METADATA.json').exists():
            live=open_case(native)
            if live.state['active']:live.append('STOP',{'reason':'R010_OPERATOR_CANCEL_NO_AUTOMATIC_RETRY'},[authority_ref(native)])
        raise ControlledCancel()
    if not control.stop_requested or not (native/'RUN_METADATA.json').exists():return
    live=open_case(native)
    pending=[x for x in live.state['pending'].values() if not x['state'].startswith('SETTLED')]
    if pending:return  # Never interrupt a reservation and pretend its effect is known.
    before=snapshot(live)
    live.append('STOP',{'reason':'R010_CONSOLE_OPERATOR_STOP_AT_SETTLED_TOOL_BOUNDARY'},[authority_ref(native)])
    stopped=snapshot(open_case(native))
    emit('STOP',{'native_checkpoint':stopped['checkpoint'],'active':stopped['active'],
                 'root_buckets':stopped['root_buckets'],'reason':'Operator requested STOP; existing native ledger is stopped.'})
    control.resume_event.wait()
    if control.cancel_requested:raise ControlledCancel()
    restored=open_case(native)
    restored.append('RESUME',{'presence':'CURRENT_CONFIRMED','authority_digest':restored.plan['authority_digest']},[authority_ref(native)])
    restored.append('STAGE_ENTER',{'stage':'REASONING_SAMPLE'},[authority_ref(native)])
    after=snapshot(open_case(native))
    assert before['root_buckets']==after['root_buckets']
    control.stop_requested=False
    emit('RESUME',{'native_checkpoint':after['checkpoint'],'root_buckets':after['root_buckets'],
                   'attempt_budget_preserved':True,'execution_replayed':False})

def _blueprint(output,result,result_href='case/RESULT.json'):
    records=result['records']
    nodes=[]
    for i,row in enumerate(records):
        label=row['role']+' | '+row.get('assessment','OBSERVED')
        fill='#f59e0b' if row.get('accepted') is False else '#6ee7b7'
        y=94+i*72
        nodes.append(f'<rect x="40" y="{y}" width="820" height="48" rx="4" fill="#102c50" stroke="{fill}"/><text x="58" y="{y+29}" fill="{fill}">{html.escape(label)}</text>')
        if i:nodes.append(f'<path d="M450 {y-24} V{y}" stroke="#9cc9ec" fill="none"/>')
    height=160+len(records)*72
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="{height}" viewBox="0 0 900 {height}"><rect width="900" height="{height}" fill="#071c38"/><g font-family="monospace" font-size="17"><text x="40" y="36" fill="#d6eaff">YamRail | {html.escape(result["case_id"])} | LOCAL EXECUTED</text><text x="40" y="65" fill="#a4c7eb">Synthetic domain/role decisions; real native ledger + Meterless processes</text>{"".join(nodes)}<text x="40" y="{height-28}" font-size="13" fill="#a4c7eb">Native journal SHA256: {result["native_journal_sha256"]}</text></g></svg>\n'
    target=output/'BLUEPRINT.svg';target.write_text(svg,encoding='utf-8',newline='\n')
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src \'self\'; style-src \'unsafe-inline\'"><title>YamRail evidence blueprint</title><style>body{background:#071c38;color:#d6eaff;font:16px monospace;margin:28px}img{max-width:100%;height:auto}a{color:#85dfff}pre{white-space:pre-wrap;overflow-wrap:anywhere}</style><h1>'+html.escape(result['case_id'])+'</h1><p>Real local execution; deterministic synthetic role decisions. No live model calls.</p><img src="BLUEPRINT.svg" alt="Actual Planner, Executor, Evaluator state transitions"><pre>Native journal SHA256: '+result['native_journal_sha256']+'</pre><p><a href="'+result_href+'">Exact case result</a> · <a href="CASE_DIFF.patch">Actual proposal diff</a></p></html>\n'
    (output/'BLUEPRINT.html').write_text(page,encoding='utf-8',newline='\n')
    plans=[r for r in records if r['role']=='PLANNER']
    first=json.dumps({k:plans[0].get(k) for k in ['selected_source','plan','assessment']},indent=2,sort_keys=True).splitlines(True)
    final=json.dumps({k:plans[-1].get(k) for k in ['selected_source','plan','assessment']},indent=2,sort_keys=True).splitlines(True)
    diff=''.join(difflib.unified_diff(first,final,fromfile='observed/initial_planner.json',tofile='observed/final_planner.json'))
    (output/'CASE_DIFF.patch').write_text(diff or '# No Planner proposal change in the confirmed fixture.\n',encoding='utf-8',newline='\n')
    return {'svg':'BLUEPRINT.svg','html':'BLUEPRINT.html','svg_sha256':sha(target.read_bytes()),'ascii':[
        '+==================== YAMRAIL BLUEPRINT ====================+',
        '| PLANNER --> EXECUTOR --> EVALUATOR --> NATIVE SEAL         |',
        '| REJECT --> WORLD MODEL --> REPAIR / STOP --> RESUME       |' if len(plans)>1 else '| Evidence confirmed; original proposal retained.             |',
        '+=========================================================+'],
        'actual_diff':diff,'no_autocad_required':True}

_rail_lock=threading.Lock()

def run_rail(name,callback=None,control=None,output=None):
    if name not in CASES:raise ValueError('Unknown fixed rail')
    if not _rail_lock.acquire(blocking=False):raise RuntimeError('ONE_FIXED_RAIL_AT_A_TIME')
    from adapters import reasoning_sample as sample
    case_id,filename=CASES[name]
    output=Path(output) if output else ROOT/'.yr-code/rails'/(name+'_'+time.strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8])
    if output.exists():
        _rail_lock.release();raise ValueError('Preserve existing run; select a fresh output')
    output.mkdir(parents=True)
    control=control or RailControl();sequence=0
    log=output/'CONTROL_EVENTS.jsonl'
    def emit(kind,data):
        nonlocal sequence
        sequence+=1
        event={'schema':'yamrail.r010.observed-control-event/1','sequence':sequence,'observed_unix_ns':time.time_ns(),'kind':kind,'data':data,'authority_effect':'NONE','native_state_writer':False}
        with log.open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(event,ensure_ascii=False)+'\n')
        if callback:callback(event)
    original=sample.run_process
    previous_view=None
    def observed_process(command,folder,process_name,**kwargs):
        nonlocal previous_view
        _safe_boundary(output/'case/native',control,emit)
        emit('TOOL_INVOCATION',{'actual_argv':[str(x) for x in command],'name':process_name,'shell':False,'dispatch':'IMMEDIATELY_BEFORE_EXISTING_RUN_PROCESS'})
        process,raw=original(command,folder,process_name,**kwargs)
        emit('TOOL_RESULT',{'process':process,'stdout_sha256':sha(raw),'actual_stdout':raw.decode('utf-8','replace'),'raw_output_retained_by_existing_runner':True})
        stderr_path=Path(folder)/(process_name+'.stderr')
        if stderr_path.is_file() and stderr_path.stat().st_size:
            emit('STDERR',{'actual_text':stderr_path.read_text(encoding='utf-8',errors='replace'),'sha256':sha(stderr_path.read_bytes())})
        data=json.loads(raw)
        if process_name.startswith('world-'):
            current=data.get('case_state',{})
            emit('WORLD_MODEL',{'native_checkpoint':data.get('native_checkpoint'),'from_state':previous_view,'to_state':current,
                                'canonical_writes':data.get('canonical_writes'),'source_journal_sha256':data.get('source_journal_sha256'),
                                'actual_backend':'NODE_PINNED_METERLESS_REFERENCE' if any(str(x).endswith('reasoning_world_model.js') for x in command) else 'PYTHON_EQUIVALENT_PROJECTION'})
            previous_view=current
        elif 'role' in data:
            role=data['role'];kind='ROLE'
            if role=='EVALUATOR' and data.get('accepted') is False:kind='REJECT'
            if role=='PLANNER' and data.get('plan')=='REPAIR_USING_AUTHORIZED_ALTERNATIVE':kind='REMEDIATION'
            emit(kind,{'role':role,'execution_class':'ACTUAL_LOCAL_PROCESS','reasoning_mode':'DETERMINISTIC_SYNTHETIC_ROLE','observed_result':data})
        return process,raw
    sample.run_process=observed_process
    old_sample=os.environ.get('SAMPLE_MODE');os.environ['SAMPLE_MODE']='true'
    try:
        emit('COMMAND',{'rail':name,'case_id':case_id,'actual_entrypoint':'existing adapters.reasoning_sample.run_case','fixture':filename,'profile':profile(),'model_calls':0})
        class ObservedStderr:
            def write(self,text):
                for line in text.splitlines():
                    if line:emit('STDERR',{'actual_text':line})
                return len(text)
            def flush(self):pass
        with contextlib.redirect_stderr(ObservedStderr()):
            result=sample.run_case(output/'case',ROOT/'fixtures/safe_public_or_synthetic/reasoning'/filename)
        assert result['case_id']==case_id and all(result['checks'].values())
        if result.get('stop_resume'):
            emit('STOP_RESUME_READBACK',{'receipt':result['stop_resume'],'native_checkpoint':result['native_checkpoint'],
                                         'executor_attempts':result['executor_attempts'],'attempt_budget_limit':3,
                                         'remaining_attempts':3-result['executor_attempts'],'native_journal_sha256':result['native_journal_sha256']})
        blueprint=_blueprint(output,result)
        emit('BLUEPRINT',blueprint)
        rows=[]
        for p in sorted(output.rglob('*')):
            if p.is_file() and p!=log:rows.append({'path':p.relative_to(output).as_posix(),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
        save(output/'CASE_MANIFEST.json',{'schema':'yamrail.r010.rail-manifest/1','files':rows,'excludes':['CONTROL_EVENTS.jsonl (ongoing observer stream)','CASE_MANIFEST.json','COMPLETION_SEAL.json'],'authority_effect':'NONE'})
        seal={'schema':'yamrail.r010.completion-seal/1','state':'PASS','case_id':case_id,'manifest_sha256':sha((output/'CASE_MANIFEST.json').read_bytes()),'native_journal_sha256':result['native_journal_sha256'],'actual_model_calls':0,'decision_class':'DETERMINISTIC_SYNTHETIC_FIXTURE','source_of_truth':'EXISTING_NATIVE_WORKLEDGER','same_hash_is_semantic_authority':False}
        save(output/'COMPLETION_SEAL.json',seal)
        receipt={'state':'PASS','case_id':case_id,'run':output.relative_to(ROOT).as_posix() if output.is_relative_to(ROOT) else str(output),
                 'result':result,'blueprint':blueprint,'seal_sha256':sha((output/'COMPLETION_SEAL.json').read_bytes()),'manifest_sha256':seal['manifest_sha256']}
        from moot_runtime import record_case
        record_case(case_id,receipt)
        emit('COMPLETE',{'state':'PASS','case_id':case_id,'run':receipt['run'],'sha256_seal':receipt['seal_sha256'],'native_journal_sha256':result['native_journal_sha256']})
        return receipt
    except ControlledCancel:
        receipt={'state':'HOLD','reason':'OPERATOR_CANCELLED; exact partial run retained; no automatic retry','run':str(output),'automatic_retry':False}
        save(output/'CANCEL_RECEIPT.json',receipt);emit('STOP',receipt);return receipt
    except Exception as exc:
        receipt={'state':'FAIL','exception_type':type(exc).__name__,'detail':str(exc)[:500],'run':str(output),'automatic_retry':False}
        save(output/'FAILURE_RECEIPT.json',receipt);emit('ERROR',receipt);raise
    finally:
        sample.run_process=original
        if old_sample is None:os.environ.pop('SAMPLE_MODE',None)
        else:os.environ['SAMPLE_MODE']=old_sample
        _rail_lock.release()

def observe_sample_batch(value):
    """Project completed legacy sample output without altering native events."""
    result=value.get('result',{})
    if value.get('status')!='PASS' or not result.get('samples'):return
    run=ROOT/result['run']
    from moot_runtime import record_case
    for case in result['samples']:
        filename=next(filename for ident,filename in CASES.values() if ident==case['case_id'])
        source=run/Path(filename).stem
        output=source/'R010_CONTROL'
        if output.exists():raise ValueError('Preserve existing sample projection')
        output.mkdir()
        preview=_blueprint(output,case,'../RESULT.json')
        rows=[{'path':p.name,'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())} for p in sorted(output.iterdir()) if p.is_file()]
        save(output/'CASE_MANIFEST.json',{'schema':'yamrail.r010.legacy-sample-observation/1','files':rows,'source_result_sha256':sha((source/'RESULT.json').read_bytes()),'native_journal_sha256':case['native_journal_sha256'],'native_events_modified':False})
        save(output/'COMPLETION_SEAL.json',{'state':'PASS','case_id':case['case_id'],'manifest_sha256':sha((output/'CASE_MANIFEST.json').read_bytes()),'native_journal_sha256':case['native_journal_sha256'],'observer_only':True})
        record_case(case['case_id'],{'run':output.relative_to(ROOT).as_posix(),'result':case,'seal_sha256':sha((output/'COMPLETION_SEAL.json').read_bytes())})

def handle_extra(argv,envelope,emit):
    if not argv:return None
    if argv[0]=='ui':
        p=argparse.ArgumentParser(prog='yr-code ui');p.parse_args(argv[1:])
        if not sys.stdin.isatty() or not sys.stdout.isatty():
            return emit(envelope('ui','HOLD',result={'reason':'Interactive terminal required; use rail or moot --format json for redirected output.'}),'json')
        from control_console import main
        return main()
    if argv[0]=='rail':
        p=argparse.ArgumentParser(prog='yr-code rail');p.add_argument('name',choices=list(CASES));p.add_argument('--format',choices=['text','json'],default='text');p.add_argument('--events',action='store_true');args=p.parse_args(argv[1:])
        callback=(lambda event:print(json.dumps(event,ensure_ascii=False),flush=True)) if args.events else None
        try:
            result=run_rail(args.name,callback=callback)
            value=envelope('rail '+args.name,result['state'],result=result)
        except Exception as exc:value=envelope('rail '+args.name,'FAIL',result={'reason':'RAIL_FAILED_OR_PARTIAL_OUTPUT_RETAINED','exception_type':type(exc).__name__})
        if args.events:return value['exit_code']
        return emit(value,args.format)
    if argv[0]=='moot':
        p=argparse.ArgumentParser(prog='yr-code moot');p.add_argument('action',choices=['status','check'],nargs='?',default='status');p.add_argument('--format',choices=['text','json'],default='text');p.add_argument('--archive');p.add_argument('--expected-sha256');args=p.parse_args(argv[1:])
        from moot_runtime import inspect,read_register
        result=inspect(args.archive,args.expected_sha256) if args.action=='check' else read_register()
        return emit(envelope('moot '+args.action,result=result),args.format)
    return None
