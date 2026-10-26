#!/usr/bin/env python3
"""YamRail/Code_CLI: transferable, observed local prework and coding workflow."""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import sys
import uuid
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from adapters.portable_io import ScopeDenied,admit_path,reject_network_path,digest,safe_read,utcnow,write_json

VERSION='0.1.0-r008-private-candidate'
ORDER='YR-WO-HACK-CODE-CLI-HANDOFF-20261026-R007'
HOLDS=[
 {'id':'SPONSOR_NIGHTSHIFT_NEMOTRON','state':'HOLD','scope':'LIVE_INFERENCE','reason':'No actual provider receipt; no unapproved paid calls.'},
 {'id':'SPONSOR_ZETARIS','state':'HOLD','scope':'LIVE_DATA_QUERY','reason':'No actual governed query receipt.'},
 {'id':'FULL_AGENT_YARD_ROUTE','state':'HOLD','scope':'ISOLATION','reason':'Whole agent/Office/CAD routing through physical yard is not proven.'},
 {'id':'RAM_AND_ENCRYPTION','state':'HOLD','scope':'STORAGE','reason':'RAM backing, encrypted scratch and zero remanence are unproven.'},
 {'id':'DIRECT_CODEX_CLI','state':'HOLD','scope':'DIRECT_INTERNAL_CLI','reason':'Prior direct CLI attempt was policy-blocked; no automatic retry.'},
 {'id':'EXTERNAL_RELEASE','state':'HOLD','scope':'HUMAN_AUTHORITY','reason':'Public/private-source release, submission and canonical promotion require separate Human artifact.'}
]

def envelope(command,status='PASS',execution='LOCAL_EXECUTED',result=None,holds=None,refs=None,next_actions=None):
    exit_code={'PASS':0,'HOLD':2,'UNKNOWN':2,'NOT_EXECUTED':2,'INPUT_REJECTED':3,'FAIL':4,'AUTHORITY_DENIED':5}.get(status,4)
    public_status='HOLD' if status in {'INPUT_REJECTED','AUTHORITY_DENIED'} else status
    return {'schema':'yamrail.code-cli.result/1','product':'YamRail/Code_CLI','version':VERSION,'command':command,'work_order_id':ORDER,'scope':'LOCAL_NONCANONICAL_PRIVATE_CANDIDATE','execution_class':execution,'status':public_status,'exit_code':exit_code,'evidence_refs':refs or [],'holds':holds or [],'next_actions':next_actions or [],'result':result or {},'observed_at_utc':utcnow(),'authority_effect':'NONE','external_submission':False}

def emit(value,fmt):
    if fmt=='json':print(json.dumps(value,ensure_ascii=False,indent=2))
    else:
        print(f"YamRail/Code_CLI {VERSION}")
        print(f"{value['command']} | {value['status']} | {value['execution_class']}")
        result=value.get('result',{})
        for key in ['state','domain_status','reason','run','report','native_trace','native_stage','checks','verified_files','manifest_sha256','summary']:
            if key in result:print(key+': '+json.dumps(result[key],ensure_ascii=False))
        if value['evidence_refs']:print('evidence: '+', '.join(value['evidence_refs']))
        for hold in value['holds']:print('HOLD '+(hold['id'] if isinstance(hold,dict) else str(hold)))
        for nxt in value['next_actions']:print('NEXT '+str(nxt))
    return value['exit_code']

def input_path(value):
    reject_network_path(value)
    p=Path(value)
    if p.is_absolute():return admit_path(p)
    candidate=admit_path(Path.cwd()/p,allow_missing=True)
    return admit_path(candidate if candidate.exists() else ROOT/p)

