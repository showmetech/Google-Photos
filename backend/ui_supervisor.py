"""App-owned recovery: clean exits respected; repeated crashes open a circuit."""
import json, os, subprocess, time
from pathlib import Path

def supervise(command, log, run=subprocess.run, sleep=time.sleep):
    failures = 0
    while True:
        started = time.monotonic()
        result = run(command, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        log({'event': 'ui_exit', 'exit_code': result.returncode, 'at': time.time()})
        if result.returncode == 0: return 0
        failures = 1 if time.monotonic() - started > 300 else failures + 1
        if failures >= 5:
            log({'event': 'recovery_paused', 'reason': 'five_consecutive_crashes', 'at': time.time()})
            return result.returncode
        sleep(min(30, 2 ** failures))

def main(root, args):
    home = Path(os.environ.get('GOOGLE_PHOTOS_HOME') or Path(os.environ['LOCALAPPDATA']) / 'GooglePhotosUploader')
    if not (home / 'config.json').exists():
        code = subprocess.run([str(root/'runtime'/'pythonw.exe'), str(root/'maintenance.py'), '--migrate'], creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).returncode
        if code: return code
    os.environ['GOOGLE_PHOTOS_HOME'] = str(home)
    folder = home/'logs'; folder.mkdir(parents=True, exist_ok=True)
    def log(record):
        with (folder/'ui-recovery.jsonl').open('a',encoding='utf-8') as stream: stream.write(json.dumps(record)+'\n')
    return supervise([str(root/'native'/'GooglePhotosWidget.exe'), '--supervised', *args], log)
