"""Headless 2D desk/drafter/plotter over the shared numeric registry.

All operations issue distinct noncanonical artifacts. Raster backgrounds stay bytes.
"""
import copy,math,html,json,io
from fractions import Fraction
from pathlib import Path
from datetime import datetime,timezone
from .binder import need,text,strict_int,digest,sha,canonical,validate,instant,result,guarded
from .numeric import number,serial,approximate
REVISION='LLM_2D_DRAWING_EQUIPMENT_R006_PRIVATE'
GEOMETRIES={'LINE','POLYLINE','ARC','CIRCLE','RECTANGLE','HATCH','TEXT','MTEXT','DIMENSION','LEADER','REVISION_CLOUD','BLOCK'}
LAYER_CLASSES={'ORIGINAL','TRACE','REDLINE','WORKING'}
OPERATIONS={'COPY','MOVE','ROTATE','MIRROR','OFFSET','TRIM','EXTEND','FILLET','CHAMFER','ARRAY','SNAP','ORTHO','OSNAP','NUMERIC_CONSTRAINT','GEOMETRIC_CONSTRAINT','DIMENSION_CONSTRAINT'}
def point(p):need(isinstance(p,list) and len(p)==2,'HOLD_POINT_TYPE');return [number(x) for x in p]
def rational(v):return Fraction(int(v['numerator']),int(v['denominator']))
def geometry(e,registry):
    need(e['geometry_type'] in GEOMETRIES,'HOLD_GEOMETRY_ENUM');g=e['geometry_parameters'];unit=g['unit'];registry.unit(Fraction(1),unit,'m')
    def p(v):return [registry.unit(x,unit,'m') for x in point(v)]
    typ=e['geometry_type'];out={'type':typ}
    if typ in {'LINE','DIMENSION'}:out.update(points=[p(g['p1']),p(g['p2'])])
    elif typ in {'POLYLINE','HATCH','LEADER','REVISION_CLOUD','BLOCK'}:
        need(isinstance(g['points'],list) and len(g['points'])>=2 and type(g['closed']) is bool,'HOLD_POLYLINE_TYPE');out.update(points=[p(x) for x in g['points']],closed=g['closed'])
    elif typ=='RECTANGLE':
        a,b=p(g['p1']),p(g['p2']);need(a[0]!=b[0] and a[1]!=b[1],'HOLD_DEGENERATE_RECTANGLE');out.update(points=[a,[b[0],a[1]],b,[a[0],b[1]]],closed=True)
    elif typ in {'CIRCLE','ARC'}:
        radius=registry.unit(number(g['radius']),unit,'m');need(radius>0,'HOLD_RADIUS');out.update(center=p(g['center']),radius=radius)
        if typ=='ARC':
            a=registry.unit(number(g['start_angle']),g['angle_unit'],'rad');b=registry.unit(number(g['end_angle']),g['angle_unit'],'rad');need(type(g['clockwise']) is bool and a!=b and abs(b-a)<=registry.unit(number('360'),'deg','rad'),'HOLD_ARC_SWEEP');out.update(start_angle=a,end_angle=b,clockwise=g['clockwise'])
    else:need(text(g['text']) and '\x00' not in g['text'],'HOLD_TEXT');out.update(points=[p(g['anchor'])],text=g['text'])
    if typ=='DIMENSION':
        dx,dy=[b-a for a,b in zip(out['points'][0],out['points'][1])];length=approximate(math.sqrt,dx*dx+dy*dy);display,policy=registry.display(registry.unit(length,'m',g['dimension_unit']),g['rounding_ref']);need(g['dimension_text']==display+' '+g['dimension_unit'],'FAIL_DIMENSION_TEXT_GEOMETRY_MISMATCH');out.update(dimension_text=g['dimension_text'],dimension_value=length)
    return out
