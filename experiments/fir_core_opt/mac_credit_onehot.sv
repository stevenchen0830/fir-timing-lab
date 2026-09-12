// Same credit protocol, one-hot occupancy/pointers to remove inc/dec carries.
module fir_mac_credit #(parameter integer LANES=16, DEPTH=64)(
    input wire clk,rst_n,in_valid,output wire in_ready,
    input wire [LANES*500-1:0] tap_data,input wire [399:0] tap_coef,
    input wire [49:0] tap_enable,input wire out_ready,
    output wire out_valid,output wire [LANES*10-1:0] result
);
    localparam integer DW=LANES*10;
    reg [DEPTH-1:0] wr_hot,rd_hot;
    reg [DEPTH:0] stored_hot,reserved_hot;
    reg [DW-1:0] data[0:DEPTH-1];
    wire consume=out_valid && out_ready;
    wire accept=in_valid && in_ready;
    wire raw_valid;wire [DW-1:0] raw_result;
    assign out_valid=~stored_hot[0];
    assign in_ready=~reserved_hot[DEPTH];
    fir_mac_narrow #(.LANES(LANES)) u_compute(clk,rst_n,1'b1,accept,
        tap_data,tap_coef,tap_enable,raw_valid,raw_result);
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin wr_hot<=1;rd_hot<=1;stored_hot<=1;reserved_hot<=1;end
        else begin
            if(raw_valid) wr_hot<={wr_hot[DEPTH-2:0],wr_hot[DEPTH-1]};
            if(consume) rd_hot<={rd_hot[DEPTH-2:0],rd_hot[DEPTH-1]};
            case({raw_valid,consume})
                2'b10:stored_hot<=stored_hot<<1;
                2'b01:stored_hot<=stored_hot>>1;
                default:stored_hot<=stored_hot;
            endcase
            case({accept,consume})
                2'b10:reserved_hot<=reserved_hot<<1;
                2'b01:reserved_hot<=reserved_hot>>1;
                default:reserved_hot<=reserved_hot;
            endcase
        end
    end
    (* keep *) wire [DW-1:0] mux_tree[0:2*DEPTH-2];
    genvar i;
    generate for(i=0;i<DEPTH;i=i+1) begin: G_SLOT
        always @(posedge clk) if(rst_n && raw_valid && wr_hot[i]) data[i]<=raw_result;
        assign mux_tree[DEPTH-1+i]=data[i] & {DW{rd_hot[i]}};
    end
    for(i=0;i<DEPTH-1;i=i+1) begin: G_OR
        assign mux_tree[i]=mux_tree[2*i+1] | mux_tree[2*i+2];
    end endgenerate
    assign result=mux_tree[0];
`ifdef MULTIRATE_ASSERTIONS
    integer s,r,k;
    initial if(DEPTH<2 || (DEPTH&(DEPTH-1))) $fatal(1,"CREDIT_DEPTH_POWER_TWO");
    always @(posedge clk) if(rst_n) begin
        if(!$onehot(wr_hot) || !$onehot(rd_hot) || !$onehot(stored_hot) || !$onehot(reserved_hot))
            $fatal(1,"CREDIT_ONEHOT_CORRUPTION");
        s=0;r=0;
        for(k=0;k<=DEPTH;k=k+1) begin if(stored_hot[k]) s=k;if(reserved_hot[k]) r=k;end
        if(s>r || (raw_valid && stored_hot[DEPTH] && !consume)) $fatal(1,"CREDIT_CAPACITY");
    end
`endif
endmodule
