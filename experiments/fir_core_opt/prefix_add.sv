// Bounded-width parallel-prefix addition; no timing exception or extra cycle.
module fir_prefix_add #(parameter integer W=17)(
    input wire [W-1:0] a,b, output wire [W-1:0] y
);
    localparam integer LEVELS=$clog2(W);
    (* keep *) wire [W-1:0] p[0:LEVELS],g[0:LEVELS];
    assign p[0]=a^b;
    assign g[0]=a&b;
    genvar l,i;
    generate for(l=0;l<LEVELS;l=l+1) begin:L
        for(i=0;i<W;i=i+1) begin:B
            if(i >= (1<<l)) begin
                assign g[l+1][i]=g[l][i] | (p[l][i]&g[l][i-(1<<l)]);
                assign p[l+1][i]=p[l][i]&p[l][i-(1<<l)];
            end else begin
                assign g[l+1][i]=g[l][i];
                assign p[l+1][i]=p[l][i];
            end
        end
    end endgenerate
    assign y=p[0] ^ {g[LEVELS][W-2:0],1'b0};
endmodule
