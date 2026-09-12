"""Check relative Markdown file links and unsafe absolute local documentation links."""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def main():
    bad=[];count=0
    for doc in ROOT.rglob('*.md'):
        if '.git' in doc.parts:continue
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',doc.read_text(encoding='utf-8')):
            target=target.split('#',1)[0].strip('<>')
            if not target or re.match(r'https?://',target):continue
            count+=1
            if re.match(r'[A-Za-z]:',target) or not (doc.parent/target).exists():
                bad.append(str(doc.relative_to(ROOT))+': '+target)
    if bad:raise SystemExit('\n'.join(bad))
    print('DOC_LINKS_PASS links='+str(count))
if __name__=='__main__':main()