def new_run(kind,requested=None):
    if requested:
        p=admit_path(requested,allow_missing=True)
        # Output may be anywhere explicitly selected except immutable package content.
        if p.is_relative_to(ROOT) and not any(p.is_relative_to(ROOT/d) for d in ['.yr-code','out']):
            raise ScopeDenied('HOLD_OUTPUT_MUST_BE_RUNTIME_DIRECTORY_OR_OUTSIDE_PACKAGE')
    else:p=admit_path(ROOT/'.yr-code/runs'/(kind+'_'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]),allow_missing=True)
    if p.exists():raise ScopeDenied('HOLD_EXISTING_RUN_NO_AUTO_RETRY')
    p.parent.mkdir(parents=True,exist_ok=True)
    return p

def portable_ref(path):
    p=Path(path).absolute()
    return p.relative_to(ROOT).as_posix() if p.is_relative_to(ROOT) else 'EXPLICIT_OPERATOR_OUTPUT/'+p.name

def save_result(run,result):
    write_json(run/'CLI_RESULT.json',result)
    return portable_ref(run/'CLI_RESULT.json')

def outcome_status(receipt):
    """Propagate only the host/domain outcome chain, not expected counterexamples."""
    statuses=[];current=receipt
    while isinstance(current,dict):
        stated=current.get('status')
        if stated in {'FAIL','HOLD','UNKNOWN','NOT_EXECUTED'}:statuses.append(stated)
        state=str(current.get('state',''))
        if state.startswith('FAIL'):statuses.append('FAIL')
        elif state.startswith(('HOLD','DENY')):statuses.append('HOLD')
        elif state.startswith('UNKNOWN'):statuses.append('UNKNOWN')
        current=current.get('result')
    return next((x for x in ['FAIL','UNKNOWN','HOLD','NOT_EXECUTED'] if x in statuses),'PASS')

def run_native(kind,args,runner):
    from adapters.native_host import supervise_stage
    run=new_run(kind,args.output)
    receipt=supervise_stage(run,kind.upper(),runner,work_order_id=ORDER,root_purpose=kind.upper()+'_LOCAL')
    status=outcome_status(receipt)
    holds=HOLDS+([{'id':kind.upper()+'_DOMAIN_'+status,'state':status,'scope':kind,'reason':'Host invocation completion does not clear the returned domain outcome.'}] if status!='PASS' else [])
    result=envelope(kind,status,result={'run':portable_ref(run),'domain_status':status,**receipt},holds=holds)
    result['evidence_refs']=[save_result(run,result)]
    return result

def last_run():
    base=admit_path(ROOT/'.yr-code/runs',allow_missing=True)
    candidates=[]
    if base.is_dir():
        for child in base.iterdir():
            directory=admit_path(child)
            if not directory.is_dir():continue
            target=directory/'CLI_RESULT.json'
            try:target.lstat()
            except FileNotFoundError:continue
            candidates.append(admit_path(target))
            if len(candidates)>512:raise ScopeDenied('HOLD_LOCAL_RUN_COUNT_LIMIT')
        candidates.sort(key=lambda p:p.stat().st_mtime_ns,reverse=True)
    if not candidates:return None
    p=candidates[0]
    receipt=json.loads(safe_read(p.parent,p.name,8*1024*1024))
    if receipt.get('schema')!='yamrail.code-cli.result/1' or receipt.get('product')!='YamRail/Code_CLI' or receipt.get('status') not in {'PASS','FAIL','HOLD','UNKNOWN','NOT_EXECUTED'}:
        raise ScopeDenied('HOLD_LOCAL_COMMAND_RECEIPT_SCHEMA')
    keys=['schema','product','version','command','status','execution_class','observed_at_utc','evidence_refs']
    limited={k:receipt[k] for k in keys if k in receipt}
    # Never echo arbitrary fields from a supplied JSON history file.
    for key in ['version','command','observed_at_utc']:
        if not isinstance(limited.get(key),str) or len(limited[key])>160:raise ScopeDenied('HOLD_LOCAL_RECEIPT_FIELD')
    native=native_readback_safely(p.parent)
    snap=native.get('snapshot',{})
    thin={'state':native.get('state','UNKNOWN'),'native_revision':native.get('native_revision'),'checkpoint':native.get('checkpoint'),'active':snap.get('active'),'only_workflow_state_writer':native.get('only_workflow_state_writer'),'execution_authority_granted_by_readback':False}
    return {'run':portable_ref(p.parent),'command_receipt':limited,'native_state':thin}

