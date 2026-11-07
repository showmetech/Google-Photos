"""Safe filesystem and explicit evidence for the uploader. No browser credentials."""
import os,json,tempfile,time,contextlib
from pathlib import Path

def io_path(path):
    text=str(Path(path).absolute())
    if os.name=='nt' and not text.startswith('\\\\?\\'):
        text=('\\\\?\\UNC\\'+text[2:]) if text.startswith('\\\\') else '\\\\?\\'+text
    return Path(text)

def enumerate_media(root,extensions,min_age=0):
    cutoff=time.time_ns()-max(0,min_age)*1_000_000_000
    def fail(exc):raise exc
    for folder,dirs,names in os.walk(io_path(root),onerror=fail):
        dirs[:]=[d for d in dirs if not os.path.islink(Path(folder)/d) and not (hasattr(os.path,"isjunction") and os.path.isjunction(Path(folder)/d))]
        for name in names:
            p=Path(folder)/name
            if p.suffix.lower() not in extensions:continue
            stat=p.stat()
            if stat.st_mtime_ns>cutoff:continue
            text=str(p)
            if text.startswith('\\\\?\\UNC\\'):text='\\\\'+text[8:]
            elif text.startswith('\\\\?\\'):text=text[4:]
            yield Path(text),stat

def atomic_json(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=path.parent,delete=False,suffix='.tmp') as f:
        json.dump(value,f,ensure_ascii=False,indent=2);temp=Path(f.name)
    try:temp.replace(path)
    finally:temp.unlink(missing_ok=True)

@contextlib.contextmanager
def atomic_csv(path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    stream=tempfile.NamedTemporaryFile('w',encoding='utf-8',newline='',dir=path.parent,delete=False,suffix='.tmp')
    temporary=Path(stream.name)
    try:
        yield stream
        stream.close();temporary.replace(path)
    finally:
        stream.close();temporary.unlink(missing_ok=True)

def prepare_schema(db):
    existing={r[1] for r in db.execute('pragma table_info(media)')}
    for name,typ in [('present','integer not null default 1'),('evidence_kind','text'),('content_sha256','text')]:
        if name not in existing:db.execute('alter table media add column '+name+' '+typ)
    db.execute("update media set evidence_kind='preserved_legacy_history' where status='uploaded' and evidence_kind is null")
    db.execute('create table if not exists web_receipts (id integer primary key, created_at text not null, album text not null, receipt_json text not null)')
    db.commit()
