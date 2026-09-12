"""Reproducible private matched MAC screen, not complete FIR PPA/signoff."""
import argparse,hashlib,json,os,re,shutil,sys
from pathlib import Path
from generate_candidate import candidate,HERE,REPO
from input_drive import boost,size_carry_cones
sys.path.insert(0,str(REPO/'experiments/fir_pipeline'))
from buffer_fanout import buffer_module
from run_support import run_stage, copy_models, tool_identity
YOSYS=os.environ.get('YOSYS','yosys')
OPENROAD=os.environ.get('OPENROAD','openroad')
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',required=True)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--lanes',type=int,default=1)
    p.add_argument('--nostall',action='store_true',help='Separate free-running diagnostic, not a compatible stalled MAC')
    p.add_argument('--credit',action='store_true',help='Include actual reserved-credit FIFO, not just tie advance high')
    p.add_argument('--onehot-credit',action='store_true')
    p.add_argument('--input-cell',choices=['DFFQX1','DFFQX2','DFFQX4'])
    p.add_argument('--reuse-mapped',type=Path)
    p.add_argument('--abc-target-ps',type=int,default=1000)
    p.add_argument('--abc-load-ff',type=float)
    p.add_argument('--carry-sizing',action='store_true')
    p.add_argument('--models',type=Path,required=True,help='Authorized matching private models outside repository')
    p.add_argument('--exclude-cells',type=Path,default=REPO/'flow/tsmc90/excluded_cells.json')
    p.add_argument('--yosys',default=YOSYS);p.add_argument('--openroad',default=OPENROAD)
    a=p.parse_args();out=a.out.resolve()
    if out==REPO or REPO in out.parents:p.error('Keep vendor models and mapped outputs outside the public repository')
    out.mkdir(parents=True,exist_ok=False)
    if a.onehot_credit:a.credit=True
    if a.nostall and a.credit:p.error('Choose diagnostic nostall or real credit shell, not both')
    if a.lanes<1:p.error('Positive lane count required')
    if ' ' in str(out):raise ValueError('Use an isolated no-space output path')
    models=out/'models';model_hashes=copy_models(a.models,models,REPO)
    expected={'fast.lib':'8ee6e41473acd3e875b8d1473185bedc5d78564a4d56001a8af8f04658f75b82',
        'slow.lib':'c6dc5053db819a3deff380003ac0d0eae695c22b19e5461563e41fe9fc2b41ca',
        'typical.lib':'f79391e02ee6a159c42428d7276ce9bdaea063090a153b6a9a650cff0f7146e5'}
    for n,h in expected.items():
        if digest(models/n)!=h:raise ValueError('LIBRARY_CHANGED '+n)
    excludes=json.loads(a.exclude_cells.read_text())
    (out/'excludes.json').write_text(json.dumps(excludes))
    lanes=a.lanes;dw=500*lanes;ow=10*lanes
    advance_port='.in_ready(in_ready),.out_ready(advance_q),' if a.credit else '.advance('+ ("1'b1" if a.nostall else 'advance_q') +'),'
    wrapper=f'''module MAC_SCREEN(input clk,rst_n,advance,in_valid,input [{dw-1}:0] x,input [399:0] c,input [49:0] e,
output reg [{ow-1}:0] out,output reg out_valid{',output wire in_ready' if a.credit else ''});
reg [{dw-1}:0] xq;reg [399:0] cq;reg [49:0] eq;reg advance_q,valid_q;
always @(posedge clk) begin xq<=x;cq<=c;eq<=e;advance_q<=advance;valid_q<=in_valid;end
wire [{ow-1}:0] y;wire v;
{'fir_mac_credit' if a.credit else 'fir_mac_narrow'} #(.LANES({lanes})) u(.clk(clk),.rst_n(rst_n),{advance_port}
 .in_valid(valid_q),.tap_data(xq),.tap_coef(cq),.tap_enable(eq),.out_valid(v),.result(y));
always @(posedge clk) if({"1'b1" if a.nostall else "advance_q"}) begin out<=y;out_valid<=v;end
endmodule
'''
    credit_file=HERE/('mac_credit_onehot.sv' if a.onehot_credit else 'mac_credit.sv')
    (out/'dut.sv').write_text(candidate(a.variant)+'\n'+(credit_file.read_text() if a.credit else '')+'\n'+wrapper)
    rows=[];result={'status':'RUNNING','variant':a.variant,'lanes':lanes,'nostall_diagnostic':a.nostall,
       'scope':'registered-input MAC only; ideal clock and zero interconnect; NOT WHOLE FIR',
       'period_ns':1,'uncertainty_ns':[.15,.03],'input_delay_ns':[.1,.05],'output_delay_ns':[.1,-.05],
       'activity':.1,'load_pf':.01,'slew_ns':.1,'sources':{str(x):digest(x) for x in [Path(__file__),HERE/'generate_candidate.py',*sorted(HERE.glob('*.sv'))]},
       'dut_sha256':digest(out/'dut.sv'),'models':{n:digest(models/n) for n in expected},'stages':rows,'corners':{},
       'abc_target_ps':a.abc_target_ps,'abc_load_ff':a.abc_load_ff}
    result['credit_shell']=a.credit
    result['onehot_credit']=a.onehot_credit
    result['exclude_cells_sha256']=digest(out/'excludes.json')
    result['tools']={'yosys':tool_identity(a.yosys),'openroad':tool_identity(a.openroad)}
    result['all_model_hashes']=model_hashes
    snapshot=out/'runner-source';snapshot.mkdir()
    for f in [*HERE.glob('*.py'),*HERE.glob('*.sv')]:shutil.copy2(f,snapshot/f.name)
    for name in ('buffer_fanout.py',):
        shutil.copy2(REPO/'experiments/fir_pipeline'/name,snapshot/name)
    result['runner_snapshot']={f.name:digest(f) for f in snapshot.iterdir()}
    def save():(out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    try:
        abc_options=''
        if a.abc_load_ff is not None:
            (out/'abc.constr').write_text(f'set_driving_cell BUFX8\nset_load {a.abc_load_ff}\n')
            abc_options=f'-constr {out}/abc.constr'
        (out/'synth.ys').write_text(f'''read_verilog -sv {out}/dut.sv
synth -top MAC_SCREEN -flatten -noabc
dfflibmap -liberty {models}/slow.lib
abc -liberty {models}/slow.lib -D {a.abc_target_ps} {abc_options} {' '.join('-dont_use '+n for n in excludes)}
clean -purge
delete t:$scopeinfo
read_liberty -lib {models}/slow.lib
check -assert
write_json {out}/mapped.json
''')
        save()
        if a.reuse_mapped:
            prior=json.loads((a.reuse_mapped/'summary.json').read_text())
            fields=('dut_sha256','models','abc_target_ps','abc_load_ff','exclude_cells_sha256','tools')
            if any(prior.get(k)!=result[k] for k in fields):
                raise ValueError('Refuse stale mapping reuse')
            shutil.copy2(a.reuse_mapped/'mapped.json',out/'mapped.json')
            result['reused_mapping']={'path':str(a.reuse_mapped),'sha256':digest(out/'mapped.json')}
        else:run_stage('synth',[a.yosys,'-s',str(out/'synth.ys')],out,600,dict(os.environ),rows)
        data=json.loads((out/'mapped.json').read_text())
        if a.input_cell:result['input_sizing']=boost(data['modules']['MAC_SCREEN'],models,a.input_cell)
        if a.carry_sizing:result['carry_sizing']=size_carry_cones(data['modules']['MAC_SCREEN'],models)
        result['buffer_proof']=buffer_module(data['modules']['MAC_SCREEN'],16)
        (out/'buffered.json').write_text(json.dumps(data))
        (out/'export.ys').write_text(f'''read_json {out}/buffered.json
check -assert
tee -o {out}/stat.json stat -json -liberty {models}/slow.lib
write_verilog -noattr -noexpr -nodec {out}/mapped.v
''')
        run_stage('export',[a.yosys,'-s',str(out/'export.ys')],out,120,dict(os.environ),rows)
        for corner in ('slow','typical','fast'):
            tcl=f'''read_lef {models}/tech.lef
read_lef {models}/cells.lef
read_liberty {models}/{corner}.lib
read_verilog {out}/mapped.v
link_design MAC_SCREEN
create_clock -name core -period 1.0 [get_ports clk]
set_clock_uncertainty -setup .150 [get_clocks core]
set_clock_uncertainty -hold .030 [get_clocks core]
set_input_delay -clock core -max .100 [get_ports {{x[*] c[*] e[*] advance in_valid rst_n}}]
set_input_delay -clock core -min .050 [get_ports {{x[*] c[*] e[*] advance in_valid rst_n}}]
set_output_delay -clock core -max .100 [all_outputs]
set_output_delay -clock core -min -.050 [all_outputs]
set_input_transition .100 [all_inputs]
set_load .010 [all_outputs]
report_design_area
puts SECTION_SETUP
report_worst_slack -max -digits 5
report_tns -max -digits 5
puts SECTION_HOLD
report_worst_slack -min -digits 5
report_tns -min -digits 5
puts SECTION_PATHS
report_checks -path_delay min_max -group_path_count 3 -format full_clock_expanded -digits 5
puts SECTION_DRV
report_check_types -max_slew -max_capacitance -max_fanout -violators
puts SECTION_POWER
set_power_activity -input -activity .1 -duty .5 -clock core
set_power_activity -global -activity .1 -duty .5 -clock core
report_power
puts MAC_SCREEN_DONE
'''
            (out/f'{corner}.tcl').write_text(tcl)
            run_stage('sta_'+corner,[a.openroad,'-no_init','-exit',str(out/f'{corner}.tcl')],out,120,dict(os.environ),rows)
            text=(out/f'sta_{corner}.log').read_text()
            if 'MAC_SCREEN_DONE' not in text or '[ERROR' in text:raise ValueError('STA incomplete')
            m={}
            for kind,nxt in [('SETUP','HOLD'),('HOLD','PATHS')]:
                part=text.split('SECTION_'+kind+'\n')[1].split('SECTION_'+nxt)[0]
                values=re.findall(r'(?:worst slack|tns)\s+(?:max\s+|min\s+)?(-?[0-9.]+)',part)
                if len(values)!=2:raise ValueError('Missing timing metrics')
                m[kind.lower()]=list(map(float,values))
            result['corners'][corner]=m;save();print(corner,m,flush=True)
        result['status']='SCREEN_COMPLETE_NOT_PHYSICAL_CLOSURE'
        result['all_corner_setup_pass']=all(c['setup'][0]>=0 for c in result['corners'].values())
        result['files']={f.name:digest(f) for f in out.iterdir() if f.is_file() and f.suffix in ('.sv','.ys','.tcl','.v','.log','.resources')}
    except BaseException as exc:result.update(status='FAILED_OR_BUDGET_STOP',error=str(exc));raise
    finally:save()
if __name__=='__main__':main()
