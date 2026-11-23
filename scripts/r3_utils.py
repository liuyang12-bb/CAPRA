from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,time,os,subprocess
ROOT=Path(__file__).resolve().parents[1];RUN=ROOT/'runs/smart_holdout_r3';DEV=RUN/'development';BASE='0876dd916e1b25d2030233826968683da730a55f'
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def dump(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def git(*args):
    # Some desktop launches expose COUNT/KEY without its empty VALUE to Python.
    # Scope removal of that malformed command injection to this read-only child.
    child_env={k:v for k,v in os.environ.items() if k!='GIT_CONFIG_COUNT' and not k.startswith(('GIT_CONFIG_KEY_','GIT_CONFIG_VALUE_'))}
    return subprocess.check_output(['git',*args],env=child_env)
def ledger():return load(RUN/'budget_ledger.json')
def record(kind,**data):
    b=ledger();b['entries'].append(dict(kind=kind,utc=datetime.now(timezone.utc).isoformat(),**data));b['elapsed_seconds']=time.perf_counter()-b['start_monotonic'];b['remaining_seconds']=max(0,b['deadline_monotonic']-time.perf_counter());dump(RUN/'budget_ledger.json',b)
def check_budget(reserve=30):
    b=ledger();assert time.perf_counter()+reserve<b['deadline_monotonic'],'R3_SHARED_BUDGET_EXHAUSTED';return b['deadline_monotonic']
