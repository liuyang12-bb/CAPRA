"""Pure inclusive timers around unchanged R3 allocator calls; no strategy changes."""
import time
from .placement_r3 import create_placement as r3_create
from .methods_r4 import spec
class TimedAllocator:
    def __init__(self,base):self.base=base;self.seconds=0.;self.requests=0
    def call(self,name,*args,**kwargs):
        began=time.perf_counter()
        try:return getattr(self.base,name)(*args,**kwargs)
        finally:self.seconds+=time.perf_counter()-began;self.requests+=1
    def baseline(self,*a,**k):return self.call('baseline',*a,**k)
    def solve(self,*a,**k):return self.call('solve',*a,**k)
    def layout(self,*a,**k):return self.call('layout',*a,**k)
    def stats(self):return dict(self.base.stats(),r4_allocator_seconds=self.seconds,r4_allocator_requests=self.requests)
    def __getattr__(self,name):return getattr(self.base,name)
def create_placement(*args,method,allocator_mode):
    spec(method,allocator_mode)
    out=r3_create(*args,method=method,allocator_mode=allocator_mode)
    out.allocator=TimedAllocator(out.allocator)
    return out
