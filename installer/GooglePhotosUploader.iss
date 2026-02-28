; Inno Setup script
#define MyAppName "Google Photos Uploader"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Bruno"
#define MyAppExeName "GooglePhotosUploader.exe"

[Setup]
AppId={{8E8A0432-CC91-4EBA-8E7C-B40E5AA3C1E4}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\GooglePhotosUploader
DefaultGroupName=Google Photos Uploader
OutputDir=.
OutputBaseFilename=GooglePhotosUploaderSetup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "portuguesebrazil"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\gphotos_allinone.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Google Photos Uploader"; Filename: "{app}\{#MyAppExeName}"
Name: "{commondesktop}\Google Photos Uploader"; Filename: "{app}\{#MyAppExeName}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir Google Photos Uploader"; Flags: nowait postinstall skipifsilent
