import json
from pathlib import Path
import numpy as np


class Responses:
    """Mapped public templates; linear per-GPU transfer is an explicit assumption."""
    def __init__(self, path, neutral=False):
        self.data = json.loads(Path(path).read_text(encoding='utf8'))
        self.neutral = neutral

    def rho(self, app, gpus, cpu, ram):
        if self.neutral:
            return 1.0
        d = self.data['profiles'][app]
        c, m = cpu/gpus, ram/gpus
        # Separable linear interpolation of the public table, clamped at boundaries.
        vals = [np.interp(m,self.data['ram_axis'],row) for row in d['table']]
        return float(np.interp(c,self.data['cpu_axis'],vals)/d['reference'])

    def preferred(self, app, gpus, node):
        base = (node.cpu*gpus/node.gpus,node.ram*gpus/node.gpus)
        points = [base]
        for c in self.data['cpu_axis']:
            for m in self.data['ram_axis']:
                if c*gpus<=node.cpu+1e-9 and m*gpus<=node.ram+1e-9:
                    points.append((c*gpus,m*gpus))
        # Same utility/protection in fixed/free placement; no ETA or GPU search.
        return min(points,key=lambda p:(-round(self.rho(app,gpus,*p),10),p[0]/node.cpu+p[1]/node.ram,p))