def inspect_drawing(d,registry,pin,base):return guarded(_inspect,d,registry,pin,base)
def _inspect(d,r,pin,base):
    need(d['schema']=='yr.drawing-equipment/1' and digest(d)==pin['input_digest'],'HOLD_DRAWING_INPUT')
    source=d['source_ref'];model=d['drawing_model']
    validate(source,pin['source_pin'],base,pin['source_subject'],{'drawing_model':model})
    need(model['source_artifact']==source['artifact_id'] and model['source_revision']==source['revision'],'HOLD_DRAWING_SOURCE_REVISION')
    r.frame(model['coordinate_system'])
    need(model['numeric_registry_sha256']==pin['registry_sha256']==r.sha256,'HOLD_DRAWING_NUMERIC_REGISTRY')
    need(model['authority_state']=='NOT_GRANTED' and model['working_state']=='DRAFT_NOT_FOR_CONSTRUCTION','HOLD_DRAWING_AUTHORITY')
    layers=model['layers'];need(isinstance(layers,list) and len({x['layer_id'] for x in layers})==len(layers) and all(x['class'] in LAYER_CLASSES and type(x['read_only']) is bool for x in layers),'HOLD_LAYER_TYPE')
    need(all(x['read_only'] is True for x in layers if x['class']=='ORIGINAL'),'HOLD_ORIGINAL_LAYER_MUTABLE')
    by={x['layer_id']:x for x in layers};ids=[];geometries=[];unknown=[];holds=[]
    for e in model['entities']:
        need(all(k in e for k in ('entity_id','layer_id','geometry_type','geometry_parameters','calc_id','source_artifact','source_revision','author_worker','created_at','modified_at','state')),'HOLD_ENTITY_FIELDS')
        need(text(e['entity_id']) and text(e['author_worker']) and e['layer_id'] in by and e['source_artifact']==source['artifact_id'] and e['source_revision']==source['revision'] and text(e['calc_id']),'HOLD_ENTITY_SOURCE')
        need(e['state'] in {'DRAFT','OBSERVED','UNKNOWN','HOLD'},'HOLD_ENTITY_STATE')
        need(instant(e['created_at'])<=instant(e['modified_at']),'HOLD_ENTITY_TIME')
        calc=model['calculation_refs'][e['calc_id']]
        validate(calc,pin['calculation_pins'][e['calc_id']],base,{'artifact_id':calc['artifact_id'],'revision':calc['revision']},{'calculation':{'calc_id':e['calc_id'],'entity_digest':digest(e),'source_artifact':source['artifact_id'],'source_revision':model['source_revision'],'registry_sha256':r.sha256,'coordinate_system':model['coordinate_system']}})
        if e['state']=='UNKNOWN':unknown.append(e['entity_id'])
        if e['state']=='HOLD':holds.append(e['entity_id'])
        ids.append(e['entity_id']);geometries.append({'entity_id':e['entity_id'],'layer_id':e['layer_id'],'calc_id':e['calc_id'],'state':e['state'],'geometry':geometry(e,r)})
    need(len(set(ids))==len(ids),'HOLD_ENTITY_COLLISION')
    groups=model['groups'];need(len({g['group_id'] for g in groups})==len(groups),'HOLD_GROUP_IDENTITY')
    for g in groups:need(g['source_revision']==source['revision'] and g['entity_ids'] and len(set(g['entity_ids']))==len(g['entity_ids']) and set(g['entity_ids'])<=set(ids),'HOLD_GROUP_ENTITY_UNBOUND')
    colors={'BLACK':{'OBSERVED','CITED'},'BLUE':{'DRAFT','PROPOSED','CALCULATED'},'RED':{'HOLD','UNKNOWN','CONFLICT','REWORK'}}
    for a in model['annotations']:need(a['color'] in colors and a['state'] in colors[a['color']] and a['source_revision']==source['revision'],'HOLD_COLOR_STATE_OR_REVISION')
    for red in model['redlines']:
        need(all(text(red.get(k)) for k in ('redline_id','source_revision','target_locator','reason','proposed_change','requester','status')) and red['source_revision']==source['revision'],'HOLD_REDLINE_FIELDS')
        need(red.get('authority_effect','NONE')=='NONE' and red['status'] in {'DRAFT','PROPOSED','HOLD','CONFLICT'},'HOLD_REDLINE_AUTHORITY')
        if red.get('calc_id') is not None:need(red['calc_id'] in model['calculation_refs'],'HOLD_REDLINE_CALC_BINDING')
    for bg in model['backgrounds']:
        validate(bg['ref'],pin['background_pins'][bg['ref']['artifact_id']],base)
        need(bg['read_only'] is True and bg['layer_id'] in by and by[bg['layer_id']]['class']=='ORIGINAL','HOLD_BACKGROUND_BOUNDARY')
    return result('PASS_DRAWING_STRUCTURAL_ONLY',tool_revision=REVISION,model_sha256=digest(model),entities=encode_geometry(geometries),source_revision=source['revision'],registry_sha256=r.sha256,unknown_entities=unknown,held_entities=holds,technical_release_eligible=False,authority_state='NOT_GRANTED',construction_issue='NOT_AUTHORIZED')
def arc_range(g,r):
    turn=r.unit(number('360'),'deg','rad');start=g['start_angle']%turn;delta=(g['end_angle']-g['start_angle'])%turn
    extent=(-turn if delta==0 else delta-turn) if g['clockwise'] else (turn if delta==0 else delta)
    return start,extent,turn
def arc_points(g,r):
    start,extent,turn=arc_range(g,r)
    angles=[start,(start+extent)%turn]
    for k in range(4):
        a=turn*k/4;distance=((start-a)%turn) if extent<0 else ((a-start)%turn)
        if distance<=abs(extent):angles.append(a)
    result=[]
    for a in angles:
        if a in {turn*k/4 for k in range(4)}:
            k=int(a/(turn/4));x,y=((1,0),(0,1),(-1,0),(0,-1))[k]
            result.append([g['center'][0]+x*g['radius'],g['center'][1]+y*g['radius']])
        else:result.append([g['center'][0]+approximate(math.cos,a)*g['radius'],g['center'][1]+approximate(math.sin,a)*g['radius']])
    return result
