"""Small pinned CPU prose inspection. Input bytes and meaning are never changed."""
from __future__ import annotations
import bisect,hashlib,json,pathlib,re

PACK_PATH=pathlib.Path(__file__).with_name('document_guard_rules_r001.json')
PACK_BYTES=PACK_PATH.read_bytes()
RULE_REVISION=hashlib.sha256(PACK_BYTES).hexdigest()
ENGINE_REVISION=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest()
PACK=json.loads(PACK_BYTES)
FAMILIES=tuple(PACK['families'])
MAX_DOCUMENT_BYTES=131072
MAX_FINDINGS=256
_CONTEXT={'language','document_type','reader','intended_reader','destination','recipient','medium',
          'proper_names','protected_spans','exceptions','recipient_rules','applicable_standard_revision','document_revision'}

def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def digest(raw):return hashlib.sha256(raw).hexdigest()

def context_profile(context,document):
    if not isinstance(context,dict) or set(context)-_CONTEXT:raise ValueError('DOCUMENT_CONTEXT_INVALID')
    result={'language':context.get('language','ja'),'document_type':context.get('document_type','GENERAL'),
            'reader':context.get('reader',context.get('intended_reader','UNSPECIFIED')),
            'destination':context.get('destination',context.get('recipient','UNSPECIFIED')),
            'medium':context.get('medium','HORIZONTAL'),
            'applicable_standard_revision':context.get('applicable_standard_revision',RULE_REVISION)}
    # A locale alias selects the same pinned Japanese rules, never new rules.
    if result['language']=='ja-JP':result['language']='ja'
    for key in ('language','document_type','reader','destination','medium','applicable_standard_revision'):
        if not isinstance(result[key],str) or not 1<=len(result[key])<=256:raise ValueError('DOCUMENT_CONTEXT_INVALID')
    for key in ('proper_names','recipient_rules'):
        values=context.get(key,[])
        if not isinstance(values,list) or len(values)>64 or any(not isinstance(x,str) or not 1<=len(x)<=256 for x in values):raise ValueError('DOCUMENT_CONTEXT_INVALID')
        result[key]=sorted(set(values))
    for key in ('protected_spans','exceptions'):
        values=context.get(key,[])
        if not isinstance(values,list) or len(values)>128:raise ValueError('DOCUMENT_CONTEXT_INVALID')
        result[key]=[]
        for value in values:
            allowed={'start','end','reason'}|({'rule_id'} if key=='exceptions' else set())
            if (not isinstance(value,dict) or set(value)!=allowed or type(value['start']) is not int or type(value['end']) is not int
                    or not 0<=value['start']<value['end']<=len(document) or not isinstance(value['reason'],str)
                    or not 1<=len(value['reason'])<=512 or ('rule_id' in value and not isinstance(value['rule_id'],str))):raise ValueError('DOCUMENT_EXCEPTION_INVALID')
            result[key].append(dict(value))
        result[key].sort(key=lambda x:(x['start'],x['end'],x.get('rule_id',''),x['reason']))
    return result

def protected_ranges(document,profile):
    ranges=[dict(x) for x in profile['protected_spans']]
    # Quotes/code/URLs/source references are data, not generated prose to repair.
    patterns=[(r'```[\s\S]*?(?:```|\Z)|~~~[\s\S]*?(?:~~~|\Z)','CODE_BLOCK'),
              (r'`[^`\n]*`','INLINE_CODE'),(r'(?m)^\s*>[^\n]*(?:\n|$)','SOURCE_BLOCKQUOTE'),
              (r'(?m)^資料\s*[0-9]+\s*の記載：[^\n]*','SOURCE_EXCERPT'),
              (r'https?://[^\s<>\u3000]+','URL'),(r'\[[^\]\n]*\]\([^\n)]*\)','EVIDENCE_LINK'),
              (r'\b[0-9a-fA-F]{32,64}\b|\b[A-Z][A-Z0-9_-]{2,}\b','IDENTIFIER'),
              (r'"[^"\n]*"','QUOTED_MATERIAL')]
    for pattern,reason in patterns:
        ranges.extend({'start':m.start(),'end':m.end(),'reason':reason} for m in re.finditer(pattern,document))
    for name in profile['proper_names']:
        ranges.extend({'start':m.start(),'end':m.end(),'reason':'DECLARED_PROPER_NAME'} for m in re.finditer(re.escape(name),document))
    # A single pass also protects an unmatched opening quote through EOF.
    stack=[];pairs={'「':'」','『':'』'}
    for i,char in enumerate(document):
        if char in pairs:stack.append((char,i))
        elif stack and char==pairs[stack[-1][0]]:
            _,start=stack.pop();ranges.append({'start':start,'end':i+1,'reason':'QUOTED_MATERIAL'})
    for _,start in stack:ranges.append({'start':start,'end':len(document),'reason':'UNTERMINATED_QUOTED_MATERIAL'})
    return sorted(ranges,key=lambda x:(x['start'],x['end'],x['reason']))

