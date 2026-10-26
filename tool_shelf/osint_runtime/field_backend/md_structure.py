"""Deterministic explanation of what an MD report actually says.

Categories describe the report's wording/sections, never independent fact truth.
All excerpts retain code-point offsets into immutable MD. Relationships describe
explicit conditions, section membership, or shared citation IDs, not inferred
real-world causality. Rendering may clamp these exact excerpts under REV3.
"""
import copy
from datetime import date
import re

SCHEMA='yamrail.osint-structured-md-graph/1'
CATEGORY_RULES=(
    ('UNKNOWN',('分からない','わからない','不明','未確認','未知','不確実')),
    ('HYPOTHESIS',('仮説','推測','見込','シナリオ')),
    ('NEXT',('次の探索','次に','探索点','測点','追加調査','調べる','調査課題','次の確認')),
    ('SYNTHESIS',('ひとことで','見立て','結論','総合評価','まとめ','総括')),
    ('KNOWN',('分かっている','わかっている','確認できた','既知','確認済','判明','事実')))
TOPIC_RULES=(
    ('INFRA',('インフラ','設備','発電','電力','送電','蓄電','系統','施設','港湾','工場')),
    ('LOGISTICS',('物流','輸送','補給','需給','在庫','燃料輸入','供給構造')),
    ('ECONOMY',('経済','需要','費用','金融','排出','GHG','CO2','価格','調達','財政')),
    ('CULTURE_LANG',('文化','言語','州紙','地域紙','報道','翻訳','世論')),
    ('RUMOR',('噂','風聞','非公式LEAD','うわさ')))
CONDITIONS=(('CONDITION','EXPLICIT_CONDITION','成立条件',('成立条件は','条件は','条件：','条件:')),
            ('SUPPORT','EXPLICIT_SUPPORT','支持する観測',('支持し得る観測は','支持する観測は','支持材料は')),
            ('COUNTEREVIDENCE','EXPLICIT_COUNTEREVIDENCE','弱める観測',('弱める観測は','反証となる観測は','反証条件は')))
POLARITY=re.compile('言い切れない|断定できない|ではない|していない|未確認|不明|仮に|ならば|なら|れば|可能性|条件|ない|得る|し得る')
ALIASES=re.compile(r'(?<![A-Za-z0-9_])[CW][0-9]+(?![A-Za-z0-9_])')
MAX_NODES=160


def span(start,end,line):return {'start':start,'end':end,'line':line}


def category_for(text,default='STATEMENT'):
    english={'known':'KNOWN','known facts':'KNOWN','unknown':'UNKNOWN','unknowns':'UNKNOWN',
             'hypothesis':'HYPOTHESIS','hypotheses':'HYPOTHESIS','next steps':'NEXT',
             'assessment':'SYNTHESIS','conclusion':'SYNTHESIS','conclusions':'SYNTHESIS'}
    normalized=text.strip().strip(':：').strip().casefold()
    if normalized in english:return english[normalized]
    for category,terms in CATEGORY_RULES:
        if any(term in text for term in terms):return category
    return default


def topic_for(text,heading):
    def matches(value):
        return [(domain,[term for term in terms if term in value]) for domain,terms in TOPIC_RULES
                if any(term in value for term in terms)]
    found=matches(heading);basis='EXPLICIT_HEADING'
    if not found:found=matches(text);basis='EXPLICIT_TERM'
    if not found:return {'domain':None,'basis':'UNCLASSIFIED','matched_text':[],'also_matched_domains':[]}
    return {'domain':found[0][0],'basis':basis,'matched_text':found[0][1],
            'also_matched_domains':[domain for domain,_ in found[1:]]}


def _sentences(text,start):
    # Sentence-ending punctuation is retained. No comma-level fragmentation can
    # silently detach a negation or conditional from its predicate.
    offset=0
    for match in re.finditer(r'.+?(?:[。！？](?:[」』）)])*|$)',text):
        raw=match.group();trimmed=raw.strip()
        if not trimmed:continue
        left=match.start()+len(raw)-len(raw.lstrip());right=match.end()-len(raw)+len(raw.rstrip())
        yield trimmed,start+left,start+right
        offset=match.end()


