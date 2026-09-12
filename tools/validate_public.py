"""Library-free verification entry point. Linux/WSL; unique persistent output."""
import argparse,json,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    commands=[
      ('reference',[sys.executable,'verification/reference_model.py']),
      ('evidence',[sys.executable,'experiments/fir_core_opt/verify_results.py']),
      ('publication',[sys.executable,'tools/verify_publication.py']),
      ('documentation',[sys.executable,'tools/check_docs.py']),
      ('buffer-tests',[sys.executable,'-m','unittest','discover','-s','experiments/fir_pipeline','-p','test_buffer_fanout.py']),
      ('mac32',[sys.executable,'experiments/fir_core_opt/test_mac.py','--variant','deep32','--latency','32','--out',str(out/'mac32')]),
      ('credit',[sys.executable,'experiments/fir_core_opt/test_credit.py','--onehot','--out',str(out/'credit')]),
      ('credit-negative',[sys.executable,'experiments/fir_core_opt/test_credit.py','--onehot','--negative','--out',str(out/'credit-negative')]),
    ]
    rows=[]
    try:
        for name,cmd in commands:
            start=time.monotonic()
            with (out/(name+'.log')).open('w') as log:
                run=subprocess.run(cmd,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=420)
            rows.append({'test':name,'exit_code':run.returncode,'seconds':time.monotonic()-start})
            print(name+': '+str(run.returncode),flush=True)
            if run.returncode: raise RuntimeError('Inspect '+str(out/(name+'.log')))
    finally:
        result={'pass':len(rows)==len(commands) and all(row['exit_code']==0 for row in rows),'tests':rows}
        (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PUBLIC_TESTS_PASS')
if __name__=='__main__':main()
