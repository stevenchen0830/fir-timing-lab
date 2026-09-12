// Experimental FAST-DOMAIN scheduler. No clock divider or CDC shim is included.
// Four command channels feed separately qualified slow-memory agents. Agents
// must preserve per-channel order and return a completion for writes as well.
// All channels/agents flush their VALID state on the same reset; SRAM is unreset.
// WIDTH=160 models one logical bank. This is not yet a 49-bank FIR wrapper.
module striped_sram_scheduler #(
    parameter integer WIDTH=160,
    parameter integer TAG_WIDTH=32,
    parameter integer MIN_LATENCY=10
)(
    input wire clk, rst_n,
    input wire req_valid,
    output wire req_ready,
    input wire [8:0] req_addr,
    input wire req_write,
    input wire [WIDTH-1:0] req_wdata,
    input wire [TAG_WIDTH-1:0] req_tag,
    output wire rsp_valid,
    input wire rsp_ready,
    output wire rsp_write,
    output wire [WIDTH-1:0] rsp_rdata,
    output wire [TAG_WIDTH-1:0] rsp_tag,
    output wire [3:0] mem_valid,
    input wire [3:0] mem_ready,
    output wire [3:0] mem_write,
    output wire [27:0] mem_addr,
    output wire [4*WIDTH-1:0] mem_wdata,
    output wire [15:0] mem_id,
    input wire [3:0] ret_valid,
    input wire [15:0] ret_id,
    input wire [4*WIDTH-1:0] ret_rdata
);
    localparam integer SLOTS=16;
    localparam integer AGE_W=$clog2(MIN_LATENCY+1);
    localparam [AGE_W-1:0] LAST_AGE=MIN_LATENCY[AGE_W-1:0];
    reg [3:0] q_ids [0:3][0:3];
    reg [1:0] q_read [0:3], q_write [0:3];
    reg [2:0] q_count [0:3];
    reg [3:0] head,tail;
    reg [4:0] used;
    reg [SLOTS-1:0] allocated,done,sent,write_op;
    reg [6:0] address [0:SLOTS-1];
    reg [WIDTH-1:0] write_data [0:SLOTS-1],read_data [0:SLOTS-1];
    reg [TAG_WIDTH-1:0] tag [0:SLOTS-1];
    reg [AGE_W-1:0] age [0:SLOTS-1];
    wire take=req_valid & req_ready;
    wire pop=rsp_valid & rsp_ready;
    wire [3:0] launch=mem_valid & mem_ready;
    assign req_ready=rst_n && used<5'd16 && q_count[req_addr[1:0]]<3'd4;
    assign rsp_valid=rst_n && used!=0 && allocated[head] && done[head] && age[head]>=LAST_AGE;
    assign rsp_write=write_op[head];
    assign rsp_rdata=read_data[head];
    assign rsp_tag=tag[head];
    genvar g;
    generate for(g=0;g<4;g=g+1) begin: G_CHANNEL
        wire [3:0] slot=q_ids[g][q_read[g]];
        assign mem_valid[g]=rst_n && q_count[g]!=0;
        assign mem_write[g]=write_op[slot];
        assign mem_addr[g*7+:7]=address[slot];
        assign mem_wdata[g*WIDTH+:WIDTH]=write_data[slot];
        assign mem_id[g*4+:4]=slot;
    end endgenerate
    integer i,j;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            head<=0; tail<=0; used<=0;
            allocated<=0; done<=0; sent<=0; write_op<=0;
            for(i=0;i<4;i=i+1) begin q_read[i]<=0; q_write[i]<=0; q_count[i]<=0; end
            for(i=0;i<SLOTS;i=i+1) age[i]<=0;
        end else begin
            for(i=0;i<SLOTS;i=i+1)
                if(allocated[i] && age[i]<LAST_AGE) age[i]<=age[i]+1'b1;
            case({take,pop})
                2'b10: used<=used+1'b1;
                2'b01: used<=used-1'b1;
                default: ;
            endcase
            if(pop) begin allocated[head]<=0; done[head]<=0; sent[head]<=0; head<=head+1'b1; end
            for(i=0;i<4;i=i+1) begin
                case({take && req_addr[1:0]==i[1:0],launch[i]})
                    2'b10: q_count[i]<=q_count[i]+1'b1;
                    2'b01: q_count[i]<=q_count[i]-1'b1;
                    default: ;
                endcase
                if(launch[i]) begin
                    sent[q_ids[i][q_read[i]]]<=1;
                    q_read[i]<=q_read[i]+1'b1;
                end
                if(ret_valid[i]) begin
                    done[ret_id[i*4+:4]]<=1;
                    read_data[ret_id[i*4+:4]]<=ret_rdata[i*WIDTH+:WIDTH];
                end
            end
            if(take) begin
                allocated[tail]<=1; done[tail]<=0; sent[tail]<=0;
                write_op[tail]<=req_write;
                address[tail]<=req_addr[8:2];
                write_data[tail]<=req_wdata;
                tag[tail]<=req_tag;
                age[tail]<=0;
                q_ids[req_addr[1:0]][q_write[req_addr[1:0]]]<=tail;
                q_write[req_addr[1:0]]<=q_write[req_addr[1:0]]+1'b1;
                tail<=tail+1'b1;
            end
`ifdef SCHEDULER_ASSERTIONS
            if(used>5'd16) $fatal(1,"SCHEDULER_ROB_OVERFLOW");
            for(i=0;i<4;i=i+1) begin
                if(q_count[i]>3'd4) $fatal(1,"SCHEDULER_QUEUE_OVERFLOW");
                if(ret_valid[i]) begin
                    if(!allocated[ret_id[i*4+:4]] || !sent[ret_id[i*4+:4]] || done[ret_id[i*4+:4]])
                        $fatal(1,"SCHEDULER_BAD_COMPLETION");
                    for(j=i+1;j<4;j=j+1)
                        if(ret_valid[j] && ret_id[i*4+:4]==ret_id[j*4+:4])
                            $fatal(1,"SCHEDULER_DUPLICATE_COMPLETION");
                end
            end
`endif
        end
    end
endmodule
