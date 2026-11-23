"""Thin P-only user-name adapter; all old methods return the unchanged R2 class."""
from .placement_r2 import PlacementR2
from .methods_r3 import spec
def create_placement(*args,method,allocator_mode):
    contract=spec(method,allocator_mode)
    p=PlacementR2(*args,method='SIA-P' if method=='SIA-SMART-P' else method,allocator_mode=allocator_mode)
    if method=='SIA-SMART-P':
        p.method=method
        assert p.method_spec==contract
    return p
