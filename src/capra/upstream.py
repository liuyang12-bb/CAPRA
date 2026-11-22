"""Only CAPRA-owned vendored modules may be imported."""
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
SIA=ROOT/'third_party/sia/sia-simulator'
assert SIA.resolve().is_relative_to(ROOT.resolve())
sys.path.insert(0,str(SIA))
sys.dont_write_bytecode=True
import simulator_config as config
config.sia_solver_verbose=False
config.sia_solver_num_threads=1
config.num_parallel_jobs=1
from applications import APPLICATIONS
from job import Job
from sia import SiaPolicy
from utils import JobInfo, NodeInfo


def import_audit():
    paths={}
    for name,module in list(sys.modules.items()):
        filename=getattr(module,'__file__',None)
        if filename:
            p=Path(filename).resolve()
            if p.drive.lower()=='d:':
                assert p.is_relative_to(ROOT.resolve()),('FOREIGN_IMPORT',name,str(p))
            paths[name]=str(p)
    assert Path(sys.prefix).resolve()==(ROOT/'.venv').resolve(),('FOREIGN_ENV',sys.prefix)
    return dict(executable=sys.executable,prefix=sys.prefix,module_files=paths)
