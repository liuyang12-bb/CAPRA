"""Local code commit before formal execution; never pushes or stages old results."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import RUN,BASE,git,dump,utc
def main():
    names=['src/capra/*direct_eval_r6.py','scripts/*direct_eval_r6.py','tests/test_direct_eval_r6.py','configs/protocol_direct_eval_r6.json','docs/CAPRA_DIRECT_R6_DESIGN.md']
    git('add','--',*names)
    changes=git('diff','--cached','--name-status',BASE).decode().splitlines();assert changes and all(x.startswith('A\t') for x in changes),'OLD_BASE_FILE_MODIFICATION_FORBIDDEN'
    if git('diff','--cached','--name-only'):git('commit','-q','-m','CAPRA Direct R6: frozen evaluation adapters and preregistered pipeline')
    head=git('rev-parse','HEAD').decode().strip();dump(RUN/'code_commit_receipt.json',dict(status='PASS',actual_execution_head=head,algorithm_base_commit=BASE,utc=utc(),no_remote_push=True))
    print('R6_CODE_COMMIT',head)
if __name__=='__main__':main()
