// Three enabled stages: local sums -> inter-group carry -> carry selection.
module fir_add2 #(parameter integer W=17,B=3)(
    input wire clk,advance,input wire [W-1:0] a,b,output wire [W-1:0] y
);
    localparam integer N=(W+B-1)/B;
    reg [W-1:0] s0,s1,s0_d,s1_d;
    reg [N-1:0] gp,gg,carry_q;
    wire [N:0] carry;assign carry[0]=0;
    always @(posedge clk) if(advance) begin s0_d<=s0;s1_d<=s1;carry_q<=carry[N-1:0];end
    genvar j,k;
    generate for(j=0;j<N;j=j+1) begin:G
        localparam integer L=j*B,BW=(L+B<=W)?B:(W-L);
        wire [BW:0] z0={1'b0,a[L+:BW]}+{1'b0,b[L+:BW]};
        wire [BW:0] z1={1'b0,a[L+:BW]}+{1'b0,b[L+:BW]}+1'b1;
        always @(posedge clk) if(advance) begin
            s0[L+:BW]<=z0[BW-1:0];s1[L+:BW]<=z1[BW-1:0];
            gg[j]<=z0[BW];gp[j]<=&(a[L+:BW]^b[L+:BW]);
        end
        (* keep *) wire [j:0] terms;
        for(k=0;k<=j;k=k+1) begin:T
            if(k==j) assign terms[k]=gg[k];
            else assign terms[k]=gg[k]&(&gp[j:k+1]);
        end
        assign carry[j+1]=|terms;
        reg [BW-1:0] out_q;
        always @(posedge clk) if(advance) out_q<=carry_q[j]?s1_d[L+:BW]:s0_d[L+:BW];
        assign y[L+:BW]=out_q;
    end endgenerate
endmodule
