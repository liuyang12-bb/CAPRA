"""Foreground owned subprocess, total-process clock and bounded external stop."""
from pathlib import Path
import argparse,json,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1]

def stop_owned(child):
    if child.poll() is None:
        # Windows venv launcher has a real-Python descendant. Kill this owned tree only.
        # The live Popen handle is retained; never select processes by image name.
        subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],capture_output=True,check=False)
        child.wait(timeout=15)


def execute(input_path,method,output,extra=None,process_limit=960,runner_module='capra.runner',audit_module='capra.audit'):
    output=Path(output)
    assert output.resolve().is_relative_to(ROOT.resolve()) and not output.exists()
    env=dict(os.environ,OPENBLAS_NUM_THREADS='1',OMP_NUM_THREADS='1',MKL_NUM_THREADS='1',NUMEXPR_NUM_THREADS='1',PYTHONHASHSEED='0',PYTHONDONTWRITEBYTECODE='1',TMP=str(ROOT/'.cache/tmp'),TEMP=str(ROOT/'.cache/tmp'))
    cmd=[sys.executable,'-X','utf8','-B','-m',runner_module,'--input',str(input_path),'--method',method,'--output',str(output),*(extra or [])]
    # Parent creates the log outside the cell directory; child owns directory creation.
    output.parent.mkdir(parents=True,exist_ok=True)
    logpath=output.parent/(output.name+'.stdout.log')
    began=time.perf_counter()
    timed_out=False
    with logpath.open('w',encoding='utf8') as log:
        child=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            while child.poll() is None:
                if time.perf_counter()-began>process_limit:
                    timed_out=True;stop_owned(child);break
                if (ROOT/'STOP_REQUEST.json').exists():
                    # Cooperative runner observes at round boundary; bounded terminate afterwards.
                    try:child.wait(timeout=15)
                    except subprocess.TimeoutExpired:stop_owned(child)
                    break
                try:child.wait(timeout=1)
                except subprocess.TimeoutExpired:pass
        finally:
            stop_owned(child)
    wall=time.perf_counter()-began
    receipt=dict(command=cmd,exit_code=child.returncode,process_wall_seconds=wall,external_wall_limit=process_limit,external_timeout=timed_out,stdout=str(logpath))
    if output.exists():(output/'process.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf8')
    if child.returncode or not (output/'summary.json').exists():
        print(json.dumps(dict(cell=output.name,status='FAILED_OR_EXTERNAL_STOP',**receipt)),flush=True)
        return None
    import importlib
    summary=importlib.import_module(audit_module).audit(output)
    print(json.dumps(dict(cell=output.name,**summary),ensure_ascii=False),flush=True)
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--method',required=True);p.add_argument('--output',required=True);p.add_argument('--max-jobs',type=int);p.add_argument('--max-rounds',type=int,default=6000);p.add_argument('--wall-limit',type=int,default=900)
    a=p.parse_args();extras=['--max-rounds',str(a.max_rounds),'--wall-limit',str(a.wall_limit)]
    if a.max_jobs:extras.extend(['--max-jobs',str(a.max_jobs)])
    r=execute(a.input,a.method,a.output,extras,a.wall_limit+60)
    sys.exit(0 if r else 1)