def operation_entity(e,ref,r):
    need(isinstance(e,dict) and all(k in e for k in ('entity_id','source_artifact','source_revision','calc_id','author_worker','created_at','modified_at','state')),'HOLD_OPERATION_ENTITY_FIELDS')
    need(text(e['entity_id']) and text(e['calc_id']) and text(e['author_worker']) and e['source_artifact']==ref['artifact_id'] and e['source_revision']==ref['revision'],'HOLD_OPERATION_ENTITY_SOURCE')
    need(e['state'] in {'DRAFT','OBSERVED','UNKNOWN','HOLD'},'HOLD_OPERATION_ENTITY_STATE');need(instant(e['created_at'])<=instant(e['modified_at']),'HOLD_OPERATION_ENTITY_TIME')
    return geometry(e,r)
def encode_geometry(g):
    if isinstance(g,Fraction):return serial(g)
    if isinstance(g,list):return [encode_geometry(v) for v in g]
    if isinstance(g,dict):return {k:encode_geometry(v) for k,v in g.items()}
    return g
def _transform_points(g,fn):
    out=copy.deepcopy(g)
    if 'points' in out:out['points']=[fn(p) for p in out['points']]
    if 'center' in out:out['center']=fn(out['center'])
    return out
def operate(d,registry,pin,base):return guarded(_operate,d,registry,pin,base)
def _operate(d,r,pin,base):
    need(digest(d)==pin['input_digest'] and d['operation'] in OPERATIONS,'HOLD_OPERATION_CONTRACT');ref=d['source_ref'];record=validate(ref,pin['source_pin'],base,pin['source_subject'],{'operation_input':d['operation_input']})['record'];v=d['operation_input'];r.frame(v['coordinate_system']);need(v['source_revision']==ref['revision'] and v['layer_class']!='ORIGINAL','HOLD_IMMUTABLE_SOURCE_OR_REVISION');g=operation_entity(v['entity'],ref,r);args=v['arguments'];op=d['operation'];out=[];method='EXACT_RATIONAL';lineage=[]
    need(v['registry_sha256']==pin['registry_sha256']==r.sha256,'HOLD_OPERATION_REGISTRY')
    need(v['layer_class'] in LAYER_CLASSES and v['layer_class']!='ORIGINAL','HOLD_OPERATION_LAYER')
    need(text(v['new_artifact_id']) and text(v['new_revision']) and (v['new_artifact_id'],v['new_revision'])!=(ref['artifact_id'],ref['revision']),'HOLD_SAME_REVISION_REPLACEMENT')
    inputs=[v['entity']]
    if op in {'TRIM','EXTEND','FILLET','CHAMFER','OSNAP'}:operation_entity(v['second_entity'],ref,r);inputs.append(v['second_entity'])
    def length(value):return r.unit(number(value),args['unit'],'m')
    def arg_point(value):
        need(isinstance(value,list) and len(value)==2,'HOLD_POINT_TYPE')
        return [length(x) for x in value]
    def norm(vec):
        nonlocal method
        method='DECLARED_BINARY64_NORM'
        return approximate(math.sqrt,sum(x*x for x in vec))
    def intersect(a,b):
        p,q=a['points'];x,y=b['points'];u=[q[i]-p[i] for i in (0,1)];w=[y[i]-x[i] for i in (0,1)];cross=lambda aa,bb:aa[0]*bb[1]-aa[1]*bb[0];den=cross(u,w);need(abs(den)>number(r.data['NUMERIC_POLICY_REGISTRY']['numeric_epsilon']),'HOLD_PARALLEL_OR_AMBIGUOUS_TOPOLOGY');t=cross([x[i]-p[i] for i in (0,1)],w)/den;return [p[i]+t*u[i] for i in (0,1)],t
    if op in {'COPY','MOVE','ARRAY'}:
        delta=arg_point(args['delta']);count=args.get('count',1);need(strict_int(count,1) and count<=1000,'HOLD_ARRAY_BOUND')
        for n in range(1,count+1):out.append(_transform_points(g,lambda p:[p[i]+n*delta[i] for i in (0,1)]))
    elif op=='ROTATE':
        angle=r.unit(number(args['angle']),args['angle_unit'],'rad');center=arg_point(args['center']);c=approximate(math.cos,angle);s=approximate(math.sin,angle);method='DECLARED_BINARY64_TRIG'
        out=[_transform_points(g,lambda p:[center[0]+(p[0]-center[0])*c-(p[1]-center[1])*s,center[1]+(p[0]-center[0])*s+(p[1]-center[1])*c])]
        if g['type']=='ARC':out[0].update(start_angle=g['start_angle']+angle,end_angle=g['end_angle']+angle)
    elif op=='MIRROR':
        a,b=arg_point(args['axis_p1']),arg_point(args['axis_p2']);u=[b[i]-a[i] for i in (0,1)];den=sum(x*x for x in u);need(den>0,'HOLD_MIRROR_AXIS')
        def mirror(p):t=sum((p[i]-a[i])*u[i] for i in (0,1))/den;return [2*(a[i]+t*u[i])-p[i] for i in (0,1)]
        need(g['type']!='ARC','HOLD_ARC_MIRROR_REQUIRES_EXPLICIT_SWEEP_REBIND');out=[_transform_points(g,mirror)]
    elif op=='OFFSET':
        distance=length(args['distance'])
        if g['type']=='LINE':
            a,b=g['points'];u=[b[i]-a[i] for i in (0,1)];length=norm(u);need(length>0,'HOLD_DEGENERATE_LINE');delta=[-u[1]*distance/length,u[0]*distance/length];out=[_transform_points(g,lambda p:[p[i]+delta[i] for i in (0,1)])];method='DECLARED_BINARY64_NORMAL'
        elif g['type'] in {'CIRCLE','ARC'}:need(g['radius']+distance>0,'HOLD_OFFSET_RADIUS');out=[{**g,'radius':g['radius']+distance}]
        else:need(False,'HOLD_OFFSET_GEOMETRY_ARGUMENTS_UNDEFINED')
    elif op in {'TRIM','EXTEND','FILLET','CHAMFER'}:
        second=geometry(v['second_entity'],r);need(g['type']==second['type']=='LINE','HOLD_OPERATION_REQUIRES_TWO_LINES');pt,t=intersect(g,second);keep=args['keep_endpoint'];need(keep in {0,1} and type(keep) is int,'HOLD_SIDE_SELECTION')
        if op in {'TRIM','EXTEND'}:need((0<=t<=1) if op=='TRIM' else not (0<t<1),'HOLD_TRIM_EXTEND_DOMAIN');out=[{**g,'points':[g['points'][keep],pt]}]
        else:
            keep2=args['second_keep_endpoint'];need(type(keep2) is int and keep2 in {0,1},'HOLD_SIDE_SELECTION');a=g['points'][keep];b=second['points'][keep2];u=[a[i]-pt[i] for i in (0,1)];w=[b[i]-pt[i] for i in (0,1)];lu,lw=norm(u),norm(w);need(lu>0 and lw>0,'HOLD_CORNER');u=[x/lu for x in u];w=[x/lw for x in w]
            if op=='CHAMFER':du,dw=length(args['distance1']),length(args['distance2']);need(0<du<=lu and 0<dw<=lw,'HOLD_CHAMFER_DOMAIN');p=[pt[i]+du*u[i] for i in (0,1)];q=[pt[i]+dw*w[i] for i in (0,1)];out=[{**g,'points':[p,q]}]
            else:
                radius=length(args['radius']);dot=sum(u[i]*w[i] for i in (0,1));need(-1<float(dot)<1 and radius>0,'HOLD_FILLET_DOMAIN');theta=approximate(math.acos,dot);run=radius/approximate(math.tan,theta/2);need(run<=lu and run<=lw,'HOLD_FILLET_TOO_LARGE');p=[pt[i]+run*u[i] for i in (0,1)];q=[pt[i]+run*w[i] for i in (0,1)];bis=[u[i]+w[i] for i in (0,1)];bl=norm(bis);center=[pt[i]+bis[i]/bl*radius/approximate(math.sin,theta/2) for i in (0,1)];out=[{'type':'ARC','center':center,'radius':radius,'start_angle':approximate(math.atan2,p[1]-center[1],p[0]-center[0]),'end_angle':approximate(math.atan2,q[1]-center[1],q[0]-center[0]),'clockwise':(u[0]*w[1]-u[1]*w[0])>0}];method='DECLARED_BINARY64_FILLET'
    elif op in {'SNAP','ORTHO','OSNAP'}:
        need(g['type']=='LINE','HOLD_SNAP_ENTITY_TYPE');a,b=g['points']
        if op=='ORTHO':need(args['axis'] in {'X','Y'},'HOLD_ORTHO_AXIS');p=[b[0],a[1]] if args['axis']=='X' else [a[0],b[1]]
        elif op=='OSNAP':
            endpoint_index=args.get('endpoint_index',0);need(type(endpoint_index) is int and endpoint_index in {0,1},'HOLD_OSNAP_ENDPOINT_INDEX')
            need(args['mode'] in {'ENDPOINT','MIDPOINT','CENTER'},'HOLD_OSNAP_MODE');target=geometry(v['second_entity'],r);p=target['center'] if args['mode']=='CENTER' else target['points'][endpoint_index] if args['mode']=='ENDPOINT' else [(target['points'][0][i]+target['points'][1][i])/2 for i in (0,1)]
        else:
            grid=length(args['grid_spacing']);need(grid>0 and args['selection_rule']=='NEAREST_TIES_TO_EVEN','HOLD_SNAP_POLICY');p=[Fraction(round(x/grid))*grid for x in b];lineage=[{'operation':'DECLARED_FINAL_GRID_QUANTIZATION','policy':'NEAREST_TIES_TO_EVEN','grid_spacing':serial(grid),'material_rounding':True}]
        out=[{**g,'points':[a,p]}]
    else:
        need(args['constraint'] in {'HORIZONTAL','VERTICAL','LENGTH','COINCIDENT'},'HOLD_CONSTRAINT_KIND');need(g['type']=='LINE','HOLD_CONSTRAINT_ENTITY');a,b=g['points'];eps=number(r.data['GEOMETRY_TOLERANCE_POLICY']['geometric_tolerance'])
        if args['constraint']=='HORIZONTAL':error=abs(b[1]-a[1])
        elif args['constraint']=='VERTICAL':error=abs(b[0]-a[0])
        elif args['constraint']=='LENGTH':error=abs(norm([b[i]-a[i] for i in (0,1)])-length(args['length']))
        else:error=norm([b[i]-a[i] for i in (0,1)])
        need(error<=eps,'FAIL_GEOMETRIC_CONSTRAINT');out=[g]
    return result('PASS_CAD_OPERATION_ONLY',tool_revision=REVISION,operation=op,source_revision=ref['revision'],source_sha256=ref['sha256'],new_artifact_id=v['new_artifact_id'],new_revision=v['new_revision'],geometries=encode_geometry(out),geometry_unit='m',coordinate_system=v['coordinate_system'],unknown_entities=[e['entity_id'] for e in inputs if e['state']=='UNKNOWN'],held_entities=[e['entity_id'] for e in inputs if e['state']=='HOLD'],input_calculation_ids=[e['calc_id'] for e in inputs],calc_id=digest({'operation':op,'input':v,'registry':r.sha256,'revision':REVISION}),registry_sha256=r.sha256,numeric_method=method,numeric_error_bound='EXACT' if method=='EXACT_RATIONAL' else 'UNKNOWN_MATHEMATICAL_BOUND',numeric_lineage=lineage,source_overwrite=False)
