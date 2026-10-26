#!/usr/bin/env python3
"""Remove only this package's local venv after an explicit operator request."""
import argparse,pathlib,shutil,sys
ROOT=pathlib.Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--venv',action='store_true',required=True);p.parse_args()
 target=ROOT/'.venv'
 if target.is_symlink() or (hasattr(target,'is_junction') and target.is_junction()):raise ValueError('HOLD_VENV_LINK')
 if target.resolve().parent!=ROOT.resolve() or target.name!='.venv':raise ValueError('HOLD_UNINSTALL_BOUNDARY')
 print('Local removal target: '+str(target.resolve()))
 if target.exists():shutil.rmtree(target)
 print('Local venv removed; source and all run evidence retained.');return 0
if __name__=='__main__':sys.exit(main())
