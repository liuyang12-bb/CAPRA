"""Windows Job Objects: suspended creation, assigned before resume, kill whole owned tree."""
import ctypes as C
from ctypes import wintypes as W
import json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
K=C.WinDLL('kernel32',use_last_error=True)
class BASIC(C.Structure):
    _fields_=[('PerProcessUserTimeLimit',C.c_int64),('PerJobUserTimeLimit',C.c_int64),('LimitFlags',W.DWORD),('MinimumWorkingSetSize',C.c_size_t),('MaximumWorkingSetSize',C.c_size_t),('ActiveProcessLimit',W.DWORD),('Affinity',C.c_size_t),('PriorityClass',W.DWORD),('SchedulingClass',W.DWORD)]
class IO(C.Structure):_fields_=[(x,C.c_uint64) for x in ('ReadOperationCount','WriteOperationCount','OtherOperationCount','ReadTransferCount','WriteTransferCount','OtherTransferCount')]
class EXTENDED(C.Structure):_fields_=[('BasicLimitInformation',BASIC),('IoInfo',IO),('ProcessMemoryLimit',C.c_size_t),('JobMemoryLimit',C.c_size_t),('PeakProcessMemoryUsed',C.c_size_t),('PeakJobMemoryUsed',C.c_size_t)]
class ACCOUNT(C.Structure):_fields_=[('TotalUserTime',C.c_int64),('TotalKernelTime',C.c_int64),('ThisPeriodTotalUserTime',C.c_int64),('ThisPeriodTotalKernelTime',C.c_int64),('TotalPageFaultCount',W.DWORD),('TotalProcesses',W.DWORD),('ActiveProcesses',W.DWORD),('TotalTerminatedProcesses',W.DWORD)]
K.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];K.CreateJobObjectW.restype=W.HANDLE
K.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
K.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
K.QueryInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p]
K.TerminateJobObject.argtypes=[W.HANDLE,W.UINT];K.CloseHandle.argtypes=[W.HANDLE]
NT=C.WinDLL('ntdll');NT.NtResumeProcess.argtypes=[W.HANDLE];NT.NtResumeProcess.restype=C.c_long
def ok(value):
    if not value:raise C.WinError(C.get_last_error())
class Owned:
    def __init__(self,cmd,log,env=None):
        self.h=K.CreateJobObjectW(None,None);ok(self.h)
        info=EXTENDED();info.BasicLimitInformation.LimitFlags=0x2000
        ok(K.SetInformationJobObject(self.h,9,C.byref(info),C.sizeof(info)))
        self.child=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,creationflags=4)
        try:
            ok(K.AssignProcessToJobObject(self.h,W.HANDLE(int(self.child._handle))))
            assert NT.NtResumeProcess(W.HANDLE(int(self.child._handle)))==0
        except BaseException:
            self.child.kill();self.child.wait();K.CloseHandle(self.h);raise
    def active(self):
        a=ACCOUNT();ok(K.QueryInformationJobObject(self.h,1,C.byref(a),C.sizeof(a),None));return a.ActiveProcesses
    def close(self):
        before=self.active();ok(K.TerminateJobObject(self.h,0xDEAD))
        self.child.wait(timeout=10)
        end=time.perf_counter()+10
        while self.active() and time.perf_counter()<end:time.sleep(.02)
        remaining=self.active();K.CloseHandle(self.h)
        assert remaining==0,('OWNED_DESCENDANTS_SURVIVED',remaining)
        return dict(active_before_cleanup=before,active_after_cleanup=remaining,mechanism='Windows Job Object; assigned suspended before resume; KILL_ON_JOB_CLOSE')
def env():
    (ROOT/'.cache/tmp').mkdir(parents=True,exist_ok=True)
    return dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONUTF8='1',PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',TMP=str(ROOT/'.cache/tmp'),TEMP=str(ROOT/'.cache/tmp'))
def execute(cmd,logpath,limit,deadline=None):
    began=time.perf_counter();logpath=Path(logpath);logpath.parent.mkdir(parents=True,exist_ok=True)
    timed=False;stopped=False
    with logpath.open('w',encoding='utf8') as log:
        job=Owned(cmd,log,env())
        try:
            while job.child.poll() is None:
                if time.perf_counter()-began>=limit or (deadline is not None and time.perf_counter()>=deadline):timed=True;break
                if (ROOT/'STOP_REQUEST.json').exists():stopped=True;break
                try:job.child.wait(timeout=.5)
                except subprocess.TimeoutExpired:pass
            exit_code=job.child.poll()
        finally:cleanup=job.close()
    return dict(command=cmd,exit_code=exit_code,process_wall_seconds=time.perf_counter()-began,external_wall_limit=limit,external_timeout=timed,user_stop=stopped,stdout=str(logpath),cleanup=cleanup)