def calibrate(d,r,pin,base):return guarded(_calibrate,d,r,pin,base)
def _calibrate(d,r,pin,base):
    need(digest(d)==pin['input_digest'],'HOLD_CALIBRATION_PIN');validate(d['scan_ref'],pin['scan_pin'],base);pairs=d['calibration_pairs'];need(len(pairs)>=2,'HOLD_TWO_KNOWN_DIMENSIONS_REQUIRED');scales=[]
    for pair in pairs:
        a,b=point(pair['scan_p1']),point(pair['scan_p2']);pixels=approximate(math.sqrt,sum((b[i]-a[i])**2 for i in (0,1)));length=r.unit(number(pair['known_length']),pair['unit'],'m');need(pixels>0 and length>0,'HOLD_CALIBRATION_DIMENSION');scales.append(length/pixels)
    need(text(d['repaired_revision']) and d['repaired_revision']!=d['scan_ref']['revision'],'HOLD_CALIBRATION_SAME_REVISION')
    tol=number(d['residual_tolerance']);need(tol>=0 and d['policy_ref']==pin['policy_ref'],'HOLD_CALIBRATION_POLICY');scale=sum(scales)/len(scales);residual=max(abs(x-scale) for x in scales);need(residual<=tol,'HOLD_ANISOTROPIC_PAPER_OR_SCAN_DISTORTION');need(d['unreadable_labels']==pin['unreadable_labels'],'HOLD_UNREADABLE_DIMENSION_ASSERTION');need(d['source_read_only'] is True,'HOLD_SCAN_SOURCE_MUTATION')
    return result('PASS_CALIBRATION_DECLARED_DIMENSIONS_ONLY',tool_revision=REVISION,scan_sha256=d['scan_ref']['sha256'],scale_metres_per_pixel=serial(scale),calibration_residual=serial(residual),unknown_labels=d['unreadable_labels'],raw_scan_unchanged=True,trace_layer_id=d['trace_layer_id'],redline_id=d['redline_id'],repaired_revision=d['repaired_revision'])
