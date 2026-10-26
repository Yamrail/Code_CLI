"""Retained R005 local CAD geometry and safe OOXML admission, ported for R007.
No AutoCAD/Office executable or remote endpoint is started by this module.
Source baseline95322; only dependency imports changed in retained helper bodies.
"""
from __future__ import annotations
import ast
from fractions import Fraction
from pathlib import Path
import stat
import zipfile
from native_runtime.core import load_native, save, sha, verify_code_fixture
from adapters.native_host import supervise_stage

def numeric_registry():
 _, _, _, _, digest, _ = load_native()
 from yr_tools.numeric import Registry
 d={
 'NUMERIC_POLICY_REGISTRY':{'revision':'RTA1','numeric_backend_revision':'FRACTION_DECIMAL_INPUT_BINARY64_TRANSCENDENTALS_R1','precision_mode':'EXACT_RATIONAL_OR_DECLARED_BINARY64','numeric_epsilon':'0','numeric_epsilon_policy_revision':'RTA1','rounding_mode':'HALF_EVEN','intermediate_rounding_policy':'PROHIBITED'},
 'COORDINATE_FRAME_REGISTRY':{'revision':'RTA1','frames':{'LOCAL':{'coordinate_frame_id':'LOCAL','coordinate_frame_revision':'RTA1','transform_rule_revision':'IDENTITY','round_trip_tolerance':'0','unit':'m','bearing_convention':'SYNTHETIC_CARTESIAN_X_RIGHT_Y_UP'}}},
 'ROBUST_PREDICATE_POLICY':{'revision':'RTA1','predicate_policy_revision':'RTA1','escalation_precision_rule':'EXACT_RATIONAL','ambiguous_topology_disposition':'HOLD'},
 'GEOMETRY_TOLERANCE_POLICY':{'revision':'RTA1','quantity_class':'LENGTH','geometric_tolerance':'0','domain_tolerance_ref':{'fixture':'EXACT_SYNTHETIC_NOT_FIELD_ACCURACY'}},
 'ROUNDING_POLICY_REGISTRY':{'revision':'RTA1','policies':{}},
 'CANONICAL_NUMERIC_SERIALIZATION':{'revision':'RTA1','serialization_policy_revision':'RTA1','quantity_class':'SYNTHETIC','unit_canonicalization':'m','decimal_or_integer_representation':'EXACT_RATIONAL','negative_zero_rule':'NORMALIZE_ZERO','nan_inf_rule':'HOLD'}}
 return Registry(d,digest(d)),d


def cad_build(out):
 load_native()
 from yr_tools.binder import ContractError
 from yr_tools.drawing_equipment import geometry,encode_geometry
 from yr_tools.numeric import expression,expression_dimension
 registry,config=numeric_registry()
 model={'geometry_type':'RECTANGLE','geometry_parameters':{'unit':'m','p1':['0','0'],'p2':['6','4']}}
 observed=geometry(model,registry)
 assert observed['points']==[[Fraction(0),Fraction(0)],[Fraction(6),Fraction(0)],[Fraction(6),Fraction(4)],[Fraction(0),Fraction(4)]]
 area=expression('span*width',{'span':Fraction(6),'width':Fraction(4)})
 assert area==24 and expression_dimension('span*width',{'span':(1,0),'width':(1,0)})==(2,0)
 refused=False
 try:geometry({'geometry_type':'RECTANGLE','geometry_parameters':{'unit':'m','p1':['0','0'],'p2':['0','4']}},registry)
 except ContractError as error:refused='DEGENERATE_RECTANGLE' in str(error)
 assert refused
 points=observed['points'];pairs=[]
 def add(code,value):pairs.extend([str(code),str(value)])
 add(0,'SECTION');add(2,'HEADER');add(9,'$ACADVER');add(1,'AC1015');add(9,'$INSUNITS');add(70,6);add(0,'ENDSEC');add(0,'SECTION');add(2,'ENTITIES')
 for a,b in zip(points,points[1:]+points[:1]):
  for code,value in [(0,'LINE'),(8,'SYNTHETIC_DRAFT'),(10,float(a[0])),(20,float(a[1])),(30,0),(11,float(b[0])),(21,float(b[1])),(31,0)]:add(code,value)
 add(0,'ENDSEC');add(0,'EOF')
 (out/'synthetic_module.dxf').write_text('\n'.join(pairs)+'\n',encoding='ascii')
 svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 640"><rect width="900" height="640" fill="white"/><g fill="none" stroke="#23536a" stroke-width="3"><rect x="100" y="130" width="600" height="400"/></g><g font-family="sans-serif" fill="#173c50"><text x="50" y="45" font-size="25">Synthetic local module: 6 m x 4 m</text><text x="50" y="80" font-size="18">Native retained geometry engine. DRAFT / NOT FOR CONSTRUCTION</text><text x="330" y="565" font-size="23">6 m</text><text x="725" y="340" font-size="23">4 m</text><text x="305" y="340" font-size="27">24 m2</text><text x="50" y="615" font-size="17">Local Cartesian fixture. Geographic CRS / epoch / datum: NOT APPLICABLE</text></g></svg>'
 (out/'synthetic_module.svg').write_text(svg,encoding='utf-8')
 save(out/'NUMERIC_REGISTRY.json',config)
 return {'state':'PASS_REUSED_COMPONENT_GEOMETRY_AND_LOCAL_EXPORT','evidence_class':'LOCAL_EXECUTED','input_class':'SYNTHETIC_FIXTURE',
         'engine':'Retained yr_tools.drawing_equipment + numeric.Registry','area_exact_rational':str(area),
         'degenerate_geometry_refused':refused,'coordinate_type':'SYNTHETIC_LOCAL_CARTESIAN','geographic_crs_epoch_datum':'NOT_APPLICABLE',
         'autocad_or_dwg_execution':'NOT_EXECUTED','full_native_drawing_acceptance':'NOT_EXECUTED','field_accuracy':'NOT_CLAIMED',
         'dxf_sha256':sha((out/'synthetic_module.dxf').read_bytes()),'svg_sha256':sha(svg.encode())}


