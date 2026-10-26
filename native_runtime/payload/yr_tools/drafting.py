"""Headless drafting calculator and geometric helpers sharing one registry."""
import math
from fractions import Fraction
from .binder import need,text,digest,result,guarded,validate
from .numeric import Registry,number,serial,approximate,expression,expression_dimension,UNIT_FACTORS
REVISION='LLM_DRAFTING_TOOLKIT_R001_PRIVATE'
def calculate(request,registry,pins,base):return guarded(_calculate,request,registry,pins,base)
def _calculate(d,registry,pins,base):
    need(isinstance(d,dict) and all(k in d for k in ('request_id','caller_worker','source_ref','input_values','formula_id','formula_version','result_unit','rounding_ref')),'HOLD_CALC_REQUEST')
    ref=d['source_ref'];pin=pins.get(ref['artifact_id']);subject={'artifact_id':ref['artifact_id'],'revision':ref['revision']}
    validate(ref,pin,base,subject,{'numeric_inputs':d['input_values']})
    need(ref['revision'] not in {'UNKNOWN','UNREGISTERED',''},'HOLD_SOURCE_REVISION_UNKNOWN')
    need(d['formula_version']=='R1','HOLD_FORMULA_REVISION_UNKNOWN');need(isinstance(d['input_values'],dict),'HOLD_INPUT_VALUES')
    need(d.get('conflict_state','NONE')=='NONE','HOLD_SOURCE_CONFLICT')
    values={};dims={};units={}
    for name,item in d['input_values'].items():
        need(isinstance(item,dict) and set(item)>={'raw','unit'},'HOLD_VALUE_TYPE');unit=item['unit'];need(unit in UNIT_FACTORS,'HOLD_UNIT_UNKNOWN')
        factor,dimension=UNIT_FACTORS[unit];values[name]=number(item['raw'])*factor;dims[name]=dimension;units[name]=unit
    formula=d['formula_id'];residual=Fraction(0);reverse={'state':'NOT_APPLICABLE','reason':'NON_GEOMETRIC_OR_UNARY_FORMULA'};frame=None
    if formula=='EXPRESSION':
        raw=expression(d['expression'],values);dim=expression_dimension(d['expression'],dims)
    elif formula=='UNIT_CONVERSION':raw=values['v'];dim=dims['v']
    elif formula in {'DISTANCE_2D','BEARING_2D','FORWARD_2D','ROTATE_2D','LINE_INTERSECTION','DOT_2D','CROSS_2D','TRIANGLE_AREA','CIRCLE_AREA','ARC_LENGTH','SCALE','TOLERANCE','RESIDUAL','DMS','SLOPE'}:
        if formula in {'DISTANCE_2D','BEARING_2D','FORWARD_2D','ROTATE_2D','LINE_INTERSECTION','DOT_2D','CROSS_2D','TRIANGLE_AREA'}:
            frame=registry.frame(d.get('coordinate_system'));need(frame['bearing_convention'] in {'NORTH_CLOCKWISE','EAST_COUNTERCLOCKWISE'},'HOLD_BEARING_CONVENTION_UNKNOWN')
            need(all(v==(1,0) for k,v in dims.items() if k not in {'angle','bearing'}),'HOLD_COORDINATE_UNIT')
        if formula in {'DISTANCE_2D','BEARING_2D'}:
            dx=values['x2']-values['x1'];dy=values['y2']-values['y1'];need(dx!=0 or dy!=0 or formula=='DISTANCE_2D','HOLD_ZERO_BEARING')
            distance=approximate(math.hypot,dx,dy);angle=approximate(math.atan2,dx,dy) if frame['bearing_convention']=='NORTH_CLOCKWISE' else approximate(math.atan2,dy,dx)
            rx=distance*approximate(math.sin,angle) if frame['bearing_convention']=='NORTH_CLOCKWISE' else distance*approximate(math.cos,angle)
            ry=distance*approximate(math.cos,angle) if frame['bearing_convention']=='NORTH_CLOCKWISE' else distance*approximate(math.sin,angle)
            residual=max(abs(rx-dx),abs(ry-dy));reverse={'state':'EXECUTED','reconstructed_delta':{'x':serial(rx),'y':serial(ry)},'residual':serial(residual)}
            raw=distance if formula=='DISTANCE_2D' else angle;dim=(1,0) if formula=='DISTANCE_2D' else (0,1)
        elif formula=='FORWARD_2D':
            need(dims['bearing']==(0,1),'HOLD_ANGLE_UNIT_UNKNOWN');a=values['bearing'];length=values['length'];need(length>=0,'HOLD_LENGTH_NEGATIVE')
            dx=length*approximate(math.sin,a) if frame['bearing_convention']=='NORTH_CLOCKWISE' else length*approximate(math.cos,a)
            dy=length*approximate(math.cos,a) if frame['bearing_convention']=='NORTH_CLOCKWISE' else length*approximate(math.sin,a)
            residual=abs(approximate(math.hypot,dx,dy)-length);reverse={'state':'EXECUTED','residual':serial(residual)}
            raw={'x':values['x1']+dx,'y':values['y1']+dy};dim=(1,0)
        elif formula=='ROTATE_2D':
            need(dims['angle']==(0,1),'HOLD_ANGLE_UNIT_UNKNOWN');x=values['x'];y=values['y'];c=approximate(math.cos,values['angle']);s=approximate(math.sin,values['angle']);raw={'x':x*c-y*s,'y':x*s+y*c}
            residual=max(abs(raw['x']*c+raw['y']*s-x),abs(-raw['x']*s+raw['y']*c-y));reverse={'state':'EXECUTED','residual':serial(residual)};dim=(1,0)
        elif formula=='LINE_INTERSECTION':
            x1,y1,x2,y2,x3,y3,x4,y4=[values[k] for k in ('x1','y1','x2','y2','x3','y3','x4','y4')]
            determinant=(x1-x2)*(y3-y4)-(y1-y2)*(x3-x4);need(abs(determinant)>number(registry.data['NUMERIC_POLICY_REGISTRY']['numeric_epsilon']),'HOLD_AMBIGUOUS_TOPOLOGY')
            a=x1*y2-y1*x2;b=x3*y4-y3*x4;raw={'x':(a*(x3-x4)-(x1-x2)*b)/determinant,'y':(a*(y3-y4)-(y1-y2)*b)/determinant};dim=(1,0)
        elif formula in {'DOT_2D','CROSS_2D'}:
            raw=values['x1']*values['x2']+values['y1']*values['y2'] if formula=='DOT_2D' else values['x1']*values['y2']-values['y1']*values['x2'];dim=(2,0)
        elif formula=='TRIANGLE_AREA':raw=abs((values['x2']-values['x1'])*(values['y3']-values['y1'])-(values['y2']-values['y1'])*(values['x3']-values['x1']))/2;dim=(2,0)
        elif formula=='CIRCLE_AREA':need(dims['r']==(1,0) and values['r']>=0,'HOLD_RADIUS');raw=Fraction.from_float(math.pi)*values['r']**2;dim=(2,0)
        elif formula=='ARC_LENGTH':need(dims['r']==(1,0) and dims['angle']==(0,1) and values['r']>=0,'HOLD_ARC_UNIT');raw=values['r']*values['angle'];dim=(1,0)
        elif formula=='SCALE':need(dims['scale']==(0,0) and values['scale']>0,'HOLD_SCALE_UNKNOWN');raw=values['v']*values['scale'];dim=dims['v']
        elif formula in {'TOLERANCE','RESIDUAL'}:
            need(dims['observed']==dims['expected']==dims['tolerance'] and values['tolerance']>=0,'HOLD_TOLERANCE_UNIT');raw=abs(values['observed']-values['expected']);dim=dims['observed'];reverse={'state':'EXECUTED','within_declared_tolerance':raw<=values['tolerance']}
        elif formula=='DMS':
            need(all(v==(0,0) for v in dims.values()) and 0<=values['minutes']<60 and 0<=values['seconds']<=60 and values['sign'] in {-1,1},'HOLD_DMS_TYPE');raw=(abs(values['degrees'])+values['minutes']/60+values['seconds']/3600)*values['sign']*UNIT_FACTORS['deg'][0];dim=(0,1)
        else:need(dims['rise']==dims['run'] and values['run']!=0,'HOLD_SLOPE');raw=values['rise']/values['run'];dim=(0,0)
    else:raise ValueError('HOLD_FORMULA_UNKNOWN')
    unit=d['result_unit'];need(unit in UNIT_FACTORS and UNIT_FACTORS[unit][1]==dim,'HOLD_RESULT_UNIT')
    factor=UNIT_FACTORS[unit][0];out=raw if isinstance(raw,dict) else {'value':raw};decision={k:serial(v/factor) for k,v in out.items()};display={};lineage=[]
    for k,v in out.items():
        rendered,rounding=registry.display(v/factor,d['rounding_ref']);display[k]=rendered
        lineage.append({'event_id':k,'stage':'DISPLAY','operation':formula,'tool_revision':REVISION,'formula_or_transform_revision':d['formula_version'],'numeric_backend':registry.data['NUMERIC_POLICY_REGISTRY']['numeric_backend_revision'],'precision_mode':registry.data['NUMERIC_POLICY_REGISTRY']['precision_mode'],'source_revision':ref['revision'],'input_refs':[ref['artifact_id']],'output_refs':[k],'rounding':{'occurred':number(rendered)!=v/factor,'kind':'display_only','policy_ref':rounding['rounding_policy_revision'],'mode':rounding['rounding_mode'],'digits_or_step':rounding['scale_or_digits']},'numeric_effect':{'observed_delta':serial(number(rendered)-v/factor),'propagated_error_bound':None,'determination':'UNKNOWN'}})
    if frame:need(residual<=number(frame['round_trip_tolerance']),'HOLD_REVERSE_CHECK_RESIDUAL')
    calc_id='CALC_'+digest({'request':d,'registry_sha256':registry.sha256,'tool_revision':REVISION})
    return result('PASS_NUMERIC_CONTRACT_ONLY',tool_revision=REVISION,calc_id=calc_id,request_id=d['request_id'],caller_worker=d['caller_worker'],source_artifact=ref['artifact_id'],source_revision=ref['revision'],source_locator=ref['locator'],input_values=d['input_values'],input_units=units,coordinate_system=d.get('coordinate_system'),angle_convention=frame['bearing_convention'] if frame else None,formula_id=formula,formula_version=d['formula_version'],precision=registry.data['NUMERIC_POLICY_REGISTRY']['precision_mode'],rounding_rule=d['rounding_ref'],raw_values=d['input_values'],decision_values=decision,display_values=display,result_units=unit,reverse_check=reverse,residual=serial(residual),tolerance=frame['round_trip_tolerance'] if frame else d.get('tolerance'),registry_sha256=registry.sha256,numeric_lineage=lineage,numeric_accuracy='NOT_A_DOMAIN_ACCEPTANCE',open_numeric_error_bound='UNKNOWN_MATHEMATICAL_ERROR_FOR_BINARY64_FUNCTIONS')
