"""Technology-specific input-register sizing with checked sequential semantics.

This is library-signature/connectivity evidence, not a full sequential LEC.
"""
import re
def group(text,pattern):
    m=re.search(pattern+r'\s*\{',text)
    if not m:raise ValueError('Missing Liberty group '+pattern)
    start=m.end();depth=1;quote=False;escape=False
    for i in range(start,len(text)):
        c=text[i]
        if escape:escape=False;continue
        if c=='\\':escape=True;continue
        if c=='"':quote=not quote
        if quote:continue
        if c=='{':depth+=1
        if c=='}':depth-=1
        if not depth:return text[start:i]
    raise ValueError('Unbalanced Liberty')

def signature(text,name):
    cell=group(text,r'\bcell\s*\(\s*'+re.escape(name)+r'\s*\)')
    ff=group(cell,r'\bff\s*\([^)]*\)')
    result={'ff':re.sub(r'\s+','',ff),'pins':{}}
    for name in ('D','CK','Q'):
        pin=group(cell,r'\bpin\s*\(\s*'+name+r'\s*\)')
        result['pins'][name]={key:re.search(r'\b'+key+r'\s*:\s*([^;]+);',pin).group(1).strip()
                             for key in ('direction','function','clock') if re.search(r'\b'+key+r'\s*:',pin)}
    return result

def boost(module,models,target):
    if target not in ('DFFQX1','DFFQX2','DFFQX4'):raise ValueError('Unsupported input sizing cell')
    for corner in ('slow','typical','fast'):
        text=(models/(corner+'.lib')).read_text()
        if signature(text,'DFFQXL')!=signature(text,target):raise ValueError('Non-equivalent flop '+corner)
    inputs={b for p in module['ports'].values() if p['direction']=='input' for b in p['bits']}
    changed=[]
    for name,cell in module['cells'].items():
        if cell['type']=='DFFQXL' and any(b in inputs for b in cell['connections']['D']):
            cell['type']=target;changed.append(name)
    return {'kind':'input-register size only','from':'DFFQXL','to':target,'instances':len(changed),
            'changed_instances':changed,'three_corner_ff_and_pin_signature_equal':True,
            'scope':'no register or port connectivity changes; not full mapped LEC'}

def logical_signature(text,name):
    cell=group(text,r'\bcell\s*\(\s*'+re.escape(name)+r'\s*\)')
    ff=group(cell,r'\bff\s*\([^)]*\)') if re.search(r'\bff\s*\(',cell) else ''
    pins={}
    for pin_name in re.findall(r'\bpin\s*\(\s*([A-Za-z0-9_]+)\s*\)',cell):
        pin=group(cell,r'\bpin\s*\(\s*'+pin_name+r'\s*\)')
        pins[pin_name]={key:re.search(r'\b'+key+r'\s*:\s*([^;]+);',pin).group(1).strip()
                         for key in ('direction','function','clock') if re.search(r'\b'+key+r'\s*:',pin)}
    return {'ff':re.sub(r'\s+','',ff),'pins':pins}

def size_carry_cones(module,models):
    replacements={'OR4X1':'OR4X4','MX2X1':'MX2X2','AND3X1':'AND3X2','EDFFHQX1':'EDFFHQX2'}
    for corner in ('slow','typical','fast'):
        text=(models/(corner+'.lib')).read_text()
        for old,new in replacements.items():
            if logical_signature(text,old)!=logical_signature(text,new):raise ValueError('Sizing changes logic '+old)
    carry_bits={b for n,net in module['netnames'].items() if re.search(r'\.(gp|gg)$',n) for b in net['bits']}
    changes=[]
    for name,cell in module['cells'].items():
        old=cell['type']
        if old not in replacements:continue
        if old=='EDFFHQX1' and not any(b in carry_bits for b in cell['connections']['Q']):continue
        cell['type']=replacements[old];changes.append({'instance':name,'from':old,'to':cell['type']})
    return {'scope':'library logical signatures and unchanged connections; not whole RTL LEC',
            'changes':changes,'count':len(changes),'carry_state_bits':len(carry_bits)}