def inspect_ooxml(path):
 with zipfile.ZipFile(path) as z:
  infos=z.infolist()
  if len(infos)>10000 or sum(x.file_size for x in infos)>100*1024*1024:raise ValueError('HOLD_OFFICE_PACKAGE_LIMIT')
  blocked=[x.filename for x in infos if 'vbaproject' in x.filename.lower() or 'vbadata' in x.filename.lower() or '/macrosheets/' in x.filename.lower() or '/dialogsheets/' in x.filename.lower() or x.filename.startswith('/') or '..' in Path(x.filename.replace('\\','/')).parts or stat.S_ISLNK(x.external_attr>>16)]
  import xml.etree.ElementTree as ET
  for info in infos:
   name=info.filename.lower()
   if name=='[content_types].xml' or name.endswith(('.rels','workbook.xml')):
    try:tree=ET.fromstring(z.read(info))
    except ET.ParseError:
     blocked.append(info.filename+':INVALID_XML');continue
    for element in tree.iter():
     values=[str(v).casefold() for v in element.attrib.values()]
     if any(any(marker in value for marker in ['macroenabled','vbaproject','macrosheet','_xlnm.auto_open','_xlnm.auto_close','auto_open','auto_close','attachedtemplate']) for value in values):
      blocked.append(info.filename+':MACRO_OR_AUTOEXEC_METADATA')
  return {'state':'DENY_MACRO_OR_UNSAFE_PACKAGE' if blocked else 'PASS_MACRO_FREE_PACKAGE_SCAN_ONLY','members':len(infos),'blocked_members':blocked,'macros_executed':False,'licensed_desktop_application_executed':False}


def admit_ooxml(path):
 """Bounded scan only; does not open a desktop application or certify safety."""
 import re
 import xml.etree.ElementTree as ET
 with zipfile.ZipFile(path) as archive:
  infos=archive.infolist();names=[info.filename for info in infos]
  if len(names)!=len(set(names)):raise ValueError('HOLD_OFFICE_DUPLICATE_MEMBER')
  if len(infos)>10000 or sum(info.file_size for info in infos)>100*1024*1024:
   raise ValueError('HOLD_OFFICE_PACKAGE_LIMIT')
  for info in infos:
   normalized=info.filename.replace('\\','/')
   if ':' in normalized or normalized.startswith('/') or '..' in normalized.split('/') or info.flag_bits & 1:
    raise ValueError('HOLD_OFFICE_UNSAFE_MEMBER')
   if info.filename.lower().endswith('.rels'):
    try:tree=ET.fromstring(archive.read(info))
    except ET.ParseError:raise ValueError('HOLD_OFFICE_INVALID_RELATIONSHIP_XML')
    if any(str(element.attrib.get('TargetMode','')).casefold()=='external' for element in tree.iter()):
     raise ValueError('HOLD_OFFICE_EXTERNAL_RELATIONSHIP')
 return inspect_ooxml(path)