def native_readback_safely(source):
    from adapters.native_host import read_native_state
    source=admit_path(source);count=0;total=0
    for folder,dirs,files in os.walk(source,followlinks=False):
        for d in dirs:admit_path(Path(folder)/d)
        for name in files:
            p=admit_path(Path(folder)/name)
            count+=1;total+=p.stat().st_size
            if count>2048 or total>64*1024*1024:raise ScopeDenied('HOLD_NATIVE_HISTORY_SIZE_LIMIT')
    return read_native_state(source)

def parser():
    p=argparse.ArgumentParser(prog='yr-code',description=__doc__)
    p.add_argument('--version',action='version',version=VERSION)
    sub=p.add_subparsers(dest='command',required=True)
    def fmt(x):x.add_argument('--format',choices=['text','json'],default='text')
    for name in ['doctor','status']:
        x=sub.add_parser(name);fmt(x)
    d=sub.add_parser('demo');fmt(d);d.add_argument('--output');d.add_argument('--profile',choices=['hackathon','hackathon_judge','full_authorized_handoff'],default='hackathon_judge');d.add_argument('--evidence-mode',choices=['replay','synthetic'],default='replay')
    r=sub.add_parser('recon');rs=r.add_subparsers(dest='recon_action',required=True);local=rs.add_parser('local');local.add_argument('--root',required=True);local.add_argument('--output');fmt(local)
    for name in ['sources','osint','diff','handover']:
        x=rs.add_parser(name);x.add_argument('arguments',nargs=argparse.REMAINDER);fmt(x)
    e=sub.add_parser('evidence');es=e.add_subparsers(dest='evidence_action',required=True)
    v=es.add_parser('verify');v.add_argument('--manifest',default='MANIFEST.json');fmt(v)
    li=es.add_parser('list');li.add_argument('--run');fmt(li)
    t=sub.add_parser('tools');t.add_argument('action',nargs='?',choices=['inventory','verify'],default='inventory');fmt(t)
    sp=sub.add_parser('sponsor');sp.add_argument('action',nargs='?',default='doctor',choices=['doctor','world-model','nightshift','zetaris']);sp.add_argument('--dry-run',action='store_true');fmt(sp)
    rp=sub.add_parser('report');rp.add_argument('action',choices=['make']);rp.add_argument('--input',required=True);rp.add_argument('--paper',choices=['a4-landscape'],default='a4-landscape');rp.add_argument('--out');rp.add_argument('--output');fmt(rp)
    g=sub.add_parser('graph');g.add_argument('action',choices=['render','history']);g.add_argument('--input');g.add_argument('--snapshot');g.add_argument('--type',default='content',choices=['content','history','workledger','security']);g.add_argument('--paper',choices=['a4-landscape'],default='a4-landscape');g.add_argument('--out');g.add_argument('--output');fmt(g)
    c=sub.add_parser('cad');c.add_argument('action',choices=['doctor','open','export']);c.add_argument('--local-only',action='store_true');c.add_argument('--input');c.add_argument('--out');c.add_argument('--format',default='json');c.add_argument('--export-format',choices=['dwg','dxf'])
    b=sub.add_parser('build');b.add_argument('action',choices=['code','compile','cad','office','all']);b.add_argument('--output');fmt(b)
    h=sub.add_parser('work_handover');h.add_argument('--run',required=True);h.add_argument('--output');fmt(h)
    for name in ['work','yard','inspect','evidence_graph','recon_osint']:
        x=sub.add_parser(name);x.add_argument('arguments',nargs=argparse.REMAINDER);fmt(x)
    return p

