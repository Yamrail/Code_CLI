"""Purpose-scoped, legible MD presentation with explicit REV3 safety valves.

No engineering geometry or source facts are inferred here. Original MD spans
remain intact; the displayed excerpts and any ellipsis are recorded separately.
"""
from __future__ import annotations
import hashlib, json, math, re
from pathlib import Path
import xml.etree.ElementTree as ET

PURPOSE='EXPLANATORY_PONCHI_DIAGRAM'
DERIVATION='STRUCTURED_MD_GRAPH'
WIDTH,HEIGHT=1414,1000
NS='http://www.w3.org/2000/svg'
INK,MUTED,BLUE,LINE,PALE,AMBER='#102f3c','#536873','#0060df','#b8c7d0','#f3f7fc','#8a5100'
CATEGORY={'KNOWN':'資料の記載','UNKNOWN':'分からないこと','HYPOTHESIS':'条件付き見立て','CONDITION':'条件・分岐','SUPPORT':'支持材料','COUNTEREVIDENCE':'弱める観測','NEXT':'次の探索点','SYNTHESIS':'現在の見立て','STATEMENT':'記載'}
RELATION={'EXPLICIT_CONDITION':'条件','EXPLICIT_SUPPORT':'支持材料','EXPLICIT_COUNTEREVIDENCE':'弱める観測','SAME_SOURCE_REFERENCE':'同じ出典・因果ではない','SECTION_MEMBER':'同じ節'}

def _canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def _sha(value):return hashlib.sha256(value).hexdigest()

