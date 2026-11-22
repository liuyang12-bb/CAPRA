"""Bounded preparation; no formal cells and no mutation of legacy evidence."""
from pathlib import Path
from datetime import datetime,timezone
import csv,gzip,hashlib,json,shutil,subprocess,sys,time
from scenario_control import Owned,env,execute
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'runs/scenarios_r1/development'
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def main():
    ledger=ROOT/'runs/scenarios_r1/budget_ledger.json';budget=json.loads(ledger.read_text());deadline=budget['deadline_monotonic']
    def record(kind,receipt):
        budget['entries'].append(dict(kind=kind,**receipt));budget['elapsed_seconds']=time.perf_counter()-budget['start_monotonic'];dump(ledger,budget)
    # Real launcher + real grandchild: prove descendants are contained before experiments.
    with (D/'owned_tree_test.log').open('w') as log:
        child_code="import subprocess,sys,time; subprocess.Popen([sys.executable,'-c','import time; time.sleep(300)']); print('TREE_READY',flush=True); time.sleep(300)"
        job=Owned([sys.executable,'-u','-c',child_code],log,env())
        began=time.perf_counter()
        while 'TREE_READY' not in (D/'owned_tree_test.log').read_text() and time.perf_counter()-began<40:time.sleep(.1)
        active=job.active();receipt=job.close()
    assert active>=2 and receipt['active_after_cleanup']==0
    record('owned_tree_validation',dict(wall_seconds=time.perf_counter()-began,descendants_observed=active,**receipt))
    # Replay original six in copies only: preserve all original outputs byte-for-byte.
    from capra.audit_v2 import audit
    original_results=[]
    expected=[[1056.1125,971.025,949.4625],[1056.55,973.725,911.475]]
    for wi,w in enumerate((2,6)):
        for mi,method in enumerate(('SIA-P','CAPRA-Fixed','CAPRA')):
            src=ROOT/f'runs/capra_v2/CAPRA_V2_R1/saturn-{w}-supported80'/method
            dst=D/f'prior_replay/w{w}'/method
            assert not dst.exists();shutil.copytree(src,dst)
            began=time.perf_counter();s=audit(dst)
            assert s['completed']==80 and abs(s['mean_jct']-expected[wi][mi])<1e-7
            # Independently inspect actual active F/K/R and training application shares.
            from collections import Counter
            selected=Counter();train=Counter()
            apps={r['name']:r['application'] for r in csv.DictReader((ROOT/f'data/saturn-{w}-supported80.csv').open(encoding='utf8'))}
            with gzip.open(src/'events.jsonl.gz','rt',encoding='utf8') as f:
                for line in f:
                    r=json.loads(line)
                    if r['plan']:selected[r['selection']['selected']]+=1
                    for e in r['executions']:train[apps[e['job']]]+=e['training']
            original_results.append(dict(workload=w,method=method,mean_jct=s['mean_jct'],p95_jct=s['p95_jct'],p99_jct=s['p99_jct'],active_selected=dict(selected),training_share={k:v/sum(train.values()) for k,v in train.items()},raw_audit=s['v2_raw_audit']))
            record('legacy_raw_replay',dict(workload=w,method=method,wall_seconds=time.perf_counter()-began,status='PASS'))
    dump(D/'original_v2_rechecked.json',original_results)
    # Explicit CPU2 + synthetic CM together, then CPU6 + CM; all apps in first20.
    for cpu in (2,6):
        dst=D/f'pilot_cpu{cpu}_cm'
        cmd=[sys.executable,'-X','utf8','-B','-m','capra.runner_v2','--input','data/scenarios_r1/w2_dense.csv','--cluster',f'data/scenarios_r1/cluster_cpu{cpu}.json','--responses','data/scenarios_r1/responses_cm.json','--scenario-id',f'pilot_cpu{cpu}_cm','--run-version','CAPRA_V2_SCENARIOS_R1_PREP','--method','CAPRA','--output',str(dst),'--max-jobs','20','--max-rounds','60','--wall-limit','150']
        receipt=execute(cmd,D/f'pilot_cpu{cpu}_cm.stdout.log',210,deadline-30);record('preparatory_pilot',receipt)
        assert receipt['exit_code']==0
        dump(dst/'process.json',receipt);s=audit(dst)
        assert s['total']==20 and s['v2_raw_audit']=='PASS'
        start=json.loads((dst/'start.json').read_text());assert start['inputs']['cluster']['relative'].endswith(f'cpu{cpu}.json') and start['inputs']['responses']['relative'].endswith('responses_cm.json')
        # Relative replay actually passes with an invalid original machine path.
        relocated=D/f'relocated_cpu{cpu}'
        shutil.copytree(dst,relocated)
        start=json.loads((relocated/'start.json').read_text())
        for x in start['inputs'].values():x['absolute']='Z:/unavailable-old-machine/'+Path(x['relative']).name
        dump(relocated/'start.json',start)
        seals=json.loads((relocated/'output_hashes.json').read_text());seals['start.json']=hashlib.sha256((relocated/'start.json').read_bytes()).hexdigest();dump(relocated/'output_hashes.json',seals)
        assert audit(relocated)['v2_raw_audit']=='PASS'
        record('relocated_raw_replay',dict(workload=f'cpu{cpu}_cm',wall_seconds=0,status='PASS',note='Time covered by monotonic total, not subtracted as zero cost'))
    # Static certificates separate from dynamic evidence.
    from capra.response import Responses
    from capra.response_v2 import V2Responses
    from capra.contracts import Node,JobGpuPlan
    from capra.node_allocator import NodeAllocator
    r=V2Responses(ROOT/'data/scenarios_r1/responses_cm.json');n=Node('rtx:0','rtx',8,24,500)
    p={k:JobGpuPlan(k,'rtx',4,n.id,1,0) for k in ('C','M')};a=NodeAllocator(p,[n],{'C':'cifar10','M':'deepspeech2'},r,{},{});base=a.baseline(n,p);sol,meta=a.solve(n.id,p)
    dump(D/'static_certificates.json',dict(three_job=dict(gpus=[4,2,2],cpu=[20,2,2],ram=[83.32,375,41.66],rho=[1.53,2.4,1],totals=[8,24,499.98]),
        two_job=dict(actual={k:vars(v) for k,v in sol.items()},candidate_ram_M=sorted({x.ram for x in a.pairs('M',n,base)}),
            continuous_M_ram=416.68,continuous_M_rho=r.rho('deepspeech2',4,4,416.68),note='Static candidate omission; dynamic occurrence must be checked separately')))
    dump(D/'validation_receipt.json',dict(status='PASS',original_six_rechecked=True,custom_inputs_replayed=True,relative_replay=True,owned_tree_proved=True,algorithms_unchanged=True))
    print('PREPARATION_PASS',flush=True)
if __name__=='__main__':main()
