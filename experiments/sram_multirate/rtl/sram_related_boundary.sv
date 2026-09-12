// Related-clock boundary, not an asynchronous FIFO. rst_n must be synchronously
// released in clk domain. No timing exceptions are implied by this RTL.
module sram_related_boundary #(
    parameter integer BANKS=49, WIDTH=160
)(
    input wire clk,rst_n,
    input wire [3:0] cmd_valid,
    output wire [3:0] cmd_ready,
    input wire [4*BANKS-1:0] cmd_read,cmd_write,
    input wire [27:0] cmd_addr,
    input wire [4*WIDTH-1:0] cmd_data,
    input wire [15:0] cmd_id,
    output reg [3:0] ret_valid,
    output reg [15:0] ret_id,
    output reg [4*BANKS*WIDTH-1:0] ret_data,
    output reg sram_clk,
    output wire [4*BANKS-1:0] sram_ce,sram_we,
    output reg [27:0] sram_addr,
    output reg [4*WIDTH-1:0] sram_wdata,
    input wire [4*BANKS*WIDTH-1:0] sram_rdata
);
    reg [1:0] phase;
    reg [3:0] launch_valid,active_valid;
    reg [15:0] launch_id,active_id;
    reg [4*BANKS-1:0] read_q,write_q;
    assign cmd_ready={4{rst_n && phase==2}};
    genvar g;
    generate for(g=0;g<4;g=g+1) begin: G_PINS
        assign sram_ce[g*BANKS+:BANKS]=(read_q[g*BANKS+:BANKS] | write_q[g*BANKS+:BANKS]) & {BANKS{launch_valid[g]}};
        assign sram_we[g*BANKS+:BANKS]=write_q[g*BANKS+:BANKS] & {BANKS{launch_valid[g]}};
    end endgenerate
    // phase is updated at rising core edges. A falling-edge flop generates
    // 1 ns high / 2 ns low when the source period is 1 ns.
    always @(negedge clk or negedge rst_n)
        if(!rst_n) sram_clk<=0;
        else sram_clk<=(phase==1);
    integer i;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            phase<=0; launch_valid<=0; active_valid<=0; ret_valid<=0;
            launch_id<=0; active_id<=0; ret_id<=0;
        end else begin
            phase<=(phase==2) ? 2'd0 : phase+1'b1;
            ret_valid<=0;
            if(phase==2) begin launch_valid<=cmd_valid; launch_id<=cmd_id; end
            // Half a core period after the physical SRAM launch edge.
            if(phase==1) begin active_valid<=launch_valid; active_id<=launch_id; end
            // Old SRAM output: capture 2.5 ns after launch, 0.5 ns before
            // the next SRAM edge. Actual min/max skew must still be timed.
            if(phase==0) begin ret_valid<=active_valid; ret_id<=active_id; end
        end
    end
    always @(posedge clk) begin
        if(rst_n && phase==2) begin
            sram_addr<=cmd_addr; sram_wdata<=cmd_data;
            read_q<=cmd_read; write_q<=cmd_write;
        end
        if(rst_n && phase==0)
            for(i=0;i<4;i=i+1)
                if(active_valid[i]) ret_data[i*BANKS*WIDTH+:BANKS*WIDTH]<=sram_rdata[i*BANKS*WIDTH+:BANKS*WIDTH];
    end
endmodule
