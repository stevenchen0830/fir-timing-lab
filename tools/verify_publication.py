"""Validate the immutable fresh-publication logs, not physical closure."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'verification/publication'
def main():
    count=0
    for line in (BASE/'manifest.sha256').read_text().splitlines():
        if not line.strip():continue
        expected,name=line.split('  ',1);path=(BASE/name).resolve()
        if BASE not in path.parents:raise ValueError('Manifest escapes directory')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('HASH_MISMATCH '+name)
        count+=1
    full=json.loads((BASE/'full-134/summary.json').read_text())
    if (full['status'],full['frames'],full['checks'],full['errors'])!=('FRAME_FUNCTIONAL_PASS_NOT_STA',134,6331544,0):
        raise ValueError('Full frame result changed')
    if not all(x['pass'] and x['exit_code']==0 and not x['timeout'] for x in full['commands']):
        raise ValueError('Incomplete full-frame run')
    if not json.loads((BASE/'public-units/summary.json').read_text())['pass']:
        raise ValueError('Unit suite incomplete')
    print('PUBLICATION_EVIDENCE_PASS files='+str(count))
if __name__=='__main__':main()
