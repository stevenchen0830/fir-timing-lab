"""Bounded hierarchical mapping and register-only STA of the complete candidate.

The external SRAM timing contract is unresolved. Therefore no IO delay values
are invented and no full-design WNS/PPA pass is reported. Explicitly selected
register-to-register paths diagnose remaining *internal* setup bottlenecks.
"""
import argparse,hashlib,json,os,re,shutil,sys
from pathlib import Path
from generate_candidate import REPO,candidate
sys.path.insert(0,str(REPO/'experiments/sram_multirate'))
from build_integrated import generate
sys.path.insert(0,str(REPO/'experiments/fir_pipeline'))
from run_support import run_stage, copy_models, tool_identity
from buffer_fanout import buffer_module
YOSYS=os.environ.get('YOSYS','yosys')
OPENROAD=os.environ.get('OPENROAD','openroad')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=int,default=600)
    p.add_argument('--models',type=Path,required=True)
    p.add_argument('--exclude-cells',type=Path,default=REPO/'flow/tsmc90/excluded_cells.json')
    p.add_argument('--yosys',default=YOSYS);p.add_argument('--openroad',default=OPENROAD)
    a=p.parse_args();out=a.out.resolve()
    if out==REPO or REPO in out.parents:p.error('Keep mapped output and models outside the public repository')
    out.mkdir(parents=True,exist_ok=False)
    if ' ' in str(out):p.error('Use a no-space private output path')
    models=out/'models';model_hashes=copy_models(a.models,models,REPO)
    (out/'top.sv').write_text(generate());(out/'mac.sv').write_text(candidate(a.variant))
    shutil.copy2(REPO/'rtl/img_filter_def.v',out/'defines.v')
    sources=['defines.v','top.sv','mac.sv']
    for src in sorted((REPO/'experiments/sram_multirate/rtl').glob('*.sv')):
        if src.name=='fir_mac_narrow.sv':continue
        shutil.copy2(src,out/src.name);sources.append(src.name)
    excludes=json.loads(a.exclude_cells.read_text())
    (out/'excludes.json').write_text(json.dumps(excludes))
    (out/'synth.ys').write_text(f'''read_verilog -sv {' '.join(str(out/s) for s in sources)}
synth -top IMG_FILTER -noabc
dfflibmap -liberty {models}/slow.lib
abc -liberty {models}/slow.lib -D 1000 {' '.join('-dont_use '+s for s in excludes)}
clean -purge
delete t:$scopeinfo
read_liberty -lib {models}/slow.lib
check -assert
write_json {out}/mapped.json
''')
    rows=[];r={'status':'RUNNING','variant':a.variant,'scope':'full hierarchical FIR, selected core register paths ONLY',
        'clock':'ideal 1 ns, setup .15 ns, hold .03 ns','parasitics':'zero wire',
        'external_io':'UNCONSTRAINED / UNKNOWN; no SRAM timing budget invented',
        'mapping':'hierarchical, no input/carry sizing; NOT matched to the flattened single-lane screen',
        'stages':rows,'sources':{s:sha(out/s) for s in sources},'corners':{},
        'models':model_hashes,'exclude_cells_sha256':sha(out/'excludes.json'),
        'tools':{'yosys':tool_identity(a.yosys),'openroad':tool_identity(a.openroad)}}
    try:
        run_stage('synth',[a.yosys,'-s',str(out/'synth.ys')],out,a.timeout,dict(os.environ),rows)
        data=json.loads((out/'mapped.json').read_text());proofs={}
        for name,mod in data['modules'].items():
            if mod.get('attributes',{}).get('blackbox') and int(mod['attributes']['blackbox'],2):continue
            if 'clk' not in mod['ports']:raise ValueError('Review clock ports before buffering '+name)
            proofs[name]=buffer_module(mod,16)
        r['fanout_proofs']=proofs
        (out/'buffered.json').write_text(json.dumps(data))
        del data
        (out/'export.ys').write_text(f'''read_json {out}/buffered.json
check -assert
tee -o {out}/stat.json stat -json -liberty {models}/slow.lib
write_verilog -noattr -noexpr -nodec {out}/mapped.v
''')
        run_stage('export',[a.yosys,'-s',str(out/'export.ys')],out,180,dict(os.environ),rows)
        for corner in ('slow','typical','fast'):
            tcl=f'''set_thread_count 4
read_lef {models}/tech.lef
read_lef {models}/cells.lef
read_liberty {models}/{corner}.lib
read_verilog {out}/mapped.v
link_design IMG_FILTER
create_clock -name core -period 1.0 [get_ports clk]
set_clock_uncertainty -setup .150 [get_clocks core]
set_clock_uncertainty -hold .030 [get_clocks core]
puts CORE_ONLY_MAX
report_checks -path_group core -path_delay max -group_path_count 3 -format full_clock_expanded -digits 5
puts CORE_ONLY_MIN
report_checks -path_group core -path_delay min -group_path_count 3 -format full_clock_expanded -digits 5
puts COVERAGE_UNKNOWN_IO_RESET_PHASE_RC_NOT_QUALIFIED
report_design_area
puts FULL_CORE_SCREEN_DONE
'''
            (out/f'{corner}.tcl').write_text(tcl)
            run_stage('sta_'+corner,[a.openroad,'-no_init','-exit',str(out/f'{corner}.tcl')],out,180,dict(os.environ),rows)
            text=(out/f'sta_{corner}.log').read_text()
            if 'FULL_CORE_SCREEN_DONE' not in text or '[ERROR' in text:raise ValueError('Incomplete core report')
            values={}
            for kind,nxt in [('MAX','CORE_ONLY_MIN'),('MIN','COVERAGE_UNKNOWN')]:
                part=text.split('CORE_ONLY_'+kind+'\n')[1].split(nxt)[0]
                slacks=re.findall(r'(-?\d+\.\d+)\s+slack\s+\(',part)
                if not slacks:raise ValueError('No selected register paths; cannot call PASS')
                values[kind.lower()]=min(map(float,slacks))
            r['corners'][corner]=values;print(corner,values,flush=True)
        r['status']='FULL_CORE_SUBSET_SCREEN_COMPLETE_NOT_CLOSURE'
    except BaseException as e:r.update(status='FAILED_OR_BUDGET_STOP',error=str(e));raise
    finally:
        r['files']={f.name:sha(f) for f in out.iterdir() if f.is_file() and f.suffix in ('.sv','.ys','.tcl','.log','.resources')}
        (out/'summary.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
