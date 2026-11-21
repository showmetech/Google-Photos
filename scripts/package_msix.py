import argparse,json,shutil,subprocess,sys,xml.sax.saxutils as xml
from pathlib import Path
from PIL import Image
p=argparse.ArgumentParser();p.add_argument('--architecture',choices=['x64','arm64'],required=True);p.add_argument('--makeappx',required=True);p.add_argument('--identity');p.add_argument('--development',action='store_true');a=p.parse_args()
root=Path(__file__).resolve().parents[1];cfg=json.loads((root/'release.json').read_text());version=cfg['version'];year,month,day,revision=map(int,version.split('.'));assert 0<=revision<100;store_version=f'{year}.{month}.{day*100+revision}.0'
if a.development:
 identity={'name':'GooglePhotosUploader.Development','publisher':'CN=DevelopmentOnly','publisherDisplayName':'Development build'}
else:
 if not a.identity:p.error('Partner Center identity is required for a Store package; use --development only for local validation')
 identity=json.loads(Path(a.identity).read_text());assert all(identity.get(k) for k in ['name','publisher','publisherDisplayName','productId'])
 assert 'Development' not in identity['publisher']
stage=root/'staging'/a.architecture
if stage.exists():
 assert stage.resolve()==root.resolve()/'staging'/a.architecture,'Unexpected staging target'
 shutil.rmtree(stage)
shutil.copytree(root/'artifacts/shared',stage,ignore=shutil.ignore_patterns('*.pyc','*.pdb','__pycache__'))
shutil.copytree(root/f'artifacts/native-{a.architecture}',stage/'native',ignore=shutil.ignore_patterns('*.pdb','*.pyc','__pycache__'))
# Validate the actual staging payload, before sealing it into the Store package.
subprocess.run([str(stage/'runtime/python.exe'),'-B',str(root/'scripts/verify_runtime.py')],check=True)
assets=stage/'Assets';assets.mkdir()
with Image.open(root/'PhotosNative/Assets/App.png') as icon:
 for name,size in [('StoreLogo',50),('Square44x44Logo',44),('Square150x150Logo',150)]:icon.resize((size,size),Image.Resampling.LANCZOS).save(assets/(name+'.png'))
escape=lambda v:xml.escape(v,{'"':'&quot;'})
manifest=f'''<?xml version="1.0" encoding="utf-8"?>
<Package xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10" xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10" xmlns:uap5="http://schemas.microsoft.com/appx/manifest/uap/windows10/5" xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities" IgnorableNamespaces="uap uap5 rescap">
 <Identity Name="{escape(identity['name'])}" Publisher="{escape(identity['publisher'])}" Version="{store_version}" ProcessorArchitecture="{a.architecture}" />
 <Properties><DisplayName>{escape(cfg["productName"])}</DisplayName><PublisherDisplayName>{escape(identity['publisherDisplayName'])}</PublisherDisplayName><Description>Photo and video upload manager</Description><Logo>Assets\\StoreLogo.png</Logo></Properties>
 <Resources><Resource Language="en-US"/><Resource Language="pt-BR"/><Resource Language="es-ES"/></Resources>
 <Dependencies><TargetDeviceFamily Name="Windows.Desktop" MinVersion="{cfg['minimumWindows']}" MaxVersionTested="10.0.26100.0"/></Dependencies>
 <Applications><Application Id="GooglePhotosUploader" Executable="native\\GooglePhotosWidget.exe" EntryPoint="Windows.FullTrustApplication">
 <uap:VisualElements DisplayName="{escape(cfg["productName"])}" Description="Photo and video upload manager" Square150x150Logo="Assets\\Square150x150Logo.png" Square44x44Logo="Assets\\Square44x44Logo.png" BackgroundColor="transparent"/>
 <Extensions><uap5:Extension Category="windows.startupTask" Executable="native\\GooglePhotosWidget.exe" EntryPoint="Windows.FullTrustApplication"><uap5:StartupTask TaskId="GooglePhotosStartup" Enabled="false" DisplayName="{escape(cfg["productName"])}"/></uap5:Extension></Extensions>
 </Application></Applications><Capabilities><rescap:Capability Name="runFullTrust"/></Capabilities>
</Package>'''
(stage/'AppxManifest.xml').write_text(manifest,encoding='utf-8')
from distribution_audit import audit
vendors=json.loads((root/'artifacts/vendor-files.json').read_text())
report=audit(stage,vendor_hashes=vendors)
if not report['passed']:raise RuntimeError(json.dumps(report))
out=root/'artifacts/packages';out.mkdir(exist_ok=True)
package=out/f'GooglePhotosUploader-{version}-{a.architecture}{"-development" if a.development else ""}.msix'
result=subprocess.run([a.makeappx,'pack','/d',str(stage),'/p',str(package),'/o'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(out/(a.architecture+'-makeappx.log')).write_bytes(result.stdout)
if result.returncode:
 print(result.stdout.decode(errors='replace')[-6000:]);raise SystemExit(result.returncode)
report=audit(package,vendor_hashes=vendors)
(out/(a.architecture+'-distribution-audit.json')).write_text(json.dumps(report,indent=2))
if not report['passed']:raise RuntimeError('Package content audit failed')
print(package)

