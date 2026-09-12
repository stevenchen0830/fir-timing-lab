"""Independent transaction scoreboard for free-running arithmetic + credits."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from generate_candidate import candidate,HERE
TB=r'''`timescale 1ns/1ps
module tb;
reg clk=0;always #0.5 clk=~clk;
reg rst_n=0,iv=0,ready=0;
reg [499:0] x=0;reg [399:0] c=0;reg [49:0] e=0;
wire ir,ov;wire [9:0] y;
fir_mac_credit #(.LANES(1)) dut(clk,rst_n,iv,ir,x,c,e,ready,ov,y);
reg [9:0] expect_q[0:8191];integer wr=0,rd=0,checks=0,full_cycles=0;
integer weights[0:49];integer n,i,j,k,total,seed,dummy;
initial begin
  seed=12345;dummy=$urandom(seed);
  repeat(3) @(negedge clk);rst_n=1;
  for(n=0;n<6200;n=n+1) begin
    @(negedge clk);
    rst_n=!(n==40 || n==161 || n==953 || n==3071 || n==5980);
    ready=(n>=6000) ? 1 : ((n>=200 && n<450) ? 0 : $urandom_range(0,1));
    if(!iv || ir || !rst_n) begin
      iv=(n<6000) && ($urandom_range(0,99)<80);
      for(i=0;i<50;i=i+1) weights[i]=0;
      if(n%7==0) weights[n%50]=128;
      else for(j=0;j<128;j=j+1) begin k=$urandom_range(0,49);weights[k]=weights[k]+1;end
      total=0;
      for(i=0;i<50;i=i+1) begin
        e[i]=$urandom_range(0,4)!=0;
        x[i*10+:10]=(n%3==0)?1023:((n%3==1)?0:$urandom_range(0,1023));
        c[i*8+:8]=weights[i];
        if(e[i]) total=total+x[i*10+:10]*weights[i];else x[i*10+:10]=10'bx;
      end
    end
    @(posedge clk);
    if(!rst_n) begin wr=0;rd=0;end
    else begin
      if(!ir) full_cycles=full_cycles+1;
      if(ov && ready) begin
        if(rd==wr || y!==expect_q[rd]) $fatal(1,"CREDIT_DATA_ORDER cycle=%0d got=%h expected=%h",n,y,expect_q[rd]);
        rd=rd+1;checks=checks+1;
      end
      if(iv && ir) begin expect_q[wr]=(total+64)>>7;wr=wr+1;end
    end
  end
  #0.01;
  if(wr!=rd || ov || full_cycles==0) $fatal(1,"CREDIT_DRAIN_OR_COVERAGE");
  $display("CREDIT_GOLDEN_PASS checks=%0d full_cycles=%0d reset_positions=5",checks,full_cycles);
  $finish;
end
endmodule
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',default='deep32');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--onehot',action='store_true')
    p.add_argument('--negative',action='store_true',help='Inject invalid one-hot credit state; expect assertion failure')
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.negative and not a.onehot:p.error('--negative requires --onehot')
    (out/'dut.sv').write_text(candidate(a.variant)+'\n'+(HERE/('mac_credit_onehot.sv' if a.onehot else 'mac_credit.sv')).read_text())
    tb=TB.replace('    @(posedge clk);','    if(n==500) force dut.reserved_hot=0;\n    @(posedge clk);',1) if a.negative else TB
    (out/'tb.sv').write_text(tb);rows=[]
    for name,cmd in [('compile',['iverilog','-g2012','-DMULTIRATE_ASSERTIONS','-s','tb','-o',str(out/'sim'),str(out/'dut.sv'),str(out/'tb.sv')]),('run',['vvp',str(out/'sim')])]:
        with (out/(name+'.log')).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        rows.append({'name':name,'exit_code':r.returncode,'sha256':hashlib.sha256((out/(name+'.log')).read_bytes()).hexdigest()})
        if r.returncode:break
    ok=len(rows)==2 and all(r['exit_code']==0 for r in rows) and 'CREDIT_GOLDEN_PASS' in (out/'run.log').read_text()
    if a.negative:ok=len(rows)==2 and rows[0]['exit_code']==0 and rows[1]['exit_code']!=0 and 'CREDIT_ONEHOT_CORRUPTION' in (out/'run.log').read_text()
    result={'status':('EXPECTED_FAILURE_DETECTED' if a.negative else 'PASS') if ok else 'FAIL',
        'variant':a.variant,'onehot':a.onehot,'negative':a.negative,'rows':rows,
        'dut_sha256':hashlib.sha256((out/'dut.sv').read_bytes()).hexdigest()}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(not ok)
if __name__=='__main__':main()
