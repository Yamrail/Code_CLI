"""Verify finite package bytes. Hash agreement is not semantic approval."""
from pathlib import Path
import os
from .portable_io import ScopeDenied,checked_relative,digest,path_is_link,safe_read
import json

MUTABLE_DIRS={'.git','.yr-code','__pycache__','.venv','out'}

def verify_manifest(manifest_path):
    p=Path(manifest_path).absolute();root=p.parent
    raw=safe_read(root,p.name,64*1024*1024);manifest=json.loads(raw)
    rows=manifest.get('files');seen=set();errors=[];verified=0;byte_count=0
    if not isinstance(rows,list) or len(rows)>100000:raise ScopeDenied('HOLD_MANIFEST_ROWS')
    for row in rows:
        rel=row.get('path');checked_relative(rel)
        if rel in seen:raise ScopeDenied('HOLD_DUPLICATE_MANIFEST_PATH')
        seen.add(rel)
        if rel in {'MANIFEST.json','SHA256SUMS.txt'} or rel.split('/')[0] in MUTABLE_DIRS:
            raise ScopeDenied('HOLD_MANIFEST_RECURSION_OR_MUTABLE_ENTRY')
        if not isinstance(row.get('bytes'),int) or row['bytes']<0 or not isinstance(row.get('sha256'),str) or len(row['sha256'])!=64:
            raise ScopeDenied('HOLD_MANIFEST_DIGEST_SHAPE')
        if row['bytes']>128*1024*1024:raise ScopeDenied('HOLD_MANIFEST_MEMBER_SIZE_LIMIT')
        try:
            b=safe_read(root,rel,max_bytes=max(1,row['bytes']))
            if len(b)!=row['bytes'] or digest(b)!=row['sha256']:errors.append({'path':rel,'reason':'BYTES_OR_SHA256_MISMATCH'})
            else:verified+=1;byte_count+=len(b)
        except (OSError,ValueError) as e:errors.append({'path':rel,'reason':type(e).__name__})
    actual=set()
    for folder,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d not in MUTABLE_DIRS]
        kept=[]
        for d in dirs:
            q=Path(folder)/d
            if path_is_link(q):errors.append({'path':q.relative_to(root).as_posix(),'reason':'UNADMITTED_LINK_DIRECTORY'})
            else:kept.append(d)
        dirs[:]=kept
        for name in files:
            q=Path(folder)/name;rel=q.relative_to(root).as_posix()
            if rel not in {p.name,'SHA256SUMS.txt'}:actual.add(rel)
    for rel in sorted(actual-seen):errors.append({'path':rel,'reason':'UNMANIFESTED_FILE'})
    index_path=root/'SHA256SUMS.txt'
    index_verified=False
    if index_path.is_file():
        index={}
        for line in safe_read(root,'SHA256SUMS.txt',64*1024*1024).decode('utf-8').splitlines():
            h,rel=line.split('  ',1);checked_relative(rel)
            if rel in index:raise ScopeDenied('HOLD_DUPLICATE_SHA256_INDEX_PATH')
            index[rel]=h
        wanted={r['path']:r['sha256'] for r in rows};wanted[p.name]=digest(raw)
        index_verified=index==wanted
        if not index_verified:errors.append({'path':'SHA256SUMS.txt','reason':'INDEX_MISMATCH'})
    else:errors.append({'path':'SHA256SUMS.txt','reason':'MISSING_INDEX'})
    return {'status':'PASS' if not errors else 'FAIL','manifest_sha256':digest(raw),'verified_files':verified,'verified_bytes':byte_count,'exact_inventory':actual==seen,'sha256_index_verified':index_verified,'errors':errors,'semantic_acceptance':'NOT_INFERRED','authority_effect':'NONE'}
