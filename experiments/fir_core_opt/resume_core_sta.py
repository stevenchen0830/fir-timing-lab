"""Resume saved full netlist with path-group queries, avoiding huge register lists."""
import argparse,hashlib,json,os,sys
from pathlib import Path
from generate_candidate import REPO
sys.path.insert(0,str(REPO/'experiments/fir_pipeline'))
from run_support import run_stage
OPENROAD=os.environ.get('OPENROAD','openroad')
def main():
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--openroad',default=OPENROAD)
    a=p.parse_args();out=a.out.resolve()
    if out==REPO or REPO in out.parents:p.error('Keep vendor-derived STA reports outside the public repository')
    out.mkdir(parents=True,exist_ok=False);src=a.source.resolve()
    rows=[];r={'status':'RUNNING','scope':'core clock path group; IO remains intentionally UNVERIFIED, not signoff',
        'source':str(src),'netlist_sha256':hashlib.sha256((src/'mapped.v').read_bytes()).hexdigest(),'stages':rows}
    try:
        for corner in ('slow','typical','fast'):
            template=(src/'slow.tcl').read_text().replace('/slow.lib',f'/{corner}.lib')
            template=template.replace('-from [all_registers] -to [all_registers]','-path_group core')
            (out/f'{corner}.tcl').write_text(template)
            run_stage('sta_'+corner,[a.openroad,'-no_init','-exit',str(out/f'{corner}.tcl')],out,120,dict(os.environ),rows)
            text=(out/f'sta_{corner}.log').read_text()
            if 'FULL_CORE_SCREEN_DONE' not in text or '[ERROR' in text:raise ValueError('Incomplete STA')
        r['status']='CORE_GROUP_REPORTS_COMPLETE_NOT_FULL_COVERAGE'
    except BaseException as e:r.update(status='FAILED_OR_BUDGET_STOP',error=str(e));raise
    finally:(out/'summary.json').write_text(json.dumps(r,indent=2)+'\n')
if __name__=='__main__':main()
