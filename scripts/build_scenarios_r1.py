"""Deterministic preregistered scenarios; refuse differing existing bytes."""
from pathlib import Path
from decimal import Decimal
import argparse, copy, csv, hashlib, io, json

ROOT=Path(__file__).resolve().parents[1]
BASE='0b87934ae558960921889b01d14502155fb0c41c'
SOURCE_HASHES={
 'data/saturn-2-supported80.csv':'25ed84bc64109a555f241eb8ad1bf38837787a85aee4f60b203143a5d5750aa1',
 'data/saturn-6-supported80.csv':'40f7aa481f693525f0c7f828b71a52c858a590aa0dc157ac6e6fffb2b583778f',
 'configs/cluster.json':'caebc9491f62b5877231a9327c63ee9f06ed5360452b0d781cbe737c8e2897b1',
 'data/responses.json':'23fa463408b32d2697b84d2ea8a562e547222832b9d38a9117a79cfcdfde07b3'}
def digest(b):return hashlib.sha256(b).hexdigest()
def encoded(x):return (json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8')
def products():
    for p,h in SOURCE_HASHES.items():assert digest((ROOT/p).read_bytes())==h,('SOURCE_CHANGED',p)
    out={};sources={}
    for w,last in ((2,Decimal('10094.5')),(6,Decimal('11067'))):
        path=f'data/saturn-{w}-supported80.csv'
        rows=list(csv.DictReader((ROOT/path).open(encoding='utf8',newline='')))
        assert len(rows)==80
        first=min(Decimal(r['time']) for r in rows)
        changed=[dict(r,time=str(first+(Decimal(r['time'])-first)/2)) for r in rows]
        assert max(Decimal(r['time']) for r in changed)==last
        assert all({k:v for k,v in a.items() if k!='time'}=={k:v for k,v in b.items() if k!='time'} for a,b in zip(rows,changed))
        s=io.StringIO(newline='');wr=csv.DictWriter(s,fieldnames=list(rows[0]),lineterminator='\n');wr.writeheader();wr.writerows(changed)
        out[f'data/scenarios_r1/w{w}_dense.csv']=s.getvalue().encode('utf8')
    original=json.loads((ROOT/'configs/cluster.json').read_text())
    for cpu in (2,3,6):
        cluster=[dict(n,cpu=cpu*n['gpus']) for n in original]
        out[f'data/scenarios_r1/cluster_cpu{cpu}.json']=encoded(cluster)
    response=json.loads((ROOT/'data/responses.json').read_text())
    out['data/scenarios_r1/responses_original.json']=(ROOT/'data/responses.json').read_bytes()
    c=[.37,.72,1.,1.3,1.53,1.75,2.4,2.4,2.4];m=[.37,1.,1.75,2.4,2.4]
    for kind in ('cn','cm'):
        r=copy.deepcopy(response)
        for app,label in (('cifar10','C'),('deepspeech2','N' if kind=='cn' else 'M'),('bert','N')):
            profile=r['profiles'][app]
            profile.update(profile_kind='synthetic_sensitivity',sensitivity_class=label,reference=1.,
                source='User preregistration: C=original CIFAR RAM62.5 CPU slice; N=constant1; M=interp_C(3*m/62.5) at existing RAM knots',
                source_sha256=SOURCE_HASHES['data/responses.json'])
            profile['table']=[[v]*5 for v in c] if label=='C' else ([m[:] for _ in c] if label=='M' else [[1.]*5 for _ in c])
        r['scenario_provenance']=dict(profile_kind='synthetic_sensitivity',base_sha256=SOURCE_HASHES['data/responses.json'],
            formula_M='c_equiv=3*m/62.5; linear C interpolation (20.83 maps to0.99984; lower-clamped to first C point=0.37)',
            reference='Fixed 3 CPU/GPU and 62.5 GB/GPU; never capacity-renormalize',
            limitations='Controlled sensitivity, not measured CIFAR/DeepSpeech2 hardware profiles')
        out[f'data/scenarios_r1/responses_{kind}.json']=encoded(r)
    specs=[('w2_dense_original',2,3,'original','Arrival intervals /2','Higher concurrency may increase complementarity or competition'),
           ('w6_dense_original',6,3,'original','Arrival intervals /2','Replicate density on W6'),
           ('w2_dense_cpu2',2,2,'original','Only CPU capacity versus w2_dense_original','Scarcity may reduce reclaimable slack'),
           ('w2_dense_cpu6',2,6,'original','Only CPU capacity versus w2_dense_original','Abundance also strengthens proportional baseline'),
           ('w2_dense_cn',2,3,'cn','CIFAR=C; DeepSpeech2=N; BERT=N','Longer-lived CPU donors'),
           ('w2_dense_cm',2,3,'cm','Only DeepSpeech2 N->M versus CN','Incremental RAM-sensitive opportunity')]
    scenarios=[dict(id=i,input=f'data/scenarios_r1/w{w}_dense.csv',cluster=f'data/scenarios_r1/cluster_cpu{cpu}.json',
        responses=f'data/scenarios_r1/responses_{kind}.json',synthetic_response=kind!='original',changes=changes,hypothesis=hyp) for i,w,cpu,kind,changes,hyp in specs]
    config=dict(base_commit=BASE,scenarios=scenarios,method_order=['SIA-P','CAPRA-Fixed','CAPRA'])
    out['configs/scenarios_r1.json']=encoded(config)
    out['data/scenarios_r1/provenance.json']=encoded(dict(base_commit=BASE,source_sha256=SOURCE_HASHES,
        derived_sha256={p:digest(b) for p,b in out.items()},arrival_formula='t_min+(t-t_min)/2 exact Decimal, no rounding',
        synthetic='CN/CM controlled sensitivity; ImageNet profile unchanged; minimum axes unchanged'))
    return out
def main():
    p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args()
    out=products()
    # Check every target before writing any: no partial overwrite on conflict.
    for name,data in out.items():
        path=ROOT/name
        if path.exists():assert path.read_bytes()==data,('REFUSE_OVERWRITE',name)
        elif a.check:raise AssertionError(('MISSING_TARGET',name))
    if not a.check:
        for name,data in out.items():
            path=ROOT/name
            if not path.exists():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    print(json.dumps(dict(status='PASS',check=a.check,targets=len(out),sha256={k:digest(v) for k,v in out.items()})))
if __name__=='__main__':main()
