"""Assemble a clean Python runtime; never copy a user profile or tokens."""
import argparse, hashlib, json, shutil, subprocess, sys, urllib.request, zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--seed',required=True);p.add_argument('--rclone-archive');p.add_argument('--skip-pip',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'release.json').read_text());seed=Path(a.seed);target=root/'artifacts/shared';runtime=target/'runtime'
if target.exists() and any(target.iterdir()):raise RuntimeError('Clean distribution output required; existing files were preserved')
runtime.mkdir(parents=True,exist_ok=True)
for name in ['python.exe','pythonw.exe','python3.dll','python313.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt']:
 if (seed/name).exists():shutil.copy2(seed/name,runtime/name)
for name in ['DLLs','Lib','tcl']:
 shutil.copytree(seed/name,runtime/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('site-packages','__pycache__','test','tests','idlelib','ensurepip'))
(runtime/'python313._pth').write_text('.\n..\nDLLs\nLib\nLib/site-packages\nimport site\n')
(runtime/'sitecustomize.py').write_text('import sys\nsys.dont_write_bytecode = True\n',encoding='utf-8')
if not a.skip_pip:
 subprocess.run([sys.executable,'-m','pip','install','--no-compile','--only-binary=:all:','--platform','win_amd64','--python-version','3.13','--implementation','cp','--abi','cp313','--target',str(runtime/'Lib/site-packages'),'-r',str(root/'requirements.txt')],check=True)
else:
 # Wheel RECORD includes native extensions and DLLs beside the import package.
 from runtime_dependencies import copy_pinned_distributions
 copy_pinned_distributions(seed,runtime/'Lib/site-packages',root/'requirements.txt')
allowed_backend=['app_config.py','app_paths.py','compare_originals.py','google_photos_upload_manager.pyw','gphotos_uploader.py','launch_manager.pyw','maintenance.py','new_media_notifications.py','online_reconciliation.py','photos_service.pyw','reliable_history.py','ui_supervisor.py','widget_ui.py','config.example.json']
for name in allowed_backend:shutil.copy2(root/'backend'/name,target/name)
for old,new in [('App.ico','AppIconYellow.ico'),('App.png','AppIconTray.png')]:shutil.copy2(root/'PhotosNative/Assets'/old,target/new)
cache=root/'.tools';cache.mkdir(exist_ok=True)
archive=Path(a.rclone_archive) if a.rclone_archive else cache/f'rclone-v{cfg["rclone"]}-windows-amd64.zip'
if not archive.exists():urllib.request.urlretrieve(f'https://downloads.rclone.org/v{cfg["rclone"]}/{archive.name}',archive)
checks_path=archive.parent/'SHA256SUMS'
if not checks_path.exists():
 if a.rclone_archive:raise RuntimeError('Official SHA256SUMS is required beside the archive')
 urllib.request.urlretrieve(f'https://downloads.rclone.org/v{cfg["rclone"]}/SHA256SUMS',checks_path)
checks=checks_path.read_text()
expected=next(line.split()[0] for line in checks.splitlines() if line.strip().endswith(archive.name))
assert hashlib.sha256(archive.read_bytes()).hexdigest().lower()==expected.lower(),'rclone digest mismatch'
with zipfile.ZipFile(archive) as z:
 dest=target/'tools/rclone';dest.mkdir(parents=True,exist_ok=True)
 for item in z.namelist():
  if Path(item).name in ('rclone.exe','COPYING','README.txt','rclone.1'):
   (dest/Path(item).name).write_bytes(z.read(item))
subprocess.run([str(runtime/'python.exe'),'-B',str(root/'scripts/verify_runtime.py')],check=True)
assert not list(target.rglob('rclone.conf')) and not list(target.rglob('*.sqlite'))

from distribution_audit import audit
vendors={p.relative_to(target).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in (target/'tools/rclone').iterdir() if p.is_file()}
(root/'artifacts/vendor-files.json').write_text(json.dumps(vendors,indent=2))
report=audit(target,vendor_hashes=vendors)
if not report['passed']:raise RuntimeError(json.dumps(report))
(root/'artifacts/runtime-distribution-audit.json').write_text(json.dumps(report,indent=2))

