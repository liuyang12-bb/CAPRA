"""Two closed-loop controls against archived R3 smokes, never rerun R3."""
import gzip,json,hashlib,itertools
from r4_utils import *
from equivalence_r3 import DROP
def semantic(x):
    if isinstance(x,dict):return {k:semantic(v) for k,v in x.items() if k not in DROP and not k.startswith('r4_')}
    if isinstance(x,list):return [semantic(v) for v in x]
    return x
def main():
    results=[]
    for i in (1,2):
        a=ROOT/f'runs/smart_holdout_r3/development/smoke_{i:02d}';b=DEV/f'smoke_{i:02d}';h=hashlib.sha256();count=0
        with gzip.open(a/'events.jsonl.gz','rt',encoding='utf8') as fa,gzip.open(b/'events.jsonl.gz','rt',encoding='utf8') as fb:
            for count,(la,lb) in enumerate(itertools.zip_longest(fa,fb),1):
                check_budget();assert la and lb
                x,y=semantic(json.loads(la)),semantic(json.loads(lb));assert x==y,('R3_R4_CLOSED_LOOP_CHANGED',i,count)
                h.update(json.dumps(x,sort_keys=True,separators=(',',':')).encode())
        assert (a/'per_job.csv').read_bytes()==(b/'per_job.csv').read_bytes()
        results.append(dict(smoke=i,status='PASS',rounds=count,strict_semantic_sha256=h.hexdigest(),R3_events_sha256=sha(a/'events.jsonl.gz'),R4_events_sha256=sha(b/'events.jsonl.gz'),job_step_new_calls=0))
    dump(DEV/'closed_loop_control.json',dict(status='PASS',controls=results,excluded_exact_keys=sorted(DROP),additional_exclusion='r4_ read-only timing fields'))
    print('R4_CLOSED_LOOP_CONTROL_PASS')
if __name__=='__main__':main()
