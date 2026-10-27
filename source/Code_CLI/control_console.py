"""Single-screen COTS terminal UI; only fixed deterministic requests are wired."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import sys
import threading
import time
import textwrap
import webbrowser
from console_runtime import (ROOT,CASES,INTERLOCK,LOGO,PROFILE_PUBLIC,RailControl,
                             intercept,profile,run_rail,sha)

def main():
    try:
        from prompt_toolkit import Application
        from prompt_toolkit.document import Document
        from prompt_toolkit.key_binding import KeyBindings
        from prompt_toolkit.layout import HSplit,Layout,Window
        from prompt_toolkit.layout.controls import FormattedTextControl
        from prompt_toolkit.lexers import Lexer
        from prompt_toolkit.styles import Style
        from prompt_toolkit.widgets import TextArea
    except ModuleNotFoundError:
        print('HOLD: verify the package and run install.py to install the bundled offline UI dependencies.',file=sys.stderr)
        return 2
    from moot_runtime import read_register
    class StreamLexer(Lexer):
        def lex_document(self,document):
            def line(number):
                text=document.lines[number]
                style='class:stream'
                for token,chosen in [('GOVERNANCE INTERCEPT','warning'),('[REJECT]','reject'),('[ERROR]','reject'),('[REMEDIATION]','repair'),('[COMPLETE]','seal'),('[STOP','warning'),('[WORLD_MDL]','world'),('[LEDGER]','world'),('[PLANNER]','planner'),('[EVALUATOR]','eval'),('[EXECUTE]','execute')]:
                    if token in text:style='class:'+chosen;break
                return [(style,text)]
            return line
    stream=TextArea(text='',read_only=True,scrollbar=True,wrap_lines=True,focusable=False,lexer=StreamLexer())
    request=TextArea(height=3,prompt='> ',multiline=True,wrap_lines=True)
    from runtime_support import discover_node
    engine='Node Meterless' if discover_node() else 'Python compatible projection'
    state={'stage':'M-J00 / READY','warning':'No live model calls; deterministic fixture roles','engine':engine,'roles':{r:'IDLE' for r in ['PLANNER','EXECUTE','EVALUATOR','WORLD_MDL','LEDGER']},'control':None,'busy':False,'last':None,'closing':False}
    kb=KeyBindings();loop=None;lines=[]
    def append(text):
        text=''.join(c if c in '\n\t' or ord(c)>=32 else '?' for c in str(text)).replace('\x7f','?')
        width=max(32,app.output.get_size().columns-4)
        for line in text.splitlines() or ['']:
            lines.extend(textwrap.wrap(line,width=width,replace_whitespace=False,drop_whitespace=False) or [''])
        if len(lines)>8000:del lines[:len(lines)-8000]
        content='\n'.join(lines)+'\n'
        stream.buffer.set_document(Document(content,len(content)),bypass_readonly=True)
        app.invalidate()
    def header():
        banner=INTERLOCK if profile()==PROFILE_PUBLIC else '[DETERMINISTIC RAIL INTERLOCK: ENGAGED | PROFILE: OWNER_CONTROLLED_FULL | CONSOLE: FIXED LOCAL RAILS]'
        return [('class:logo',LOGO+'\n'),('class:interlock',banner)]
    def roles():
        out=[]
        for role,current in state['roles'].items():out.extend([('class:active' if current!='IDLE' else 'class:muted',f' [{role}] {current} ')])
        return out
    def moot():
        register=read_register();out=[]
        for i,item in enumerate(register['items']):
            status=item['state'];style='class:seal' if status=='PASS' else 'class:warning' if status in {'HOLD','FAIL'} else 'class:muted'
            out.append((style,f' {item["moot_id"]}:{status} '))
            if i==4:out.append(('','\n'))
        out.append(('','\n'))
        for name,status in register['cases'].items():out.append(('class:seal' if status=='PASS' else 'class:muted',f' {name}:{status} '))
        return out
    def status():
        return [('class:status',f' PROJECT YamRail | WORKTREE {ROOT.name} | ENGINE {state["engine"]} + native | INTERLOCK ENGAGED | {state["stage"]} | {state["warning"]}')]
    layout=HSplit([
        Window(FormattedTextControl(header),height=lambda:7 if app.output.get_size().columns<110 else 6,wrap_lines=True),
        Window(FormattedTextControl(roles),height=1,wrap_lines=False),
        Window(FormattedTextControl(moot),height=lambda:5 if app.output.get_size().columns<110 else 3,wrap_lines=True),
        Window(height=1,char='-'),
        stream,
        Window(FormattedTextControl(status),height=lambda:3 if app.output.get_size().columns<110 else 2,wrap_lines=True),
        Window(FormattedTextControl('Enter submit | Alt+Enter newline | Ctrl+C stop | F2 evidence F3 Moot F4 manifest F5 SHA256 F6 tools F7 blueprint'),height=1),
        request,
    ])
    def on_event(event):
        kind,data=event['kind'],event['data']
        stamp=time.strftime('%H:%M:%S')
        if kind=='COMMAND':append(f'{stamp} [ACTUAL COMMAND] demo {data["rail"]} | {data["case_id"]} | model calls: 0')
        elif kind=='TOOL_INVOCATION':
            process_name=data['name'];role='WORLD_MDL' if process_name.startswith('world-') else next((r for r in ['PLANNER','EVALUATOR'] if r.lower() in process_name),'EXECUTE')
            state['roles']={r:'IDLE' for r in state['roles']};state['roles'][role]='RUNNING';state['roles']['LEDGER']='OBSERVING'
            append(f'{stamp} [{role}] TOOL START '+subprocess_display(data['actual_argv']))
        elif kind=='TOOL_RESULT':
            append(f'{stamp} [TOOL RESULT] '+json.dumps(data['process'],ensure_ascii=False))
            raw=data['actual_stdout'];append('[STDOUT] '+raw[:2500]+(' ... [complete bytes retained in run]' if len(raw)>2500 else ''))
            state['roles']={r:'IDLE' for r in state['roles']}
        elif kind in {'ROLE','REJECT','REMEDIATION'}:
            value=data['observed_result'];label={'EXECUTOR':'EXECUTE'}.get(data['role'],data['role'])
            suffix=' [REJECT]' if kind=='REJECT' else ' [REMEDIATION / REPAIR]' if kind=='REMEDIATION' else ''
            append(f'{stamp} [{label}]{suffix} '+json.dumps(value,ensure_ascii=False))
            if kind=='REJECT':state['warning']='Evidence rejected; authorized alternative required'
            if kind=='REMEDIATION':state['warning']='Observed repair proposal; awaiting Evaluator'
        elif kind=='WORLD_MODEL':
            state['engine']='Node Meterless' if data.get('actual_backend')=='NODE_PINNED_METERLESS_REFERENCE' else 'Python compatible projection'
            state['roles']['LEDGER']='READBACK';append(f'{stamp} [WORLD_MDL] STATE '+json.dumps(data,ensure_ascii=False))
        elif kind=='STDERR':append('[STDERR] '+data['actual_text'])
        elif kind in {'STOP','RESUME','STOP_RESUME_READBACK'}:
            state['roles']['LEDGER']='STOPPED' if kind=='STOP' else 'READBACK'
            state['warning']='Stopped; type resume' if kind=='STOP' else 'Budget preserved; no replay'
            append(f'{stamp} [LEDGER] [{kind}] '+json.dumps(data,ensure_ascii=False))
        elif kind=='BLUEPRINT':
            append('\n'.join(data['ascii']));append('[ACTUAL FILE DIFF]\n'+(data['actual_diff'] or '(confirmed proposal unchanged)'));append('[BLUEPRINT SHA256] '+data['svg_sha256'])
        elif kind=='COMPLETE':
            state['stage']='M-J05 / SEALED';state['warning']='Local fixture complete; Human release gate separate'
            append('[COMPLETE] '+json.dumps(data,ensure_ascii=False))
        else:append('['+kind+'] '+json.dumps(data,ensure_ascii=False))
        app.invalidate()
    async def rail(names):
        if state['busy']:append('[WARNING] One rail is running; use stop, resume, or wait.');return
        state['busy']=True;state['control']=RailControl();state['stage']='M-J05 / EXECUTING'
        try:
            for name in names:
                receipt=await asyncio.to_thread(run_rail,name,lambda event:loop.call_soon_threadsafe(on_event,event),state['control'])
                state['last']=receipt
                if receipt['state']!='PASS' or state['closing']:break
        except Exception as exc:append('[ERROR] '+type(exc).__name__+': '+str(exc));state['warning']='Failure retained; inspect evidence before any new run'
        finally:
            state['busy']=False;state['control']=None;state['roles']={r:'IDLE' for r in state['roles']};app.invalidate()
            if state['closing']:app.exit(result=0)
    async def check_moot():
        if state['busy']:append('[WARNING] Run inspection after the active rail completes.');return
        from moot_runtime import inspect
        value=await asyncio.to_thread(inspect)
        append('[MOOT] '+json.dumps(value,ensure_ascii=False));app.invalidate()
    def view(name):
        if name=='moot':
            register=read_register();append('[MOOT REGISTER] Evidence-bound local projection; no Human approval inferred.')
            for item in register['items']:append(item['moot_id']+' | '+item['state']+' | '+item['item_name'])
            for case,current in register['cases'].items():append(case+' | '+current)
        elif name in {'manifest','sha256'}:
            path=ROOT/('MANIFEST.json' if name=='manifest' else 'SHA256SUMS.txt')
            if not path.is_file():append('[WARNING] Seal file is not present.');return
            if name=='manifest':
                value=json.loads(path.read_bytes());append('[MANIFEST] '+json.dumps({k:v for k,v in value.items() if k!='files'},ensure_ascii=False));append('[MANIFEST SHA256] '+sha(path.read_bytes()))
            else:append('[SHA256] '+path.read_text(encoding='utf-8')[:10000])
        elif name=='tools':
            append('[TOOL INVENTORY] Python fixed fixture processes | Meterless World Model (Node) | native WorkLedger | offline evidence verifier | SVG/HTML blueprint renderer. No arbitrary execution port.')
        elif name=='evidence':append('[EVIDENCE]\n'+json.dumps(read_register().get('case_receipts',{}),ensure_ascii=False,indent=2))
        elif name=='blueprint':
            last=state['last']
            if not last or last['state']!='PASS':append('[WARNING] Run one fixed demo to produce a blueprint.');return
            target=Path(last['run']);target=target if target.is_absolute() else ROOT/target
            append('[BLUEPRINT] '+str(target/'BLUEPRINT.html')+' | '+last['blueprint']['svg_sha256'])
        app.invalidate()
    def submit(text):
        append('> '+text)
        normalized=' '.join(text.strip().split())
        if normalized in {'help','?'}:append('Fixed requests: demo confirmed | demo insufficient | demo stop | sample --all | moot status | moot check | evidence verify | evidence | manifest | sha256 | tools | blueprint | stop | resume | exit')
        elif normalized.startswith('demo ') and normalized[5:] in CASES:app.create_background_task(rail([normalized[5:]]))
        elif normalized=='sample --all':app.create_background_task(rail(list(CASES)))
        elif normalized in {'moot status','moot'}:view('moot')
        elif normalized=='moot check':app.create_background_task(check_moot())
        elif normalized=='evidence verify':
            from adapters.evidence_verify import verify_manifest
            append('[EVIDENCE VERIFY] '+json.dumps(verify_manifest(ROOT/'MANIFEST.json'),ensure_ascii=False))
        elif normalized in {'evidence','manifest','sha256','tools','blueprint'}:view(normalized)
        elif normalized=='stop':
            if state['control']:state['control'].stop();append('[LEDGER] STOP requested; waiting for a settled native boundary.')
            else:append('[LEDGER] No active rail; existing stopped checkpoints remain unchanged.')
        elif normalized=='resume':
            if state['control']:state['control'].resume();append('[LEDGER] RESUME requested for this suspended in-process rail only.')
            else:append('[LEDGER] No suspended rail. Prior unknown or killed runs are not replayed.')
        elif normalized in {'exit','quit'}:
            if state['control']:state['closing']=True;state['control'].cancel();append('[LEDGER] Cancelling at the next safe boundary; partial output retained.')
            else:app.exit(result=0)
        else:
            denied=intercept(text)
            append('>>> [GOVERNANCE INTERCEPT | DETERMINISTIC RAIL INTERLOCK]\n! BLOCKED: '+denied['reason']+'\n! Policy Ref : '+denied['clause']+'\n! Permitted  : sample --all | evidence verify | moot status\n! Cases      : demo confirmed | demo insufficient | demo stop')
    @kb.add('enter')
    def enter(event):
        text=request.text;request.buffer.reset()
        if text.strip():submit(text[:4096])
    @kb.add('escape','enter')
    def newline(event):request.buffer.insert_text('\n')
    @kb.add('c-c')
    def stop_key(event):submit('stop')
    @kb.add('c-d')
    def quit_key(event):submit('exit')
    @kb.add('c-l')
    def redraw_key(event):
        event.app.renderer.reset();event.app.invalidate()
    for key,name in [('f2','evidence'),('f3','moot'),('f4','manifest'),('f5','sha256'),('f6','tools'),('f7','blueprint')]:
        def handler(event,name=name):view(name)
        kb.add(key)(handler)
    style=Style.from_dict({'':'bg:#101419 #d2d9e4','stream':'#d2d9e4','logo':'bold #90b9d5','interlock':'bold #93e3ba','warning':'#f1be62','reject':'bold #ff7e82','repair':'bold #8be4af','seal':'#82dfb7','world':'#81bfec','planner':'#b9a1ee','eval':'#ffcb85','execute':'#9bc8e4','muted':'#8a98ac','active':'bold #b6e2ff','status':'reverse','text-area':'#e5edf8'})
    app=Application(layout=Layout(layout,focused_element=request),key_bindings=kb,style=style,full_screen=True,mouse_support=False)
    async def start():
        nonlocal loop
        loop=asyncio.get_running_loop()
        append('Ready. Three credential-free fixtures; real processes and native journals; deterministic synthetic decisions.\nType sample --all, or demo insufficient to inspect a rejection and repair.\nInstallation begins UNKNOWN until measured; type moot check for host inspection.')
    def pre_run():app.create_background_task(start())
    return app.run(pre_run=pre_run)

def subprocess_display(argv):
    # Display only: this string is never executed by a shell.
    return ' '.join(json.dumps(str(x),ensure_ascii=False) if ' ' in str(x) else str(x) for x in argv)
