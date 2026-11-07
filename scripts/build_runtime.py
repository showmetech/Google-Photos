"""Assemble a clean Python runtime; never copy a user profile or tokens."""
import argparse, hashlib, json, shutil, subprocess, sys, urllib.request, zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--seed',required=True);p.add_argument('--rclone-archive');p.add_argument('--skip-pip',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'release.json').read_text());seed=Path(a.seed);target=root/'artifacts/shared';runtime=target/'runtime';runtime.mkdir(parents=True,exist_ok=True)
for name in ['python.exe','pythonw.exe','python3.dll','python313.dll','vcruntime140.dll','vcruntime140_1.dll','LICENSE.txt']:
 if (seed/name).exists():shutil.copy2(seed/name,runtime/name)
for name in ['DLLs','Lib','tcl']:
 shutil.copytree(seed/name,runtime/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('site-packages','__pycache__','test','tests','idlelib','ensurepip'))
(runtime/'python313._pth').write_text('.\n..\nDLLs\nLib\nLib/site-packages\nimport site\n')
if not a.skip_pip:
 subprocess.run([sys.executable,'-m','pip','install','--only-binary=:all:','--platform','win_amd64','--python-version','3.13','--implementation','cp','--abi','cp313','--target',str(runtime/'Lib/site-packages'),'-r',str(root/'requirements.txt')],check=True)
else:
 # For an already isolated runtime seed only. Select installed dependency names explicitly.
 for name in ('PIL','pillow_heif','psutil','pystray','six.py'):
  source=seed/'Lib/site-packages'/name
  if source.is_dir():shutil.copytree(source,runtime/'Lib/site-packages'/name,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__'))
  else:shutil.copy2(source,runtime/'Lib/site-packages'/name)
 for source in (seed/'Lib/site-packages').glob('*.dist-info'):
  if source.name.lower().startswith(('pillow','psutil','pystray','six-')):shutil.copytree(source,runtime/'Lib/site-packages'/source.name,dirs_exist_ok=True)
for file in (root/'backend').iterdir():
 if file.is_file() and file.suffix in ('.py','.pyw','.json'):shutil.copy2(file,target/file.name)
for old,new in [('App.ico','AppIconYellow.ico'),('App.png','AppIconTray.png')]:shutil.copy2(root/'PhotosNative/Assets'/old,target/new)
cache=root/'.tools';cache.mkdir(exist_ok=True)
archive=Path(a.rclone_archive) if a.rclone_archive else cache/f'rclone-v{cfg["rclone"]}-windows-amd64.zip'
if not archive.exists():urllib.request.urlretrieve(f'https://downloads.rclone.org/v{cfg["rclone"]}/{archive.name}',archive)
if not a.rclone_archive:
 checks=urllib.request.urlopen(f'https://downloads.rclone.org/v{cfg["rclone"]}/SHA256SUMS').read().decode()
 expected=next(line.split()[0] for line in checks.splitlines() if line.strip().endswith(archive.name))
 assert hashlib.sha256(archive.read_bytes()).hexdigest().lower()==expected.lower(),'rclone digest mismatch'
with zipfile.ZipFile(archive) as z:
 dest=target/'tools/rclone';dest.mkdir(parents=True,exist_ok=True)
 for item in z.namelist():
  if Path(item).name in ('rclone.exe','COPYING','README.txt','rclone.1'):
   (dest/Path(item).name).write_bytes(z.read(item))
subprocess.run([str(runtime/'python.exe'),'-B','-c','import tkinter,PIL,psutil,pillow_heif;print("Clean runtime OK")'],check=True)
assert not list(target.rglob('rclone.conf')) and not list(target.rglob('*.sqlite'))
