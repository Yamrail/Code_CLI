"""Local dotenv loading and discovery for the three credential-free rails."""
from pathlib import Path
import json,os,re,shutil,subprocess,sys

ROOT=Path(__file__).resolve().parent
ENV_KEYS={'SAMPLE_MODE','OPENAI_API_KEY','OPENAI_MODEL','NIGHTSHIFT_BASE_URL','NIGHTSHIFT_API_KEY','NIGHTSHIFT_MODEL','ZETARIS_BASE_URL','ZETARIS_TOKEN','RTA_NODE'}

def load_environment(root=None,cwd=None,environ=None):
    root=Path(root or ROOT).resolve();cwd=Path(cwd or Path.cwd()).resolve();env=os.environ if environ is None else environ
    package=root.parent.parent if root.parent.name=='source' else root
    candidates=[]
    for folder in [cwd,package,root]:
        if folder not in candidates:candidates.append(folder)
    found=False;loaded=[];credential_fields_seen=False
    for folder in candidates:
        path=folder/'.env'
        if not path.is_file() or path.is_symlink():continue
        found=True
        for line in path.read_text(encoding='utf-8-sig').splitlines():
            line=line.strip()
            if not line or line.startswith('#'):continue
            if line.startswith('export '):line=line[7:].lstrip()
            name,separator,value=line.partition('=');name=name.strip()
            if not separator or name not in ENV_KEYS:continue
            if name.endswith(('_KEY','_TOKEN')):credential_fields_seen=True
            value=value.strip()
            if len(value)>1 and value[0]==value[-1] and value[0] in {'"',"'"}:value=value[1:-1]
            else:value=re.split(r'\s+#',value,maxsplit=1)[0].rstrip()
            if name not in env:env[name]=value;loaded.append(name)
    if not found:
        for folder in candidates:
            example=folder/'.env.example'
            if example.is_file() and not example.is_symlink() and re.search(r'^\s*SAMPLE_MODE\s*=\s*[\"\']?true[\"\']?\s*(?:#.*)?$',example.read_text(encoding='utf-8-sig'),re.M|re.I):
                env.setdefault('SAMPLE_MODE','true');break
    return {'dotenv_present':found,'loaded_names':sorted(set(loaded)),'credential_fields_seen':credential_fields_seen,'credential_values_reported':False,'process_environment_overridden':False}

def sample_environment():
    # These commands only run fixed synthetic/offline cases. Explicit sample
    # invocation cannot turn into a paid or general-purpose execution route.
    os.environ['SAMPLE_MODE']='true'

def node_candidates():
    candidates=[]
    def add(value):
        if value:
            try:path=Path(value).expanduser()
            except RuntimeError:return
            if path not in candidates:candidates.append(path)
    add(os.environ.get('RTA_NODE'));add(shutil.which('node'))
    add(Path(os.environ.get('ProgramFiles',r'C:\Program Files'))/'nodejs/node.exe')
    try:home=Path.home()
    except RuntimeError:home=None
    local=os.environ.get('LOCALAPPDATA')
    if local:add(Path(local)/'Programs/nodejs/node.exe')
    elif home:add(home/'AppData/Local/Programs/nodejs/node.exe')
    for path in [Path(sys.executable).parent/'node.exe',ROOT/'runtime/node.exe',ROOT/'runtime/node/bin/node.exe',ROOT/'runtimes/node/node.exe',ROOT/'node/node.exe']:
        add(path)
    if home:add(home/'.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe')
    return candidates

def discover_node():
    return next((str(path.resolve()) for path in node_candidates() if path.is_file()),None)

def world_model_command(input_path):
    node=discover_node()
    return [node,str(ROOT/'adapters/reasoning_world_model.js'),str(input_path)] if node else [sys.executable,'-I','-S','-B',str(ROOT/'adapters/reasoning_world_model.py'),str(input_path)]

def world_model_runtime():
    node=discover_node()
    if node:
        run=subprocess.run([node,'--version'],capture_output=True,timeout=15)
        smoke=subprocess.run([node,'-e','process.stdout.write(JSON.stringify({ok:2+2===4}))'],capture_output=True,timeout=15)
        ok=run.returncode==smoke.returncode==0 and json.loads(smoke.stdout).get('ok') is True
        return {'status':'PASS' if ok else 'FAIL','backend':'NODE_PINNED_METERLESS_REFERENCE','node_discovered':True,'node_path':node,'node_version':run.stdout.decode('utf-8','replace').strip(),'smoke':'PASS' if ok else 'FAIL','provider_calls':0}
    run=subprocess.run([sys.executable,'-I','-S','-B',str(ROOT/'adapters/reasoning_world_model.py'),'--self-test'],capture_output=True,timeout=15)
    result=json.loads(run.stdout);result.update(node_discovered=False,node_path=None,smoke=result['status'])
    if run.returncode!=0:result['status']='FAIL'
    return result
