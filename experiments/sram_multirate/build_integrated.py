#!/usr/bin/env python3
"""Generate a transaction-based FIR candidate, preserving historical v4 RTL."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
BASE='b1ffeaf5fccad2442519b58076420b3a723d9c800e29ad7f26974ca817566283'

def generate():
    raw=(REPO/'rtl/img_filter.v').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=BASE: raise ValueError('Baseline hash mismatch')
    text=raw.decode()
    text=text.replace('input  wire                             rst_n,','input  wire                             arst_n,')
    start=text.index('    // external single-port SRAM')
    end=text.index('    localparam NBK',start)
    text=text[:start]+'''    // Four physical stripes per logical row bank, external macro pins.
    output wire mem_clk,
    output wire [195:0] mem_ce,mem_we,
    output wire [27:0] mem_addr,
    output wire [639:0] mem_wdata,
    input wire [31359:0] mem_rdata
);
    // Asynchronous assert, two-core-edge synchronous release. All controller
    // and generated-clock valid state shares this reset. SRAM is unreset.
    (* async_reg="true" *) reg [1:0] reset_sync;
    always @(posedge clk or negedge arst_n)
        if(!arst_n) reset_sync<=0;else reset_sync<={reset_sync[0],1'b1};
    wire rst_n=reset_sync[1];
    wire tx_ready;
''' + text[end:]
    text=text.replace("wire pipe_en   = (ocnt != 2'd2) & (e_needin ? ihas : 1'b1);",
                      "wire pipe_en   = tx_ready & (e_needin ? ihas : 1'b1);")
    start=text.index('    reg [NBK-1:0] m_ce;')
    end=text.index('    //========================================================================\n    // 8.',start)
    text=text[:start]+'''    // Front-end accepts only when the transaction queue reserves a slot.
    // Metadata is sampled at exactly the same edge as address/data acceptance.
    wire [159:0] input_head=ird ? ibuf1 : ibuf0;
    wire [48:0] write_mask=(e_iswr ? (49'b1<<wbank) : 49'b0);
    wire [48:0] read_mask=e_isout ? ce_cur : 49'b0;
    wire [3:0] cmd_valid,cmd_ready,ret_valid;
    wire [195:0] cmd_read,cmd_write;
    wire [27:0] cmd_addr;
    wire [639:0] cmd_data;
    wire [15:0] cmd_id,ret_id;
    wire [31359:0] ret_data;
    wire rsp_valid,rsp_output;
    wire [7839:0] rsp_data;
    wire [48:0] rsp_read;
    wire [159:0] rsp_bypass;
    wire [399:0] rsp_coef;
    wire [4:0] tx_occupancy;
    wire mac_advance=(ocnt!=2'd2);
    fir_transaction_queue u_tx(
        .clk(clk),.rst_n(rst_n),.req_valid(e_go),.req_ready(tx_ready),
        .req_addr(c_cnt),.req_read(read_mask),.req_write(write_mask),
        .req_data(input_head),.req_bypass(input_head),.req_coef({cbp_cur,c_cur}),.req_output(e_isout),
        .rsp_valid(rsp_valid),.rsp_ready(mac_advance),.rsp_data(rsp_data),.rsp_read(rsp_read),
        .rsp_bypass(rsp_bypass),.rsp_coef(rsp_coef),.rsp_output(rsp_output),.occupancy(tx_occupancy),
        .cmd_valid(cmd_valid),.cmd_ready(cmd_ready),.cmd_read(cmd_read),.cmd_write(cmd_write),
        .cmd_addr(cmd_addr),.cmd_data(cmd_data),.cmd_id(cmd_id),
        .ret_valid(ret_valid),.ret_id(ret_id),.ret_data(ret_data));
    sram_related_boundary u_boundary(
        .clk(clk),.rst_n(rst_n),.cmd_valid(cmd_valid),.cmd_ready(cmd_ready),
        .cmd_read(cmd_read),.cmd_write(cmd_write),.cmd_addr(cmd_addr),.cmd_data(cmd_data),.cmd_id(cmd_id),
        .ret_valid(ret_valid),.ret_id(ret_id),.ret_data(ret_data),
        .sram_clk(mem_clk),.sram_ce(mem_ce),.sram_we(mem_we),.sram_addr(mem_addr),
        .sram_wdata(mem_wdata),.sram_rdata(mem_rdata));
    wire [159:0] result;
    wire mac_valid;
    fir_mac_narrow u_mac(.clk(clk),.rst_n(rst_n),.advance(mac_advance),
        .in_valid(rsp_valid && rsp_output),.tap_data({rsp_bypass,rsp_data}),
        .tap_coef(rsp_coef),.tap_enable({(|rsp_coef[399:392]),rsp_read}),
        .out_valid(mac_valid),.result(result));

''' + text[end:]
    text=text.replace('wire opush = pipe_en & out_d4;', 'wire opush = mac_advance & mac_valid;')
    return '// GENERATED multirate candidate; header below describes the historical front end.\n'+text

def main():
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=False)
    payload=generate();(a.output/'img_filter_multirate.sv').write_text(payload)
    sources=[REPO/'rtl/img_filter.v',Path(__file__),*sorted((HERE/'rtl').glob('*.sv'))]
    (a.output/'manifest.json').write_text(json.dumps({'candidate':'multirate49_v6','physical_status':'NOT_RUN',
        'inputs':{str(x.relative_to(REPO)):hashlib.sha256(x.read_bytes()).hexdigest() for x in sources},
        'generated_sha256':hashlib.sha256(payload.encode()).hexdigest()},indent=2)+'\n')
if __name__=='__main__':main()
