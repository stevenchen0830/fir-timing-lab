"""Independent candidates; never overwrite the previously validated v6 RTL."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]

def prefix_candidate():
    s=(REPO/'experiments/sram_multirate/rtl/fir_mac_narrow.sv').read_text()
    s=s.replace('wire [17:0] prod={4\'b0,lo_q}+{hi_q,4\'b0};', '''wire [17:0] prod;
            wire [13:0] lo_next,hi_next;
            wire [11:0] m0,m1,m2,m3;
            fir_prefix_add #(.W(12)) u_m0(.a({2'b0,x}&{12{c[0]}}),.b({1'b0,x,1'b0}&{12{c[1]}}),.y(m0));
            fir_prefix_add #(.W(12)) u_m1(.a({2'b0,x}&{12{c[2]}}),.b({1'b0,x,1'b0}&{12{c[3]}}),.y(m1));
            fir_prefix_add #(.W(12)) u_m2(.a({2'b0,x}&{12{c[4]}}),.b({1'b0,x,1'b0}&{12{c[5]}}),.y(m2));
            fir_prefix_add #(.W(12)) u_m3(.a({2'b0,x}&{12{c[6]}}),.b({1'b0,x,1'b0}&{12{c[7]}}),.y(m3));
            fir_prefix_add #(.W(14)) u_lo(.a({2'b0,p0}),.b({p1,2'b0}),.y(lo_next));
            fir_prefix_add #(.W(14)) u_hi(.a({2'b0,p2}),.b({p3,2'b0}),.y(hi_next));
            fir_prefix_add #(.W(18)) u_prod(.a({4'b0,lo_q}),.b({hi_q,4'b0}),.y(prod));''')
    s=s.replace('p0<=x*c[1:0];p1<=x*c[3:2];p2<=x*c[5:4];p3<=x*c[7:6];',
                'p0<=m0;p1<=m1;p2<=m2;p3<=m3;')
    s=s.replace("lo_q<={2'b0,p0}+{p1,2'b0};hi_q<={2'b0,p2}+{p3,2'b0};",'lo_q<=lo_next;hi_q<=hi_next;')
    s=s.replace('always @(posedge clk) if(advance) sum_q<=sums[level-1][2*node]+rhs;', '''wire [16:0] sum_next;
                    fir_prefix_add #(.W(17)) u_add(.a(sums[level-1][2*node]),.b(rhs),.y(sum_next));
                    always @(posedge clk) if(advance) sum_q<=sum_next;''')
    s=s.replace("wire [17:0] rounded={1'b0,sums[6][0]}+18'd64;",'''wire [17:0] rounded;
        fir_prefix_add #(.W(18)) u_round(.a({1'b0,sums[6][0]}),.b(18'd64),.y(rounded));''')
    return s+'\n'+(HERE/'prefix_add.sv').read_text()

def candidate(name):
    if name=='v6':return (REPO/'experiments/sram_multirate/rtl/fir_mac_narrow.sv').read_text()
    if name=='prefix':return prefix_candidate()
    if name=='segmented':return (HERE/'mac_segmented.sv').read_text()+'\n'+(HERE/'add2.sv').read_text()
    if name=='segmented_kept':return (HERE/'mac_segmented.sv').read_text()+'\n'+(HERE/'add2.sv').read_text().replace('wire [j:0] terms;','(* keep *) wire [j:0] terms;')
    if name=='segmented_mask':
        s=(HERE/'mac_segmented.sv').read_text().replace('Twenty enabled cycles','Twenty-one enabled cycles')
        s=s.replace('reg [19:0] valid','reg [20:0] valid').replace('valid[18:0]','valid[19:0]').replace('out_valid=valid[19]','out_valid=valid[20]')
        s=s.replace("assign sums[0][tap]=enables[5][tap]?prod:17'b0;", "reg [16:0] masked_q;\n            always @(posedge clk) if(advance) masked_q<=enables[5][tap]?prod:17'b0;\n            assign sums[0][tap]=masked_q;")
        return s+'\n'+(HERE/'add2.sv').read_text().replace('wire [j:0] terms;','(* keep *) wire [j:0] terms;')
    if name=='deep32':
        s=(HERE/'mac_segmented.sv').read_text().replace('Twenty enabled cycles','Thirty-two enabled cycles')
        s=s.replace('reg [19:0] valid','reg [31:0] valid').replace('valid[18:0]','valid[30:0]').replace('out_valid=valid[19]','out_valid=valid[31]')
        s=s.replace('enables[0:5]','enables[0:9]').replace('d<6','d<10').replace('enables[5]','enables[9]')
        s=s.replace("assign sums[0][tap]=enables[9][tap]?prod:17'b0;", "reg [16:0] masked_q;\n            always @(posedge clk) if(advance) masked_q<=enables[9][tap]?prod:17'b0;\n            assign sums[0][tap]=masked_q;")
        anchor='wire [11:0] p0,p1,p2,p3;wire [13:0] lo,hi;wire [16:0] prod;'
        registers='\n'
        for i in range(4):
            registers+=f"            reg [11:0] a{i},b{i};\n            always @(posedge clk) if(advance) begin a{i}<={{2'b0,x}}&{{12{{c[{2*i}]}}}};b{i}<={{1'b0,x,1'b0}}&{{12{{c[{2*i+1}]}}}};end\n"
            s=s.replace(f"{{2'b0,x}}&{{12{{c[{2*i}]}}}},{{1'b0,x,1'b0}}&{{12{{c[{2*i+1}]}}}}",f'a{i},b{i}')
        s=s.replace(anchor,anchor+registers)
        return s+'\n'+(HERE/'add3.sv').read_text()
    raise ValueError(name)
