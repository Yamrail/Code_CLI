"""Bounded local file admission. These checks are not an OS sandbox."""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat

class ScopeDenied(ValueError):
    pass

def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def digest(data):
    return hashlib.sha256(data).hexdigest()

def write_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def checked_relative(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or '\x00' in name:
        raise ScopeDenied('HOLD_PATH_SYNTAX')
    p=PurePosixPath(name)
    if p.is_absolute() or any(x in {'.','..',''} for x in name.split('/')):
        raise ScopeDenied('HOLD_PATH_TRAVERSAL')
    return p

def path_is_link(path):
    st=Path(path).lstat()
    return stat.S_ISLNK(st.st_mode) or bool(getattr(st,'st_file_attributes',0)&0x400)

def reject_network_path(value):
    text=os.fspath(value)
    if text.startswith(('\\\\','//')) or '://' in text:
        raise ScopeDenied('HOLD_NETWORK_OR_DEVICE_PATH_NOT_LOCAL_SCOPE')
    if os.name=='nt':
        p=Path(text)
        if p.drive and not p.is_absolute():raise ScopeDenied('HOLD_DRIVE_RELATIVE_PATH')
        if p.drive and p.root:
            import ctypes
            if ctypes.windll.kernel32.GetDriveTypeW(p.anchor)==4:
                raise ScopeDenied('HOLD_REMOTE_MAPPED_DRIVE')

def admit_path(value,allow_missing=False):
    """Check lexical components before resolve can erase persistent links."""
    reject_network_path(value)
    original=Path(value)
    if original.drive and not original.is_absolute():raise ScopeDenied('HOLD_DRIVE_RELATIVE_PATH')
    path=Path(os.path.abspath(original))
    current=Path(path.anchor)
    for part in path.parts[1:]:
        if ':' in part or '\x00' in part:raise ScopeDenied('HOLD_ADS_OR_INVALID_PATH')
        current=current/part
        try:info=current.lstat()
        except FileNotFoundError:
            if allow_missing:return path
            raise ScopeDenied('HOLD_INPUT_NOT_FOUND')
        if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
            raise ScopeDenied('HOLD_PATH_LINK_OR_REPARSE')
    if path.is_file() and path.stat().st_nlink!=1:raise ScopeDenied('HOLD_INPUT_HARDLINK')
    return path

def safe_read(root, relative, max_bytes=8*1024*1024):
    """Reject persistent links/reparse points and check the opened regular file.

    Not a concurrent-adversarial-filesystem boundary; untrusted workers must not
    mutate this tree while the trusted host reads it.
    """
    root=admit_path(root);rel=checked_relative(relative);p=root
    if path_is_link(root):raise ScopeDenied('HOLD_ROOT_LINK')
    for part in rel.parts:
        p=p/part
        if path_is_link(p):raise ScopeDenied('HOLD_PATH_LINK_OR_REPARSE')
    if not p.resolve().is_relative_to(root.resolve()):raise ScopeDenied('HOLD_PATH_ESCAPE')
    before=p.stat(follow_symlinks=False)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1:raise ScopeDenied('HOLD_NONREGULAR_OR_HARDLINK')
    if getattr(before,'st_file_attributes',0)&(0x200|0x4000):raise ScopeDenied('HOLD_SPARSE_OR_ENCRYPTED_FILE')
    if before.st_size>max_bytes:raise ScopeDenied('HOLD_FILE_SIZE_LIMIT')
    flags=os.O_RDONLY|getattr(os,'O_BINARY',0)|getattr(os,'O_NOFOLLOW',0)
    fd=os.open(p,flags)
    try:
        opened=os.fstat(fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink!=1 or (opened.st_dev,opened.st_ino)!=(before.st_dev,before.st_ino):
            raise ScopeDenied('HOLD_FILE_CHANGED_OR_LINKED')
        with os.fdopen(fd,'rb',closefd=False) as handle:
            data=handle.read(max_bytes+1)
        after=os.fstat(fd)
        if len(data)>max_bytes or (opened.st_size,opened.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):
            raise ScopeDenied('HOLD_FILE_CHANGED_OR_LIMIT')
        return data
    finally:os.close(fd)

def load_json(root,relative,max_bytes=8*1024*1024):
    return json.loads(safe_read(root,relative,max_bytes))