def build(analysis,ledger,binding,original_projection,source_binding):
    sources={row['id']:row for row in ledger['items']}
    nodes=[];edges=[];sections=[];timeline=[];omissions=[];offset=0
    current=None;line_nodes={};section_by_id={};all_lines=[];resource_omitted_count=0
    model_board=original_projection.get('board') if original_projection.get('state')=='MODEL_BOARD_CANDIDATE' else None
    model_node_reserve=sum(len(lane['nodes']) for lane in model_board.get('lanes',[])) if isinstance(model_board,dict) else 0
    md_node_limit=max(0,MAX_NODES-model_node_reserve)
    def edge(a,b,relation,label,evidence,refs=(),origin='MD_STRUCTURE'):
        identity=(a,b,relation)
        if any((e['from'],e['to'],e['relation'])==identity for e in edges):return
        edges.append({'id':'edge_'+str(len(edges)+1),'from':a,'to':b,'relation':relation,'label':label,
                      'md_span':copy.deepcopy(evidence),'source_refs':list(refs),'causal':False,'origin':origin})
    def add(text,start,end,line,context,category,section,refs,unbound,origin='MD_STRUCTURE',ident=None):
        nonlocal resource_omitted_count
        if len(nodes)>=MAX_NODES or origin=='MD_STRUCTURE' and len(nodes)>=md_node_limit:
            resource_omitted_count+=1
            if len(omissions)<32:
                omissions.append({'reason':'STRUCTURE_RESOURCE_BOUND','md_span':span(start,end,line)})
            return None
        ident=ident or 'md_'+str(start)+'_'+str(end)
        item={'id':ident,'text':text,'category':category,'section_id':section['id'] if section else None,
              'md_span':span(start,end,line),'context_span':copy.deepcopy(context),'source_refs':list(refs),
              'unbound_source_refs':list(unbound),'source_bindings':[source_binding(ref,sources[ref]) for ref in refs],
              'source_reference_scope':'ENCLOSING_PHYSICAL_MD_LINE','factual_verification':'NOT_PERFORMED',
              'topic':topic_for(text,section['title'] if section else ''),'origin':origin,
              'polarity_spans':[{'start':m.start(),'end':m.end(),'text':m.group()} for m in POLARITY.finditer(text)],
              'context_polarity_spans':[{'start':m.start(),'end':m.end(),'text':m.group()}
                   for m in POLARITY.finditer(analysis[context['start']:context['end']])]}
        nodes.append(item)
        if section:
            section['node_ids'].append(ident)
            edge(section['id'],ident,'SECTION_MEMBER','節に記載',section['md_span'])
        return item
    for number,raw_line in enumerate(analysis.splitlines(keepends=True),1):
        line=raw_line.rstrip('\r\n');all_lines.append((number,line,offset))
        heading=re.match(r'^\s*(#{1,6})\s+(.+?)\s*#*\s*$',line)
        if heading:
            title=heading.group(2);s=offset+heading.start(2);e=s+len(title)
            current={'id':'section_'+str(number),'title':title,'category':category_for(title),
                     'md_span':span(s,e,number),'level':len(heading.group(1)),'node_ids':[]}
            sections.append(current);section_by_id[current['id']]=current
            offset+=len(raw_line);continue
        if not line.strip() or re.match(r'^\s*(?:```|~~~|\|?\s*:?-{3,})',line):
            offset+=len(raw_line);continue
        prefix=re.match(r'^\s*(?:[-*+]\s+|\d+[.)]\s+)?',line).end()
        text=line[prefix:].strip();start=offset+prefix+len(line[prefix:])-len(line[prefix:].lstrip())
        if not text:offset+=len(raw_line);continue
        aliases=list(dict.fromkeys(ALIASES.findall(line)));refs=[a for a in aliases if a in sources];unbound=[a for a in aliases if a not in sources]
        context=span(offset,offset+len(line),number)
        base_category=current['category'] if current else 'STATEMENT'
        if base_category=='STATEMENT':
            leading=re.match(r'^(?:既知|不明|仮説|次|価値|結論|見立て)[：:]',text)
            if leading:base_category=category_for(leading.group(), 'NEXT' if text.startswith('次') else 'SYNTHESIS' if text.startswith('価値') else 'STATEMENT')
        hypothesis=None
        for sentence,s,e in _sentences(text,start):
            category=base_category;relation=None;label=None
            for kind,rel,lab,phrases in CONDITIONS:
                if any(sentence.startswith(phrase) for phrase in phrases):category,relation,label=kind,rel,lab;break
            item=add(sentence,s,e,number,context,category,current,refs,unbound)
            if not item:continue
            line_nodes.setdefault(number,[]).append(item)
            if category=='HYPOTHESIS' and hypothesis is None:hypothesis=item
            if relation and hypothesis:
                edge(item['id'],hypothesis['id'],relation,label,context,refs)
        offset+=len(raw_line)
    # All accepted model-Graph items survive as a distinct origin, including
    # items not selected for visible Top-N. They are never relabelled facts.
    model_map={}
    board=model_board
    if isinstance(board,dict) and isinstance(board.get('lanes'),list):
        for lane in board['lanes']:
            for model in lane['nodes']:
                quote=''.join(model['lines'])
                index=analysis.find(quote)
                if index<0:continue
                number=analysis.count('\n',0,index)+1
                row=next(((n,t,o) for n,t,o in all_lines if n==number),None)
                context=span(row[2],row[2]+len(row[1]),number) if row else span(index,index+len(quote),number)
                section=next((s for s in reversed(sections) if s['md_span']['start']<=index),None)
                category=section['category'] if section else 'STATEMENT'
                if model['kind']=='CONDITIONAL_HYPOTHESIS':category='HYPOTHESIS'
                elif model['kind']=='LEAD':category='NEXT'
                elif model['kind']=='UNKNOWN':category='UNKNOWN'
                item=add(quote,index,index+len(quote),number,context,category,section,model['source_refs'],[],
                         origin='MODEL_GRAPH',ident='model_'+model['id'])
                if item:model_map[model['id']]=item['id']
        for lane in board['lanes']:
            for original in lane['edges']:
                if original['from'] in model_map and original['to'] in model_map:
                    evidence=original_projection.get('md_semantics',{}).get('edges',[])
                    matching=next((x for x in evidence if x['from']==original['from'] and x['to']==original['to'] and x['relation']==original['relation']),None)
                    quote=matching['md_quote'] if matching else ''
                    index=analysis.find(quote) if quote else -1
                    if index>=0:
                        edge(model_map[original['from']],model_map[original['to']],original['relation'],original['relation'],
                             span(index,index+len(quote),analysis.count('\n',0,index)+1),original['support_refs'],'MODEL_GRAPH')
    # Shared citation IDs show document lineage only, not causal support or
    # independent corroboration. A sparse chain avoids an invented clique.
    previous={}
    for item in nodes:
        for alias in item['source_refs']:
            if alias in previous and previous[alias]!=item['id']:
                edge(previous[alias],item['id'],'SAME_SOURCE_REFERENCE','同じ出典ID '+alias,
                     item['context_span'],[alias])
            previous[alias]=item['id']
    # Dates retain exact spelling and granularity; years are not fabricated into
    # complete dates, nor assumed to be event rather than publication dates.
    date_pattern=re.compile(r'(?<!\d)(?:20\d{2}[-/]\d{1,2}[-/]\d{1,2}|20\d{2}年\d{1,2}月\d{1,2}日|20\d{2}年\d{1,2}月|20\d{2}年)(?!\d)')
    seen_dates=set()
    for item in nodes:
        for match in date_pattern.finditer(item['text']):
            expressed=match.group();identity=(expressed,item['md_span']['line'])
            if identity in seen_dates:continue
            seen_dates.add(identity);numbers=list(map(int,re.findall(r'\d+',expressed)));normalized=None
            if len(numbers)==3:
                try:normalized=date(*numbers).isoformat()
                except ValueError:pass
            local=item['text'];kind='PUBLICATION' if any(x in local for x in ('公表日','公開日','発表日')) else 'EVENT' if '観測日' in local else 'UNKNOWN'
            timeline.append({'id':'date_'+str(len(timeline)+1),'node_id':item['id'],'text':item['text'],
                'expressed_date':expressed,'normalized_date':normalized,'granularity':('DAY' if len(numbers)==3 else 'MONTH' if len(numbers)==2 else 'YEAR'),
                'time_kind':kind,'source_refs':list(item['source_refs']),
                'md_span':span(item['md_span']['start']+match.start(),item['md_span']['start']+match.end(),item['md_span']['line'])})
    timeline.sort(key=lambda item:({'DAY':0,'MONTH':1,'YEAR':2}[item['granularity']],item['md_span']['start']))
    degree={n['id']:0 for n in nodes}
    for e in edges:
        if e['relation'] not in ('SECTION_MEMBER','SAME_SOURCE_REFERENCE'):
            for endpoint in (e['from'],e['to']):
                if endpoint in degree:degree[endpoint]+=1
    dated={x['node_id'] for x in timeline};buckets={}
    for item in nodes:
        section=section_by_id.get(item['section_id'],{})
        siblings=line_nodes.get(item['md_span']['line'],[])
        anchor=(not siblings or item['origin']=='MODEL_GRAPH' or siblings[0]['id']==item['id'])
        item['selection_features']={'dependency_degree':degree[item['id']],'dated':item['id'] in dated,
                                    'section_level':section.get('level',0),'source_reference_count':len(item['source_refs']),
                                    'paragraph_anchor':anchor,
                                    'quantified_statement':bool(re.search(r'\d+(?:\.\d+)?\s*(?:%|％|GW|MW|km|キロ|億|万人|件|倍)',item['text']))}
        buckets.setdefault(item['category'],[]).append(item)
    for values in buckets.values():
        values.sort(key=lambda n:(-n['selection_features']['section_level'],-int(n['selection_features']['paragraph_anchor']),
                                  -int(n['selection_features']['quantified_statement']),-n['selection_features']['dependency_degree'],
                                  -int(n['selection_features']['dated']),n['md_span']['start']))
    order=[];categories=('KNOWN','HYPOTHESIS','UNKNOWN','CONDITION','SUPPORT','COUNTEREVIDENCE','NEXT','SYNTHESIS')
    while any(buckets.get(category) for category in categories):
        for category in categories:
            if buckets.get(category):order.append(buckets[category].pop(0)['id'])
    order.extend(node['id'] for node in buckets.get('STATEMENT',[]))
    def category_ids(categories):
        return [n['id'] for n in sorted(nodes,key=lambda n:(-section_by_id.get(n['section_id'],{}).get('level',0),n['md_span']['start']))
                if n['category'] in categories]
    return {'schema':SCHEMA,'purpose':'EXPLANATORY_PONCHI_DIAGRAM','offset_unit':'UNICODE_CODE_POINTS',
            'sections':sections,'nodes':nodes,'edges':edges,'timeline':timeline,
            'next_stations':category_ids(('NEXT',)),
            'footer':{'synthesis_node_ids':category_ids(('SYNTHESIS',)),
                      'unknown_node_ids':category_ids(('UNKNOWN',)),
                      'branch_node_ids':category_ids(('CONDITION','COUNTEREVIDENCE'))},
            'display_order':order,'selection':{'maximum_visible_nodes':12,'policy':'CONTENT_CATEGORY_COVERAGE_THEN_PARAGRAPH_ANCHOR_QUANTIFIED_STATEMENT_EXPLICIT_CONNECTIVITY_DATE_MD_ORDER',
                'total_nodes':len(nodes),'accepted_nodes':len(nodes),'resource_omitted_count':resource_omitted_count,
                'total_candidates':len(nodes)+resource_omitted_count,
                'omission_span_details_complete':resource_omitted_count<=len(omissions),
                'model_node_reserved_capacity':model_node_reserve,
                'top_node_ids':order[:12],'value_features_preserved_not_aggregated':True},'omissions':omissions}


