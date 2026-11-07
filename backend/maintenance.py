"""Installer coordination and non-destructive per-user migration. Never uploads."""
import argparse,hashlib,json,os,shutil,sqlite3,subprocess,sys,time,uuid
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--app',default=str(Path(__file__).resolve().parent))
parser.add_argument('--prepare-update',action='store_true')
parser.add_argument('--migrate',action='store_true')
args=parser.parse_args()
root=Path(args.app).resolve()
standard=Path(os.environ.get('GOOGLE_PHOTOS_HOME') or Path(os.environ['LOCALAPPDATA'])/'GooglePhotosUploader')
home=standard if (standard/'config.json').exists() else root if (root/'config.json').exists() else standard
def read(path):
    try:return json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError,ValueError):return {}
def locked(path):
    if not path.exists():return False
    import msvcrt
    with path.open('a+b') as stream:
        stream.seek(0)
        try:msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:return True
        stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
    return False
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True);temporary=path.with_name(path.name+'.tmp-'+uuid.uuid4().hex)
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
def prepare():
    status=read(home/'data'/'ui-service-status.json')
    fresh=time.time()-status.get('heartbeat',0)<20
    if (fresh and status.get('busy')) or locked(home/'data'/'worker.lock'):
        print('An operation is active. Wait for it to finish before updating.');return 2
    if fresh:
        write(home/'data'/'ui-commands'/(uuid.uuid4().hex+'.json'),{'command':'shutdown'})
        deadline=time.monotonic()+12
        while time.monotonic()<deadline and locked(home/'data'/'manager.lock'):time.sleep(.2)
    if locked(home/'data'/'manager.lock'):
        print('Close the previous manager before updating. No process was forcibly stopped.');return 3
    # The monitor has released its own lock. Close only this application's visual process.
    try:
        import psutil
        expected=os.path.normcase(str(root/'native'/'GooglePhotosWidget.exe'))
        for process in psutil.process_iter(['exe']):
            try:
                if os.path.normcase(process.info['exe'] or '')==expected:process.terminate();process.wait(timeout=10)
            except (psutil.NoSuchProcess,psutil.AccessDenied):continue
    except ImportError:
        exe=root/'native'/'GooglePhotosWidget.exe'
        if exe.exists():subprocess.run([str(exe),'--exit'],timeout=10,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    return 0
def migrate():
    if (standard/'config.json').exists():return 0
    old=root/'config.json'
    if not old.exists():
        sys.path.insert(0,str(root))
        from app_paths import bootstrap
        bootstrap();return 0
    if locked(root/'data'/'manager.lock') or locked(root/'data'/'worker.lock'):
        raise RuntimeError('The previous monitor must stop before migration.')
    cfg=read(old)
    if not cfg:raise ValueError('Existing configuration could not be read; migration stopped.')
    standard.mkdir(parents=True,exist_ok=True)
    for name in ('data','logs','audit'):(standard/name).mkdir(exist_ok=True)
    record={'at':time.time(),'source':str(root),'destination':str(standard),'profile_sha256_preserved':False}
    database=Path(cfg.get('database','data/gphotos_uploader.sqlite'))
    if not database.is_absolute():database=root/database
    if database.exists():
        source=sqlite3.connect(f'file:{database.as_posix()}?mode=ro',uri=True);dest=sqlite3.connect(standard/'data'/'gphotos_uploader.sqlite')
        try:source.backup(dest)
        finally:source.close();dest.close()
    else:cfg['auto_monitor_enabled']=False
    if cfg.get('rclone_config'):
        profile=Path(cfg['rclone_config'])
        if not profile.is_absolute():profile=root/profile
        if profile.exists():
            target=standard/'data'/'rclone.conf';shutil.copy2(profile,target)
            assert hashlib.sha256(profile.read_bytes()).digest()==hashlib.sha256(target.read_bytes()).digest()
            record['profile_sha256_preserved']=True;cfg['rclone_config']=str(target)
    for name in ('logs','audit'):
        folder=Path(cfg.get(name+'_dir',name))
        if not folder.is_absolute():folder=root/folder
        if folder.is_dir():
            for file in folder.iterdir():
                if file.is_file() and file.suffix.lower() in ('.csv','.json','.log','.txt'):shutil.copy2(file,standard/name/file.name)
    for name in ('current_status.json','native-widget.json','native-last-preview.jpg','native-preview-source.json','last_uploaded_preview.jpg'):
        source=root/'data'/name
        if source.is_file():shutil.copy2(source,standard/'data'/name)
    cfg['database']=str(standard/'data'/'gphotos_uploader.sqlite')
    cfg['logs_dir']=str(standard/'logs');cfg['audit_dir']=str(standard/'audit')
    cfg['photos_roots']=cfg.get('photos_roots') or ([cfg['photos_root']] if cfg.get('photos_root') else [])
    # Configuration is the commit marker. The original installation remains untouched.
    write(standard/'migration-receipt.json',record);write(standard/'config.json',cfg)
    return 0
if __name__=='__main__':
    try:raise SystemExit(prepare() if args.prepare_update else migrate() if args.migrate else 0)
    except (OSError,ValueError,RuntimeError,sqlite3.Error) as exc:print(str(exc));raise SystemExit(4)
