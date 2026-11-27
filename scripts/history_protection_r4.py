"""Read-only exact Git-blob census of all historical worktrees."""
import os,subprocess,hashlib
from r4_utils import *

def main():
    env={k:v for k,v in os.environ.items() if k!='GIT_CONFIG_COUNT' and not k.startswith(('GIT_CONFIG_KEY_','GIT_CONFIG_VALUE_'))}
    records=[]
    for name,commit in [
        ('CAPRA','0b87934ae558960921889b01d14502155fb0c41c'),
        ('CAPRA-scenarios-r1','81b1109ab1124feeac4e846003f4383b39143fc4'),
        ('CAPRA-ablation-ram-r2','0876dd916e1b25d2030233826968683da730a55f'),
        ('CAPRA-smart-holdout-r3','5af0bdb6b86b797225908f717b5b9324cd48a539')]:
        tree=Path('D:/科研启航')/name
        def git(*a):return subprocess.check_output(['git','-C',str(tree),*a],env=env)
        assert git('rev-parse','HEAD').decode().strip()==commit
        assert not git('status','--porcelain','--untracked-files=no')
        verified={}
        for item in git('ls-tree','-rz',commit).split(b'\0'):
            if not item:continue
            meta,rel=item.split(b'\t',1);mode,kind,oid=meta.split();assert kind==b'blob'
            path=rel.decode('utf8');data=(tree/path).read_bytes()
            actual=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            assert actual==oid.decode(),(name,path)
            verified[path]=hashlib.sha256(data).hexdigest()
        records.append(dict(worktree=str(tree),commit=commit,status='PASS',tracked_files=len(verified),files_sha256=verified,untracked_files_untouched=True))
    dump(RUN/'history_worktrees_verification.json',dict(status='PASS',worktrees=records,no_writes_to_history=True))
    print('R4_HISTORY_WORKTREES_PASS',[(Path(x['worktree']).name,x['tracked_files']) for x in records])
if __name__=='__main__':main()