def render_structured(board,binding,source_ledger,*,projection,raw_model_text):
    from . import silver_board_renderer as kernel
    from .silver_board import validate_ledger
    from .explanatory_graph import validate_projection
    error=kernel.BoardRenderUnavailable
    if not isinstance(raw_model_text,str):raise error('STRUCTURED_MD_RAW_REQUIRED')
    try:analysis=json.loads(raw_model_text)['analysis_markdown']
    except (ValueError,TypeError,KeyError):raise error('STRUCTURED_MD_RAW_BINDING') from None
    if (not isinstance(analysis,str) or projection.get('purpose')!=PURPOSE or projection.get('derivation')!=DERIVATION
        or board.get('schema')!='yamrail.osint-structured-md-graph/1' or projection.get('board')!=board
        or projection.get('binding')!=binding or projection.get('board_sha256')!=_sha(_canonical(board))
        or projection.get('analysis_sha256')!=_sha(analysis.encode('utf-8'))
        or projection.get('model_output_sha256')!=_sha(raw_model_text.encode('utf-8'))
        or source_ledger.get('binding')!=binding or set(binding)!={'workface_id','epoch','revision','input_sha256'}):
        raise error('STRUCTURED_MD_SOURCE_BINDING')
    sources=validate_ledger(source_ledger)
    if projection.get('source_ledger_sha256')!=source_ledger.get('sha256'):raise error('STRUCTURED_MD_LEDGER_BINDING')
    if (_sha(kernel.VENDOR.read_bytes())!=kernel.VENDOR_SHA256 or _sha(kernel.FONT.read_bytes())!=kernel.FONT_SHA256):raise error('BOARD_RENDERER_OR_FONT_IDENTITY')
    metrics=kernel._metrics();advances=metrics['advances'];units=metrics['units_per_em']
    warnings=[]
    try:validate_projection(projection,analysis,source_ledger,binding,raw_model_text=raw_model_text)
    except (ValueError,TypeError,KeyError):
        # Presentation availability cannot authorise unverified categories or
        # reversed relations. Recover the deterministic structure from MD.
        from .explanatory_graph import derive_structured_md
        projection=derive_structured_md(analysis,source_ledger,binding,raw_model_text)
        board=projection['board']
        warnings.append('STRUCTURE_RECOMPUTED_FROM_CANONICAL_MD')
    model,texts,layers,bounds,display_spans=[],{},{},[],[]
    glyph_codes=set()
    def warn(code):
        if code not in warnings:warnings.append(code)
    def normalise(text):
        rendered=[];substitutions=[]
        for index,char in enumerate(text):
            valid=(str(ord(char)) in advances and (ord(char)>=32 or char=='\t') and ord(char) not in (0xfffe,0xffff))
            if not valid:
                rendered.append('□');substitutions.append({'index':index,'codepoint':'U+'+format(ord(char),'04X'),'replacement':'□'});glyph_codes.add(ord(char));warn('UNSUPPORTED_FONT_GLYPH_SUBSTITUTED')
            else:rendered.append(char)
        return ''.join(rendered),substitutions
    def width(text,size):return sum(advances.get(str(ord(char)),advances['9633']) for char in text)*size/units
    def wrap(text,allowed,size):
        lines=[];current=''
        for char in text:
            if current and width(current+char,size)>allowed:
                lines.append(current);current=char
            else:current+=char
        if current or not lines:lines.append(current)
        return lines
    def excerpt(node,allowed,size=13,maximum_lines=3,maximum_chars=90,role='node'):
        source=node.get('text','');source=source if isinstance(source,str) else str(source)
        clean,substitutions=normalise(source);length=len(source)
        polarities=[]
        for span in node.get('polarity_spans',[]):
            if (isinstance(span,dict) and type(span.get('start')) is int and type(span.get('end')) is int
                and 0<=span['start']<span['end']<=length and span.get('text')==source[span['start']:span['end']]):polarities.append(dict(span))
        visible_tokens=list(dict.fromkeys(span['text'] for span in polarities))
        context_span=node.get('context_span',node.get('md_span',{}))
        context_text=analysis[context_span.get('start',0):context_span.get('end',0)] if isinstance(context_span,dict) else ''
        context_polarities=[]
        for span in node.get('context_polarity_spans',[]):
            if (isinstance(span,dict) and type(span.get('start')) is int and type(span.get('end')) is int
                and 0<=span['start']<span['end']<=len(context_text) and span.get('text')==context_text[span['start']:span['end']]):context_polarities.append(dict(span))
        context_tokens=list(dict.fromkeys(span['text'] for span in context_polarities))
        if length<=maximum_chars:
            for candidate_size in (size,12,11):
                if candidate_size>size:continue
                if len(wrap(clean,allowed,candidate_size))<=maximum_lines:
                    size=candidate_size;fragments=[{'start':0,'end':length,'text':source}];display=clean;break
            else:fragments=None
        else:fragments=None
        if fragments is None:
            def compose(parts):
                chunks=['…'] if parts[0][0]>0 else []
                for index,(start,end) in enumerate(parts):
                    if index and start>parts[index-1][1]:chunks.append('…')
                    chunks.append(clean[start:end])
                if parts[-1][1]<length:chunks.append('…')
                return ''.join(chunks)
            # A leading publisher label and repeated trailing aliases can be
            # omitted together when that preserves the complete quantified
            # statement and predicate. Exact aliases are printed separately.
            source_tail=re.search(r'[（(][CW][0-9]+(?:[/ ,、]+[CW][0-9]+)*[）)](?=[。.!！?？]?$)',source)
            comma=source.find('、');parts=None
            if source_tail and 0<comma<30 and re.search(r'[A-Za-z]',source[:comma]):
                candidate=[(comma+1,source_tail.start())]
                if source_tail.end()<length:candidate.append((source_tail.end(),length))
                candidate_text=compose(candidate)
                if len(candidate_text)<=maximum_chars:
                    for candidate_size in (size,12,11):
                        if candidate_size<=size and len(wrap(candidate_text,allowed,candidate_size))<=maximum_lines:
                            parts=candidate;size=candidate_size;break
            if parts is None:
                # Reserve the predicate suffix first; allowing the head cut to
                # force tail_start forward used to reduce predicates to 1字.
                tail_start=max(1,length-45)
                for span in polarities:
                    if span['end']>tail_start:tail_start=min(tail_start,max(1,span['start']-8))
                head=min(tail_start-1,max(1,maximum_chars-(length-tail_start)-1))
                candidate=[(0,head),(tail_start,length)]
                for candidate_size in (size,12,11):
                    if candidate_size>size:continue
                    if len(wrap(compose(candidate),allowed,candidate_size))<=maximum_lines:
                        parts=candidate;size=candidate_size;break
                if parts is None:
                    while head>1 and len(wrap(compose(candidate),allowed,11))>maximum_lines:
                        head-=1;candidate=[(0,head),(tail_start,length)]
                    parts=candidate;size=11
            display=compose(parts);fragments=[{'start':start,'end':end,'text':source[start:end]} for start,end in parts]
        lines=wrap(display,allowed,size)
        # An exceptionally long token is always shortened at the declared valve;
        # original source/polarity tokens remain in metadata and the card header.
        while len(lines)>maximum_lines and fragments[0]['end']>1:
            fragments[0]['end']-=1;fragments[0]['text']=source[:fragments[0]['end']]
            display=clean[:fragments[0]['end']]+'…';fragments=fragments[:1];lines=wrap(display,allowed,size)
        item={'node_id':node.get('id',''),'role':role,'source_md_span':dict(node.get('md_span',{})),
              'source_text':source,'source_refs':list(node.get('source_refs',[])),
              'display_text':display,'display_fragments':fragments,'ellipsis':display!=clean,
              'rendered_lines':lines,'font_size':size,'max_lines':maximum_lines,
              'polarity_spans':polarities,'visible_polarity_texts':[token for token in visible_tokens if token in display],
              'source_context_span':dict(context_span),'source_context_text':context_text,
              'context_polarity_spans':context_polarities,'visible_context_polarity_texts':[token for token in context_tokens if token in display],
              'polarity_presentation':'CATEGORY_AND_EXACT_CLAUSE_NOT_TOKEN_STRIP',
              'glyph_substitutions':substitutions}
        display_spans.append(item);return item
    def primitive(kind,layer,color,points,body=()):model.append({'type':kind,'body':list(body),'layer':layer,'color':color,'points':[(x,HEIGHT-y) for x,y in points]})
    def line(layer,x1,y1,x2,y2,color=LINE):primitive('LINE',layer,color,[(x1,y1),(x2,y2)])
    def rectangle(layer,x,y,w,h,fill='#ffffff'):
        primitive('SOLID',layer,fill,[(x,y),(x+w,y),(x+w,y+h),(x,y+h)])
        for x1,y1,x2,y2 in ((x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)):line(layer,x1,y1,x2,y2)
    def text(layer,value,x,baseline,size,allowed,color=INK):
        size=max(11,size);value=normalise(str(value))[0]
        # Every caller has a bounded line. This defensive last valve prevents a
        # metadata label or an extreme header from becoming a render exception.
        if width(value,size)>allowed:
            while value and width(value+'…',size)>allowed:value=value[:-1]
            value+='…';warn('PRESENTATION_LABEL_CLAMPED')
        token='YRSTRUCTTEXT'+str(len(texts)).zfill(5);texts[token]={'text':value,'size':size}
        bounds.append({'layer':layer,'x':x,'baseline':baseline,'font_size':size,'measured_width':round(width(value,size),6),'allowed_width':allowed})
        primitive('TEXT',layer,color,[(x,baseline)],[(1,token),(40,size),(50,0)])
    def semantic(layer,kind,node=None,refs=(),**extra):
        layers[layer]={'kind':kind,'source_refs':list(refs),'accessible_label':node.get('text','') if node else '',**extra}
    def source_refs(layer,refs,x,y,allowed):
        values=[ref for ref in refs if ref in sources]
        text(layer,'出典 '+' '.join(values) if values else '出典の対応は未確定',x,y,11,allowed,MUTED)
    def valid_span(span,text_value):
        return (isinstance(span,dict) and type(span.get('start')) is int and type(span.get('end')) is int
            and 0<=span['start']<=span['end']<=len(analysis) and analysis[span['start']:span['end']]==text_value)
    safe_nodes=[];by_id={}
    for node in board.get('nodes',[]):
        if not isinstance(node,dict) or not isinstance(node.get('id'),str) or not isinstance(node.get('text'),str) or not valid_span(node.get('md_span'),node.get('text')):
            warn('NODE_SOURCE_SPAN_OMITTED');continue
        if node['id'] in by_id:warn('DUPLICATE_NODE_OMITTED');continue
        safe_nodes.append(node);by_id[node['id']]=node
    if not safe_nodes:
        # Valid MD with headings only still has a real, explicitly located span.
        for offset,line_value in enumerate(analysis.splitlines(keepends=True)):
            start=sum(len(v) for v in analysis.splitlines(keepends=True)[:offset]);value=line_value.rstrip('\r\n')
            if value.strip():
                node={'id':'available_md_'+str(start),'text':value,'md_span':{'start':start,'end':start+len(value),'line':offset+1},'category':'STATEMENT','source_refs':[],'polarity_spans':[],'section_id':None}
                safe_nodes.append(node);by_id[node['id']]=node
                if len(safe_nodes)>=12:break
        warn('AVAILABLE_MD_SPAN_FALLBACK')
    order=[value for value in board.get('display_order',[]) if value in by_id]
    order+= [node['id'] for node in safe_nodes if node['id'] not in order]
    chosen=[by_id[value] for value in order[:12]]
    total=board.get('selection',{}).get('total_candidates',board.get('selection',{}).get('total_nodes',len(board.get('nodes',[]))))
    if type(total) is not int or total<len(safe_nodes):total=max(len(safe_nodes),len(board.get('nodes',[])))
    total=max(total,len(chosen));remaining=total-len(chosen)
    if remaining:warn('PARTIAL_PROJECTION')
    rectangle('00_frame',0.8,0.8,WIDTH-1.6,HEIGHT-1.6)
    line('01_grid',0,86,WIDTH,86);line('01_grid',707,86,707,872);line('01_grid',0,898,WIDTH,898)
    text('10_header','調査Graph | 資料・見立て・次の探索',16,31,22,1000,BLUE)
    text('10_header','対象 '+binding['workface_id'][:8]+' / E'+str(binding['epoch'])+' R'+str(binding['revision']),1040,30,11,355,MUTED)
    synthesis=next((by_id[value] for value in board.get('footer',{}).get('synthesis_node_ids',[]) if value in by_id),safe_nodes[0] if safe_nodes else None)
    if synthesis:
        item=excerpt(synthesis,1378,13,1,100,'header')
        text('10_header',item['rendered_lines'][0],16,57,item['font_size'],1378)
    text('10_header','資料の記載・仮説・条件を区別。線はMDに明示された対応であり、独立した事実認定ではありません。',16,77,11,1378,MUTED)
    positions={};numbers={}
    for index,node in enumerate(chosen):
        row,column=divmod(index,2);x=8+349*column;y=100+129*row;layer='30_node_'+str(index)
        category=CATEGORY.get(node.get('category'),'記載')
        if node.get('category') not in CATEGORY:warn('CATEGORY_UNCONFIRMED_DISPLAYED_AS_STATEMENT')
        semantic(layer,'node',node,node.get('source_refs',[]),node_id=node['id'],category=node.get('category','STATEMENT'),md_start=node['md_span']['start'],md_end=node['md_span']['end'])
        rectangle(layer,x,y,341,120,PALE)
        text(layer,str(index+1).zfill(2)+' '+category,x+8,y+15,11,325,BLUE)
        item=excerpt(node,325,13,3,90,'node')
        # Isolated matching tokens are validation metadata, not a proposition.
        # The complete excerpt and category carry the visible meaning.
        item['polarity_rendered_lines']=[]
        first=36
        for text_index,value in enumerate(item['rendered_lines']):text(layer,value,x+8,y+first+16*text_index,item['font_size'],325)
        source_refs(layer,node.get('source_refs',[]),x+8,y+113,325)
        positions[node['id']]=(x,y,341,120);numbers[node['id']]=index+1
    edges=[];omitted_edges=[];section_edges=[]
    priority={'EXPLICIT_CONDITION':0,'EXPLICIT_SUPPORT':1,'EXPLICIT_COUNTEREVIDENCE':2,'SAME_SOURCE_REFERENCE':3,'SECTION_MEMBER':4}
    for edge in sorted(board.get('edges',[]),key=lambda e:priority.get(e.get('relation'),9)):
        if edge.get('relation')=='SECTION_MEMBER':
            if edge.get('to') in positions:section_edges.append(edge.get('id'))
            else:omitted_edges.append(edge.get('id'))
            continue
        if edge.get('from') not in positions or edge.get('to') not in positions or edge.get('causal') is not False or edge.get('relation') not in RELATION:
            omitted_edges.append(edge.get('id'));continue
        if len(edges)>=6:omitted_edges.append(edge.get('id'));continue
        edges.append(edge)
        a,b=positions[edge['from']],positions[edge['to']];layer='40_edge_'+str(len(edges))
        semantic(layer,'edge',refs=edge.get('source_refs',[]),from_node=edge['from'],to_node=edge['to'],relation=edge['relation'],causal=False,accessible_label=edge.get('label',edge['relation']))
        if a[1]==b[1]:
            x1,y1=(a[0]+a[2],a[1]+61) if a[0]<b[0] else (a[0],a[1]+61);x2,y2=(b[0],b[1]+61) if a[0]<b[0] else (b[0]+b[2],b[1]+61)
            line(layer,x1,y1,x2,y2,MUTED)
        else:
            downward=a[1]<b[1];x1=a[0]+a[2]/2;y1=a[1]+a[3] if downward else a[1];x2=b[0]+b[2]/2;y2=b[1] if downward else b[1]+b[3]
            gutter=702 if downward else 4;via1=y1+4 if downward else y1-4;via2=y2-4 if downward else y2+4
            for start,end in (((x1,y1),(x1,via1)),((x1,via1),(gutter,via1)),((gutter,via1),(gutter,via2)),((gutter,via2),(x2,via2)),((x2,via2),(x2,y2))):line(layer,*start,*end,MUTED)
        dx,dy=x2-x1,y2-y1;length=max(1,math.hypot(dx,dy));ux,uy=dx/length,dy/length
        line(layer+'_arrow',x2,y2,x2-5*ux+3*uy,y2-5*uy-3*ux,MUTED);line(layer+'_arrow',x2,y2,x2-5*ux-3*uy,y2-5*uy+3*ux,MUTED)
    text('60_timeline_heading','時空間の突合',730,110,18,668,BLUE)
    grouped=[];groups={}
    for event in board.get('timeline',[]):
        node=by_id.get(event.get('node_id'))
        if not node:continue
        context=node.get('context_span',node['md_span']);key=(context.get('start'),context.get('end'))
        if key not in groups:groups[key]={'node':node,'events':[]};grouped.append(groups[key])
        groups[key]['events'].append(event)
    for index,group in enumerate(grouped[:3]):
        node=group['node'];events=group['events'];top=128+80*index;layer='62_timeline_'+str(index)
        expressed=list(dict.fromkeys(str(e.get('expressed_date')) for e in events if e.get('expressed_date') is not None));date_label='原文 '+ ' / '.join(expressed)
        normalised=list(dict.fromkeys(str(e.get('normalized_date')) for e in events if e.get('normalized_date') is not None))
        if normalised:date_label+=' | 正規化 '+' / '.join(normalised)
        semantic(layer,'timeline',node,node.get('source_refs',[]),event_ids=' '.join(str(e.get('id')) for e in events),node_id=node['id'])
        text(layer,date_label,730,top+13,11,668,MUTED)
        item=excerpt(node,654,13,2,90,'timeline')
        for j,value in enumerate(item['rendered_lines']):text(layer,value,738,top+33+16*j,item['font_size'],654)
        source_refs(layer,node.get('source_refs',[]),738,top+70,654)
    if not grouped:text('61_timeline_empty','MDに日付付き事象の記載なし',730,151,13,668,MUTED)
    text('70_next_heading','次の探索点',730,410,18,668,BLUE)
    next_nodes=[];next_contexts=set()
    for node_id in board.get('next_stations',[]):
        node=by_id.get(node_id)
        if not node:continue
        context=node.get('context_span',node['md_span']);key=(context.get('start'),context.get('end'))
        if key in next_contexts:continue
        next_contexts.add(key);next_nodes.append(node)
    for index,node in enumerate(next_nodes[:3]):
        x,top,layer=726,428+132*index,'72_station_'+str(index)
        rectangle(layer,x,top,676,124)
        semantic(layer,'next_station',node,node.get('source_refs',[]),node_id=node['id'],category=node.get('category'))
        text(layer,str(index+1)+' '+CATEGORY.get(node.get('category'),'探索の手掛かり'),738,top+17,11,652,BLUE)
        item=excerpt(node,652,13,3,90,'next_station')
        for j,value in enumerate(item['rendered_lines']):text(layer,value,738,top+39+16*j,item['font_size'],652)
        source_refs(layer,node.get('source_refs',[]),738,top+111,652)
    if not next_nodes:text('71_next_empty','次に確認する対象のMD記載なし',730,452,13,668,MUTED)
    for index,edge in enumerate(edges[:3]):
        label=str(numbers[edge['from']])+' → '+str(numbers[edge['to']])+' '+RELATION[edge['relation']]
        text('75_edge_legend',label,730,843+13*index,11,668,MUTED)
    partial='[部分投影: 全'+str(total)+'件中 上位'+str(len(chosen))+'件を表示 / 残余は正本MD収録]'
    if warnings:partial+=' | 注意 '+str(len(warnings))+'項目'
    text('79_partial',partial,16,886,11,1382,AMBER)
    for index,(field,label) in enumerate((('synthesis_node_ids','現在の見立て'),('unknown_node_ids','残る未知'),('branch_node_ids','分岐条件'))):
        node=next((by_id[value] for value in board.get('footer',{}).get(field,[]) if value in by_id),None);baseline=920+27*index
        text('80_footer',label,16,baseline,11,138,BLUE)
        if node:
            item=excerpt(node,1030,13,1,90,'footer');semantic('80_footer_'+str(index),'footer',node,node.get('source_refs',[]),node_id=node['id'])
            text('80_footer_'+str(index),item['rendered_lines'][0],160,baseline,item['font_size'],1030)
            source_refs('80_footer_'+str(index),node.get('source_refs',[]),1200,baseline,198)
        else:text('80_footer','該当するMD記載なし',160,baseline,13,1238,MUTED)
    raw=kernel._vendor_module().render_svg(model,(0,0,WIDTH,HEIGHT),width=WIDTH,height=HEIGHT,margin=0)
    svg=ET.fromstring(raw);svg.set('id','yamrail-silver-board');svg.set('role','group');svg.set('aria-label','調査Graph。資料・条件付き見立て・時空間・次の探索点。')
    for key,value in {'preserveAspectRatio':'xMidYMid meet','data-board-schema':board['schema'],'data-purpose':PURPOSE,'data-derivation':DERIVATION,'data-font-sha256':kernel.FONT_SHA256,'data-font-asset':kernel.FONT_URL,'font-family':kernel.FONT_FAMILY,'font-kerning':'none','font-variant-ligatures':'none'}.items():svg.set(key,value)
    svg.find('{'+NS+'}rect').set('fill','#ffffff')
    replaced=0
    for group in svg.findall('{'+NS+'}g'):
        layer=group.get('data-layer','');info=layers.get(layer)
        if info:
            group.set('data-board-kind',info['kind']);group.set('data-source-refs',' '.join(info['source_refs']))
            if info['source_refs']:
                group.set('tabindex','0');group.set('role','button');group.set('aria-label',normalise(info.get('accessible_label',''))[0]+'。出典 '+' '.join(info['source_refs']))
            for key,value in info.items():
                if key not in {'kind','source_refs','accessible_label'}:group.set('data-'+key.replace('_','-'),str(value))
        for element in group:
            if element.tag=='{'+NS+'}text':
                frozen=texts.get(element.text)
                if frozen is None:raise error('BOARD_TEXT_REPLACEMENT_IDENTITY')
                element.text=frozen['text'];element.set('font-family',kernel.FONT_FAMILY);element.set('font-size',str(frozen['size']));element.set('font-kerning','none');element.set('font-variant-ligatures','none');replaced+=1
            if element.tag=='{'+NS+'}polygon':element.set('fill-opacity','1')
            element.attrib.pop('vector-effect',None)
            if layer.startswith('40_edge_') and not layer.endswith('_arrow'):element.set('stroke-dasharray','4 3')
    if replaced!=len(texts):raise error('BOARD_TEXT_REPLACEMENT_IDENTITY')
    minimum=min((row['font_size'] for row in bounds),default=11)
    metadata={'schema':'yamrail.osint-silver-board-render/1','interface_spec_id':'OSINT_GRAPH_MINIMAL_VALIDATION_R034_REV3','binding':dict(binding),'board_sha256':_sha(_canonical(board)),
        'source_ledger_sha256':source_ledger['sha256'],'renderer_sha256':_sha(Path(kernel.__file__).read_bytes()),'presentation_renderer_sha256':_sha(Path(__file__).read_bytes()),
        'vendor_renderer_sha256':kernel.VENDOR_SHA256,'font_sha256':kernel.FONT_SHA256,'font_asset':kernel.FONT_URL,'font_family':kernel.FONT_FAMILY,'font_metrics_sha256':kernel.METRICS_SHA256,
        'logical_canvas':{'width':WIDTH,'height':HEIGHT},'physical_page_mm':[297,210],'uniform_fit_mm':[296.94,210],'side_margin_mm':0.03,
        'zones':{'header':[0,0,1414,86],'cards':[0,86,707,786],'timeline':[707,86,707,300],'next_stations':[707,390,707,440],'footer':[0,898,1414,102]},
        'text_lines':len(texts),'text_geometry':bounds,'primitive_count':len(model),'vendor_render_invocations':1,'text_reflow':True,'text_truncation':any(row['ellipsis'] for row in display_spans),'font_substitution':False,
        'solid_verified_relationship_edges':0,'authority_effect':'NONE','source_truth':'NOT_ESTABLISHED_BY_RENDERING','purpose':PURPOSE,'derivation':DERIVATION,
        'canonical_md_sha256':projection['analysis_sha256'],'model_output_sha256':projection['model_output_sha256'],'analysis_markdown_sha256':projection['analysis_sha256'],
        'md_semantics_sha256':_sha(_canonical(projection['md_semantics'])),'semantic_validation':projection['md_semantics']['validation_state'],'responsibility_scope':'OSINT_EXPLANATORY_PRESENTATION_ONLY_NOT_ENGINEERING_DELIVERABLE',
        'completeness_required':False,'deterministic_font_fit':False,
        'legibility':{'min_font_px':minimum,'body_font_px':13,'max_lines_per_card':3,'max_nodes_per_board':12,'text_clamping':True,'layout_policy':'DETERMINISTIC_GRID_WITH_CLAMPED_TEXT','overflow':False},
        'display_projection':{'total_nodes':total,'accepted_nodes':len(safe_nodes),'displayed_nodes':len(chosen),'remaining_nodes':remaining,'visible_node_ids':[n['id'] for n in chosen],
            'omitted_node_ids':[n['id'] for n in safe_nodes if n['id'] not in positions],'displayed_edge_ids':[edge.get('id') for edge in edges],'omitted_edge_ids':omitted_edges,'section_edges_as_category_badges':section_edges,
            'timeline_groups_total':len(grouped),'timeline_groups_displayed':min(3,len(grouped)),'next_stations_total':len(next_nodes),'next_stations_displayed':min(3,len(next_nodes))},
        'display_spans':display_spans,'warnings':warnings,'glyph_substitution_codepoints':['U+'+format(c,'04X') for c in sorted(glyph_codes)]}
    content=ET.SubElement(svg,'{'+NS+'}metadata');content.text=json.dumps({key:value for key,value in metadata.items() if key!='text_geometry'},ensure_ascii=True,sort_keys=True,separators=(',',':'),allow_nan=False)
    serialized=ET.tostring(svg,encoding='unicode',short_empty_elements=True)+'\n';metadata['svg_sha256']=_sha(serialized.encode('utf-8'))
    return {'svg':serialized,'metadata':metadata}
