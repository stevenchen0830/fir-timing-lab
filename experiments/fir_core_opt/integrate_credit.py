"""Generate a credit-based candidate without editing the frozen front end."""
from pathlib import Path
def rewrite(source):
    edits=[
        ('wire mac_advance=(ocnt!=2\'d2);','wire mac_advance=(ocnt!=2\'d2);\n    wire mac_accept_ready;'),
        ('.rsp_ready(mac_advance)', '.rsp_ready(mac_accept_ready)'),
        ('fir_mac_narrow u_mac(.clk(clk),.rst_n(rst_n),.advance(mac_advance),',
         'fir_mac_credit u_mac(.clk(clk),.rst_n(rst_n),.in_ready(mac_accept_ready),.out_ready(mac_advance),')]
    for old,new in edits:
        if source.count(old)!=1:raise ValueError('Credit integration anchor changed: '+old)
        source=source.replace(old,new)
    return source

def patch_generator(text):
    old="    return '// GENERATED multirate candidate; header below describes the historical front end.\\n'+text"
    if text.count(old)!=1:raise ValueError('Generator return anchor changed')
    return text.replace(old,"    from integrate_credit import rewrite\n    return rewrite(text)")