def inspect_desk(d,pin,base):return guarded(_desk,d,pin,base)
def _desk(d,pin,base):
    need(digest(d)==pin['input_digest'] and len({s['sheet_id'] for s in d['sheets']})==len(d['sheets']),'HOLD_DESK_SHEET_IDENTITY')
    sheets={s['sheet_id']:s for s in d['sheets']}
    for s in sheets.values():
        need(all(k in s for k in ('sheet_id','drawing_title','source_revision','scale','coordinate_system','authority_state','working_state','source_hash','source_ref','pinned','order','zoom')),'HOLD_DESK_TAG_FIELDS');need(s['source_hash']==s['source_ref']['sha256'] and s['source_revision']==s['source_ref']['revision'],'HOLD_DESK_REVISION');validate(s['source_ref'],pin['source_pins'][s['source_ref']['artifact_id']],base);need(s['authority_state']=='NOT_GRANTED' and type(s['pinned']) is bool and strict_int(s['order']) and number(s['zoom'])>0,'HOLD_DESK_PROFILE')
    need(isinstance(d['closed_sheet_ids'],list) and len(set(d['closed_sheet_ids']))==len(d['closed_sheet_ids']) and set(d['closed_sheet_ids'])<=set(sheets),'HOLD_DESK_CLOSED_SHEET_IDENTITY')
    need(all(x['working_state'] in {'DRAFT_NOT_FOR_CONSTRUCTION','OBSERVED','HOLD','UNKNOWN','CONFLICT'} and number(x['scale'])>0 for x in sheets.values()),'HOLD_DESK_WORKING_STATE')
    for link in d['drawing_links']:need(link['from_sheet'] in sheets and link['to_sheet'] in sheets and text(link['location_identity']),'HOLD_DRAWING_LINK')
    for overlay in d['overlays']:
        a,b=[sheets[i] for i in overlay['sheet_ids']];need(a['coordinate_system']==b['coordinate_system'] and a['scale']==b['scale'],'HOLD_UNCALIBRATED_OVERLAY');need(overlay['source_revisions']==[a['source_revision'],b['source_revision']],'HOLD_REVISION_OVERLAY_COLLAPSE')
    return result('PASS_DESK_SOURCE_CONTINUITY_ONLY',tool_revision=REVISION,sheets=d['sheets'],drawing_links=d['drawing_links'],overlays=d['overlays'],closed_sheet_ids=d['closed_sheet_ids'],semantic_merging='NOT_PERFORMED')
