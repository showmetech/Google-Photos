param([string]$AppPath=(Join-Path $env:LOCALAPPDATA 'Programs\Google Photos Upload Manager'),[string]$StatePath=(Join-Path $env:LOCALAPPDATA 'GooglePhotosUploader'))
$ErrorActionPreference='Stop'
$app=[IO.Path]::GetFullPath($AppPath)
$issues=@()
foreach($name in 'config.json','data','audit','logs','backup') {if(Test-Path -LiteralPath (Join-Path $app $name)){$issues+="Legacy state in installation: $name"}}
$programs=Split-Path $app
$issues+=@(Get-ChildItem -LiteralPath $programs -Directory -Filter 'Photos-Backup-*' | ForEach-Object {"Backup in Programs: $($_.FullName)"})
if(-not (Test-Path -LiteralPath (Join-Path $app 'native\GooglePhotosWidget.exe'))){$issues+='Native application missing'}
if(-not (Test-Path -LiteralPath (Join-Path $StatePath 'config.json'))){$issues+='Active per-user configuration missing'}
$trayKey='HKCU:\Control Panel\NotifyIconSettings'
$legacyHost=Join-Path $app 'runtime\pythonw.exe'
foreach($entry in Get-ChildItem $trayKey -ErrorAction SilentlyContinue){$v=Get-ItemProperty $entry.PSPath;if($v.ExecutablePath -eq $legacyHost -and $v.InitialTooltip -eq 'Google Photos Upload Manager'){$issues+='Legacy Python tray registration remains'}}
$record=@{at=(Get-Date -Format o);app=$app;passed=($issues.Count -eq 0);issues=$issues}
$record | ConvertTo-Json -Depth 4
if($issues.Count){throw 'Installation audit failed. Preserve user data; investigate and archive verified legacy items before declaring the update complete.'}
