"""Independent RAM replay from specification; no allocator/placement/repair imports."""
import math
EPS=1e-9
def close(a,b):assert abs(a-b)<=1e-7,(a,b)
def verify_trace(trace,node,apps,response,locks):
    initial=trace['initial'];out={k:dict(v) for k,v in initial.items()};ids=sorted(out);axes=response.data['ram_axis']
    for vector in (initial,trace['final']):
        for field in ('gpus','cpu','ram'):assert math.fsum(a[field] for a in vector.values())<=node[field]+1e-7
        for k,a in vector.items():
            g=a['gpus'];assert a['node']==node['id'] and a['gpu_type']==node['gpu_type'] and g in (1,2,4,8)
            assert response.data['cpu_axis'][0]*g-1e-9<=a['cpu']<=min(node['cpu'],response.data['cpu_axis'][-1]*g)+1e-9
            assert min(axes)*g-1e-9<=a['ram']<=min(node['ram'],max(axes)*g)+1e-9
            close(a['rho'],response.rho(apps[k],g,a['cpu'],a['ram']))
            if k in locks:assert a==locks[k]
            else:assert a['rho']>=response.rho(apps[k],g,node['cpu']*g/node['gpus'],node['ram']*g/node['gpus'])-1e-7
    if 'legacy_meta' in trace:
        meta=trace['legacy_meta'];assert 1<=meta['initial_vectors']<=2
        assert meta['upgrades']<=meta['upgrade_bound']==sum(v-1 for v in meta['candidate_pairs'].values())
    expected_bound=1+sum(sum(m*out[k]['gpus']>out[k]['ram'] for m in axes) for k in ids if k not in locks)
    assert expected_bound==trace['ram_step_bound'] and len(trace['updates'])<=expected_bound
    queries=0
    def possible():
        nonlocal queries
        candidates={}
        for k in ids:
            if k in locks:continue
            a=out[k];g=a['gpus'];other=math.fsum(out[j]['ram'] for j in ids if j!=k)
            upper=min(max(axes)*g,node['ram']-other)
            for _ in range(4):
                if math.fsum([other,upper])<=node['ram']:break
                upper=math.nextafter(upper,-math.inf)
            points={}
            for value in [m*g for m in axes]+[upper]:
                if value<=a['ram']+EPS or value>upper or value<min(axes)*g-1e-9:continue
                if not (response.data['cpu_axis'][0]*g-1e-9<=a['cpu']<=min(node['cpu'],response.data['cpu_axis'][-1]*g)+1e-9):continue
                key=round(value,8);points[key]=min(value,points.get(key,value))
            for value in points.values():
                queries+=1;rho=response.rho(apps[k],g,a['cpu'],value)
                if rho-a['rho']>EPS:candidates[(k,round(value,8))]=(value,rho,upper,other)
        return candidates
    for index,update in enumerate(trace['updates'],1):
        possibilities=possible();logged=update['candidates'];assert len(logged)==len(possibilities)
        close(update['free_ram_before'],node['ram']-math.fsum(a['ram'] for a in out.values()))
        ranks=[]
        for c in logged:
            k=c['job'];a=out[k];value,rho,upper,other=possibilities.pop((k,round(c['ram'],8)))
            close(c['ram'],value);close(c['rho_before'],a['rho']);close(c['rho_after'],rho)
            close(c['physical_upper'],upper);close(c['other_ram'],other)
            gain=c['rho_after']-a['rho'];delta=c['ram']-a['ram']
            assert gain>EPS and delta>EPS and c['ram']<=upper
            close(c['delta_rho'],gain);close(c['delta_ram'],delta)
            rank=[-round(gain/(delta/node['ram']),12),-round(gain,12),k,c['ram']]
            assert rank==c['rank'];ranks.append((tuple(rank),c))
            sources=[s for s,v in [('axis',any(c['ram']==m*a['gpus'] for m in axes)),('physical_upper',c['ram']==upper)] if v]
            assert sources==c['sources']
        assert not possibilities
        chosen=min(ranks,key=lambda x:x[0])[1];assert chosen==update['selected'] and update['index']==index
        k=chosen['job'];assert k not in locks
        out[k]=dict(out[k],ram=chosen['ram'],rho=chosen['rho_after'])
        assert math.fsum(a['ram'] for a in out.values())<=node['ram']
        close(update['free_ram_after'],node['ram']-math.fsum(a['ram'] for a in out.values()))
    assert not possible(),'RESIDUAL_RAM_GAIN'
    assert trace['ram_candidates']==queries and trace['ram_steps']==len(trace['updates']) and trace['terminal_candidates']==[]
    assert set(out)==set(trace['final'])
    for k,a in out.items():
        assert a==trace['final'][k]
        assert all(a[x]==initial[k][x] for x in ('node','gpu_type','gpus','cpu'))
        assert a['ram']>=initial[k]['ram'] and a['rho']>=initial[k]['rho']-EPS
        if k in locks:assert a==initial[k]==locks[k]
    close(trace['added_ram'],math.fsum(out[k]['ram']-initial[k]['ram'] for k in ids))
    return dict(steps=len(trace['updates']),queries=queries,residual=0)
