"""Fail closed for accidental private assets, oversized files and token patterns."""
import argparse,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DENY={'.lib','.lef','.gds','.gds2','.oas','.spef','.sdf','.db','.odb','.def',
      '.cdl','.sp','.spice','.gz','.zip','.tar','.7z','.exe','.dll','.so','.a','.o','.vvp'}
NAMES={'mapped.v','placed.v','.env','license.dat','license.lic'}
SECRETS=[re.compile(r'gh[pousr]_[A-Za-z0-9]{30,}'),
         re.compile(r'github_pat_[A-Za-z0-9_]{40,}'),
         re.compile(r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----')]
def main():
    p=argparse.ArgumentParser();p.add_argument('--tracked',action='store_true');a=p.parse_args()
    if a.tracked:
        names=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'ls-files','-z'],cwd=ROOT).decode().split('\0')
        files=[ROOT/name for name in names if name]
    else:
        files=[f for f in ROOT.rglob('*') if f.is_file()
          and not any(part in {'.git','__pycache__'} for part in f.relative_to(ROOT).parts)]
    bad=[]
    for f in files:
        rel=f.relative_to(ROOT)
        if f.is_symlink():bad.append(str(rel)+': symlink');continue
        low=f.name.lower()
        if f.suffix.lower() in DENY or low in NAMES or '.lib.' in low or '.lef.' in low:
            bad.append(str(rel)+': private/binary format');continue
        if any(part.lower() in {'private','pdk','models'} for part in rel.parts):
            bad.append(str(rel)+': private directory');continue
        if f.stat().st_size>2*1024*1024:bad.append(str(rel)+': oversized; manual review needed')
        try:text=f.read_text(encoding='utf-8')
        except UnicodeError:bad.append(str(rel)+': non-text');continue
        if any(pattern.search(text) for pattern in SECRETS):bad.append(str(rel)+': credential pattern')
        if f.suffix.lower() in {'.v','.sv','.svh'} and re.search(r'(?i)copyright.{0,80}(tsmc|taiwan semiconductor)',text):
            bad.append(str(rel)+': vendor copyright in RTL')
    if bad:raise SystemExit('\n'.join(bad))
    print('PUBLIC_TREE_PASS files='+str(len(files))+' (not a license certification)')
if __name__=='__main__':main()
