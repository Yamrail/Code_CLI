"""Read-only/evidence-bound installation projection; never a canonical ledger."""
from pathlib import Path
import importlib.metadata,json,os,platform,shutil,struct,subprocess,sys
import threading
from console_runtime import ROOT,CASES,save,sha
REGISTER=ROOT/'.yr-code/INSTALL_MOOT_RESULT.json'
_lock=threading.RLock()

def _new():
    value=json.loads((ROOT/'setup/INSTALL_MOOT_RESULT_TEMPLATE.json').read_bytes())
    for item in value['items']:item['state']='UNKNOWN'
    value['host_observed']=False
    return value

def read_register():
    with _lock:
        return json.loads(REGISTER.read_bytes()) if REGISTER.is_file() else _new()

def _item(value,ident,state,fact,refs=()):
    item=next(x for x in value['items'] if x['moot_id']==ident)
    item.update(state=state,observed_fact=fact,evidence_refs=list(refs))

def inspect(archive=None,expected=None):
    from adapters.evidence_verify import verify_manifest
    from adapters.host_capabilities import doctor
    with _lock:
        value=read_register();folder=ROOT/'.yr-code/install';folder.mkdir(parents=True,exist_ok=True)
        host={'os':platform.system(),'build':platform.version(),'architecture':platform.machine(),'python_bits':struct.calcsize('P')*8,'available_disk':shutil.disk_usage(ROOT).free,'workspace':str(ROOT),'writable':os.access(ROOT,os.W_OK)}
        save(folder/'HOST_INVENTORY.json',host)
        host_ok=host['os']=='Windows' and host['python_bits']==64 and host['writable']
        _item(value,'M-J00','PASS' if host_ok else 'HOLD',host,['.yr-code/install/HOST_INVENTORY.json'])
        verified=verify_manifest(ROOT/'MANIFEST.json')
        observed={'source_manifest':verified,'archive_verification':'NOT_EXECUTED'}
        state='UNKNOWN'
        if archive and expected:
            path=Path(archive).absolute()
            if path.is_symlink() or not path.is_file():raise ValueError('ARCHIVE_MUST_BE_REGULAR_LOCAL_FILE')
            digest=sha(path.read_bytes());observed.update(archive_verification='PASS' if digest==expected else 'FAIL',archive_sha256=digest,expected_sha256=expected)
            state='PASS' if digest==expected and verified['status']=='PASS' else 'FAIL'
        elif verified['status']!='PASS':state='FAIL'
        save(folder/'ARCHIVE_VERIFICATION.json',observed)
        _item(value,'M-J01',state,observed,['.yr-code/install/ARCHIVE_VERIFICATION.json'])
        py={'version':platform.python_version(),'bits':struct.calcsize('P')*8,'executable':sys.executable,'wheelhouse_present':(ROOT/'wheelhouse').is_dir()}
        _item(value,'M-J02','PASS' if sys.version_info[:2]==(3,12) and py['bits']==64 and py['wheelhouse_present'] else 'HOLD',py,['.yr-code/install/RUNTIME_DISCOVERY.json'])
        from runtime_support import world_model_runtime
        runtime=world_model_runtime()
        _item(value,'M-J03',runtime['status'],runtime,['.yr-code/install/RUNTIME_DISCOVERY.json'])
        save(folder/'RUNTIME_DISCOVERY.json',{'python':py,'world_model':runtime})
        doc=doctor();save(folder/'CODECLI_DOCTOR.json',doc)
        local_venv=Path(sys.prefix).resolve()==(ROOT/'.venv').resolve()
        installed={}
        # Each profile has its own finite offline lock. An owner-only package
        # must not become a Public installation prerequisite.
        locked={}
        for line in (ROOT/'requirements-lock.txt').read_text(encoding='utf-8').splitlines():
            requirement=line.split(' --hash=',1)[0].strip()
            if not requirement or requirement.startswith('#'):continue
            package,version=requirement.split('==',1);locked[package]=version
        for package in locked:
            try:installed[package]=importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:installed[package]=None
        install={'local_venv_in_use':local_venv,'dependencies':installed,'required_locked_versions':locked,'doctor_status':doc['status'],'installer_execution':'SEE_INSTALL_ACCEPTANCE_RECEIPT; not inferred from dependency discovery'}
        save(folder/'CODECLI_INSTALL_RECEIPT.json',install)
        _item(value,'M-J04','PASS' if local_venv and locked and installed==locked and doc['status']=='PASS' else 'UNKNOWN',install,['.yr-code/install/CODECLI_INSTALL_RECEIPT.json','.yr-code/install/CODECLI_DOCTOR.json'])
        for ident,ref in [('M-J06','EEA'),('M-J07','GPLCore')]:
            _item(value,ident,'NOT_EXECUTED',{'disposition':'PINNED_STATIC_REFERENCE_ONLY','reference':ref,'base_demo_blocked':False,'policy':'R010 R003 overrides original supplement optional-reference HOLD wording'},['setup/REFERENCE_SOURCES.json','setup/R010_SETUP_BINDING.json'])
        _item(value,'M-J09','NOT_EXECUTED',{'default':'OPTIONAL_JUDGE_PROBE_NOT_REQUESTED','provider_calls':0,'owner_CAD_connection':'Separate owner receipt, not a judge API probe'},[])
        value['host_observed']=True
        _summarize(value)
        save(REGISTER,value);return value

def _summarize(value):
    all_cases=all(value['cases'].get(name)=='PASS' for name,_ in CASES.values())
    if all_cases:
        refs=[x['run']+'/COMPLETION_SEAL.json' for x in value.get('case_receipts',{}).values()]
        _item(value,'M-J05','PASS',{'three_new_local_cases':True,'decision_class':'DETERMINISTIC_SYNTHETIC_FIXTURE','actual_processes_and_native_journals':True,'actual_model_calls':0},refs)
        _item(value,'M-J08','PASS',{'technical_evidence_summary':'THREE_CASE_SEALS_RECORDED','human_acceptance':'NOT_INFERRED','independent_hardware':'NOT_ESTABLISHED','references':'PINNED_STATIC_REFERENCE_ONLY'},refs)

def record_case(case_id,receipt):
    with _lock:
        value=read_register();value['cases'][case_id]='PASS'
        value.setdefault('case_receipts',{})[case_id]={'run':receipt['run'],'seal_sha256':receipt['seal_sha256'],'native_journal_sha256':receipt['result']['native_journal_sha256'],'checks':receipt['result']['checks']}
        _summarize(value);save(REGISTER,value)
