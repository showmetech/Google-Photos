"""Bundle both CPU packages into the single Store upload artifact."""
import argparse,json,shutil,subprocess,zipfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--makeappx',required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1];version=json.loads((root/'release.json').read_text())['version'];packages=root/'artifacts/packages'
sources=[p for p in packages.glob(f'GooglePhotosUploader-{version}-*.msix')]
assert len(sources)==2,'Exactly x64 and ARM64 packages are required'
development=all('-development' in p.name for p in sources)
assert development or all('-development' not in p.name for p in sources),'Mixed package identities'
inputs=root/'staging/bundle-input'
if inputs.exists():shutil.rmtree(inputs)
inputs.mkdir(parents=True)
for source in sources:shutil.copy2(source,inputs/source.name)
name=f'GooglePhotosUploader-{version}{"-development" if development else ""}'
bundle=packages/(name+'.msixbundle')
result=subprocess.run([a.makeappx,'bundle','/d',str(inputs),'/p',str(bundle),'/o'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
(packages/'bundle-makeappx.log').write_bytes(result.stdout)
if result.returncode:print(result.stdout.decode(errors='replace')[-5000:]);raise SystemExit(result.returncode)
with zipfile.ZipFile(packages/(name+'.msixupload'),'w',zipfile.ZIP_STORED) as upload:upload.write(bundle,bundle.name)
print(packages/(name+'.msixupload'))
