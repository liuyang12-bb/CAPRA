"""Post-experiment CLI: raw v2 audit, with explicit rejection of v1 cells."""
import sys,json
from pathlib import Path
from capra.audit_v2 import audit
directory=Path(sys.argv[1])
assert json.loads((directory/'start.json').read_text(encoding='utf8'))['version'].startswith('CAPRA_V2')
print(json.dumps(audit(directory),ensure_ascii=False,indent=2))
