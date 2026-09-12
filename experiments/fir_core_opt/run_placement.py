"""Bounded same-floorplan MAC placement sensitivity test, NOT physical signoff.

Uses vendor LEF's deliberately conservative RC estimates. No clock tree,
macro, routing, SPEF, resize or timing repair is included.
"""
import argparse, hashlib, json, os, re, shutil, sys
from pathlib import Path
from generate_candidate import REPO
sys.path.insert(0,str(REPO/'experiments/fir_pipeline'))
from run_support import run_stage, copy_models, tool_identity
OPENROAD=os.environ.get('OPENROAD','openroad')

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=int,default=420)
    p.add_argument('--openroad',default=OPENROAD)
    p.add_argument('--condition-wires',action='store_true',help='One bounded electrical/100um wire repair, not setup/hold repair')
    a=p.parse_args();out=a.out.resolve()
    if out==REPO or REPO in out.parents:p.error('Keep physical outputs/models outside the public repository')
    out.mkdir(parents=True,exist_ok=False)
    if ' ' in str(out):p.error('Use a no-space private output path')
    source=a.source.resolve();models=out/'models';copy_models(source/'models',models,REPO)
    shutil.copy2(source/'mapped.v',out/'mapped.v')
    # Exactly retain the source screen's clock, absolute IO delays and loads.
    sdc=(source/'slow.tcl').read_text().split('create_clock',1)[1].split('puts SECTION_SETUP',1)[0]
    sdc='create_clock'+sdc
    sdc=sdc.replace('report_design_area','')
    (out/'constraint.sdc').write_text(sdc)
    config={'core_um':[10,10,1610,1610],'die_um':[0,0,1620,1620],
        'density':.45,'seed':42,'threads':4,'signal_layer':'M2','clock_layer':'M3',
        'wire_conditioning':a.condition_wires}
    conditioning='''estimate_parasitics -placement
repair_design -max_wire_length 100 -max_utilization 45
detailed_placement
check_placement -verbose
''' if a.condition_wires else ''
    tcl=f'''set_thread_count 4
read_lef {models}/tech.lef
read_lef {models}/cells.lef
read_liberty {models}/slow.lib
read_verilog {out}/mapped.v
link_design MAC_SCREEN
read_sdc {out}/constraint.sdc
initialize_floorplan -site TSM90NMSITE -die_area {{0 0 1620 1620}} -core_area {{10 10 1610 1610}}
make_tracks
set_wire_rc -signal -layer M2
set_wire_rc -clock -layer M3
place_pins -hor_layers M3 -ver_layers M2
write_db {out}/floorplan.odb
global_placement -density .45 -random_seed 42 -overflow .1
write_db {out}/global_place.odb
detailed_placement
check_placement -verbose
{conditioning}
write_db {out}/placed.odb
write_def {out}/placed.def
write_verilog {out}/placed.v
report_design_area
puts PLACEMENT_ONLY_DONE
'''
    (out/'place.tcl').write_text(tcl)
    rows=[];r={'status':'RUNNING','scope':'MAC_SCREEN one lane only; fixed common floorplan',
        'parasitics':'LEF coarse conservative RC, placement estimate; no extracted SPEF',
        'clock':'ideal; NO CTS','config':config,'source':str(source),
        'netlist_sha256':sha(out/'mapped.v'),'sdc_sha256':sha(out/'constraint.sdc'),
        'tool':tool_identity(a.openroad),
        'models':{p.name:sha(p) for p in models.glob('*') if p.is_file()},'stages':rows,'corners':{}}
    try:
        run_stage('place',[a.openroad,'-no_init','-exit',str(out/'place.tcl')],out,a.timeout,dict(os.environ),rows)
        if 'PLACEMENT_ONLY_DONE' not in (out/'place.log').read_text():raise ValueError('Missing placement marker')
        for corner in ('slow','typical','fast'):
            # Read the identical placed database independently for every PVT.
            report=(source/f'{corner}.tcl').read_text().split('puts SECTION_SETUP',1)[1]
            script=f'''set_thread_count 4
read_liberty {models}/{corner}.lib
read_db {out}/placed.odb
read_sdc {out}/constraint.sdc
set_wire_rc -signal -layer M2
set_wire_rc -clock -layer M3
estimate_parasitics -placement
puts SECTION_SETUP
'''+report
            (out/f'{corner}.tcl').write_text(script)
            run_stage('sta_'+corner,[a.openroad,'-no_init','-exit',str(out/f'{corner}.tcl')],out,120,dict(os.environ),rows)
            txt=(out/f'sta_{corner}.log').read_text()
            if 'MAC_SCREEN_DONE' not in txt or '[ERROR' in txt:raise ValueError('Incomplete timing report')
            metrics={}
            for kind,nxt in [('SETUP','HOLD'),('HOLD','PATHS')]:
                section=txt.split('SECTION_'+kind+'\n')[1].split('SECTION_'+nxt)[0]
                vals=re.findall(r'(?:worst slack|tns)\s+(?:max\s+|min\s+)?(-?[0-9.]+)',section)
                if len(vals)!=2:raise ValueError('Incomplete timing metrics')
                metrics[kind.lower()]=list(map(float,vals))
            r['corners'][corner]=metrics;print(corner,metrics,flush=True)
        r['status']='EARLY_PLACEMENT_COMPLETE_NOT_SIGNOFF'
    except BaseException as e:r.update(status='FAILED_OR_BUDGET_STOP',error=str(e));raise
    finally:
        r['files']={p.name:sha(p) for p in out.iterdir() if p.is_file() and p.suffix in ('.tcl','.sdc','.log','.resources')}
        (out/'summary.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