def _compile_fixture(stage):
 source=verify_code_fixture('hold_report.py');raw=source.read_bytes()
 tree=ast.parse(raw.decode('utf-8'));compile(tree,'pinned_safe_fixture/hold_report.py','exec')
 risky=[]
 for node in ast.walk(tree):
  if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id in {'eval','exec','__import__'}:
   risky.append({'line':node.lineno,'rule':'DYNAMIC_CODE_REVIEW_REQUIRED'})
 return {'state':'PASS_PYTHON_AST_COMPILE','evidence_class':'LOCAL_EXECUTED','source_class':'PINNED_SAFE_CODE_FIXTURE',
         'source_sha256':sha(raw),'execution':'SYNTAX_BUILD_ONLY','arbitrary_code_executed':False,
         'review_findings':risky,'compiler_scope':'PYTHON_BUILTIN_COMPILE_ONLY','external_compiler':'NOT_EXECUTED',
         'security_certification':'NOT_CLAIMED'}


def _office_fixture(stage):
 stage.mkdir(parents=True,exist_ok=True)
 cases={
  'safe_marker.zip':{'[Content_Types].xml':'<Types/>','word/document.xml':'<document/>'},
  'vba_marker.zip':{'xl/vbaProject.bin':b'SYNTHETIC_NON_EXECUTABLE_MARKER_ONLY'},
  'xlm_marker.zip':{'[Content_Types].xml':'<Types><Override ContentType="application/vnd.ms-excel.macrosheet+xml"/></Types>'},
  'autoopen_marker.zip':{'xl/workbook.xml':'<workbook><definedName name="_xlnm.Auto_Open">SYNTHETIC</definedName></workbook>'},
 }
 receipts={}
 for name,members in cases.items():
  path=stage/name
  with zipfile.ZipFile(path,'x') as archive:
   for member,raw in members.items():archive.writestr(member,raw)
  receipts[name]={'sha256':sha(path.read_bytes()),'admission':admit_ooxml(path)}
 if receipts['safe_marker.zip']['admission']['state']!='PASS_MACRO_FREE_PACKAGE_SCAN_ONLY':
  raise AssertionError('Safe marker scan changed')
 if not all(receipts[name]['admission']['state']=='DENY_MACRO_OR_UNSAFE_PACKAGE' for name in cases if name!='safe_marker.zip'):
  raise AssertionError('Macro marker was admitted')
 return {'state':'PASS_SCOPED_OOXML_ADMISSION_BREAK_TESTS','evidence_class':'LOCAL_EXECUTED','input_class':'SYNTHETIC_FIXTURE',
         'cases':receipts,'fixtures_are_valid_office_documents':False,'desktop_office_execution':'NOT_EXECUTED',
         'macro_execution':False,'licensed_binary_exported':False,'security_certification':'NOT_CLAIMED'}


def run_build(kind,output):
 """Create-only retained local helper stage; no network or licensed app launch."""
 if kind not in {'compile','cad','office','all'}:raise ValueError('HOLD_UNSUPPORTED_BUILD_KIND')
 def runner(stage):
  results={}
  if kind in {'compile','all'}:results['compile']=_compile_fixture(stage)
  if kind in {'cad','all'}:
   results['cad']=cad_build(stage)
   results['cad']['actual_autocad_status']='HOLD_NOT_EXECUTED_USE_SEPARATE_VERIFIED_LOCAL_AUTOCAD_ROUTE'
   results['cad']['native_dwg_output']='NOT_PRODUCED'
  if kind in {'office','all'}:results['office']=_office_fixture(stage/'office_admission')
  value={'state':'PASS_SCOPED_LOCAL_BUILD','kind':kind,'components':results,'evidence_class':'LOCAL_EXECUTED',
         'domain_class':'SYNTHETIC_FIXTURE','provider_calls':0,'canonical_effect':'NONE',
         'autocad_or_office_process_launched':False}
  save(stage/'BUILD_COMPONENTS.json',value)
  return value
 native=supervise_stage(output,'BUILD_'+kind.upper(),runner,work_order_id='CODE-CLI-R007-LOCAL-BUILD-'+kind.upper(),root_purpose='BUILD_'+kind.upper())
 return {'schema':'code-cli.native-local-build/1','state':native.get('result',{}).get('state',native['state']),
         'kind':kind,'result':native.get('result'),'native_host':native,'canonical_effect':'NONE'}
