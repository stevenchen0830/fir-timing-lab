// One shared controller for a 49-bank transaction, not 49 independent ROBs.
// Masks, weights and bypass travel with each accepted request. Writes also ack.
module fir_transaction_queue(
    input wire clk,rst_n,req_valid,
    output wire req_ready,
    input wire [8:0] req_addr,
    input wire [48:0] req_read,req_write,
    input wire [159:0] req_data,req_bypass,
    input wire [399:0] req_coef,
    input wire req_output,
    output wire rsp_valid,
    input wire rsp_ready,
    output wire [7839:0] rsp_data,
    output wire [48:0] rsp_read,
    output wire [159:0] rsp_bypass,
    output wire [399:0] rsp_coef,
    output wire rsp_output,
    output wire [4:0] occupancy,
    output wire [3:0] cmd_valid,
    input wire [3:0] cmd_ready,
    output wire [195:0] cmd_read,cmd_write,
    output wire [27:0] cmd_addr,
    output wire [639:0] cmd_data,
    output wire [15:0] cmd_id,
    input wire [3:0] ret_valid,
    input wire [15:0] ret_id,
    input wire [31359:0] ret_data
);
    reg [3:0] head,tail,qhead[0:3],qtail[0:3];
    reg [2:0] count[0:3];
    reg [3:0] ids[0:3][0:3];
    reg [4:0] used;
    reg [15:0] allocated,done,sent,is_output;
    reg [3:0] age[0:15];
    reg [6:0] address[0:15];
    reg [48:0] reads[0:15],writes[0:15];
    reg [159:0] wdata[0:15],bypass[0:15];
    reg [399:0] coef[0:15];
    reg [7839:0] data[0:15];
    assign occupancy=used;
    assign req_ready=rst_n && used<16 && count[req_addr[1:0]]<4;
    assign rsp_valid=rst_n && used!=0 && done[head] && age[head]>=12;
    assign rsp_data=data[head]; assign rsp_read=reads[head];
    assign rsp_bypass=bypass[head]; assign rsp_coef=coef[head];
    assign rsp_output=is_output[head];
    wire take=req_valid && req_ready, pop=rsp_valid && rsp_ready;
    wire [3:0] launch=cmd_valid & cmd_ready;
    genvar g;
    generate for(g=0;g<4;g=g+1) begin: G_CMD
        wire [3:0] id=ids[g][qhead[g][1:0]];
        assign cmd_valid[g]=rst_n && count[g]!=0;
        assign cmd_read[g*49+:49]=reads[id]; assign cmd_write[g*49+:49]=writes[id];
        assign cmd_addr[g*7+:7]=address[id]; assign cmd_data[g*160+:160]=wdata[id];
        assign cmd_id[g*4+:4]=id;
    end endgenerate
    integer i,j;
    always @(posedge clk or negedge rst_n) begin
        if(!rst_n) begin
            head<=0;tail<=0;used<=0;allocated<=0;done<=0;sent<=0;is_output<=0;
            for(i=0;i<4;i=i+1) begin count[i]<=0;qhead[i]<=0;qtail[i]<=0; end
            for(i=0;i<16;i=i+1) age[i]<=0;
        end else begin
            for(i=0;i<16;i=i+1) if(allocated[i] && age[i]<12) age[i]<=age[i]+1'b1;
            case({take,pop}) 2'b10:used<=used+1'b1; 2'b01:used<=used-1'b1; default:; endcase
            if(pop) begin allocated[head]<=0;done[head]<=0;sent[head]<=0;head<=head+1'b1; end
            for(i=0;i<4;i=i+1) begin
                case({take && req_addr[1:0]==i[1:0],launch[i]})
                    2'b10:count[i]<=count[i]+1'b1;
                    2'b01:count[i]<=count[i]-1'b1;
                    default:;
                endcase
                if(launch[i]) begin sent[ids[i][qhead[i][1:0]]]<=1;qhead[i]<=qhead[i]+1'b1;end
                if(ret_valid[i]) done[ret_id[i*4+:4]]<=1;
            end
            if(take) begin
                allocated[tail]<=1;done[tail]<=0;sent[tail]<=0;is_output[tail]<=req_output;
                age[tail]<=0;tail<=tail+1'b1;
                ids[req_addr[1:0]][qtail[req_addr[1:0]][1:0]]<=tail;
                qtail[req_addr[1:0]]<=qtail[req_addr[1:0]]+1'b1;
            end
`ifdef MULTIRATE_ASSERTIONS
            if(used>16) $fatal(1,"TX_CREDIT_OVERFLOW");
            if(take && (|(req_read & req_write))) $fatal(1,"TX_READ_WRITE_COLLISION");
            for(i=0;i<4;i=i+1) begin
                if(count[i]>4) $fatal(1,"TX_QUEUE_OVERFLOW");
                if(ret_valid[i] && (!allocated[ret_id[i*4+:4]] || !sent[ret_id[i*4+:4]] || done[ret_id[i*4+:4]]))
                    $fatal(1,"TX_INVALID_COMPLETION");
                for(j=i+1;j<4;j=j+1)
                    if(ret_valid[i] && ret_valid[j] && ret_id[i*4+:4]==ret_id[j*4+:4]) $fatal(1,"TX_DUPLICATE_COMPLETION");
            end
`endif
        end
    end
    always @(posedge clk) begin
        if(take) begin
            address[tail]<=req_addr[8:2];reads[tail]<=req_read;writes[tail]<=req_write;
            wdata[tail]<=req_data;bypass[tail]<=req_bypass;coef[tail]<=req_coef;
        end
        for(integer b=0;b<4;b=b+1)
            if(ret_valid[b]) data[ret_id[b*4+:4]]<=ret_data[b*7840+:7840];
    end
endmodule
