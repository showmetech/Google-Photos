#ifndef ProductVersion
#define ProductVersion "2026.11.7.2"
#endif
[Setup]
#ifdef TestBuild
AppId={{E92742ED-68B5-4EF3-8591-0D542FAEE13E}
OutputDir=test-installer
OutputBaseFilename=Google-Photos-Uploader-Test-Setup
#else
AppId={{7A9317C8-AC8E-4938-9B32-7468D085D617}
OutputDir=artifacts\packages
OutputBaseFilename=Google-Photos-Uploader-{#ProductVersion}-Setup
#endif
AppName=Google Photos Uploader
AppVersion={#ProductVersion}
DefaultDirName={localappdata}\Programs\Google Photos Upload Manager
#ifdef TestBuild
DefaultGroupName=Google Photos Uploader Test
#else
DefaultGroupName=Google Photos Uploader
#endif
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible or arm64
ArchitecturesInstallIn64BitMode=x64compatible or arm64
MinVersion=10.0.22000
SetupIconFile=PhotosNative\Assets\App.ico
UninstallDisplayIcon={app}\native\GooglePhotosWidget.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=no
RestartApplications=no
VersionInfoVersion={#ProductVersion}
[Languages]
#include "installer-languages.iss"
[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"
Name: "startup"; Description: "{cm:StartupTask}"; Flags: unchecked
[CustomMessages]
english.StartupTask=Start with Windows (hidden in the notification area)
english.OperationActive=An upload or another operation is active. Wait for it to finish, then retry.
english.CloseManager=Close the previous Google Photos manager, then retry. Existing operations were preserved.
english.MigrationFailed=User data migration could not be completed. Existing data was preserved.
brazilianportuguese.StartupTask=Iniciar com o Windows (oculto na bandeja)
brazilianportuguese.OperationActive=Há um envio ou outra operação em andamento. Aguarde a conclusão e tente novamente.
brazilianportuguese.CloseManager=Feche o gerenciador antigo do Google Fotos e tente novamente. As operações existentes foram preservadas.
brazilianportuguese.MigrationFailed=Não foi possível concluir a migração dos dados. Os dados anteriores foram preservados.
[Files]
Source: "artifacts\shared\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "artifacts\native-x64\*"; DestDir: "{app}\native"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: not IsArm64
Source: "artifacts\native-arm64\*"; DestDir: "{app}\native"; Flags: ignoreversion recursesubdirs createallsubdirs; Check: IsArm64
Source: "backend\maintenance.py"; DestDir: "{tmp}"; DestName: "photos-update-helper.py"; Flags: dontcopy
[Icons]
Name: "{group}\Google Photos Uploader"; Filename: "{app}\native\GooglePhotosWidget.exe"
Name: "{userdesktop}\Google Photos Upload Manager"; Filename: "{app}\native\GooglePhotosWidget.exe"; IconFilename: "{app}\native\Assets\App.ico"; Tasks: desktopicon
[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Google Photos Uploader"; ValueData: """{app}\native\GooglePhotosWidget.exe"" --minimized"; Tasks: startup; Flags: uninsdeletevalue
[Run]
Filename: "{app}\native\GooglePhotosWidget.exe"; Parameters: "--settings"; Flags: nowait postinstall skipifsilent
[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var ExitCode: Integer;
begin
 Result := '';
 if FileExists(ExpandConstant('{app}\runtime\python.exe')) then begin
  ExtractTemporaryFile('photos-update-helper.py');
  if not Exec(ExpandConstant('{app}\runtime\python.exe'), '-X utf8 "' + ExpandConstant('{tmp}\photos-update-helper.py') + '" --app "' + ExpandConstant('{app}') + '" --prepare-update', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
   Result := CustomMessage('CloseManager')
  else if ExitCode = 2 then Result := CustomMessage('OperationActive')
  else if ExitCode <> 0 then Result := CustomMessage('CloseManager');
 end;
end;
procedure CurStepChanged(CurStep: TSetupStep);
var ExitCode: Integer;
begin
 if CurStep = ssPostInstall then begin
  if not Exec(ExpandConstant('{app}\runtime\python.exe'), '-X utf8 "' + ExpandConstant('{app}\maintenance.py') + '" --migrate', '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then RaiseException(CustomMessage('MigrationFailed'));
  if ExitCode <> 0 then RaiseException(CustomMessage('MigrationFailed'));
 end;
end;
function InitializeUninstall(): Boolean;
var ExitCode: Integer;
begin
 Result := Exec(ExpandConstant('{app}\runtime\python.exe'), '-X utf8 "' + ExpandConstant('{app}\maintenance.py') + '" --prepare-update', '', SW_HIDE, ewWaitUntilTerminated, ExitCode);
 if Result then Result := ExitCode = 0;
 if not Result then MsgBox('Close Google Photos Uploader after its current operation completes, then retry. User data is preserved.', mbInformation, MB_OK);
end;


