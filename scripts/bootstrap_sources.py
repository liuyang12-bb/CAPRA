"""Record downloaded upstream versions and apply small, reviewable compatibility hooks."""
from pathlib import Path
import hashlib, json, subprocess

ROOT=Path(__file__).resolve().parents[1]
records=[]
for name,url in [('sia','https://github.com/siasosp23/artifacts'),('synergy','https://github.com/msr-fiddle/synergy')]:
    repo=ROOT/'third_party'/name
    commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
    records.append(dict(name=name,url=url,commit=commit))
    assert repo.resolve().is_relative_to(ROOT.resolve()) and not repo.is_symlink()
(ROOT/'docs/upstream_versions.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
source=ROOT/'third_party/sia/sia-simulator'
patches={}
def patch(name, old, new):
    p=source/name
    text=p.read_text(encoding='utf8')
    assert text.count(old)==1,(name,old[:80],text.count(old))
    patches.setdefault(name,hashlib.sha256(p.read_bytes()).hexdigest())
    p.write_text(text.replace(old,new),encoding='utf8')

patch('sia.py','valid_config_idxs = alloc_configs[0] <= nnodes',
      'valid_config_idxs = (alloc_configs[0] <= nnodes) & (alloc_configs[0] == 1)  # CAPRA single-node domain')
patch('sia.py','        # solve problem\n        problem = cp.Problem(obj, constraints=constraints)',
      "        # CAPRA shared feasibility hook: same Sia objective, exact physical locks.\n        if getattr(self, 'capra_constraints', None):\n            constraints.extend(self.capra_constraints(adaptive_X, adaptive_jobnames))\n        # solve problem\n        problem = cp.Problem(obj, constraints=constraints)")
patch('sia.py', '        problem.solve(solver=cp.CBC, verbose=sim_config.sia_solver_verbose, \n                      numberThreads=sim_config.sia_solver_num_threads, \n                      allowablePercentageGap=sim_config.sia_solver_thresh*100)',
      "        problem.solve(solver=cp.SCIPY, verbose=False,\n                      scipy_options={'time_limit': 10.0, 'mip_rel_gap': sim_config.sia_solver_thresh})\n        self.capra_solver_status = problem.status\n        self.capra_solver_objective = problem.value\n        if problem.status not in ('optimal', 'optimal_inaccurate'):\n            raise RuntimeError('SIA_SOLVER_NO_VERIFIED_OPTIMUM: '+str(problem.status))")
patch('job.py','        self.progress = 0.0','        self.progress = 0.0\n        self.capra_rho = 1.0\n        self.capra_segments = []')
patch('job.py','            goodput = goodput * self.calibration_factor',
      '            goodput = goodput * self.calibration_factor\n            capra_raw_rate = float(goodput)\n            goodput *= self.capra_rho  # apply auxiliary response exactly once to training\n            capra_start = float(self.current_time)\n            capra_before = float(self.progress)')
patch('job.py','                self.progress += goodput * seconds',
      "                self.capra_segments.append(dict(start=capra_start,seconds=float(seconds),raw_rate=capra_raw_rate,rho=float(self.capra_rho),before=capra_before,after=float(self.progress+goodput*seconds),rounding=False,atomic_bsz=int(self.atomic_bsz),accum_steps=int(self.accum_steps)))\n                self.progress += goodput * seconds")
patch('job.py','                self.progress = next_progress',
      "                self.capra_segments.append(dict(start=capra_start,seconds=float(delta),raw_rate=capra_raw_rate,rho=float(self.capra_rho),before=capra_before,after=float(next_progress),rounding=True,atomic_bsz=int(self.atomic_bsz),accum_steps=int(self.accum_steps)))\n                self.progress = next_progress")
(ROOT/'docs/upstream_patch_base_hashes.json').write_text(json.dumps(patches,indent=2)+'\n',encoding='utf8')
for name in ('sia','synergy'):
    repo=ROOT/'third_party'/name
    diff=subprocess.check_output(['git','-C',str(repo),'diff','--no-ext-diff','--binary'])
    (ROOT/'docs'/f'{name}_upstream.patch').write_bytes(diff)
    backup=ROOT/'.upstream-git'/name
    backup.parent.mkdir(exist_ok=True)
    assert not backup.exists()
    # These are freshly downloaded CAPRA-owned Git databases, never the old project's .git.
    (repo/'.git').rename(backup)
print(json.dumps(records))
