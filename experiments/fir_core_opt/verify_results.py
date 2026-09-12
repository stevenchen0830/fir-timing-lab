"""Read-only, fail-closed checks of recorded evidence and claim boundaries."""
import hashlib,json
from generate_candidate import HERE,REPO
def main():
    root=HERE/'results';count=0
    for line in (root/'manifest.sha256').read_text().splitlines():
        expected,name=line.split('  ',1);p=root/name
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:raise ValueError('Evidence hash mismatch '+name)
        count+=1
    if hashlib.sha256((REPO/'rtl/img_filter.v').read_bytes()).hexdigest()!='b1ffeaf5fccad2442519b58076420b3a723d9c800e29ad7f26974ca817566283':
        raise ValueError('Frozen v4 RTL changed')
    rows={r['run']:r for r in json.loads((root/'screen_summary.json').read_text())['rows']}
    assert rows['deep32']['all_corner_setup_pass']
    assert rows['deep32']['corners']['fast']['hold'][0]<0
    assert rows['place-deep32-v3']['corners']['slow']['setup'][0]<0
    assert rows['full-core-group-sta']['core_group_setup_sample_ns']['slow']<0
    for name in ('test-prefix','test-segmented','test-mask','test-deep32','test-credit','test-credit-onehot'):
        assert json.loads((root/name/'summary.json').read_text())['status']=='PASS',name
    assert json.loads((root/'test-credit-negative/summary.json').read_text())['status']=='EXPECTED_FAILURE_DETECTED'
    for name in ('fir-core-opt-segmented-full-20260912','fir-core-opt-deep32-full-20260912',
                 'fir-core-opt-credit-onehot-full-20260912'):
        data=json.loads((root/name/'summary.json').read_text())
        assert data['status']=='FRAME_FUNCTIONAL_PASS_NOT_STA' and data['frames']==134 and data['errors']==0,name
    print(f'EVIDENCE_PASS files={count}; three full-frame candidates PASS; WHOLE_FIR_1GHZ=NOT_CLOSED')
if __name__=='__main__':main()
