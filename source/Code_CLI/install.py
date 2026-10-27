#!/usr/bin/env python3
"""Offline-only local venv installation. No system packages or provider keys."""
import json,os,pathlib,subprocess,sys,venv
sys.dont_write_bytecode=True
ROOT=pathlib.Path(__file__).resolve().parent
def main():
 if sys.version_info[:2]!=(3,12):
  print('HOLD: full offline graph wheelhouse requires CPython 3.12 (core CLI needs 3.11+).');return 2
 from adapters.evidence_verify import verify_manifest
 result=verify_manifest(ROOT/'MANIFEST.json')
 if result['status']!='PASS':print(json.dumps(result));return 4
 target=ROOT/'.venv'
 if target.exists():print('HOLD: .venv already exists; inspect it or uninstall explicitly before reinstalling.');return 2
 venv.EnvBuilder(with_pip=True,system_site_packages=False).create(target)
 exe=target/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
 keys={'SYSTEMROOT','WINDIR','COMSPEC','PATH','PATHEXT','TEMP','TMP','LANG','LC_ALL'}
 env={k:v for k,v in os.environ.items() if k.upper() in keys}
 env.update({'PIP_CONFIG_FILE':os.devnull,'PIP_NO_INDEX':'1','PIP_DISABLE_PIP_VERSION_CHECK':'1','PYTHONNOUSERSITE':'1','PYTHONDONTWRITEBYTECODE':'1'})
 process=subprocess.run([str(exe),'-B','-m','pip','install','--no-index','--no-cache-dir','--require-hashes','--find-links',str(ROOT/'wheelhouse'),'-r',str(ROOT/'requirements-lock.txt')],cwd=ROOT,env=env)
 if process.returncode:return 4
 print('PASS: local .venv installed offline. Use yr-code.cmd or ./yr-code.sh; no system environment was changed.')
 return 0
if __name__=='__main__':sys.exit(main())
