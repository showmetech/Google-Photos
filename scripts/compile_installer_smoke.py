"""Compile the actual installer policy code with an inert fixture; never install."""
import argparse,json,subprocess,tempfile
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--compiler',required=True)
    args=parser.parse_args()
    root=Path(__file__).resolve().parent.parent
    source=(root/'installer.iss').read_text(encoding='utf-8-sig')
    messages=source.split('[CustomMessages]\n',1)[1].split('[Files]\n',1)[0]
    code=source.split('[Code]\n',1)[1]
    with tempfile.TemporaryDirectory(prefix='photos-installer-compile-') as folder:
        fixture=Path(folder)/'fixture.iss'
        fixture.write_text('[Setup]\nAppId=PhotosInstallerCompileOnly\nAppName=Photos installer compile check\n'
            'AppVersion=1.0\nDefaultDirName={tmp}\\PhotosInstallerCompileOnly\nUninstallable=no\n'
            'CreateUninstallRegKey=no\nOutputBaseFilename=compile-only\n'
            '[Languages]\nName: "english"; MessagesFile: "compiler:Default.isl"\n'
            'Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\\BrazilianPortuguese.isl"\n'
            '[CustomMessages]\n'+messages+'[Code]\n'+code,encoding='utf-8-sig')
        for defines in ([],['/DTestBuild']):
            result=subprocess.run([args.compiler,'/Qp',*defines,str(fixture)],capture_output=True,text=True)
            if result.returncode:raise RuntimeError(result.stdout+'\n'+result.stderr)
    print(json.dumps({'production_policy_compiles':True,'isolated_test_policy_compiles':True,'installer_executed':False}))

if __name__=='__main__':main()
