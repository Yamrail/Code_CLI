#!/usr/bin/env python3
"""Create a NEW LOCAL candidate byte seal; this grants no release authority."""
from __future__ import annotations
import argparse,datetime,hashlib,json,os
from pathlib import Path
import sys
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from adapters.portable_io import admit_path,safe_read
SKIP={'.git','.yr-code','out','.venv','__pycache__'}

def digest(b):return hashlib.sha256(b).hexdigest()

def origin(rel):
    if rel.startswith('orders/'):
        return {'kind':'EXACT_RECEIVED_REMOTE_EXECUTION_ORDER','record':'SOURCE_PINS.json','authority_effect':'PRIVATE_EXECUTION_ONLY_NOT_EXTERNAL_RELEASE'}
    if rel.startswith('native_runtime/'):
        return {'kind':'PINNED_NATIVE_CODE_OR_LABELLED_DERIVATIVE','record':'native_runtime/IMPORT_PROVENANCE.json'}
    if rel.startswith('tool_shelf/osint_runtime/'):
        return {'kind':'PINNED_OSINT_CODE_FONT_OR_LABELLED_DERIVATIVE','record':'tool_shelf/osint_runtime/SOURCE_PROVENANCE.json'}
    if rel.startswith(('wheelhouse/','dependency_licenses/')):
        return {'kind':'PINNED_OSS_DISTRIBUTION_OR_ORIGINAL_NOTICE','record':'DEPENDENCIES.json'}
    if rel.startswith('tool_shelf/'):
        return {'kind':'R005_SHELF_SANITIZED_INDEX_OR_REVIEWED_SOURCE','record':'LICENSES_AND_PROVENANCE.csv'}
    if rel.startswith('evidence/'):
        return {'kind':'LABELLED_OBSERVATION_OR_DERIVED_RESEARCH_RECORD','record':'GENERATION_RECEIPT.json'}
    if rel.startswith('media/'):
        return {'kind':'GENERATED_CURRENT_PRODUCT_MEDIA','record':'GENERATION_RECEIPT.json'}
    return {'kind':'R007_R008_GENERATED_SOURCE_DOCUMENT_OR_SYNTHETIC_FIXTURE','record':'GENERATION_RECEIPT.json'}

def generate(label):
    rows=[]
    for folder,dirs,files in os.walk(ROOT,followlinks=False):
        dirs[:]=sorted(d for d in dirs if d not in SKIP)
        for directory in dirs:admit_path(Path(folder)/directory)
        for name in sorted(files):
            p=Path(folder)/name;rel=p.relative_to(ROOT).as_posix()
            if rel in {'MANIFEST.json','SHA256SUMS.txt','_PRIVATE_INTAKE.md'} or p.suffix=='.pyc':continue
            p=admit_path(p);b=safe_read(ROOT,rel,max_bytes=128*1024*1024)
            rows.append({'path':rel,'bytes':len(b),'sha256':digest(b),'origin':origin(rel)})
    rows.sort(key=lambda r:r['path'])
    manifest={'schema':'yamrail.code-cli.finite-manifest/1','label':label,'scope':'PRIVATE_CANDIDATE_NOT_HUMAN_RELEASE_APPROVAL','files':rows,'file_count':len(rows),'total_bytes':sum(x['bytes'] for x in rows),'excluded':['MANIFEST.json own bytes','SHA256SUMS.txt own index','.git/','.yr-code/','out/','.venv/','__pycache__/'],'own_hash':'NOT_EMBEDDED','stochastic_decision':'NOT_INFERRED_FROM_DETERMINISTIC_FREEZE','authority_effect':'NONE'}
    target=ROOT/'MANIFEST.json'
    if target.exists():
        history=ROOT/'.yr-code/seals/history';history.mkdir(parents=True,exist_ok=True)
        old=target.read_bytes();(history/(digest(old)+'.manifest.json')).write_bytes(old)
        idx=ROOT/'SHA256SUMS.txt'
        if idx.exists():(history/(digest(old)+'.SHA256SUMS.txt')).write_bytes(idx.read_bytes())
    target.write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    sums=[row['sha256']+'  '+row['path'] for row in rows]+[digest(target.read_bytes())+'  MANIFEST.json']
    (ROOT/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='utf-8')
    return {'manifest_sha256':digest(target.read_bytes()),'index_sha256':digest((ROOT/'SHA256SUMS.txt').read_bytes()),'files':len(rows),'bytes':manifest['total_bytes'],'label':label,'authority_effect':'NONE'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--new-local-candidate',required=True);a=p.parse_args();print(json.dumps(generate(a.new_local_candidate)))
