"""Preserve exact frozen execution bytes and hash all six local evidence bundles."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1]
RUN=ROOT/'runs/main_v1'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
manifest=json.loads((ROOT/'configs/experiment_manifest.json').read_text(encoding='utf8'))
paths={ROOT/name for name in manifest['source_sha256']}
paths.update(ROOT/c['input'] for c in manifest['cells'])
paths.update((ROOT/'configs/experiment_manifest.json',ROOT/'README.md',ROOT/'docs/DESIGN.md',ROOT/'docs/upstream_versions.json',ROOT/'docs/sia_upstream.patch',ROOT/'docs/upstream_patch_base_hashes.json'))
archive=RUN/'frozen_execution_source.zip'
assert not archive.exists()
with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as out:
    for p in sorted(paths):out.write(p,p.relative_to(ROOT))
with zipfile.ZipFile(archive) as check:
    for name,digest in manifest['source_sha256'].items():
        assert hashlib.sha256(check.read(name.replace('\\','/'))).hexdigest()==digest,('ARCHIVE_BYTES',name)
hashes={str(p.relative_to(ROOT)):sha(p) for p in RUN.rglob('*') if p.is_file() and p.name!='evidence_hashes.json'}
(RUN/'evidence_hashes.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
print(json.dumps(dict(archive=str(archive),bytes=archive.stat().st_size,sha256=sha(archive),evidence_files=len(hashes)),ensure_ascii=False))
