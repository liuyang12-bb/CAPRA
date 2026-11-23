import os,sys,platform,hashlib,importlib.metadata
from r3_utils import *
def main():
    check_budget();pins={'numpy':'1.26.4','scipy':'1.13.1','cvxpy':'1.6.5'}
    versions={k:importlib.metadata.version(k) for k in pins};assert versions==pins and platform.python_version()=='3.10.10'
    from scipy.optimize._highs import _highs_wrapper
    old=load(ROOT/'configs/experiment_manifest_ram_r2.json')['environment'];binary=Path(_highs_wrapper.__file__)
    assert sha(binary)==old['highs_wrapper_sha256'] and sha(ROOT/'requirements_v2.lock.txt')==old['dependency_lock_sha256']
    from capra.upstream import import_audit
    paths=import_audit()
    out=dict(old,base_commit=BASE,executable=sys.executable,prefix=sys.prefix,python=platform.python_version(),versions=versions,highs_wrapper_sha256=sha(binary),import_audit=paths)
    dump(DEV/'environment.json',out)
    raw=git('-C',str(ROOT),'ls-tree','-rz',BASE);paths={x.split(b'\t',1)[1].decode():x.split(b'\t',1)[0].split()[2].decode() for x in raw.split(b'\0') if x}
    for p,h in paths.items():
        check_budget();b=(ROOT/p).read_bytes();assert hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest()==h,('BASE_CHANGED',p)
    dump(DEV/'protected_base.json',{p:sha(ROOT/p) for p in paths})
    print('R3_ENVIRONMENT_AND_2000_BASE_FILES_PASS')
if __name__=='__main__':main()
