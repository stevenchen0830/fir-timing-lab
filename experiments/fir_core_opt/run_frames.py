"""Snapshot a full FIR candidate and run the existing strict frame suite.

Only the candidate MAC is substituted. The mathematical golden, transaction
controller, related-clock SRAM boundary and phase checks remain unchanged.
"""
import argparse,hashlib,json,shutil,subprocess,sys
from pathlib import Path
from generate_candidate import candidate,HERE,REPO
def make_snapshot(a):
    if a.onehot_credit:a.credit=True
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False);snap=out/'source'
    srcs=['rtl/img_filter.v','rtl/img_filter_def.v','verification/img_filter_tb.v']
    legacy=REPO/'experiments/sram_multirate'
    srcs += [str(f.relative_to(REPO)) for f in legacy.glob('*.py')]
    srcs += [str(f.relative_to(REPO)) for f in (legacy/'rtl').glob('*.sv')]
    srcs += ['experiments/sram_multirate/verification/striped_memory_model.svh']
    for name in srcs:
        dst=snap/name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(REPO/name,dst)
    target=snap/'experiments/sram_multirate/rtl/fir_mac_narrow.sv';target.write_text(candidate(a.variant))
    if a.credit:
        from integrate_credit import patch_generator
        dst=snap/'experiments/sram_multirate'
        shutil.copy2(HERE/('mac_credit_onehot.sv' if a.onehot_credit else 'mac_credit.sv'),dst/'rtl/mac_credit.sv')
        shutil.copy2(HERE/'integrate_credit.py',dst/'integrate_credit.py')
        gen=dst/'build_integrated.py';gen.write_text(patch_generator(gen.read_text()))
    manifest={'variant':a.variant,'scope':'complete generated FIR frame regression, not STA',
        'baseline_files':{name:hashlib.sha256((REPO/name).read_bytes()).hexdigest() for name in srcs},
        'candidate_mac_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'credit_shell':a.credit,
        'onehot_credit':a.onehot_credit,
        'snapshot_files':{str(p.relative_to(snap)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in snap.rglob('*') if p.is_file()}}
    (out/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return out,snap

def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--engine',choices=['iverilog','verilator'],default='verilator')
    p.add_argument('--suite',choices=['quick','smoke','full'],default='full')
    p.add_argument('--verilator',default='verilator')
    p.add_argument('--credit',action='store_true',help='Experimental free-running MAC with reserved output credits')
    p.add_argument('--onehot-credit',action='store_true')
    a=p.parse_args();out,snap=make_snapshot(a)
    cmd=[sys.executable,str(snap/'experiments/sram_multirate/run_integrated.py'),
         '--output',str(out/'run'),'--engine',a.engine,'--suite',a.suite,'--verilator',a.verilator]
    try:
        r=subprocess.run(cmd,timeout=1900)
    finally:
        # Some WSL setups mount /tmp on a volatile filesystem. Archive before
        # this process exits, not in a later WSL invocation. Separate per-run
        # directories avoid concurrent writers racing over one summary.
        archive=out/'evidence';archive.mkdir(parents=True,exist_ok=True)
        for name in ('summary.json','frames.log'):
            source=out/'run'/name
            if source.exists():shutil.copy2(source,archive/name)
        shutil.copy2(out/'source_manifest.json',archive/'source_manifest.json')
    if r.returncode:raise SystemExit(r.returncode)
    print((out/'run/summary.json').read_text())
if __name__=='__main__':main()
