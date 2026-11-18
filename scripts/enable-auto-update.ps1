param()
$ErrorActionPreference='Stop'
$homePath=Join-Path $env:LOCALAPPDATA 'GooglePhotosUploader'
$target=Join-Path $homePath 'updater'
$taskName='Google Photos Uploader - Updates'
$powershell=$null
foreach($candidate in @((Join-Path $env:ProgramFiles 'PowerShell\7\pwsh.exe'),(Join-Path $env:USERPROFILE 'scoop\apps\pwsh\current\pwsh.exe'),(Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'))){
 if(Test-Path -LiteralPath $candidate){
  $policy=(& $candidate -NoProfile -NonInteractive -Command 'Get-ExecutionPolicy'|Out-String).Trim()
  if($LASTEXITCODE -eq 0 -and $policy -in @('RemoteSigned','Unrestricted','Bypass')){$powershell=$candidate;break}
 }
}
if(-not $powershell){throw 'No independent PowerShell host permits local scripts. No policy was changed.'}
New-Item -ItemType Directory $target -Force|Out-Null
$previous=Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if($previous){
 if($previous.Actions.Arguments -notlike ('*'+(Join-Path $target 'release.ps1')+'*')){throw 'Existing task has another owner; it was preserved'}
 Export-ScheduledTask -TaskName $taskName|Set-Content -LiteralPath (Join-Path $target 'previous-task.xml')
}
foreach($name in 'release.ps1','auto-update.ps1','audit-installation.ps1'){
 $source=Join-Path $PSScriptRoot $name;$dest=Join-Path $target $name
 if(Test-Path -LiteralPath $dest){Copy-Item -LiteralPath $dest -Destination ($dest+'.previous') -Force}
 Copy-Item -LiteralPath $source -Destination $dest -Force
 if((Get-FileHash -LiteralPath $source).Hash -ne (Get-FileHash -LiteralPath $dest).Hash){throw 'Updater copy verification failed'}
}
$arguments='-NoProfile -NonInteractive -WindowStyle Hidden -File "'+(Join-Path $target 'release.ps1')+'" -Automatic -Install'
$action=New-ScheduledTaskAction -Execute $powershell -Argument $arguments -WorkingDirectory $target
$login=New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
$periodic=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Hours 6)
$principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings=New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 1)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger @($login,$periodic) -Principal $principal -Settings $settings -Description 'Google Photos Uploader: install only stable releases with successful GitHub and Store submission gates; defer during uploads.' -Force|Out-Null
Start-ScheduledTask -TaskName $taskName
Get-ScheduledTask -TaskName $taskName|Select-Object TaskName,State,@{n='Action';e={$_.Actions.Arguments}}

