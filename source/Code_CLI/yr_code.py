#!/usr/bin/env python3
"""YamRail Code_CLI: three fixed offline rails and their evidence inspections."""
from __future__ import annotations
import argparse,json,os
from pathlib import Path
import sys,time,uuid
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from runtime_support import load_environment
load_environment()
VERSION='0.3.0-r010-public-minimal'
ORDER='YR-WO-CODECLI-R010-20261027-R003'

def envelope(command,status='PASS',result=None,**_):
    code={'PASS':0,'HOLD':2,'UNKNOWN':2,'NOT_EXECUTED':2,'FAIL':4,'AUTHORITY_DENIED':5}.get(status,4)
    return {'schema':'yamrail.code-cli.result/1','product':'YamRail/Code_CLI','version':VERSION,'command':command,'work_order_id':ORDER,'scope':'PUBLIC_FIXED_LOCAL_DEMO_NONCANONICAL','execution_class':'LOCAL_EXECUTED','status':'HOLD' if status=='AUTHORITY_DENIED' else status,'exit_code':code,'evidence_refs':[],'holds':[],'next_actions':[],'result':result or {},'authority_effect':'NONE','external_submission':False}

def emit(value,fmt):
    if fmt=='json':print(json.dumps(value,ensure_ascii=False,indent=2))
    else:
        print('YamRail/Code_CLI '+VERSION)
        print(value['command']+' | '+value['status'])
        print(json.dumps(value['result'],ensure_ascii=False,indent=2))
    return value['exit_code']

def main(argv=None):
    from console_runtime import handle_extra,observe_sample_batch
    actual=list(sys.argv[1:] if argv is None else argv)
    if not actual and argv is None and sys.stdin.isatty() and sys.stdout.isatty():actual=['ui']
    if actual and actual[0] in {'ui','rail','moot'}:return handle_extra(actual,envelope,emit)
    if actual and actual[0]=='--version':print(VERSION);return 0
    # There is no hidden owner-mode switch, shell expansion, provider or CAD route.
    if actual and actual[0] not in {'doctor','status','sample','evidence','tools','-h','--help'}:
        return emit(envelope(actual[0],'AUTHORITY_DENIED',{'state':'GOVERNANCE_INTERCEPT','clause':'R010-Sec04: Unbounded Autonomy Containment','reason':'Only three fixed deterministic rails and read-only setup/evidence commands are wired.','operation_dispatched':False,'allowed':['sample --all','evidence verify','moot status']}),'json' if 'json' in actual else 'text')
    parser=argparse.ArgumentParser(prog='yr-code',description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    def fmt(p):p.add_argument('--format',choices=['text','json'],default='text')
    for command in ['doctor','status']:
        p=sub.add_parser(command);fmt(p)
    p=sub.add_parser('sample');p.add_argument('--all',action='store_true');fmt(p)
    p=sub.add_parser('evidence');p.add_argument('action',choices=['verify','list']);p.add_argument('--manifest',choices=['MANIFEST.json'],default='MANIFEST.json');fmt(p)
    p=sub.add_parser('tools');p.add_argument('action',nargs='?',choices=['inventory','verify'],default='inventory');fmt(p)
    args=parser.parse_args(actual)
    try:
        if args.command=='doctor':
            from adapters.host_capabilities import doctor
            result=doctor();value=envelope('doctor',result['status'],result=result)
        elif args.command=='status':
            from moot_runtime import read_register
            register=read_register();value=envelope('status',result={'state':'OBSERVED_LOCAL_MOOT_PROJECTION','cases':register['cases'],'case_receipts':register.get('case_receipts',{}),'provider_calls':0,'authority_effect':'NONE'})
        elif args.command=='sample':
            from adapters.reasoning_sample import run_samples
            run=ROOT/'.yr-code/runs'/('sample_'+time.strftime('%Y%m%dT%H%M%S')+'_'+uuid.uuid4().hex[:8]);run.parent.mkdir(parents=True,exist_ok=True)
            result=run_samples(run)
            value=envelope('sample',result={'run':run.relative_to(ROOT).as_posix(),**result})
            observe_sample_batch(value)
            from console_runtime import save
            save(run/'CLI_RESULT.json',value)
        elif args.command=='evidence' and args.action=='list':
            from moot_runtime import read_register
            value=envelope('evidence list',result=read_register().get('case_receipts',{}))
        elif args.command=='evidence' or (args.command=='tools' and args.action=='verify'):
            from adapters.evidence_verify import verify_manifest
            result=verify_manifest(ROOT/'MANIFEST.json');value=envelope(args.command+' verify',result['status'],result)
        else:
            value=envelope('tools inventory',result={'tools':['three fixed deterministic fixture rails','Meterless World Model local projection','native WorkLedger STOP/readback','finite manifest/SHA256 verifier','SVG/HTML blueprint renderer'],'general_tool_execution':'UNCONNECTED','provider_gateway':'NOT_DISTRIBUTED','CAD_mutation':'UNCONNECTED'})
    except Exception as exc:
        value=envelope(args.command,'HOLD' if str(exc).startswith('HOLD_') else 'FAIL',{'reason':str(exc)[:300],'exception_type':type(exc).__name__,'no_automatic_retry':True})
    return emit(value,args.format)

if __name__=='__main__':sys.exit(main())