def dispatch(args):
    cmd=args.command
    if cmd=='doctor':
        from adapters.host_capabilities import doctor
        return envelope(cmd,result=doctor(),holds=HOLDS)
    if cmd=='status':return envelope(cmd,result={'state':'OBSERVED_NATIVE_READBACK' if (recent:=last_run()) else 'NO_LOCAL_RUN_YET','last_run':recent,'sponsor_live_calls':0},holds=HOLDS)
    if cmd=='demo':
        from adapters.demo import run_demo
        run=new_run('demo',args.output)
        receipt=run_demo(run)
        value=envelope(cmd,outcome_status(receipt),result={'run':portable_ref(run),'requested_evidence_mode':args.evidence_mode,'effective_evidence_mode':'DERIVED_SAFE_CODE_FIXTURE_AND_CURRENT_LOCAL_TESTS','profile_request':args.profile,'profile_effect':'SCENARIO_LABEL_ONLY_NO_ADDITIONAL_AUTHORITY_OR_INSTALLATION',**receipt},holds=HOLDS)
        value['evidence_refs']=[save_result(run,value)]
        return value
    if cmd=='recon':
        if args.recon_action!='local':return envelope('recon '+args.recon_action,'NOT_EXECUTED',result={'reason':'External/source adapters require a separately qualified scope; only recon local is implemented.'})
        from adapters.readonly_recon import run_recon
        root=input_path(args.root)
        return run_native('recon',args,lambda stage:run_recon(root,stage,ROOT/'fixtures/safe_public_or_synthetic'))
    if cmd=='evidence' and args.evidence_action=='verify':
        from adapters.evidence_verify import verify_manifest
        result=verify_manifest(input_path(args.manifest))
        return envelope('evidence verify',result['status'],result=result)
    if cmd=='evidence':
        run=input_path(args.run) if args.run else None
        return envelope('evidence list',result={'run':portable_ref(run) if run else None,'last_run':last_run() if run is None else None,'rule':'Existing native journals are evidence; do not rebind a relocated active ledger.'})
    if cmd=='tools':
        if args.action=='verify':
            if not (ROOT/'MANIFEST.json').is_file():return envelope('tools verify','HOLD',result={'reason':'HOLD_PACKAGE_MANIFEST_NOT_PRESENT'})
            from adapters.evidence_verify import verify_manifest
            verified=verify_manifest(ROOT/'MANIFEST.json')
            return envelope('tools verify',verified['status'],result={'verification_scope':'SEALED_PACKAGE_BYTES_ONLY_NOT_TOOL_FUNCTIONALITY_OR_LICENSE',**verified})
        data=json.loads(safe_read(ROOT,'tool_shelf/TOOLS.json',32*1024*1024))
        return envelope('tools '+args.action,result=data,holds=[{'id':'SOURCE_IMPORT_NOT_EXECUTION_AUTHORITY','state':'HOLD'}])
    if cmd=='sponsor':
        keys=['NIGHTSHIFT_API_KEY','METERLESS_API_KEY','ZETARIS_API_KEY','ZETARIS_TOKEN']
        presence={k:bool(os.environ.get(k)) for k in keys}
        return envelope('sponsor '+args.action,'HOLD',result={'state':'NO_LIVE_SPONSOR_REQUEST_DISPATCHED','credentials_present_by_name_only':presence,'credential_values_emitted':False,'network_requests':0,'dry_run':bool(args.dry_run),'world_model':'SEE_NATIVE_DEMO_LOCAL_RECEIPT','nightshift_nemotron':'LIVE_UNEXECUTED','zetaris':'LIVE_UNEXECUTED'},holds=HOLDS[:2])
    if cmd in {'report','graph'}:
        from adapters.osint_render import render_graph,make_report,history_graph
        src=input_path(args.snapshot or args.input) if cmd=='graph' else input_path(args.input)
        if src.is_symlink() or not src.is_file():raise ScopeDenied('HOLD_CASE_INPUT_NOT_REGULAR')
        args.output=args.output or args.out
        if cmd=='report':runner=lambda stage:make_report(src,stage)
        elif args.action=='history':runner=lambda stage:history_graph(src,stage)
        else:runner=lambda stage:render_graph(src,stage,args.type)
        return run_native(cmd,args,runner)
    if cmd=='cad':
        from adapters.cad_local import doctor,operation
        result=doctor(args.local_only) if args.action=='doctor' else operation(args.action,ROOT,args.input,args.local_only,args.export_format,args.out)
        return envelope('cad '+args.action,'AUTHORITY_DENIED' if result['reason'].startswith('DENY_') else 'HOLD',result=result,holds=[{'id':result['reason'],'state':'HOLD'}])
    if cmd=='build':
        from adapters.build_pipeline import run_build
        run=new_run('build',args.output)
        result=run_build('compile' if args.action=='code' else args.action,run)
        value=envelope('build '+args.action,outcome_status(result),result=result,holds=HOLDS)
        value['evidence_refs']=[save_result(run,value)]
        return value
    if cmd=='work_handover':
        source=input_path(args.run)
        if not source.is_relative_to(ROOT/'.yr-code') and not source.is_relative_to(ROOT/'out'):
            raise ScopeDenied('HOLD_HANDOVER_SOURCE_OUTSIDE_LOCAL_RUNTIME')
        observed=native_readback_safely(source)
        if not str(observed.get('state','')).startswith('PASS_'):
            return envelope(cmd,'HOLD',result={'reason':'NATIVE_READBACK_NOT_QUALIFIED','readback':observed})
        raw=safe_read(source,'CLI_RESULT.json',32*1024*1024)
        run=new_run('handover',args.output);run.mkdir()
        handoff={'schema':'yamrail.code-cli.worker-handover/1','source_run':portable_ref(source),'source_command_receipt_sha256':digest(raw),'native_readback_state':observed['state'],'source_code_version':VERSION,'new_operator_route':'Verify package, read prior evidence, start a fresh work order at the new location. Do not silently rebind a relocated native journal.','human_approval':'NOT_PRESENT_NOT_FABRICATED','external_submission':'PENDING_SEPARATE_HUMAN_GATE','holds':HOLDS,'created_utc':utcnow()}
        write_json(run/'HANDOVER.json',handoff)
        return envelope(cmd,result={'run':portable_ref(run),'state':'HANDOVER_RECEIPT_CREATED'},refs=[portable_ref(run/'HANDOVER.json')],holds=HOLDS)
    return envelope(cmd,'NOT_EXECUTED',result={'reason':'Command vocabulary is reserved; this adapter is not implemented or qualified. No action was dispatched.'},next_actions=['Use doctor, demo, recon local, evidence verify, report make, graph render/history or cad doctor.'])

def main(argv=None):
    args=parser().parse_args(argv)
    fmt=getattr(args,'format','text')
    if fmt not in {'json','text'}:
        # R008 cad export --format dwg is a requested output format, not proof of execution.
        if args.command=='cad' and fmt in {'dwg','dxf'}:args.export_format=fmt;fmt='json'
        else:fmt='json'
    try:value=dispatch(args)
    except ScopeDenied as e:value=envelope(args.command,'INPUT_REJECTED',result={'reason':str(e)},holds=[{'id':str(e),'state':'HOLD'}])
    except ModuleNotFoundError as e:value=envelope(args.command,'HOLD',result={'reason':'OPTIONAL_RUNTIME_OR_ADAPTER_MISSING','module':e.name},next_actions=['Read INSTALL.md and run doctor; no output is fabricated.'])
    except Exception as e:
        # A bounded diagnostic; do not dump environment or supplied source data.
        value=envelope(args.command,'FAIL',result={'reason':'EXECUTION_EXCEPTION','exception_type':type(e).__name__},next_actions=['Keep run evidence and inspect the local receipt before retrying.'])
    return emit(value,fmt)

if __name__=='__main__':sys.exit(main())
