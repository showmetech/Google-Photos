import sys
import json,os,subprocess,tempfile,time,uuid
from pathlib import Path
stage=Path(__file__).parent/'backend'
python=Path(sys.executable)
def wait(predicate,timeout=25):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        result=predicate()
        if result:return result
        time.sleep(.2)
    raise RuntimeError('Service test timed out')
results={}
with tempfile.TemporaryDirectory(prefix='photos-service-') as temp:
    state=Path(temp)/'state';env=dict(os.environ,GOOGLE_PHOTOS_HOME=str(state))
    process=subprocess.Popen([str(python),str(stage/'photos_service.pyw')],env=env,creationflags=subprocess.CREATE_NO_WINDOW)
    def read(path):
        try:return json.loads(path.read_text(encoding='utf-8'))
        except (OSError,ValueError):return {}
    status_path=state/'data'/'ui-service-status.json'
    try:
        wait(lambda:read(status_path))
        results['clean_service_no_auth_or_upload']=not read(status_path)['automatic'] and not read(status_path)['account_configured']
        def request(command,**extra):
            ident=uuid.uuid4().hex;target=state/'data'/'ui-commands'/(ident+'.json')
            temporary=target.with_suffix('.tmp');temporary.write_text(json.dumps(dict(command=command,**extra)),encoding='utf-8');temporary.replace(target)
            receipt=state/'data'/'ui-receipts'/(ident+'.json')
            wait(lambda:read(receipt))
            return receipt
        folder=Path(temp)/'Pictures';folder.mkdir();(folder/'fixture.jpg').write_bytes(b'not a real upload')
        assert read(request('configure',folders=[str(folder)]))['ok']
        assert not read(status_path)['automatic']
        receipt=request('scan');wait(lambda:read(receipt).get('completed'))
        assert read(receipt)['exit_code']==0
        results['setup_and_scan_completion_receipt']=True
        assert not read(request('upload'))['ok']
        results['upload_blocked_without_authorization']=True
        assert not read(request('mark-baseline'))['ok']
        results['baseline_requires_explicit_confirmation']=True
        request('shutdown');process.wait(timeout=10)
        results['graceful_shutdown']=process.returncode==0
    finally:
        if process.poll() is None:process.terminate();process.wait(timeout=10)
assert all(results.values()),results
print(json.dumps(results,indent=2))
(Path(__file__).parent/'service-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
