import copy,csv,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from capra import inputs
from capra.response import Responses
from capra.response_v2 import V2Responses
from capra.contracts import Node,JobGpuPlan
from capra.node_allocator import NodeAllocator
ROOT=Path(__file__).resolve().parents[1]

class ScenarioChecks(unittest.TestCase):
    def test_arrival_exact_and_other_fields_unchanged(self):
        for w,last in ((2,10094.5),(6,11067)):
            old=list(csv.DictReader((ROOT/f'data/saturn-{w}-supported80.csv').open()))
            new=list(csv.DictReader((ROOT/f'data/scenarios_r1/w{w}_dense.csv').open()))
            self.assertEqual(len(new),80);first=min(float(r['time']) for r in old)
            for a,b in zip(old,new):
                self.assertEqual(float(b['time']),first+(float(a['time'])-first)/2)
                self.assertEqual({k:v for k,v in a.items() if k!='time'},{k:v for k,v in b.items() if k!='time'})
            self.assertEqual(max(float(r['time']) for r in new),last)

    def test_capacity_only_cpu_and_supported_topology(self):
        old=json.loads((ROOT/'configs/cluster.json').read_text())
        for cpu in (2,3,6):
            new=json.loads((ROOT/f'data/scenarios_r1/cluster_cpu{cpu}.json').read_text())
            self.assertEqual(sum(x['gpus'] for x in new),40)
            for a,b in zip(old,new):
                self.assertEqual({k:v for k,v in a.items() if k!='cpu'},{k:v for k,v in b.items() if k!='cpu'})
                self.assertEqual(b['cpu'],cpu*b['gpus'])
            self.assertEqual([x['gpu_type'] for x in new],['aws','aws','dgx-ext','dgx-ext','rtx','rtx'])

    def test_response_control_monotonicity_and_cpu_capacity_reference(self):
        original=Responses(ROOT/'data/responses.json');cn=Responses(ROOT/'data/scenarios_r1/responses_cn.json');cm=Responses(ROOT/'data/scenarios_r1/responses_cm.json')
        for r in (original,cn,cm):
            for p in r.data['profiles'].values():
                a=np.array(p['table'])/p['reference']
                self.assertTrue(np.all(a>0));self.assertTrue(np.all(np.diff(a,axis=0)>=-1e-9));self.assertTrue(np.all(np.diff(a,axis=1)>=-1e-9))
            for app in ('cifar10','bert','deepspeech2'):self.assertEqual(r.rho(app,1,3,62.5),1)
        for app,r2,r6 in (('cifar10',.72,1.75),('deepspeech2',.66,1),('bert',1,1)):
            self.assertAlmostEqual(original.rho(app,1,2,62.5),r2);self.assertAlmostEqual(original.rho(app,1,6,62.5),r6)
        for app in cn.data['profiles']:
            if app!='deepspeech2':self.assertEqual(cn.data['profiles'][app],cm.data['profiles'][app])
        self.assertEqual(original.data['profiles']['imagenet'],cm.data['profiles']['imagenet'])
        self.assertEqual(cm.data['profiles']['deepspeech2']['table'],[[.37,1,1.75,2.4,2.4]]*9)
        for ratio in (2,3,6):
            for app in original.data['profiles']:
                for g in (1,2,4,8):
                    self.assertGreaterEqual(ratio*g,g);self.assertGreaterEqual(62.5*g,20.83*g)
        for r in (cn,cm):
            v=V2Responses(ROOT/f"data/scenarios_r1/responses_{'cn' if r is cn else 'cm'}.json")
            for app in ('cifar10','bert','deepspeech2'):
                for c,m in ((3,62.5),(5,20.83),(1,104.17),(2.3,83.4)):
                    self.assertAlmostEqual(v.rho(app,1,c,m),r.rho(app,1,c,m),places=9)

    def test_portable_input_and_hash_rejection(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'data').mkdir();(root/'configs').mkdir()
            for p in ('data/a.csv','configs/cluster.json','data/responses.json'):(root/p).write_text('x')
            paths={'workload':'data/a.csv','cluster':'configs/cluster.json','responses':'data/responses.json'}
            start={'inputs':{k:dict(relative=p,absolute='Z:/old-machine/missing',sha256=inputs.sha(root/p)) for k,p in paths.items()}}
            start.update(input_sha256=inputs.sha(root/'data/a.csv'),cluster_sha256=inputs.sha(root/'configs/cluster.json'),responses_sha256=inputs.sha(root/'data/responses.json'))
            with patch.object(inputs,'ROOT',root):
                resolved=inputs.resolve_inputs(start);self.assertEqual(resolved['workload'],root/'data/a.csv')
                (root/'data/a.csv').write_text('changed')
                with self.assertRaisesRegex(AssertionError,'INPUT_HASH_MISMATCH'):inputs.resolve_inputs(start)
                (root/'data/a.csv').unlink()
                with self.assertRaisesRegex(AssertionError,'MISSING_RECORDED_INPUT'):inputs.resolve_inputs(start)

    def test_static_feasible_certificate_and_ram_candidate_gap(self):
        r=V2Responses(ROOT/'data/scenarios_r1/responses_cm.json');n=Node('rtx:0','rtx',8,24,500)
        values=[r.rho('cifar10',4,20,83.32),r.rho('deepspeech2',2,2,375),r.rho('bert',2,2,41.66)]
        for a,b in zip(values,(1.53,2.4,1)):self.assertAlmostEqual(a,b)
        self.assertAlmostEqual(83.32+375+41.66,499.98)
        p={k:JobGpuPlan(k,'rtx',4,n.id,1,0) for k in ('C','M')};apps={'C':'cifar10','M':'deepspeech2'}
        allocator=NodeAllocator(p,[n],apps,r,{},{});base=allocator.baseline(n,p)
        pool=allocator.pairs('M',n,base)
        self.assertFalse(any(abs(x.ram-416.68)<1e-6 for x in pool))
        result,_=allocator.solve(n.id,p)
        self.assertEqual((result['C'].cpu,result['C'].ram),(20,83.32))
        self.assertEqual(result['M'].ram,250)
        self.assertAlmostEqual(r.rho('deepspeech2',4,4,416.68),1.50004)
if __name__=='__main__':unittest.main()
