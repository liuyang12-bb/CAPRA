"""Recorded, hash-checked inputs; repository-relative replay across machines."""
import hashlib
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[2]
DEFAULTS = {'cluster': 'configs/cluster.json', 'responses': 'data/responses.json'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def describe(path):
    path = Path(path).resolve()
    relative = path.relative_to(ROOT.resolve()).as_posix()
    return dict(absolute=str(path), relative=relative, sha256=sha(path))


def resolve_inputs(start):
    result = {}
    if 'inputs' in start:
        for kind in ('workload', 'cluster', 'responses'):
            entry = start['inputs'][kind]
            path = (ROOT / entry['relative']).resolve()
            assert path.is_relative_to(ROOT.resolve()), ('FOREIGN_INPUT', kind)
            if not path.is_file():
                path = Path(entry['absolute'])
            assert path.is_file(), ('MISSING_RECORDED_INPUT', kind, str(path))
            assert sha(path) == entry['sha256'], ('INPUT_HASH_MISMATCH', kind)
            legacy_key = 'input_sha256' if kind == 'workload' else kind + '_sha256'
            assert entry['sha256'] == start[legacy_key], ('INCONSISTENT_INPUT_HASH', kind)
            result[kind] = path
    else:
        for kind in ('workload', 'cluster', 'responses'):
            if kind == 'workload':
                path = Path(start['input'])
                if not path.is_file():
                    path = ROOT / 'data' / PureWindowsPath(start['input']).name
                key = 'input_sha256'
            else:
                path = ROOT / DEFAULTS[kind]
                key = kind + '_sha256'
            assert path.is_file() and sha(path) == start[key], ('LEGACY_INPUT_HASH', kind)
            result[kind] = path
    return result
