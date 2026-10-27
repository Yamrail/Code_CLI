"""Read-only command/module discovery, not license or execution authority."""
import importlib.util
import os,platform,shutil,subprocess,sys
from .portable_io import utcnow

def doctor():
    from runtime_support import world_model_runtime,load_environment
    tools={}
    for name in ['python','python3','node','git','gh','codex','gemini','claude','dotnet','cl','clang','gcc','g++','rustc','cargo','cmake','ninja','msbuild','docker','podman','wsl','ffmpeg']:
        found=shutil.which(name)
        tools[name]={'found_on_path':bool(found),'execution_status':'DISCOVERED_NOT_INVOKED' if found else 'NOT_FOUND_ON_PATH','license':'NOT_INFERRED','binary_bundled':False}
    modules={name:bool(importlib.util.find_spec(name)) for name in ['PIL','reportlab','cairosvg','pptx','openpyxl','docx']}
    runtime=world_model_runtime();config=load_environment()
    return {'schema':'yamrail.code-cli.doctor/1','observed_at_utc':utcnow(),'status':runtime['status'] if sys.version_info>=(3,11) else 'HOLD','python':{'version':platform.python_version(),'minimum':'3.11','standard_library_core':True},'host':{'os':platform.system(),'release':platform.release(),'architecture':platform.machine()},'tools':tools,'world_model_runtime':runtime,'dotenv':config,'python_optional_modules':modules,'credential_values_read':config['credential_fields_seen'],'credential_values_reported':False,'network_requests':0,'provider_invocations':0,'commercial_product_license':'UNKNOWN_NOT_INFERRED','ram_backing':'UNPROVEN','encrypted_scratch':'UNPROVEN','full_agent_isolation':'UNPROVEN','all_tools_installed_claimed':False}