def inspect_document(document,context,rule_revision=None):
    if not isinstance(document,str):raise ValueError('DOCUMENT_UTF8_REQUIRED')
    try:raw=document.encode('utf-8','strict')
    except UnicodeError:raise ValueError('DOCUMENT_UTF8_REQUIRED') from None
    if not 1<=len(raw)<=MAX_DOCUMENT_BYTES:raise ValueError('DOCUMENT_SIZE')
    if rule_revision is not None and rule_revision!=RULE_REVISION:raise ValueError('DOCUMENT_RULE_REVISION_UNSUPPORTED')
    profile=context_profile(context,document);revision=context.get('document_revision',digest(raw))
    if not isinstance(revision,str) or re.fullmatch('[0-9a-f]{64}',revision) is None:raise ValueError('DOCUMENT_REVISION_INVALID')
    applicable=(profile['language']=='ja' and profile['document_type'] in {'GENERAL','OFFICIAL'}
                and profile['medium'] in {'HORIZONTAL','VERTICAL'} and profile['applicable_standard_revision']==RULE_REVISION)
    result={'schema':'yamrail.document-inspection/1','rule_revision':RULE_REVISION,'engine_revision':ENGINE_REVISION,'document_revision':revision,
            'span_convention':'ZERO_BASED_HALF_OPEN_UNICODE_CODEPOINTS_AND_UTF8_BYTES_NO_NORMALIZATION',
            'document_sha256':digest(raw),'document_bytes':len(raw),'applicability':profile,
            'precedence':PACK['precedence'],'findings':[],'coverage':[],
            'authority_effect':'NONE','external_api_calls':0,'document_mutation':'NONE'}
    if not applicable:
        result.update(status='NOT_APPLICABLE',coverage=[{'family':f,'status':'NOT_APPLICABLE','limits':'UNSUPPORTED_LANGUAGE_PROFILE_OR_STANDARD'} for f in FAMILIES])
        return result
    protections=protected_ranges(document,profile);findings=result['findings'];truncated=False
    merged=[]
    for x in protections:
        if merged and x['start']<=merged[-1][1]:merged[-1][1]=max(merged[-1][1],x['end'])
        else:merged.append([x['start'],x['end']])
    starts=[x[0] for x in merged]
    def protected(a,b):
        i=bisect.bisect_left(starts,b)-1
        return i>=0 and merged[i][1]>a
    def emit(family,rule,a,b,verdict,expected,*,allow_identifier=False):
        nonlocal truncated
        if a>=b:return
        if protected(a,b) and not allow_identifier:return
        if len(findings)>=MAX_FINDINGS:truncated=True;return
        source=PACK['families'][family]
        exceptions=[x for x in profile['exceptions'] if x['rule_id']==rule and x['start']==a and x['end']==b]
        finding={'rule_id':rule,'family':family,'rule_revision':RULE_REVISION,'source_revision':revision,'document_revision':revision,
                 'source_clause':{'document':PACK['official_source']['title'],'sha256':PACK['official_source']['sha256'],
                                  'section':source['section'],'pages':source['pages'],'printed_pages':source['printed_pages']},
                 'span':{'start':a,'end':b,'utf8_start':len(document[:a].encode('utf-8')),'utf8_end':len(document[:b].encode('utf-8'))},
                 'observed':document[a:b],'expected':expected,'applicability':{k:profile[k] for k in ('language','document_type','reader','destination','medium')},
                 'verdict':'NOT_APPLICABLE' if exceptions else verdict,'exceptions':exceptions}
        if profile['recipient_rules'] and not exceptions:
            finding['verdict']='REVIEW';finding['precedence_review']='RECIPIENT_REQUIREMENTS_NOT_MACHINE_INTERPRETED'
        finding['finding_id']=digest(canonical(finding));findings.append(finding)
    for family in ('CHARACTER_USAGE','OKURIGANA','AUXILIARY_VERB_NOTATION'):
        if family=='OKURIGANA' and profile['document_type']=='GENERAL':continue
        for observed,expected in PACK['families'][family]['pairs'].items():
            for m in re.finditer(re.escape(observed),document):
                emit(family,{'CHARACTER_USAGE':'CHAR_PRINTED_EXAMPLE','OKURIGANA':'OKURI_NOUN_READER','AUXILIARY_VERB_NOTATION':'AUXILIARY_OR_ACTION_UNKNOWN'}[family],m.start(),m.end(),
                     'UNKNOWN' if family=='AUXILIARY_VERB_NOTATION' else 'REVIEW',expected+'（原意・用法・例外を確認。自動置換しない）')
    commas=[m for m in re.finditer('[、，]',document) if not protected(m.start(),m.end())]
    if {m.group() for m in commas}=={'、','，'}:
        for m in commas:emit('PUNCTUATION_CONSISTENCY','PUNCT_MIXED_COMMA',m.start(),m.end(),'VIOLATION','同じ本文内の読点表記を統一する。横書きの「，」単独は許容。')
    if profile['medium']=='HORIZONTAL':
        for m in re.finditer(r'[一二三四五六七八九十百千]+(?:件|円|個|台|回)',document):
            before=document[max(0,m.start()-1):m.start()]
            if before in {'数','約','余'}:continue
            emit('NUMERAL_NOTATION','NUMERAL_HORIZONTAL_CANDIDATE',m.start(),m.end(),'REVIEW','横書きの算用数字原則と概数・成語・名称の例外を照合。数値は保持する。')
        digits=[m for m in re.finditer('[0-9０-９]+',document) if not protected(m.start(),m.end())]
        if any(re.search('[0-9]',m.group()) for m in digits) and any(re.search('[０-９]',m.group()) for m in digits):
            for m in digits:emit('NUMERAL_NOTATION','NUMERAL_WIDTH_CONTEXT',m.start(),m.end(),'REVIEW','全角・半角の使い分けの統一を確認。値・単位は保持する。')
    for term in PACK['families']['TERMINOLOGY_CONSISTENCY']['terms']:
        for m in re.finditer(r'(?<![A-Za-z0-9_])'+term+r'(?![A-Za-z0-9_])',document):
            if any(m.start()<x['end'] and m.end()>x['start'] and x['reason']!='IDENTIFIER' for x in protections):continue
            if not re.match(r'\s*[（(][^）)]+[）)]',document[m.end():m.end()+200]):
                # Acronyms are preserved; this is an explanation review, not a spelling repair.
                emit('TERMINOLOGY_CONSISTENCY','TERM_FIRST_EXPLANATION',m.start(),m.end(),'REVIEW','想定読者に初出の説明が必要か確認。正式名称・識別子は保持する。',allow_identifier=True)
            break
    if profile['document_type']=='OFFICIAL' and not re.match(r'\s*(?:#{1,6}\s+|【)',document):
        end=next((i for i,c in enumerate(document) if c=='\n'),len(document))
        emit('DOCUMENT_STRUCTURE','STRUCTURE_TITLE_REVIEW',0,min(end,160),'REVIEW','標題で主題・文書の性格が分かるか確認。Markdown見出しの欠如だけで違反にしない。')
    for m in re.finditer('ないわけではない',document):emit('DOCUMENT_STRUCTURE','STRUCTURE_DOUBLE_NEGATION',m.start(),m.end(),'REVIEW','強調・法的効果・原意を維持したまま、二重否定の必要性を確認。')
    for m in re.finditer(r'(?m)^#{1,6}\s+[^\n]+\n[ \t]*(?=\n#{1,6}\s|\Z)',document):
        emit('DOCUMENT_STRUCTURE','STRUCTURE_EMPTY_HEADING',m.start(),m.end(),'REVIEW','見出しに対応する本文の有無を確認。')
    findings.sort(key=lambda x:(x['span']['start'],x['span']['end'],x['rule_id']))
    result['coverage']=[{'family':f,'status':('UNKNOWN' if f=='CHARACTER_USAGE' else 'REVIEW' if f in {'OKURIGANA','AUXILIARY_VERB_NOTATION','TERMINOLOGY_CONSISTENCY','DOCUMENT_STRUCTURE'} else 'CHECKED'),
                         'limits':PACK['families'][f]['limits']} for f in FAMILIES]
    result['protected_spans']=[{'start':a,'end':b,'reason':'SOURCE_OR_DECLARED_PROTECTION'} for a,b in merged[:256]]
    result['protected_range_count']=len(merged)
    if len(merged)>256:result['protection_display_truncated']=True
    if truncated:result['finding_limit_reached']=True
    result['status']=('UNKNOWN' if truncated else 'FINDINGS' if any(x['verdict']=='VIOLATION' for x in findings) else
                      'UNKNOWN' if any(x['verdict']=='UNKNOWN' for x in findings) else 'REVIEW' if any(x['verdict']=='REVIEW' for x in findings) else 'NO_FINDINGS_IN_BOUNDED_RULES')
    return result

def inspect_bytes(document,context,rule_revision=None):return canonical(inspect_document(document,context,rule_revision))
