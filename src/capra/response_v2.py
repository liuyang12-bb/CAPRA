"""Same frozen response model, vectorized/cached queries and explicit legal domain."""
from collections import OrderedDict
import numpy as np
from .response import Responses

class V2Responses(Responses):
    def __init__(self,path,neutral=False):
        super().__init__(path,neutral)
        self.ca=np.asarray(self.data['cpu_axis'],float);self.ma=np.asarray(self.data['ram_axis'],float)
        self.tables={k:np.asarray(v['table'],float)/v['reference'] for k,v in self.data['profiles'].items()}
        self.cache=OrderedDict();self.hits=0;self.misses=0

    def legal(self,g,c,m,node):
        return self.ca[0]*g-1e-9<=c<=min(node.cpu,self.ca[-1]*g)+1e-9 and self.ma[0]*g-1e-9<=m<=min(node.ram,self.ma[-1]*g)+1e-9

    def rhos(self,app,g,points):
        keys=[(app,g,round(c,8),round(m,8)) for c,m in points]
        missing=list(dict.fromkeys(k for k in keys if k not in self.cache))
        self.hits+=len(keys)-len(missing);self.misses+=len(missing)
        if missing:
            c=np.array([k[2]/g for k in missing]);m=np.array([k[3]/g for k in missing])
            ci=np.clip(np.searchsorted(self.ca,c,side='right')-1,0,len(self.ca)-2)
            mi=np.clip(np.searchsorted(self.ma,m,side='right')-1,0,len(self.ma)-2)
            x=np.clip((c-self.ca[ci])/(self.ca[ci+1]-self.ca[ci]),0,1)
            y=np.clip((m-self.ma[mi])/(self.ma[mi+1]-self.ma[mi]),0,1)
            t=self.tables[app]
            values=np.ones(len(missing)) if self.neutral else ((1-x)*(1-y)*t[ci,mi]+x*(1-y)*t[ci+1,mi]+(1-x)*y*t[ci,mi+1]+x*y*t[ci+1,mi+1])
            for k,v in zip(missing,values):self.cache[k]=float(v)
        result=[self.cache[k] for k in keys]
        while len(self.cache)>65536:self.cache.popitem(last=False)
        return result

    def rho(self,app,g,cpu,ram):return self.rhos(app,g,[(cpu,ram)])[0]
