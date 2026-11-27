"""Post-smoke audit rejection tests on copies only; never mutate source evidence."""
import shutil,json,gzip
from r4_utils import *
from capra.audit_r4 import audit
def main():
    source=DEV/'smoke_01';results=[]
    for kind in ('wrong_engine','nonproportional','missing_repair','wrong_gpu_plan'):
        check_budget();d=DEV/'audit_rejection'/kind;assert not d.exists();shutil.copytree(source,d)
        s=load(d/'start.json')
        with gzip.open(d/'events.jsonl.gz','rt',encoding='utf8') as f:rows=[json.loads(x) for x in f]
        r=next(x for x in rows if x['plan']);k=next(iter(r['plan']))
        if kind=='wrong_engine':s['placement_engine']='sia_fast_original';dump(d/'start.json',s)
        if kind=='nonproportional':r['selection']['candidates'][0]['allocations'][k]['cpu']+=0.01
        if kind=='missing_repair':
            # Declare repaired output with no record/witness, independent check must reject.
            r['lock_repaired_gpu_plan'][k]['node']='invalid-node'
        if kind=='wrong_gpu_plan':r['gpu_stage']['smart_records'][0]['gpu_allocations'][next(iter(r['gpu_stage']['smart_records'][0]['gpu_allocations']))]['gpus']+=1
        with gzip.open(d/'events.jsonl.gz','wt',encoding='utf8') as f:
            for x in rows:f.write(json.dumps(x)+'\n')
        seals=load(d/'output_hashes.json')
        for name in seals:seals[name]=sha(d/name)
        dump(d/'output_hashes.json',seals)
        try:audit(d)
        except (AssertionError,KeyError) as e:results.append(dict(case=kind,status='REJECTED',error=repr(e)))
        else:raise AssertionError(('INVALID_AUDIT_ACCEPTED',kind))
    dump(DEV/'audit_rejection_receipt.json',dict(status='PASS',cases=results));print('R4_AUDIT_REJECTIONS_PASS')
if __name__=='__main__':main()
