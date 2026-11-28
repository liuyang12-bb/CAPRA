"""Frozen R6 protocol, portable paths and metadata; no scheduling imports."""
from pathlib import Path
from datetime import datetime,timezone
import os,json,hashlib,csv,subprocess,time
ROOT=Path(__file__).resolve().parents[2];RUN=ROOT/'runs/direct_eval_r6'
BASE='b40cdefdff27d46d8044510652a557e8d7599920';R4='ffa953fb9cd12773992559512d85065bbd26b7b2'
VERSION='CAPRA_V2_DIRECT_EVAL_R6';METHODS=('CAPRA-F-Only','CAPRA-Direct')
INPUTS={
 'data/pressure_r4/saturn7_dense05.csv':'44f7ad31cbd3d7b953b547a494c98ae4c9b7258dfcfe98ce5f4e0f82f0a10a4b',
 'data/pressure_r4/saturn8_dense05.csv':'e1028199a17ef943c03922730e5b59c7f3ece2e83892729742510af74319db75',
 'data/scenarios_r1/cluster_cpu3.json':'8f88c856b1f229e8c3271327340fe36be9a0dacd5fc8f174d7220420182d4842',
 'data/scenarios_r1/responses_original.json':'23fa463408b32d2697b84d2ea8a562e547222832b9d38a9117a79cfcdfde07b3',
 'data/scenarios_r1/responses_cm.json':'75f4ce5e011ae5dd232be3f2b5122101c2761b833c2b8e2a1c18c2d4a1d60782'}
ORDER=[('saturn7_dense05_original','CAPRA-F-Only'),('saturn7_dense05_original','CAPRA-Direct'),('saturn7_dense05_cm','CAPRA-Direct'),('saturn7_dense05_cm','CAPRA-F-Only'),('saturn8_dense05_original','CAPRA-Direct'),('saturn8_dense05_original','CAPRA-F-Only'),('saturn8_dense05_cm','CAPRA-F-Only'),('saturn8_dense05_cm','CAPRA-Direct')]
NUMERIC=dict(OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0')
EPS=1e-9;CAP_EPS=1e-7;PAIR_EPS=1e-7
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);tmp=p.with_name(p.name+f'.{os.getpid()}.tmp');tmp.write_bytes((json.dumps(x,ensure_ascii=False,indent=2)+'\n').encode('utf8'));os.replace(tmp,p)
def utc():return datetime.now(timezone.utc).isoformat()
def git(*args,check=True):
    child_env={k:v for k,v in os.environ.items() if k!='GIT_CONFIG_COUNT' and not k.startswith(('GIT_CONFIG_KEY_','GIT_CONFIG_VALUE_'))}
    r=subprocess.run(['git','-C',str(ROOT),*args],env=child_env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    if check:assert r.returncode==0,(args,r.stderr.decode('utf8',errors='replace'))
    return r.stdout if check else r
def source_files():
    inventory=load(RUN/'base_git_blobs.json')['objects']
    names={p for p in inventory if p.startswith(('src/capra/','third_party/sia/'))}
    names|={p.relative_to(ROOT).as_posix() for folder in ('src/capra','scripts','tests') for p in (ROOT/folder).glob('*direct_eval_r6.py')}
    names|=set(INPUTS)|{'requirements_v2.lock.txt','pyproject.toml','scripts/scenario_control.py','configs/protocol_direct_eval_r6.json'}
    return {p:sha(ROOT/p) for p in sorted(names)}
def input_rows(path):
    rows=list(csv.DictReader(Path(path).open(encoding='utf8',newline='')))
    assert len(rows)==80 and len({r['name'] for r in rows})==80,'EXACT_80_INPUT_REQUIRED'
    return rows
def cells():
    result=[]
    for i,(scenario,method) in enumerate(ORDER,1):
        profile='cm' if scenario.endswith('_cm') else 'original';workload='_'.join(scenario.split('_')[:2])
        result.append(dict(index=i,logical_id=f'{i:02d}',scenario=scenario,method=method,workload=f'data/pressure_r4/{workload}.csv',cluster='data/scenarios_r1/cluster_cpu3.json',responses=f'data/scenarios_r1/responses_{profile}.json',candidate_labels=['F'] if method=='CAPRA-F-Only' else ['F','D'],output=f'runs/direct_eval_r6/{VERSION}/{scenario}/{method}'))
    return result
class StopTracker:
    """Progress, not completion count; full decisions, not only active decisions."""
    def __init__(self):self.stagnant=0;self.overhead=0
    def update(self,all_arrived,executions,decision_seconds):
        grew=any(e['progress_after']>e['progress_before']+1e-10 for e in executions)
        self.stagnant=(self.stagnant+1 if not grew else 0) if all_arrived else 0
        self.overhead=self.overhead+1 if decision_seconds>30 else 0
        if self.stagnant>=30:return 'NO_PROGRESS_30_ROUNDS'
        if self.overhead>=3:return 'CONTROL_OVERHEAD_3X30S'
        return None
