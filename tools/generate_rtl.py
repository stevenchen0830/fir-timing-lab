"""Generate exactly the same candidate snapshot used by the frame runner."""
import argparse, hashlib, importlib.util, json, shutil, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/fir_core_opt'))
from run_frames import make_snapshot

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--variant',required=True)
    p.add_argument('--credit',action='store_true');p.add_argument('--onehot-credit',action='store_true')
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out,snap=make_snapshot(a)
    module_dir=snap/'experiments/sram_multirate'
    sys.path.insert(0,str(module_dir))
    spec=importlib.util.spec_from_file_location('snapshot_integrated',module_dir/'build_integrated.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    (out/'top.sv').write_text(module.generate())
    shutil.copy2(snap/'rtl/img_filter_def.v',out/'defines.v')
    files=[out/'defines.v',out/'top.sv']
    for source in sorted((module_dir/'rtl').glob('*.sv')):
        shutil.copy2(source,out/source.name);files.append(out/source.name)
    (out/'rtl.f').write_text(''.join(str(f)+'\n' for f in files))
    manifest=json.loads((out/'source_manifest.json').read_text())
    manifest['generated_files']={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
    (out/'source_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('RTL_GENERATED '+str(out/'rtl.f'))
if __name__=='__main__':main()

