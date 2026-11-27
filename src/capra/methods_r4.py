"""R4 protocol whitelist; all algorithms come unchanged from R3."""
from .methods_r3 import spec as r3_spec,engine
VERSIONS=('CAPRA_V2_PRESSURE_R4','CAPRA_V2_PRESSURE_R4_PREP')
METHODS=('SIA-SMART-P','CAPRA-FK','CAPRA')
def spec(method,mode):
    assert method in METHODS
    return r3_spec(method,mode)
