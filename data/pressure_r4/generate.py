"""Exact Decimal half-spacing; preserve all 80 jobs and all non-time fields."""
from pathlib import Path
from decimal import Decimal
import csv,io,json,hashlib
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def number(d):
    s=format(d,'f')
    return s.rstrip('0').rstrip('.') if '.' in s else s
def transform(rows):
    assert len(rows)==80 and len({r['name'] for r in rows})==80
    t0=min(Decimal(r['time']) for r in rows);out=[];mapping=[]
    for i,r in enumerate(rows):
        d=dict(r);d['time']=number(t0+(Decimal(r['time'])-t0)/Decimal(2))
        out.append(d);mapping.append(dict(source_row=i,job=r['name'],original_time=r['time'],dense_time=d['time']))
    order=sorted(range(len(out)),key=lambda i:(Decimal(out[i]['time']),i))
    # Frozen R3 input is time-sorted; exact affine transformation must preserve it.
    assert order==list(range(80)),'UNEXPECTED_SOURCE_ORDER'
    return out,mapping
def distribution(xs):
    import numpy as np
    x=[float(v) for v in xs]
    return dict(n=len(x),min=min(x),median=float(np.median(x)),p95=float(np.quantile(x,.95)),max=max(x),mean=float(np.mean(x)),zero_count=sum(v==0 for v in x))
def main():
    from sys import path;path.insert(0,str(ROOT/'scripts'))
    from r4_utils import check_budget,dump,load
    old=load(ROOT/'data/holdout_r3/provenance.json');by={x['output']:x for x in old};allmeta=[]
    for w in (7,8):
        check_budget();rel=f'data/holdout_r3/saturn{w}_supported80.csv';src=ROOT/rel
        assert sha(src)==by[rel]['sha256']
        with src.open(encoding='utf8',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
        out,mapping=transform(rows)
        for a,b in zip(rows,out):assert {k:v for k,v in a.items() if k!='time'}=={k:v for k,v in b.items() if k!='time'}
        text=io.StringIO(newline='');wr=csv.DictWriter(text,fields,lineterminator='\n');wr.writeheader();wr.writerows(out)
        dst=ROOT/f'data/pressure_r4/saturn{w}_dense05.csv';data=text.getvalue().encode('utf8')
        assert not dst.exists() or dst.read_bytes()==data,'REFUSE_CONFLICTING_DERIVED_INPUT'
        if not dst.exists():dst.write_bytes(data)
        orig=[Decimal(x['time']) for x in rows];dense=[Decimal(x['time']) for x in out]
        record=dict(scenario=f'saturn{w}_dense05',source=rel,source_sha256=sha(src),output=dst.relative_to(ROOT).as_posix(),sha256=sha(dst),generator_sha256=sha(__file__),rows=80,formula='t0 + Decimal(0.5)*(ti-t0)',all_non_time_fields_unchanged=True,row_order_preserved=True,source_and_derived_row_mapping=mapping,first_original=number(min(orig)),last_original=number(max(orig)),first_dense=number(min(dense)),last_dense=number(max(dense)),original_interarrivals=distribution([b-a for a,b in zip(orig,orig[1:])]),dense_interarrivals=distribution([b-a for a,b in zip(dense,dense[1:])]),applications=dict(Counter(x['application'] for x in out)),requested_gpus=dict(Counter(x['num_replicas'] for x in out)),scope='Pressure derivative of original R3 holdout, not independent holdout or production record')
        dump(dst.with_suffix('.provenance.json'),record);allmeta.append(record)
    dump(ROOT/'data/pressure_r4/provenance.json',allmeta);print('R4_DENSE_INPUTS_PASS',flush=True)
if __name__=='__main__':main()
