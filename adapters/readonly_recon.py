"""Passive local fixture review; no network, imports or target execution."""
from __future__ import annotations
import ast,json,os,re
from pathlib import Path
from .portable_io import ScopeDenied,admit_path,digest,path_is_link,safe_read,utcnow,write_json

MAX_FILES=256
MAX_TOTAL=16*1024*1024
MAX_FILE=2*1024*1024

def inspect_python(text):
    findings=[]
    try:tree=ast.parse(text)
    except SyntaxError as e:return [{'rule':'PYTHON_SYNTAX_ERROR','line':e.lineno,'scope':'STATIC_ONLY'}]
    for node in ast.walk(tree):
        if not isinstance(node,ast.Call):continue
        name=node.func.id if isinstance(node.func,ast.Name) else node.func.attr if isinstance(node.func,ast.Attribute) else ''
        if name in {'eval','exec'}:findings.append({'rule':'DYNAMIC_CODE_EXECUTION_CALL','line':node.lineno,'scope':'REVIEW_FINDING_NOT_EXPLOIT_PROOF'})
        if any(k.arg=='shell' and isinstance(k.value,ast.Constant) and k.value.value is True for k in node.keywords):
            findings.append({'rule':'SHELL_TRUE_CALL','line':node.lineno,'scope':'REVIEW_FINDING_NOT_EXPLOIT_PROOF'})
    return findings

def run_recon(root,output,allowed_fixture):
    allowed=admit_path(allowed_fixture).resolve()
    root=admit_path(root);output=Path(output)
    if path_is_link(root) or not root.resolve().is_relative_to(allowed):
        raise ScopeDenied('HOLD_SCOPE_NOT_PACKAGED_SYNTHETIC_FIXTURE')
    if output.resolve().is_relative_to(root.resolve()):raise ScopeDenied('HOLD_OUTPUT_INSIDE_READONLY_TARGET')
    files=[];denied=[];total=0
    for folder,dirs,names in os.walk(root,followlinks=False):
        kept=[]
        for d in sorted(dirs):
            p=Path(folder)/d;rel=p.relative_to(root).as_posix()
            if path_is_link(p):denied.append({'path':rel,'reason':'LINK_OR_REPARSE_DIRECTORY'})
            elif d not in {'.git','__pycache__','.venv'}:kept.append(d)
        dirs[:]=kept
        for name in sorted(names):
            p=Path(folder)/name;rel=p.relative_to(root).as_posix()
            if len(files)+len(denied)>=MAX_FILES:raise ScopeDenied('HOLD_RECON_FILE_COUNT')
            try:b=safe_read(root,rel,MAX_FILE)
            except (OSError,ValueError) as e:denied.append({'path':rel,'reason':str(e) if isinstance(e,ScopeDenied) else type(e).__name__});continue
            total+=len(b)
            if total>MAX_TOTAL:raise ScopeDenied('HOLD_RECON_TOTAL_BYTES')
            row={'source_id':'LOCAL_'+digest(rel.encode())[:12],'path':rel,'bytes':len(b),'sha256':digest(b),'observed_at_utc':utcnow(),'evidence_class':'SYNTHETIC_FIXTURE','findings':[]}
            if p.suffix=='.py':row['findings']=inspect_python(b.decode('utf-8',errors='replace'))
            if p.suffix=='.json':
                try:json.loads(b)
                except (ValueError,UnicodeDecodeError):row['findings'].append({'rule':'INVALID_JSON','scope':'STATIC_ONLY'})
            # Report locations only; never print a candidate credential's value.
            for i,line in enumerate(b.decode('utf-8',errors='replace').splitlines(),1):
                if re.search(r'(?i)(api[_-]?key|password|secret)\s*=\s*[\'\"][^\'\"]+',line):
                    row['findings'].append({'rule':'POTENTIAL_EMBEDDED_CREDENTIAL_REVIEW','line':i,'value_emitted':False})
            files.append(row)
    report={'schema':'yamrail.code-cli.local-recon/1','status':'PASS' if not denied else 'HOLD','mode':'READ_ONLY_LOCAL_SYNTHETIC_FIXTURE','network_requests':0,'target_executed':False,'writes_to_target':False,'scope':'PACKAGED_SAFE_PUBLIC_OR_SYNTHETIC_FIXTURE','observed_at_utc':utcnow(),'sources':files,'denied_entries':denied,'not_a_security_certification':True,'host_checks_not_an_os_sandbox':True}
    write_json(output/'recon.json',report)
    lines=['# Local read-only prework','',f"Sources: {len(files)}; actual network requests: 0.",'','All target files are synthetic fixtures. Findings need investigator review.','']
    for row in files:
        lines.append(f"- `{row['path']}` — SHA256 `{row['sha256']}`")
        for f in row['findings']:lines.append(f"  - {f['rule']} at line {f.get('line','?')} (static review)")
    if denied:lines+=['','Denied links or other entries are preserved in recon.json as HOLD.']
    (output/'recon.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return report
