#!/usr/bin/env python3
"""Bounded complete-frame regression of the generated multirate FIR."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from build_integrated import generate,HERE,REPO

def build_tb():
    tb=(REPO/'verification/img_filter_tb.v').read_text()
    a=tb.index('    wire [NBK-1:0]     mem_ce;')
    b=tb.index('    IMG_FILTER u_dut',a)
    tb=tb[:a]+'''    wire mem_clk;
    wire [195:0] mem_ce,mem_we;
    wire [27:0] mem_addr;
    wire [639:0] mem_wdata;
    reg [31359:0] mem_rdata;
'''+tb[b:]
    tb=tb.replace('.rst_n       (rst_n),','.arst_n      (rst_n),\n        .mem_clk     (mem_clk),')
    a=tb.index('    reg [DW-1:0] sram ')
    b=tb.index('    //-----------------------------------------------------------------------\n    // Frame state',a)
    tb=tb[:a]+(HERE/'verification/striped_memory_model.svh').read_text()+'\n'+tb[b:]
    marker='    //-----------------------------------------------------------------------\n    initial begin\n        seed ='
    task='''    task abort_and_recover;
        input integer delay_cycles;
        integer z;
        begin
            W=28;H=24;BV=3;HV=1;NB=7;
            make_coef(3);
            for(z=0;z<672;z=z+1) img[z]=0;
            o_row=0;o_beat=0;o_cnt=0;first_out_cycle=-1;
            @(negedge clk);
            frm_start=1;img_width=27;img_height=23;blk_v=3;coef=coef_v;
            @(negedge clk);frm_start=0;
            in_pix_rdy=1;in_pix_data=0;out_pix_need=0;
            repeat(delay_cycles) @(negedge clk);
            #0.2;rst_n=0;in_pix_rdy=0;out_pix_need=0;
            repeat(4) @(negedge clk);
            #0.1;rst_n=1;
            repeat(8) @(negedge clk);
            if(out_pix_rdy!==0 || u_dut.tx_occupancy!==0 || u_dut.ret_valid!==0)
                $fatal(1,"RESET_STALE_TRANSACTION");
            run_frame(28,25,5,20,30,1);
            $display("RESET_RECOVERY_PASS offset=%0d",delay_cycles);
        end
    endtask
    always @(posedge clk) begin
        if(rst_n && in_gap==0 && out_gap==0 && o_cnt>0 && o_cnt<H*NB && out_pix_need && !out_pix_rdy)
            $fatal(1,"UNEXPECTED_OUTPUT_BUBBLE");
    end
'''
    assert marker in tb
    tb=tb.replace(marker,task+marker)
    # Leave the mathematical golden and original protocol checks unchanged.
    marker='        if ($test$plusargs("H4096_ONLY")) begin'
    tb=tb.replace(marker,'''        if($test$plusargs("RESET_SWEEP")) begin
            abort_and_recover(4);abort_and_recover(20);abort_and_recover(60);
            abort_and_recover(100);abort_and_recover(200);
        end
        if ($test$plusargs("QUICK")) begin
            run_frame(28,24,3,0,0,0);
        end else '''+marker.strip())
    marker='        $display(\n"== %0d frames'
    tb=tb.replace(marker,'''        if($test$plusargs("ALL_KERNELS")) begin
            for(integer kernel=1;kernel<=49;kernel=kernel+2) begin
                run_frame(24,24,kernel,0,0,0);
                run_frame(27,25,kernel,25,35,1);
                run_frame(1440,24,kernel,0,0,0);
            end
            if(cov_blk_v!==50'h2aaaaaaaaaaaa) $fatal(1,"KERNEL_COVERAGE_MISSING");
        end
        $display("BOUNDARY checks=%0d command_checks=%0d",clock_checks,command_checks);
'''+marker)
    return tb

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--engine',choices=('verilator','iverilog'),default='verilator')
    p.add_argument('--verilator',default='verilator');p.add_argument('--suite',choices=('quick','smoke','full'),default='quick')
    p.add_argument('--negative',action='store_true');p.add_argument('--timeout',type=int,default=900)
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=False)
    top=out/'img_filter_multirate.sv';top.write_text(generate())
    tb=out/'tb.sv';tb.write_text(build_tb())
    src=[top,tb,*sorted((HERE/'rtl').glob('*.sv'))]
    inputs=[Path(__file__),HERE/'build_integrated.py',REPO/'rtl/img_filter.v',REPO/'verification/img_filter_tb.v',
            HERE/'verification/striped_memory_model.svh',*sorted((HERE/'rtl').glob('*.sv'))]
    meta={'status':'RUNNING','engine':a.engine,'suite':a.suite,'physical_status':'NOT_RUN',
          'sources':{str(f.relative_to(REPO)):hashlib.sha256(f.read_bytes()).hexdigest() for f in inputs},
          'generated':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in (top,tb)},'commands':[]}
    def save(): (out/'summary.json').write_text(json.dumps(meta,indent=2)+'\n')
    def run(name,cmd,marker=None,negative=False):
        save();start=time.monotonic();log=out/(name+'.log')
        with log.open('w') as f:
            proc=subprocess.Popen([str(x) for x in cmd],cwd=REPO,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
            timed_out=False
            try:proc.wait(timeout=a.timeout)
            except subprocess.TimeoutExpired:
                timed_out=True;os.killpg(proc.pid,signal.SIGTERM)
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL);proc.wait()
        txt=log.read_text(errors='replace')
        ok=(proc.returncode!=0 if negative else proc.returncode==0) and not timed_out
        if marker:ok=ok and marker in txt
        meta['commands'].append({'name':name,'argv':[str(x) for x in cmd],'exit_code':proc.returncode,
            'timeout':timed_out,'seconds':time.monotonic()-start,'pass':ok,'sha256':hashlib.sha256(log.read_bytes()).hexdigest()})
        save();print(name+': '+str(ok),flush=True)
        if not ok:raise RuntimeError('Inspect '+str(log))
        return txt
    try:
        files=[REPO/'rtl/img_filter_def.v',*src]
        if a.engine=='iverilog':
            run('compile',['iverilog','-g2012','-DMULTIRATE_ASSERTIONS','-s','img_filter_tb','-o',out/'tb.vvp',*files])
            exe=['vvp',out/'tb.vvp']
        else:
            run('compile',[a.verilator,'--binary','--timing','-j','2','-Wno-fatal','-DMULTIRATE_ASSERTIONS',
                '-I'+str(REPO/'rtl'),'--top-module','img_filter_tb','--Mdir',out/'obj',*files])
            exe=[out/'obj/Vimg_filter_tb']
        args={'quick':['+QUICK'],'smoke':['+SMOKE'],'full':['+ALL_KERNELS','+RESET_SWEEP']}[a.suite]
        if a.negative:args+=['+SLOW_DATA']
        txt=run('frames',exe+args,'TEST FAILED' if a.negative else 'TEST PASSED',a.negative)
        m=re.search(r'== (\d+) frames, (\d+) component checks, (\d+) errors',txt)
        if not m:raise RuntimeError('Missing frame summary')
        meta['frames']=int(m[1]);meta['checks']=int(m[2]);meta['errors']=int(m[3])
        expected={'quick':1,'smoke':13,'full':134}[a.suite]
        if int(m[1])!=expected or (not a.negative and int(m[3])):raise RuntimeError('Frame gate')
        meta['status']='EXPECTED_TIMING_MODEL_FAILURE' if a.negative else 'FRAME_FUNCTIONAL_PASS_NOT_STA'
    except BaseException as e:meta.update(status='FAILED',error=str(e));raise
    finally:save()
if __name__=='__main__':main()
