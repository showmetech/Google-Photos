"""Fail-closed audit of expanded distribution files. Never prints secret values."""
import argparse,json,re,zipfile,os,hashlib
from pathlib import Path,PurePosixPath

PRIVATE_NAMES={'config.json','rclone.conf','.env','native-last-preview.jpg',
               'native-preview-source.json','current_status.json','ui-service-status.json',
               'historical-online-inventory.json','deployment-installed.json'}
PRIVATE_DIRS={'audit','logs','backups','secrets','.git','__pycache__','ui-receipts','ui-commands'}
PATTERNS=[re.compile(rb'ya29\.[A-Za-z0-9_-]{24,}'),
          re.compile(rb'1//0[A-Za-z0-9_-]{64,}'),
          re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]


def inspect_file(name,data,sensitive_values=(),vendor_trusted=False):
    path=PurePosixPath(name.replace('\\','/'))
    lower=path.name.lower();parts={p.lower() for p in path.parts}
    reasons=[]
    media={'.jpg','.jpeg','.heic','.heif','.mp4','.mov','.webp','.avif','.dng','.nef','.arw'}
    if path.suffix.lower() in media:reasons.append('unexpected photo or video in application payload')
    if lower=='config.example.json':
        try:
            example=json.loads(data.decode('utf-8-sig'))
            if example.get('photos_root') or example.get('photos_roots') or example.get('auto_monitor_enabled') or not example.get('dry_run',True):
                reasons.append('unsafe or personalized first-run defaults')
        except (ValueError,UnicodeError):reasons.append('invalid first-run defaults')
    if lower in PRIVATE_NAMES or parts & PRIVATE_DIRS:reasons.append('private state or directory')
    if lower.endswith(('.sqlite','.sqlite-wal','.sqlite-shm','.db','.pfx','.key','.pdb','.pyc')):reasons.append('private database/key/debug artifact')
    if lower.startswith(('client_secret','credentials')) and lower.endswith('.json'):reasons.append('authorization file')
    views=[data]
    for encoding in ('utf-16-le','utf-16-be'):
        try:views.append(data.decode(encoding,errors='ignore').encode('utf-8'))
        except UnicodeError:pass
    if not vendor_trusted and any(pattern.search(view) for pattern in PATTERNS for view in views):reasons.append('credential pattern requiring review')
    profile=os.environ.get('USERPROFILE','')
    if profile and len(profile)>8:
        for variant in (profile,profile.replace('\\','/')):
            if any(variant.lower().encode(encoding) in data.lower() for encoding in ('utf-8','utf-16-le','utf-16-be')):
                reasons.append('local user-profile path detected');break
    for value in sensitive_values:
        if len(value)>=8 and any(value.encode(encoding) in data for encoding in ('utf-8','utf-16-le','utf-16-be')):
            reasons.append('local sensitive value detected');break
    return [{'path':str(path),'reason':reason} for reason in reasons]


def audit(root,sensitive_values=(),vendor_hashes=None):
    root=Path(root);issues=[];count=0;vendor_hashes=vendor_hashes or {}
    def inspect(name,data):
        trusted=vendor_hashes.get(name)==hashlib.sha256(data).hexdigest()
        return inspect_file(name,data,sensitive_values,trusted)
    if root.is_file() and root.suffix.lower() in ('.msix','.appx','.zip'):
        with zipfile.ZipFile(root) as archive:
            for item in archive.infolist():
                if item.is_dir():continue
                count+=1;issues+=inspect(item.filename,archive.read(item))
    elif root.is_dir():
        for path in root.rglob('*'):
            if path.is_file():count+=1;issues+=inspect(path.relative_to(root).as_posix(),path.read_bytes())
    else:raise ValueError('Expanded distribution or MSIX/Appx archive required')
    return {'passed':not issues,'files_checked':count,'issues':issues}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('path');parser.add_argument('--output');parser.add_argument('--vendor-manifest')
    args=parser.parse_args();vendors=json.loads(Path(args.vendor_manifest).read_text()) if args.vendor_manifest else {};result=audit(args.path,vendor_hashes=vendors)
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.output:Path(args.output).write_text(text,encoding='utf-8')
    print(text);raise SystemExit(0 if result['passed'] else 1)

if __name__=='__main__':main()

