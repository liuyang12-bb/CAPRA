"""Strict semantic equivalence. No profile rounding or approximate comparison."""
import gzip,json,hashlib
from pathlib import Path
from r3_utils import *
DROP={'version','method','scenario_id','candidate_seconds','mapping_scoring_seconds','generation_seconds','ram_repair_seconds','candidate_timings','gpu_stage_seconds','reference_seconds','commit_seconds','decision_seconds','smart_seconds','response_cache'}
def semantic(x):
    if isinstance(x,dict):return {k:semantic(v) for k,v in x.items() if k not in DROP}
    if isinstance(x,list):return [semantic(v) for v in x]
    return x
def control(a,b,destination):
    count=0;h=hashlib.sha256()
    import itertools
    with gzip.open(a/'events.jsonl.gz','rt',encoding='utf8') as fa,gzip.open(b/'events.jsonl.gz','rt',encoding='utf8') as fb:
        for i,(la,lb) in enumerate(itertools.zip_longest(fa,fb)):
            check_budget();assert la is not None and lb is not None,('ROUND_COUNT',i)
            xa=semantic(json.loads(la));xb=semantic(json.loads(lb));assert xa==xb,('SEMANTIC_CONTROL',i)
            h.update(json.dumps(xa,sort_keys=True,separators=(',',':')).encode());count+=1
    # CSV includes the complete per-job time ledger and progress, exact fields.
    assert (a/'per_job.csv').read_bytes()==(b/'per_job.csv').read_bytes(),'PER_JOB_CONTROL'
    result=dict(status='PASS',strict=True,rounds=count,semantic_sha256=h.hexdigest(),source_a=str(a.relative_to(ROOT)),source_b=str(b.relative_to(ROOT)),events_a_sha256=sha(a/'events.jsonl.gz'),events_b_sha256=sha(b/'events.jsonl.gz'),excluded_exact_keys=sorted(DROP))
    dump(destination,result);return result
if __name__=='__main__':
    control(RUN/'CAPRA_V2_SMART_R3/w2_dense_original/SIA-SMART-P',RUN/'CAPRA_V2_SMART_R3/w2_dense_cm/SIA-SMART-P',RUN/'smart_control_certificate.json')
