// Twenty enabled cycles. Exact modulo-17 accumulation is valid only under
// the FIR contract: nonnegative coefficients, total enabled weight <=128.
module fir_mac_narrow #(parameter integer LANES=16)(
    input wire clk,rst_n,advance,in_valid,
    input wire [50*LANES*10-1:0] tap_data,
    input wire [399:0] tap_coef,input wire [49:0] tap_enable,
    output wire out_valid,output wire [LANES*10-1:0] result
);
    reg [19:0] valid;
    reg [49:0] enables[0:5];integer d;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) valid<=0;else if(advance) valid<={valid[18:0],in_valid};
    always @(posedge clk) if(advance) begin
        enables[0]<=tap_enable;for(d=1;d<6;d=d+1) enables[d]<=enables[d-1];
    end
    assign out_valid=valid[19];
    genvar lane,tap,level,node;
    generate for(lane=0;lane<LANES;lane=lane+1) begin:G_LANE
        wire [16:0] sums[0:6][0:49];
        for(tap=0;tap<50;tap=tap+1) begin:G_MULT
            wire [9:0] x=tap_data[tap*LANES*10+lane*10+:10];
            wire [7:0] c=tap_coef[tap*8+:8];
            wire [11:0] p0,p1,p2,p3;wire [13:0] lo,hi;wire [16:0] prod;
            fir_add2 #(.W(12)) m0(clk,advance,{2'b0,x}&{12{c[0]}},{1'b0,x,1'b0}&{12{c[1]}},p0);
            fir_add2 #(.W(12)) m1(clk,advance,{2'b0,x}&{12{c[2]}},{1'b0,x,1'b0}&{12{c[3]}},p1);
            fir_add2 #(.W(12)) m2(clk,advance,{2'b0,x}&{12{c[4]}},{1'b0,x,1'b0}&{12{c[5]}},p2);
            fir_add2 #(.W(12)) m3(clk,advance,{2'b0,x}&{12{c[6]}},{1'b0,x,1'b0}&{12{c[7]}},p3);
            fir_add2 #(.W(14)) ml(clk,advance,{2'b0,p0},{p1,2'b0},lo);
            fir_add2 #(.W(14)) mh(clk,advance,{2'b0,p2},{p3,2'b0},hi);
            fir_add2 #(.W(17)) mp(clk,advance,{3'b0,lo},{hi[12:0],4'b0},prod);
            assign sums[0][tap]=enables[5][tap]?prod:17'b0;
        end
        for(level=1;level<=6;level=level+1) begin:G_REDUCE
            localparam integer PREV=(50+(1<<(level-1))-1)>>(level-1);
            localparam integer COUNT=(PREV+1)/2;
            for(node=0;node<50;node=node+1) begin:G_NODE
                if(node<COUNT) begin:USED
                    wire [16:0] rhs;
                    if(2*node+1<PREV) assign rhs=sums[level-1][2*node+1];
                    else assign rhs=0;
                    fir_add2 #(.W(17)) ma(clk,advance,sums[level-1][2*node],rhs,sums[level][node]);
                end else assign sums[level][node]=0;
            end
        end
        wire [17:0] rounded;
        fir_add2 #(.W(18)) mr(clk,advance,{1'b0,sums[6][0]},18'd64,rounded);
        assign result[lane*10+:10]=rounded[17]?10'd1023:rounded[16:7];
    end endgenerate
endmodule
