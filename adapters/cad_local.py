"""Default-off local CAD admission. Never starts or remote-controls AutoCAD.

Actual product entitlement/session integration is not yet qualified. Presence,
registry entries, environment assertions and simulated receipts never admit it.
"""
from __future__ import annotations
import os,platform,sys
from pathlib import Path
from .portable_io import utcnow

HOSTED_MARKERS=('CI','GITHUB_ACTIONS','GITLAB_CI','TF_BUILD','JENKINS_URL','KUBERNETES_SERVICE_HOST','WEBSITE_INSTANCE_ID','CODESPACES','SSH_CONNECTION','SSH_CLIENT','REMOTE_CONTAINERS')

def doctor(local_only=False):
    hosted=any(os.environ.get(k) for k in HOSTED_MARKERS)
    windows=platform.system()=='Windows'
    session={'current_session_id':None,'active_console_session_id':None,'same_active_console':False}
    if windows:
        try:
            import ctypes
            sid=ctypes.c_ulong()
            if ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(),ctypes.byref(sid)):
                active=ctypes.windll.kernel32.WTSGetActiveConsoleSessionId()
                session={'current_session_id':sid.value,'active_console_session_id':active,'same_active_console':sid.value==active and sid.value!=0}
        except (AttributeError,OSError):pass
    reason='DENY_SERVER_CLOUD_OR_REMOTE_CONTEXT' if hosted or not windows else 'HOLD_CAD_LICENSE_UNVERIFIED_NO_AUTOCAD_LAUNCH'
    return {'schema':'yamrail.code-cli.local-cad-admission/1','status':'HOLD','observed_at_utc':utcnow(),'local_only_requested':bool(local_only),'default':'OFF','reason':reason,'windows_desktop_candidate':windows and not hosted,'hosted_or_remote_marker_detected':hosted,'session':session,'caller_interactive_tty':bool(sys.stdin.isatty()),'actual_product_entitlement':'UNVERIFIED','user_initiated_local_broker_qualified':False,'installation_implies_license':False,'simulated_receipts_accepted':False,'autocad_launched':False,'com_activated':False,'remote_control_attempted':False,'cloud_fallback':False,'paid_api_calls':0,'next_action':'A local user must qualify the actual product entitlement and supported in-session host broker before any AutoCAD operation.'}

def operation(action,package_root,input_path=None,local_only=False,format=None,out=None):
    result=doctor(local_only)
    result['requested_operation']=action
    result['input_read']=False;result['output_written']=False
    if result['hosted_or_remote_marker_detected'] or not result['windows_desktop_candidate']:
        result['reason']='DENY_SERVER_CLOUD_OR_REMOTE_CONTEXT'
        return result
    if not local_only:
        result['reason']='DENY_LOCAL_ONLY_REQUIRED'
        return result
    if action not in {'open','export'}:
        result['reason']='DENY_CAD_OPERATION_NOT_ALLOWLISTED'
        return result
    if input_path:
        # Default-off denial never probes a caller path or a remote filesystem.
        from .portable_io import reject_network_path,ScopeDenied
        try:reject_network_path(input_path)
        except ScopeDenied:
            result['reason']='DENY_CAD_NONLOCAL_INPUT_SYNTAX'
            return result
        p=Path(os.path.abspath(input_path));scratch=Path(package_root).absolute()/'.yr-code'
        if p.suffix.lower() in {'.lsp','.fas','.vlx','.scr','.dll','.exe'}:
            result['reason']='DENY_LISP_SCRIPT_OR_BINARY_AUTOLOAD'
        elif not p.is_relative_to(scratch):result['reason']='DENY_CAD_INPUT_OUTSIDE_LOCAL_STAGING'
    return result
