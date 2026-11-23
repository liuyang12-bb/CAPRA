"""Frozen method contracts; proportional is real quotas, never neutral response."""
SPECS={
 'SIA-P':(('P',),'proportional'),
 'CAPRA-Fixed':(('F',),'optimized'),
 'SIA-P-K':(('F','K'),'proportional'),
 'CAPRA-FK':(('F','K'),'optimized'),
 'CAPRA':(('F','K','R'),'optimized')}
def spec(method,allocator_mode):
    labels,quota=SPECS[method]
    assert allocator_mode in ('none','legacy','ram_slack_v1')
    assert (allocator_mode=='none')==(quota=='proportional')
    return dict(candidate_labels=list(labels),quota_mode=quota,allocator_mode=allocator_mode,ram_repair_enabled=allocator_mode=='ram_slack_v1')
