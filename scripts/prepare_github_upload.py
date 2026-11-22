"""Prepare a complete code/results/report inventory; no credentials or network."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
assert ROOT.name=='CAPRA' and not ROOT.is_symlink()
subprocess.run(['git','-C',str(ROOT),'add','--','.gitignore','README.md','docs/GITHUB_BACKUP.md','scripts/prepare_github_upload.py','runs'],check=True)
raw=subprocess.check_output(['git','-C',str(ROOT),'ls-files','-z'])
names=[x.decode('utf8') for x in raw.split(b'\0') if x]
records=[]
for name in names:
    if name=='docs/github_upload_manifest.json':continue
    path=ROOT/name
    assert path.resolve().is_relative_to(ROOT.resolve()) and path.is_file()
    assert not any(x in Path(name).parts for x in ('.venv','.git','.cache','.upstream-git','__pycache__'))
    size=path.stat().st_size
    assert size<100*1024*1024,('GITHUB_FILE_LIMIT',name,size)
    records.append(dict(path=name,bytes=size,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
tracked=set(names)
for path in (ROOT/'runs').rglob('*'):
    if path.is_file():assert path.relative_to(ROOT).as_posix() in tracked,('RESULT_NOT_TRACKED',str(path))
for path in (ROOT/'src').rglob('*.py'):
    assert path.relative_to(ROOT).as_posix() in tracked
manifest=dict(repository='liuyang12-bb/CAPRA',private=True,prepared_utc=datetime.now(timezone.utc).isoformat(),
    scope='All tracked CAPRA source and vendored upstream, inputs, configs, dependencies lock, docs and every runs file; no virtualenv/cache/git databases.',
    files=records,file_count=len(records),bytes=sum(r['bytes'] for r in records),
    raw_event_files=[r['path'] for r in records if r['path'].endswith('events.jsonl.gz')],
    console_logs=[r['path'] for r in records if r['path'].endswith('.stdout.log')])
target=ROOT/'docs/github_upload_manifest.json'
target.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
subprocess.run(['git','-C',str(ROOT),'add','--','docs/github_upload_manifest.json'],check=True)
print(json.dumps({k:manifest[k] for k in ('repository','file_count','bytes','raw_event_files','console_logs')},ensure_ascii=False))
