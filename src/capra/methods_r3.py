"""R3 explicit method/engine whitelist; no global smart flag."""
from .methods_r2 import spec as old_spec
VERSIONS=('CAPRA_V2_SMART_R3','CAPRA_V2_HOLDOUT_R3','CAPRA_V2_SMART_R3_PREP','CAPRA_V2_HOLDOUT_R3_PREP')
METHODS=('SIA-SMART-P','SIA-P-K','CAPRA-FK','CAPRA')
def spec(method,mode):
    assert method in METHODS
    assert mode==('none' if method in ('SIA-SMART-P','SIA-P-K') else 'ram_slack_v1')
    return old_spec('SIA-P' if method=='SIA-SMART-P' else method,mode)
def engine(method):
    assert method in METHODS
    return 'sia_smart_adapted_v1' if method=='SIA-SMART-P' else 'sia_fast_original'
