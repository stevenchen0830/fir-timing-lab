// Transaction-credit shell. The arithmetic pipeline never stalls; each accepted
// item reserves an output FIFO slot until the consumer actually takes it.
// This is a different microarchitecture, NOT a timing exception or an always-
// ready assumption about the external consumer. State is reset; payload is not.
module fir_mac_credit #(
    parameter integer LANES=16, DEPTH=64, AW=$clog2(DEPTH)
)(
    input wire clk,rst_n,in_valid,
    output wire in_ready,
    input wire [LANES*500-1:0] tap_data,
    input wire [399:0] tap_coef,
    input wire [49:0] tap_enable,
    input wire out_ready,
    output wire out_valid,
    output wire [LANES*10-1:0] result
);
    reg [LANES*10-1:0] data[0:DEPTH-1];
    reg [AW-1:0] wr,rd;
    reg [AW:0] stored,reserved;
    wire accept=in_valid && in_ready;
    wire consume=out_valid && out_ready;
    wire raw_valid;
    wire [LANES*10-1:0] raw_result;
    assign out_valid=(stored!=0);
    assign result=data[rd];
    // Conservatively do not borrow a simultaneous consumption credit. This
    // removes a ready->ready combinational path at the full boundary.
    assign in_ready=(reserved<DEPTH);
    fir_mac_narrow #(.LANES(LANES)) u_compute(
        .clk(clk),.rst_n(rst_n),.advance(1'b1),.in_valid(accept),
        .tap_data(tap_data),.tap_coef(tap_coef),.tap_enable(tap_enable),
        .out_valid(raw_valid),.result(raw_result));
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin wr<=0;rd<=0;stored<=0;reserved<=0;end
        else begin
            case({accept,consume})
                2'b10:reserved<=reserved+1'b1;
                2'b01:reserved<=reserved-1'b1;
                default:reserved<=reserved;
            endcase
            case({raw_valid,consume})
                2'b10:stored<=stored+1'b1;
                2'b01:stored<=stored-1'b1;
                default:stored<=stored;
            endcase
            if(raw_valid) wr<=(wr==DEPTH-1) ? 0 : wr+1'b1;
            if(consume) rd<=(rd==DEPTH-1) ? 0 : rd+1'b1;
        end
    end
    always @(posedge clk) if(rst_n && raw_valid) data[wr]<=raw_result;
`ifdef MULTIRATE_ASSERTIONS
    initial if(DEPTH<2) $fatal(1,"MAC_CREDIT_DEPTH");
    always @(posedge clk) if(rst_n) begin
        if(reserved>DEPTH || stored>reserved) $fatal(1,"MAC_CREDIT_ACCOUNTING");
        if(raw_valid && stored==DEPTH && !consume) $fatal(1,"MAC_OUTPUT_OVERFLOW");
        if(consume && reserved==0) $fatal(1,"MAC_CREDIT_UNDERFLOW");
    end
`endif
endmodule
