import sys
import hashlib,json,msvcrt,os,sqlite3,subprocess,tempfile
from pathlib import Path
work=Path(__file__).parent;stage=work/'backend'
python=Path(sys.executable)
checks={}
with tempfile.TemporaryDirectory(prefix='photos-migration-') as temp:
    old=Path(temp)/'old installation';old.mkdir();(old/'data').mkdir()
    new=Path(temp)/'new user data';pictures=Path(temp)/'Photos';pictures.mkdir()
    cfg={'photos_root':str(pictures),'auto_monitor_enabled':True,'database':'data/history.sqlite','rclone_config':'data/rclone.conf','logs_dir':'logs','audit_dir':'audit'}
    (old/'config.json').write_text(json.dumps(cfg),encoding='utf-8')
    profile=old/'data'/'rclone.conf';profile.write_text('[gphotos]\ntype = google photos\nclient_id = TEST_ONLY\n',encoding='utf-8')
    db=sqlite3.connect(old/'data'/'history.sqlite');db.execute('create table media(path text,status text,evidence_kind text)');db.execute("insert into media values('fixture','uploaded','explicit_fixture_declaration')");db.commit();db.close()
    env=dict(os.environ,GOOGLE_PHOTOS_HOME=str(new))
    result=subprocess.run([str(python),str(stage/'maintenance.py'),'--app',str(old),'--migrate'],env=env,capture_output=True,text=True)
    assert result.returncode==0,result.stdout+result.stderr
    migrated=json.loads((new/'config.json').read_text(encoding='utf-8'))
    assert migrated['photos_root']==cfg['photos_root'] and migrated['auto_monitor_enabled']
    assert hashlib.sha256(profile.read_bytes()).digest()==hashlib.sha256((new/'data'/'rclone.conf').read_bytes()).digest()
    db=sqlite3.connect(new/'data'/'gphotos_uploader.sqlite');assert db.execute('select * from media').fetchall()==[('fixture','uploaded','explicit_fixture_declaration')];db.close()
    checks['state_and_authorization_preserved']=True
    before=(new/'config.json').read_bytes()
    subprocess.run([str(python),str(stage/'maintenance.py'),'--app',str(old),'--migrate'],env=env,check=True)
    assert before==(new/'config.json').read_bytes();checks['migration_idempotent']=True
    lock=new/'data'/'worker.lock'
    with lock.open('w+b') as handle:
        handle.write(b'0');handle.flush();handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        result=subprocess.run([str(python),str(stage/'gphotos_uploader.py'),'scan'],env=env,capture_output=True)
        assert result.returncode==75,result.stderr
        checks['parallel_cli_worker_rejected']=True
        result=subprocess.run([str(python),str(stage/'maintenance.py'),'--app',str(old),'--prepare-update'],env=env,capture_output=True)
        assert result.returncode==2,result.stderr
        checks['update_refused_during_worker']=True
        handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)
print(json.dumps(checks,indent=2))
(work/'migration-results.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