def validate_structure(board,ledger):
    if not isinstance(board,dict) or board.get('schema')!=SCHEMA or board.get('purpose')!='EXPLANATORY_PONCHI_DIAGRAM':
        raise ValueError('STRUCTURED_MD_GRAPH_INVALID')
    nodes=board.get('nodes');sections=board.get('sections');edges=board.get('edges')
    if not isinstance(nodes,list) or len(nodes)>MAX_NODES or not isinstance(sections,list) or not isinstance(edges,list):
        raise ValueError('STRUCTURED_MD_GRAPH_RESOURCE_BOUND')
    node_ids={n['id'] for n in nodes};section_ids={s['id'] for s in sections};sources={row['id'] for row in ledger['items']}
    if len(node_ids)!=len(nodes) or len(section_ids)!=len(sections):raise ValueError('STRUCTURED_MD_GRAPH_DUPLICATE_ID')
    for n in nodes:
        if (not isinstance(n.get('text'),str) or not n['text'] or any(ref not in sources for ref in n.get('source_refs',[]))
                or n.get('factual_verification')!='NOT_PERFORMED'):
            raise ValueError('STRUCTURED_MD_GRAPH_NODE_BINDING')
    for e in edges:
        if e['from'] not in node_ids|section_ids or e['to'] not in node_ids or e.get('causal') is not False:
            raise ValueError('STRUCTURED_MD_GRAPH_EDGE_BINDING')
    return True
