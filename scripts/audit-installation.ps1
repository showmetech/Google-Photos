param([string]$AppPath=(Join-Path $env:LOCALAPPDATA 'Programs\Google Photos Upload Manager'),[string]$StatePath=(Join-Path $env:LOCALAPPDATA 'GooglePhotosUploader'))
$ErrorActionPreference='Stop'
$app=[IO.Path]::GetFullPath($AppPath)
$legacyApp=$app
$store=Get-AppxPackage -Name Showmetech.GooglePhotosUploader -ErrorAction SilentlyContinue
if($store){
 $app=$store.InstallLocation
 $privateState=Join-Path $env:LOCALAPPDATA ('Packages\'+$store.PackageFamilyName+'\LocalCache\Local\GooglePhotosUploader')
 if(-not $PSBoundParameters.ContainsKey('StatePath') -and -not(Test-Path -LiteralPath (Join-Path $StatePath 'config.json')) -and (Test-Path -LiteralPath (Join-Path $privateState 'config.json'))){$StatePath=$privateState}
}
$issues=@()
if($store){
 if($store.Status -ne 'Ok'){$issues+='Microsoft Store reports a package integrity problem'}
 if(Test-Path -LiteralPath (Join-Path $legacyApp 'native\GooglePhotosWidget.exe')){$issues+='Classic binaries remain alongside Microsoft Store'}
 $oldRun=(Get-ItemProperty 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run' -ErrorAction SilentlyContinue).'Google Photos Uploader'
 if($oldRun -and $oldRun.IndexOf($legacyApp,[StringComparison]::OrdinalIgnoreCase) -ge 0){$issues+='Classic startup entry remains alongside Microsoft Store'}
 if(Get-ScheduledTask -TaskName 'Google Photos Uploader - Updates' -ErrorAction SilentlyContinue){$issues+='Independent updater task remains alongside Microsoft Store'}
 if(@(Get-Process GooglePhotosWidget -ErrorAction SilentlyContinue | Where-Object {$_.Path -and $_.Path.StartsWith($legacyApp.TrimEnd('\')+'\',[StringComparison]::OrdinalIgnoreCase)}).Count){$issues+='Classic widget is active instead of the Store edition'}
}
foreach($name in 'config.json','data','audit','logs','backup') {if(Test-Path -LiteralPath (Join-Path $app $name)){$issues+="Legacy state in installation: $name"}}
$programs=Split-Path $legacyApp
if(Test-Path -LiteralPath $programs){$issues+=@(Get-ChildItem -LiteralPath $programs -Directory -Filter 'Photos-Backup-*' | ForEach-Object {"Backup in Programs: $($_.FullName)"})}
if(-not (Test-Path -LiteralPath (Join-Path $app 'native\GooglePhotosWidget.exe'))){$issues+='Native application missing'}
$setupPending=-not (Test-Path -LiteralPath (Join-Path $StatePath 'config.json'))
if($setupPending -and -not $store){$issues+='Active per-user configuration missing'}
$trayKey='HKCU:\Control Panel\NotifyIconSettings'
$legacyHost=Join-Path $legacyApp 'runtime\pythonw.exe'
foreach($entry in Get-ChildItem $trayKey -ErrorAction SilentlyContinue){$v=Get-ItemProperty $entry.PSPath;if($v.ExecutablePath -eq $legacyHost -and $v.InitialTooltip -eq 'Google Photos Upload Manager'){$issues+='Legacy Python tray registration remains'}}
$record=@{at=(Get-Date -Format o);app=$app;state=$StatePath;distribution=$(if($store){'store'}else{'classic'});setupPending=$setupPending;passed=($issues.Count -eq 0);issues=$issues}
$record | ConvertTo-Json -Depth 4
if($issues.Count){throw 'Installation audit failed. Preserve user data; investigate and archive verified legacy items before declaring the update complete.'}
