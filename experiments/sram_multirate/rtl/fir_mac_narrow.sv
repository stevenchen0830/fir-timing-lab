// v6 candidate: four 10x2 multipliers -> two partial sums -> product/mask ->
// six binary reduction stages. No inactive-data mask in front of multiplier.
module fir_mac_narrow #(parameter integer LANES=16)(
    input wire clk,rst_n,advance,in_valid,
    input wire [50*LANES*10-1:0] tap_data,
    input wire [399:0] tap_coef,
    input wire [49:0] tap_enable,
    output wire out_valid,
    output wire [LANES*10-1:0] result
);
    reg [8:0] valid;
    reg [49:0] en0,en1;
    always @(posedge clk or negedge rst_n)
        if(!rst_n) valid<=0;
        else if(advance) valid<={valid[7:0],in_valid};
    always @(posedge clk) if(advance) begin en0<=tap_enable;en1<=en0;end
    assign out_valid=valid[8];
    genvar lane,tap,level,node;
    generate for(lane=0;lane<LANES;lane=lane+1) begin:G_LANE
        wire [16:0] sums[0:6][0:49];
        for(tap=0;tap<50;tap=tap+1) begin:G_MULT
            wire [9:0] x=tap_data[tap*LANES*10+lane*10+:10];
            wire [7:0] c=tap_coef[tap*8+:8];
            reg [11:0] p0,p1,p2,p3;
            reg [13:0] lo_q,hi_q;
            reg [16:0] prod_q;
            wire [17:0] prod={4'b0,lo_q}+{hi_q,4'b0};
            always @(posedge clk) if(advance) begin
                p0<=x*c[1:0];p1<=x*c[3:2];p2<=x*c[5:4];p3<=x*c[7:6];
                lo_q<={2'b0,p0}+{p1,2'b0};hi_q<={2'b0,p2}+{p3,2'b0};
                prod_q<=en1[tap] ? prod[16:0] : 17'b0;
            end
            assign sums[0][tap]=prod_q;
        end
        for(level=1;level<=6;level=level+1) begin:G_REDUCE
            localparam PREV=(50+(1<<(level-1))-1)>>(level-1);
            localparam COUNT=(PREV+1)/2;
            for(node=0;node<50;node=node+1) begin:G_NODE
                if(node<COUNT) begin:G_USED
                    reg [16:0] sum_q;
                    wire [16:0] rhs;
                    if(2*node+1<PREV) assign rhs=sums[level-1][2*node+1];
                    else assign rhs=0;
                    always @(posedge clk) if(advance) sum_q<=sums[level-1][2*node]+rhs;
                    assign sums[level][node]=sum_q;
                end else assign sums[level][node]=0;
            end
        end
        wire [17:0] rounded={1'b0,sums[6][0]}+18'd64;
        assign result[lane*10+:10]=rounded[17] ? 10'd1023 : rounded[16:7];
    end endgenerate
endmodule
