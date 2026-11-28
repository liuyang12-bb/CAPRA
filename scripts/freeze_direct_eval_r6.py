"""Freeze acyclic execution source, exact inputs, fixed matrix, methods and metrics."""
from pathlib import Path
import sys,zipfile
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from capra.protocol_direct_eval_r6 import *
def main():
    path=ROOT/'configs/experiment_manifest_direct_eval_r6.json';assert not path.exists()
    files=source_files();fingerprint=digest(files);snapshot=RUN/'source_snapshot.zip';assert not snapshot.exists()
    with zipfile.ZipFile(snapshot,'w',zipfile.ZIP_DEFLATED) as z:
        for p in files:z.write(ROOT/p,p)
        z.writestr('FILES_SHA256.json',json.dumps(files,indent=2))
    head=git('rev-parse','HEAD').decode().strip();assert git('merge-base','--is-ancestor',BASE,head,check=False).returncode==0
    assert not git('diff','--name-only','--','src','scripts','tests'),'EXECUTION_CODE_NOT_COMMITTED'
    protocol=load(ROOT/'configs/protocol_direct_eval_r6.json')
    manifest=dict(**protocol,actual_execution_head=head,source_snapshot=snapshot.relative_to(ROOT).as_posix(),source_snapshot_sha256=sha(snapshot),source_files_sha256=files,source_fingerprint=fingerprint,environment=load(RUN/'environment.json'),cells=cells(),frozen_utc=utc(),command_template='python -X utf8 -B -m capra.runner_direct_eval_r6 --manifest <relative_manifest> --cell <index> --output <new_attempt_directory> --wall-limit 540',source_tree_note='Snapshot excludes this manifest; actual_execution_head is code commit, final delivery SHA is separate')
    manifest['execution_source_files_sha256']={p:h for p,h in files.items() if p.startswith(('src/capra/','third_party/sia/','data/')) or p in ('requirements_v2.lock.txt','pyproject.toml','scripts/scenario_control.py','configs/protocol_direct_eval_r6.json')}
    dump(path,manifest);dump(RUN/'freeze_receipt.json',dict(manifest_path=path.relative_to(ROOT).as_posix(),manifest_sha256=sha(path),source_snapshot_sha256=sha(snapshot),actual_execution_head=head,source_fingerprint=fingerprint))
    print('R6_FROZEN',head,len(files),fingerprint)
if __name__=='__main__':main()
