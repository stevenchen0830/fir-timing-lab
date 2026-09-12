"""Bounded Linux EDA execution; private model qualification; no downloads."""
import hashlib, json, os, re, shutil, signal, subprocess, time
from pathlib import Path

LIB_HASHES = {
    'fast.lib': '8ee6e41473acd3e875b8d1473185bedc5d78564a4d56001a8af8f04658f75b82',
    'slow.lib': 'c6dc5053db819a3deff380003ac0d0eae695c22b19e5461563e41fe9fc2b41ca',
    'typical.lib': 'f79391e02ee6a159c42428d7276ce9bdaea063090a153b6a9a650cff0f7146e5',
}
MODEL_FILES = (*LIB_HASHES, 'tech.lef', 'cells.lef')

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''): h.update(chunk)
    return h.hexdigest()

def tool_identity(command):
    executable = shutil.which(command)
    if not executable: raise ValueError('Tool not found: ' + command)
    executable = Path(executable).resolve()
    return {'path': str(executable), 'sha256': sha(executable)}

def copy_models(source, target, repo):
    """Whitelist exact files; reject public model locations or changed libraries."""
    source = Path(source).resolve()
    if source == repo or repo in source.parents:
        raise ValueError('Private models must remain outside the public repository')
    for name in MODEL_FILES:
        if not (source/name).is_file(): raise ValueError('Missing private input: '+name)
    for name, expected in LIB_HASHES.items():
        if sha(source/name) != expected: raise ValueError('LIBRARY_CHANGED '+name)
    target.mkdir()
    for name in MODEL_FILES: shutil.copy2(source/name, target/name)
    return {name: sha(target/name) for name in MODEL_FILES}

def save(path, obj): path.write_text(json.dumps(obj, indent=2)+'\n')

def run_stage(name, command, out, limit, env, rows):
    """Stop only our process group on timeout; preserve diagnostic output."""
    started = time.monotonic(); timed_out = False
    with (out/(name+'.log')).open('w') as log:
        proc = subprocess.Popen(['/usr/bin/time', '-v', '-o', str(out/(name+'.resources')), *command],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True, env=env)
        save(out/'active.json', {'stage':name,'process_group':proc.pid,
            'timeout_seconds':limit,'command':command})
        print(json.dumps({'stage':name,'pid':proc.pid,'limit_seconds':limit}), flush=True)
        try: proc.wait(timeout=limit)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            timed_out = True
            os.killpg(proc.pid, signal.SIGTERM)
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL); proc.wait()
    row = {'stage':name,'exit_code':proc.returncode,'timeout':timed_out,
        'wall_seconds':time.monotonic()-started,'log_sha256':sha(out/(name+'.log'))}
    resources = out/(name+'.resources')
    if resources.exists():
        match = re.search(r'Maximum resident set size \(kbytes\):\s*(\d+)', resources.read_text())
        row['peak_rss_kib'] = int(match[1]) if match else None
    rows.append(row); save(out/'stages.json',rows)
    save(out/'active.json',{'stage':name,'state':'EXITED','exit_code':proc.returncode})
    print(json.dumps(row),flush=True)
    if timed_out or proc.returncode:
        raise RuntimeError(name+' failed or exceeded its budget; inspect log/checkpoints')

