"""A revisit does not count as consecutive stagnation."""
from .binder import digest,need,text
REVISION='COMMON_CONSECUTIVE_STAGNATION_PRIMITIVE_R001_PRIVATE'
def signature(basis):
    need(isinstance(basis,dict) and text(basis.get('evidence_epoch')) and text(basis.get('progress_token')),'HOLD_PROGRESS_OBSERVATION_UNKNOWN')
    return digest(basis)
def consecutive(history,current):
    need(isinstance(history,list) and all(text(x) and len(x)==64 for x in history),'HOLD_STAGNATION_HISTORY_TYPE')
    count=1
    for previous in reversed(history):
        if previous!=current:break
        count+=1
    return count
def longest(signatures):
    count=best=0;previous=None
    for sig in signatures:
        count=count+1 if sig==previous else 1;previous=sig;best=max(best,count)
    return best
