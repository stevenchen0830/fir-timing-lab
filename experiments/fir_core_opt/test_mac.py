"""Four-state independent MAC golden model, randomized stalls/reset/X masking."""
import argparse,hashlib,json,subprocess,time
from pathlib import Path
from generate_candidate import candidate

TB=r'''`timescale 1ns/1ps
module tb;
reg clk=0;always #0.5 clk=~clk;
reg rst_n=0,advance=0,in_valid=0;
reg [499:0] data;
reg [399:0] coef;
reg [49:0] en;
wire valid;wire [9:0] result;
fir_mac_narrow #(.LANES(1)) dut(clk,rst_n,advance,in_valid,data,coef,en,valid,result);
localparam integer LATENCY=LAT_VALUE;
reg [9:0] expected[0:LATENCY-1];reg [LATENCY-1:0] v;
integer i,j,k,cycle,total,checks,seed,dummy;integer weights[0:49];
initial begin
  seed=12345;dummy=$urandom(seed);v=0;checks=0;data=0;coef=0;en=0;
  repeat(3) @(negedge clk);rst_n=1;
  for(cycle=0;cycle<6000;cycle=cycle+1) begin
    @(negedge clk);
    rst_n= !(cycle==40 || cycle==161 || cycle==953 || cycle==3071 || cycle==5980);
    advance=cycle>5960 ? 1 : ($urandom_range(0,99)>=30);
    in_valid=cycle<5960 && ($urandom_range(0,99)<80);
    for(i=0;i<50;i=i+1) weights[i]=0;
    // Includes coefficient 128, zero/maximum pixels and scattered bank enables.
    if(cycle%7==0) weights[cycle%50]=128;
    else for(j=0;j<128;j=j+1) begin k=$urandom_range(0,49);weights[k]=weights[k]+1;end
    total=0;
    for(i=0;i<50;i=i+1) begin
      en[i]=$urandom_range(0,4)!=0;
      data[i*10+:10]=(cycle%3==0)?1023:((cycle%3==1)?0:$urandom_range(0,1023));
      coef[i*8+:8]=weights[i];
      if(en[i]) total=total+data[i*10+:10]*weights[i];
      else data[i*10+:10]=10'bx;
    end
    @(posedge clk);
    if(!rst_n) v=0;
    else if(advance) begin
      for(i=LATENCY-1;i>0;i=i-1) expected[i]=expected[i-1];
      expected[0]=(total+64)>>7;
      v={v[LATENCY-2:0],in_valid};
    end
    #0.01;
    if(valid!==v[LATENCY-1]) $fatal(1,"VALID_ALIGNMENT cycle=%0d",cycle);
    if(valid) begin
      if(result!==expected[LATENCY-1]) $fatal(1,"MAC_MISMATCH cycle=%0d got=%h expected=%h",cycle,result,expected[LATENCY-1]);
      checks=checks+1;
    end
  end
  $display("MAC_GOLDEN_PASS cycles=6000 checks=%0d reset_positions=5",checks);$finish;
end
endmodule
'''
def main():
    p=argparse.ArgumentParser();p.add_argument('--variant',required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--latency',type=int,default=9);a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    (out/'dut.sv').write_text(candidate(a.variant));(out/'tb.sv').write_text(TB.replace('LAT_VALUE',str(a.latency)))
    start=time.monotonic();rows=[]
    for name,cmd in [('compile',['iverilog','-g2012','-s','tb','-o',str(out/'sim'),str(out/'dut.sv'),str(out/'tb.sv')]),('run',['vvp',str(out/'sim')])]:
        with (out/(name+'.log')).open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,timeout=180)
        rows.append({'name':name,'exit_code':r.returncode,'sha256':hashlib.sha256((out/(name+'.log')).read_bytes()).hexdigest()})
        if r.returncode:break
    ok=all(r['exit_code']==0 for r in rows) and len(rows)==2 and 'MAC_GOLDEN_PASS' in (out/'run.log').read_text()
    result={'variant':a.variant,'status':'PASS' if ok else 'FAIL','latency_enabled_cycles':a.latency,
            'dut_sha256':hashlib.sha256((out/'dut.sv').read_bytes()).hexdigest(),'rows':rows,'wall_seconds':time.monotonic()-start}
    (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result));raise SystemExit(0 if ok else 1)
if __name__=='__main__':main()