def plot(d,r,pin,base):return guarded(_plot,d,r,pin,base)
def _plot(d,r,pin,base):
    inspected=_inspect(d['drawing_request'],r,pin['drawing_pin'],base);need(inspected['verdict']=='PASS_DRAWING_STRUCTURAL_ONLY','HOLD_PLOT_DRAWING');need(digest(d)==pin['input_digest'],'HOLD_PLOT_PIN');model=d['drawing_request']['drawing_model'];need(d['source_revision']==model['source_revision'] and d['title_revision']==model['source_revision'],'FAIL_REVISION_PRINT_MISMATCH');need(d['issue_state']=='DRAFT_NOT_FOR_CONSTRUCTION','HOLD_DRAFT_ISSUE_AUTHORITY')
    orientation=d['orientation'];need(orientation in {'PORTRAIT','LANDSCAPE'} and d['paper_size_mm']==[594,841],'FAIL_A1_PAGE_SIZE');width,height=([594,841] if orientation=='PORTRAIT' else [841,594]);scale=number(d['intended_scale']);need(scale>0 and scale==number(d['actual_output_scale']),'FAIL_PRINT_SCALE');margin=number(d['margin_mm']);need(0<margin<min(width,height)/4,'FAIL_PRINT_MARGIN');need(d['font_profile']=='HELVETICA_ASCII_R001' and number(d['lineweight_mm'])>0 and number(d['text_height_mm'])>0,'HOLD_FONT_OR_LINEWEIGHT');need(d['external_refs_missing']==[] and d['layer_ids_visible']==[l['layer_id'] for l in model['layers']],'HOLD_PLOT_EXTERNAL_REF_OR_LAYER')
    factor=Fraction(1000)/scale;shapes=[]
    for e in model['entities']:
        g=geometry(e,r);need(g.get('text','').isascii() and g.get('dimension_text','').isascii(),'HOLD_UNSUPPORTED_FONT_GLYPH');shapes.append((e,g))
        points=g.get('points',[])
        if g['type']=='ARC':points=arc_points(g,r)
        elif 'center' in g:points=[[g['center'][i]+sign*g['radius'] for i in (0,1)] for sign in (-1,1)]
        need(all(0<=p[0]*factor<=number(str(width))-2*margin and 0<=p[1]*factor<=number(str(height))-2*margin-number('50') for p in points),'FAIL_PRINTABLE_AREA_OVERFLOW')
    formats=d['formats'];need(isinstance(formats,list) and bool(formats) and set(formats)<={'PDF','SVG','DXF','JSON'} and len(formats)==len(set(formats)),'HOLD_EXPORT_FORMAT');folder=(Path(base)/d['output_directory']).resolve();need(folder.is_relative_to(Path(base).resolve()) and not folder.exists(),'HOLD_CREATE_ONLY_PLOT_DESTINATION');outputs={};plot_id=digest({'request':d,'model_hash':inspected['model_sha256'],'tool':REVISION});title=f"DRAFT / NOT FOR CONSTRUCTION - {model['drawing_id']} - Rev {model['source_revision']}";need(title.isascii(),'HOLD_UNSUPPORTED_FONT_GLYPH')
    state_labels=[e['state']+': '+e['entity_id'] for e,g in shapes if e['state'] in {'UNKNOWN','HOLD'}]
    need(all(x.isascii() and '\n' not in x and '\r' not in x for x in state_labels),'HOLD_STATE_SCOPE_FONT_OR_LINE')
    need(len(state_labels)*(number(d['text_height_mm'])+2)<=25,'HOLD_STATE_SCOPE_HEADER_OVERFLOW')
    from reportlab.pdfbase.pdfmetrics import stringWidth,getAscentDescent
    font_points=float(number(d['text_height_mm']))*72/25.4
    ascent_points,descent_points=getAscentDescent('Helvetica',font_points)
    for entity,g in shapes:
        body=None
        if g['type'] in {'TEXT','MTEXT'}:anchor=g['points'][0];body=g['text']
        elif g['type']=='DIMENSION':anchor=[sum(p[i] for p in g['points'])/2 for i in (0,1)];body=g['dimension_text']
        if body is not None:
            need('\n' not in body and '\r' not in body,'HOLD_PRINT_MULTILINE_TEXT_LAYOUT_UNDEFINED')
            for output_format in formats:
                x,y=[float(v*factor)*72/25.4 for v in anchor]
                if g['type']=='DIMENSION' and output_format=='PDF':x+=5;y+=5
                need(x+stringWidth(body,'Helvetica',font_points)<=float(number(str(width))-2*margin)*72/25.4 and y+descent_points>=0 and y+ascent_points<=float(number(str(height))-2*margin-50)*72/25.4,'FAIL_PRINT_ENTITY_TEXT_BOUNDS_OVERFLOW')
    need(all(stringWidth(x,'Helvetica',float(number(d['text_height_mm']))*72/25.4)<=float(number(str(width))-2*margin-5)*72/25.4 for x in [title]+state_labels),'FAIL_PRINT_TEXT_WIDTH_OVERFLOW')
    if 'PDF' in formats:
        from reportlab.pdfgen import canvas
        mm=72/25.4;stream=io.BytesIO();c=canvas.Canvas(stream,pagesize=(width*mm,height*mm),pageCompression=0,invariant=1);c.setTitle(title);c.setLineWidth(float(number(d['lineweight_mm']))*mm);c.rect(float(margin)*mm,float(margin)*mm,(width-2*float(margin))*mm,(height-2*float(margin))*mm);c.setFont('Helvetica',float(number(d['text_height_mm']))*mm);c.drawString(float(margin+number('5'))*mm,(height-float(margin)-12)*mm,title);c.drawString(float(margin+number('5'))*mm,(height-float(margin)-20)*mm,'A1 '+orientation+' | SCALE 1:'+str(scale)+' | '+plot_id[:20])
        for i,label in enumerate(state_labels):c.drawString(float(margin+5)*mm,(height-float(margin)-28-i*(float(number(d['text_height_mm']))+2))*mm,label)
        for e,g in shapes:
            def xy(p):return tuple(float(margin+v*factor)*mm for v in p)
            if g['type'] in {'CIRCLE','ARC'}:
                x,y=xy(g['center']);rr=float(g['radius']*factor)*mm
                if g['type']=='CIRCLE':c.circle(x,y,rr)
                else:
                    start,extent,turn=arc_range(g,r);c.arc(x-rr,y-rr,x+rr,y+rr,startAng=float(start)*360/float(turn),extent=float(extent)*360/float(turn))
            elif g['type'] in {'TEXT','MTEXT'}:c.drawString(*xy(g['points'][0]),g['text'])
            else:
                points=g['points']+([g['points'][0]] if g.get('closed') else []);p=c.beginPath();p.moveTo(*xy(points[0]));[p.lineTo(*xy(pt)) for pt in points[1:]];c.drawPath(p)
                if g['type']=='DIMENSION':a,b=g['points'];mid=[(a[i]+b[i])/2 for i in (0,1)];x,y=xy(mid);c.drawString(x+5,y+5,g['dimension_text'])
        c.showPage();c.save();outputs['PDF']=stream.getvalue()
    if 'SVG' in formats:
        rows=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="0 0 {width} {height}">',f'<metadata>{html.escape(json.dumps({"plot_id":plot_id,"source_revision":model["source_revision"],"scale":str(scale),"authority":"NONE"}))}</metadata>',f'<text x="{margin}" y="{margin+number("8")}" font-size="4">{html.escape(title)}</text>',f'<g transform="translate({margin},{height-float(margin)}) scale(1,-1)" fill="none" stroke="black" stroke-width="{d["lineweight_mm"]}">']
        for e,g in shapes:
            if g['type']=='CIRCLE':rows.append(f'<circle id="{html.escape(e["entity_id"],quote=True)}" cx="{float(g["center"][0]*factor)}" cy="{float(g["center"][1]*factor)}" r="{float(g["radius"]*factor)}"/>')
            elif g['type']=='ARC':
                start,extent,turn=arc_range(g,r);points=arc_points(g,r);a=points[0];b=points[1];rr=float(g['radius']*factor)
                if abs(extent)==turn:rows.append(f'<circle cx="{float(g["center"][0]*factor)}" cy="{float(g["center"][1]*factor)}" r="{rr}"/>')
                else:rows.append(f'<path d="M {float(a[0]*factor)} {float(a[1]*factor)} A {rr} {rr} 0 {int(abs(extent)>turn/2)} {int(extent>0)} {float(b[0]*factor)} {float(b[1]*factor)}"/>')
            elif g['type'] in {'TEXT','MTEXT'}:
                xx=float(g['points'][0][0]*factor);yy=float(g['points'][0][1]*factor);rows.append(f'<text transform="translate({xx},{yy}) scale(1,-1)" fill="black" stroke="none" font-family="Helvetica" font-size="{d["text_height_mm"]}">{html.escape(g["text"])}</text>')
            elif 'points' in g:rows.append('<polyline points="'+' '.join(f'{float(p[0]*factor)},{float(p[1]*factor)}' for p in g['points']+([g['points'][0]] if g.get('closed') else []))+'"/>')
            else:need(False,'HOLD_SVG_ARC_EXPORT_REQUIRES_DECLARED_SWEEP')
        for e,g in shapes:
            if g['type']=='DIMENSION':
                a,b=g['points'];xx=float((a[0]+b[0])/2*factor);yy=float((a[1]+b[1])/2*factor);rows.append(f'<text transform="translate({xx},{yy}) scale(1,-1)" fill="black" stroke="none" font-family="Helvetica" font-size="{d["text_height_mm"]}">{html.escape(g["dimension_text"])}</text>')
        rows+=['</g>']+[f'<text x="{margin+5}" y="{margin+28+i*(float(number(d["text_height_mm"]))+2)}" font-family="Helvetica" font-size="{d["text_height_mm"]}">{html.escape(label)}</text>' for i,label in enumerate(state_labels)]+['</svg>'];outputs['SVG']='\n'.join(rows).encode('utf-8')
    if 'DXF' in formats:
        rows=['0','SECTION','2','HEADER','9','$INSUNITS','70','6','0','ENDSEC','0','SECTION','2','ENTITIES']
        for e,g in shapes:
            if g['type']=='LINE':a,b=g['points'];rows+=['0','LINE','8',e['layer_id'],'10',str(float(a[0])),'20',str(float(a[1])),'11',str(float(b[0])),'21',str(float(b[1]))]
            elif g['type']=='CIRCLE':a=g['center'];rows+=['0','CIRCLE','8',e['layer_id'],'10',str(float(a[0])),'20',str(float(a[1])),'40',str(float(g['radius']))]
            elif g['type']=='ARC':
                start,extent,turn=arc_range(g,r);a=g['center'];sa=start if extent>0 else (start+extent)%turn;ea=(start+extent)%turn if extent>0 else start
                rows+=['0','ARC','8',e['layer_id'],'10',str(float(a[0])),'20',str(float(a[1])),'40',str(float(g['radius'])),'50',str(float(sa)*360/float(turn)),'51',str(float(ea)*360/float(turn))]
            elif g['type'] in {'TEXT','MTEXT'}:
                a=g['points'][0];rows+=['0','TEXT','8',e['layer_id'],'10',str(float(a[0])),'20',str(float(a[1])),'40',str(float(number(d['text_height_mm'])*scale/1000)),'1',g['text']]
            elif g['type']=='DIMENSION':
                a,b=g['points'];mid=[(a[i]+b[i])/2 for i in (0,1)];rows+=['0','LINE','8',e['layer_id'],'10',str(float(a[0])),'20',str(float(a[1])),'11',str(float(b[0])),'21',str(float(b[1])),'0','TEXT','8',e['layer_id'],'10',str(float(mid[0])),'20',str(float(mid[1])),'40',str(float(number(d['text_height_mm'])*scale/1000)),'1',g['dimension_text']]
            else:need(False,'HOLD_DXF_GEOMETRY_EXPORT_UNDEFINED')
        for i,label in enumerate([title]+state_labels):rows+=['0','TEXT','8','REDLINE','10','0','20',str(float((number(str(height))-2*margin-12-i*(number(d['text_height_mm'])+2))*scale/1000)),'40',str(float(number(d['text_height_mm'])*scale/1000)),'1',label]
        rows+=['0','ENDSEC','0','EOF'];outputs['DXF']='\n'.join(rows).encode('ascii')
    if 'JSON' in formats:outputs['JSON']=canonical({'model':model,'inspection':inspected,'plot_id':plot_id})
    if 'PDF' in outputs:
        from pypdf import PdfReader
        page=PdfReader(io.BytesIO(outputs['PDF'])).pages[0]
        need(abs(float(page.mediabox.width)*25.4/72-width)<0.001 and abs(float(page.mediabox.height)*25.4/72-height)<0.001,'FAIL_PDF_PAGE_SIZE_READBACK')
    folder.mkdir(parents=True);receipts=[]
    for kind,b in outputs.items():
        dest=folder/('drawing.'+kind.lower());dest.write_bytes(b);need(dest.read_bytes()==b,'HOLD_PLOT_READBACK');receipts.append({'plot_id':plot_id,'drawing_id':model['drawing_id'],'source_revision':model['source_revision'],'sheet_id':model['sheet_id'],'paper_size_mm':[594,841],'orientation':orientation,'intended_scale':str(scale),'actual_output_scale':str(scale),'lineweight_profile':d['lineweight_mm'],'font_profile':d['font_profile'],'output_format':kind,'output_hash':sha(b),'authority_state':'NOT_GRANTED','generated_by':REVISION,'generated_at':datetime.now(timezone.utc).isoformat(),'generated_time_basis':'LOCAL_PROCESS_CLOCK_NOT_DUAL_ANCHORED','locator':str(dest.relative_to(Path(base).resolve())).replace('\\','/')})
    return result('PASS_PRIVATE_DRAFT_PLOT_ONLY',tool_revision=REVISION,plot_receipts=receipts,inspection=inspected,preflight_checks_passed=15,source_overwrite=False,physical_print='NOT_EXECUTED',human_gate='NOT_EXECUTED')
