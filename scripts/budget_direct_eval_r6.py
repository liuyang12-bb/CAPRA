"""One absolute 5400s window, actual cumulative accounting and existing Job Objects."""
from pathlib import Path
import os,sys,time,json,ctypes
from scenario_control import Owned,env
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import RUN,load,dump,utc
BP=RUN/'budget_ledger.json'

def alive(pid):
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=[ctypes.c_ulong,ctypes.c_int,ctypes.c_ulong];k.OpenProcess.restype=ctypes.c_void_p
    k.GetExitCodeProcess.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_ulong)];k.CloseHandle.argtypes=[ctypes.c_void_p]
    h=k.OpenProcess(0x1000,False,pid)
    if not h:return False
    code=ctypes.c_ulong()
    try:return bool(k.GetExitCodeProcess(h,ctypes.byref(code))) and code.value==259
    finally:k.CloseHandle(h)

class Budget:
    def __init__(self,resume=False):
        if BP.exists():
            assert resume,'EXPLICIT_RESUME_REQUIRED_NO_BUDGET_RESET';b=load(BP)
            if b.get('controller_pid')!=os.getpid():assert not alive(b['controller_pid']),'CONTROLLER_ALREADY_RUNNING'
            for a in b['attempts']:
                if a['state']=='RUNNING':a.update(state='UNCLOSED_UNVERIFIED',charged_seconds=a['outer_hard_seconds'],reason='Unknown closure conservatively charged full allowed wall; Job Object ownership closes with prior controller')
            self.data=b
        else:self.data=None
    def start(self):
        if self.data is None:
            t=time.monotonic();e=time.time();self.data=dict(total_window_seconds=5400.,start_monotonic=t,deadline_monotonic=t+5400.,start_epoch=e,deadline_epoch=e+5400.,start_utc=utc(),clock_epoch=e-t,attempts=[],controller_pid=os.getpid(),scope='All validation/formal/audits/analysis/figures/final checks/cleanup; absolute and cumulative constraints')
        self.data['controller_pid']=os.getpid();self.save()
    def save(self):
        b=self.data;b['cumulative_charged_seconds']=sum(a.get('charged_seconds',0) for a in b['attempts']);b['elapsed_window_seconds']=time.monotonic()-b['start_monotonic'];b['remaining_seconds']=self.remaining();dump(BP,b)
    def remaining(self):
        if self.data is None:return 5400.
        b=self.data
        return max(0.,min(b['deadline_monotonic']-time.monotonic(),b['deadline_epoch']-time.time(),5400-sum(a.get('charged_seconds',0) for a in b['attempts'])))
    def used_kind(self,prefix):return sum(a.get('charged_seconds',0) for a in self.data['attempts'] if a['kind'].startswith(prefix))
    def run(self,kind,cmd,case,hard,worker_limit=None,cell=None):
        self.start();case=Path(case);assert not case.exists();case.mkdir(parents=True)
        hard=min(float(hard),self.remaining());assert hard>=31,'INSUFFICIENT_BUDGET_CLEANUP_RESERVE'
        work=min(hard-30,float(worker_limit) if worker_limit is not None else hard-30)
        row=dict(kind=kind,cell=cell,state='RUNNING',start_utc=utc(),start_monotonic=time.monotonic(),start_epoch=time.time(),command=cmd,outer_hard_seconds=hard,worker_limit_seconds=work,cleanup_reserve_seconds=30,output=case.relative_to(ROOT).as_posix(),controller_pid=os.getpid())
        self.data['attempts'].append(row);self.save();begin=time.monotonic();job=None;timeout=False;exit_code=None;cleanup=None
        print(json.dumps(dict(event='COMMAND_START',kind=kind,cell=cell,remaining_seconds=self.remaining(),hard_seconds=hard)),flush=True)
        try:
            with (case/'stdout.log').open('w',encoding='utf8') as log:
                job=Owned(cmd,log,env());row['pid']=job.child.pid;self.save()
                try:
                    while job.child.poll() is None:
                        if time.monotonic()-begin>=work or self.remaining()<=30:timeout=True;break
                        try:job.child.wait(timeout=.2)
                        except __import__('subprocess').TimeoutExpired:pass
                    exit_code=job.child.poll()
                finally:cleanup=job.close()
            row.update(state='EXTERNAL_TIMEOUT' if timeout else ('PASS' if exit_code==0 else 'FAILED'),exit_code=exit_code,external_timeout=timeout,cleanup=cleanup)
        except BaseException as error:
            row.update(state='FAILED',error=repr(error));raise
        finally:
            row.update(charged_seconds=time.monotonic()-begin,end_utc=utc(),end_monotonic=time.monotonic(),end_epoch=time.time())
            if cleanup is not None:row['cleanup']=cleanup
            self.save();dump(case/'process.json',row)
        assert row['charged_seconds']<=hard+1e-6,('HARD_LIMIT_AND_CLEANUP_EXCEEDED',row['charged_seconds'],hard)
        print(json.dumps(dict(event='COMMAND_END',kind=kind,cell=cell,state=row['state'],wall_seconds=row['charged_seconds'],remaining_seconds=self.remaining())),flush=True)
        return row

def assert_window():
    b=load(BP);assert min(b['deadline_monotonic']-time.monotonic(),b['deadline_epoch']-time.time(),5400-sum(a.get('charged_seconds',0) for a in b['attempts']))>0,'R6_EXECUTION_WINDOW_EXPIRED'
    return b
