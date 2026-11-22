"""Select two upstream workloads by a frozen non-performance rule; export public templates."""
from pathlib import Path
import csv, json, hashlib, sys
ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
cpu=[1,2,3,4,5,6,9,12,24]
ram=[20.83,62.5,125,187.5,250]
sys.path.insert(0,str(ROOT/'third_party/synergy/simulator'))
from models.res18_1 import res18_1
from models.res50_1 import res50_1
from models.bert_1 import bert_1
from models.deepspeech_1 import deepspeech_1
mapping={'cifar10':res18_1,'imagenet':res50_1,'bert':bert_1,'deepspeech2':deepspeech_1}
profiles={}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for app,cls in mapping.items():
    model=cls(app)
    filename=ROOT/'third_party/synergy/simulator/models'/f'{cls.__name__}.py'
    profiles[app]=dict(template=cls.__name__,source=str(filename.relative_to(ROOT)),source_sha256=sha(filename),table=model.tput.tolist(),reference=float(model.tput[2,1]),upstream_batch=model.batch)
(DATA/'responses.json').write_text(json.dumps(dict(cpu_axis=cpu,ram_axis=ram,profiles=profiles,
    assumptions=['One-GPU public template mapped to Sia app family; cifar10->res18 and imagenet->res50 are mappings, not measurements.',
    'Per-GPU CPU/RAM linear scaling; same normalized sensitivity for GPU type and current atomic batch; no measured coverage claim.',
    'Bilinear interpolation, boundary clamp; normalize at 3 CPU/62.5 GB per GPU. Host RAM, not GPU VRAM.',
    'Sia throughput traces are the proportional-reference performance; multiply normalized response once.']),indent=2)+'\n',encoding='utf8')
sources=[]
eligible_files=[]
for i in range(1,11):
    src=ROOT/f'third_party/sia/sia-simulator/workloads/saturn/workload-{i}.csv'
    rr=list(csv.DictReader(src.open(encoding='utf8',newline='')))
    if sum(r['application'] in mapping and 1<=int(r['num_replicas'])<=8 for r in rr)>=80:
        eligible_files.append(i)
for i in eligible_files[:2]:
    src=ROOT/f'third_party/sia/sia-simulator/workloads/saturn/workload-{i}.csv'
    rows=list(csv.DictReader(src.open(encoding='utf8',newline='')))
    indexed=[(j,r) for j,r in enumerate(rows) if r['application'] in mapping and 1<=int(r['num_replicas'])<=8]
    chosen=sorted(indexed,key=lambda jr:(float(jr[1]['time']),jr[0]))[:80]
    assert len(chosen)==80
    out=DATA/f'saturn-{i}-supported80.csv'
    with out.open('w',encoding='utf8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(r for _,r in chosen)
    sources.append(dict(input=str(out.relative_to(ROOT)),sha256=sha(out),source=str(src.relative_to(ROOT)),source_sha256=sha(src),source_rows=[j for j,_ in chosen],
        selection='first two numerically ordered Saturn files with >=80 eligible rows; first 80 by original time then zero-based source row; apps cifar10/imagenet/bert/deepspeech2, original request 1..8 GPUs; all fields unchanged',
        original_rows=len(rows),eligible_rows=len(indexed),first_time=float(chosen[0][1]['time']),last_time=float(chosen[-1][1]['time'])))
(DATA/'provenance.json').write_text(json.dumps(dict(workloads=sources,responses_sha256=sha(DATA/'responses.json')),indent=2)+'\n',encoding='utf8')
(ROOT/'configs').mkdir(exist_ok=True)
nodes=[]
for typ,g,c,m in [('aws',4,12,250),('dgx-ext',8,24,500),('rtx',8,24,500)]:
    for i in range(2):nodes.append(dict(id=f'{typ}:{i}',gpu_type=typ,gpus=g,cpu=c,ram=m))
(ROOT/'configs/cluster.json').write_text(json.dumps(nodes,indent=2)+'\n',encoding='utf8')
print(json.dumps(sources,indent=2))
