// Generic delayed functional model, NOT a replacement for vendor Liberty/SDF.
// Four physical stripes per logical bank. Writes hold read output as expected
// by the separate read/write-port adapter. Inactive data is deliberately X.
integer mem_reads,mem_writes;
realtime last_rise=-1.0,last_fall=-1.0,last_command=-1.0;
integer clock_checks=0,command_checks=0;
real model_tco;
initial model_tco=$test$plusargs("SLOW_DATA") ? 3.2 : 1.8;
always @(mem_addr or mem_wdata or mem_ce or mem_we) begin
    if(rst_n && last_rise>=0 && (|mem_ce) && $realtime-last_rise<1.499)
        $fatal(1,"BOUNDARY_COMMAND_HOLD");
    last_command=$realtime;
end
always @(negedge mem_clk) begin
    if(rst_n && last_rise>=0 && $realtime-last_rise<0.999)
        $fatal(1,"BOUNDARY_HIGH_WIDTH");
    last_fall=$realtime;
end
always @(posedge mem_clk) begin
    if(rst_n) begin
        if(last_rise>=0 && $realtime-last_rise<2.999) $fatal(1,"BOUNDARY_PERIOD");
        if(last_fall>=0 && $realtime-last_fall<1.999) $fatal(1,"BOUNDARY_LOW_WIDTH");
        if((|mem_ce) && $realtime-last_command<1.499) $fatal(1,"BOUNDARY_COMMAND_SETUP");
        clock_checks=clock_checks+1;
        if(|mem_ce) command_checks=command_checks+1;
    end
    last_rise=$realtime;
end
// Separate storage avoids a reproduced Verilator 5.050 delayed variable-slice
// NBA issue. The independent delayed_slice_tb retains the failing old pattern.
genvar ms,mb;
generate for(ms=0;ms<4;ms=ms+1) begin:G_STRIPE_MODEL
    for(mb=0;mb<49;mb=mb+1) begin:G_BANK_MODEL
        reg [159:0] ram[0:127];
        reg [159:0] q;
        assign mem_rdata[(ms*49+mb)*160+:160]=q;
        always @(posedge mem_clk) begin
            if(mem_ce[ms*49+mb]===1'b1) begin
                if(mem_we[ms*49+mb]===1'b1) begin
                    ram[mem_addr[ms*7+:7]]<=mem_wdata[ms*160+:160];
                    mem_writes=mem_writes+1;
                end else begin
                    q<= #(model_tco) ram[mem_addr[ms*7+:7]];
                    mem_reads=mem_reads+1;
                end
            end else q<= #(model_tco) {160{1'bx}};
        end
    end
end endgenerate
// Reset aborts the frame; clock pulse-width tests resume from a fresh epoch.
always @(negedge rst_n) begin last_rise=-1;last_fall=-1;last_command=-1;end
