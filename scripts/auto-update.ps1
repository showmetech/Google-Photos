param([switch]$Install,[switch]$LibraryOnly,
 [string]$AppPath=(Join-Path $env:LOCALAPPDATA 'Programs\Google Photos Upload Manager'),
 [string]$StatePath=(Join-Path $env:LOCALAPPDATA 'GooglePhotosUploader'))
$ErrorActionPreference='Stop'
$repository='showmetech/Google-Photos'
function Get-ReleasePlan($Release,[version]$Installed) {
 if($Release.draft -or $Release.prerelease){throw 'Only stable published releases are allowed'}
 if($Release.tag_name -notmatch '^v(\d+\.\d+\.\d+\.\d+)$'){throw 'Invalid release version'}
 $text=$Matches[1];$version=[version]$text
 if($version -le $Installed){return $null}
 if($Release.target_commitish -notmatch '^[a-f0-9]{40}$'){throw 'A release bound to an exact commit is required'}
 $name="Google-Photos-Uploader-$text-Setup.exe"
 $installer=@($Release.assets|Where-Object name -CEQ $name)
 $sums=@($Release.assets|Where-Object name -CEQ 'SHA256SUMS.txt')
 if($installer.Count -ne 1 -or $sums.Count -ne 1){throw 'Expected one installer and one checksum manifest'}
 foreach($asset in @($installer[0],$sums[0])) {
  $expected="https://github.com/showmetech/Google-Photos/releases/download/v$text/$($asset.name)"
  if($asset.browser_download_url -cne $expected){throw 'Unexpected release download origin'}
 }
 [pscustomobject]@{Version=$text;Commit=$Release.target_commitish;Name=$name;Installer=$installer[0].browser_download_url;Checksums=$sums[0].browser_download_url}
}
function Assert-ReleaseJobs($Runs,$Jobs,[string]$Commit) {
 $valid=@($Runs.workflow_runs|Where-Object { $_.head_sha -ceq $Commit -and $_.path -eq '.github/workflows/release.yml' -and $_.status -eq 'completed' -and $_.conclusion -eq 'success' })
 if(-not $valid.Count){throw 'Approved release workflow has not completed successfully'}
 foreach($name in 'build','github-release','microsoft-store') {
  $match=@($Jobs.jobs|Where-Object {$_.name -ceq $name -and $_.conclusion -eq 'success'})
  if($match.Count -ne 1){throw "Release gate not satisfied: $name"}
 }
}
function Assert-InstallerDigest([string]$Installer,[string]$Manifest,[string]$Name) {
 $lines=@(Get-Content -LiteralPath $Manifest|Where-Object {$_ -cmatch ('^[a-fA-F0-9]{64}  '+[regex]::Escape($Name)+'$')})
 if($lines.Count -ne 1){throw 'Missing or ambiguous installer checksum'}
 $expected=$lines[0].Substring(0,64)
 if((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash -ine $expected){throw 'Installer SHA-256 mismatch'}
}
function Test-UploadBusy([string]$StateDirectory) {
 $statusFile=Join-Path $StateDirectory 'data\ui-service-status.json'
 if(Test-Path -LiteralPath $statusFile){
  $s=Get-Content -LiteralPath $statusFile -Raw|ConvertFrom-Json
  if([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-$s.heartbeat -lt 20 -and $s.busy){return $true}
 }
 $lock=Join-Path $StateDirectory 'data\worker.lock'
 if(Test-Path -LiteralPath $lock){try{$f=[IO.File]::Open($lock,'Open','ReadWrite','None');$f.Dispose()}catch [IO.IOException]{return $true}}
 return $false
}
function Write-UpdateStatus([string]$Status,[string]$Detail='') {
 $target=Join-Path $StatePath 'data\desktop-update-status.json'
 New-Item -ItemType Directory (Split-Path $target) -Force|Out-Null
 $tmp=$target+'.'+[guid]::NewGuid().ToString('N')+'.tmp'
 @{checkedAt=[DateTimeOffset]::UtcNow.ToString('o');status=$Status;detail=$Detail;installedVersion=$script:installed;availableVersion=$script:available;repository=$repository}|ConvertTo-Json|Set-Content -LiteralPath $tmp -Encoding UTF8
 Move-Item -LiteralPath $tmp -Destination $target -Force
}
function Get-PublicApi([string]$Path) {
 Invoke-RestMethod -Uri ('https://api.github.com/repos/'+$repository+'/'+$Path) -Headers @{'User-Agent'='GooglePhotosUploader-DesktopUpdater';Accept='application/vnd.github+json'} -TimeoutSec 30
}
function Stop-PhotosForUpdate {
 if(Test-UploadBusy $StatePath){throw 'Upload active; update deferred'}
 $exe=Join-Path $AppPath 'native\GooglePhotosWidget.exe'
 if(Test-Path -LiteralPath $exe){Start-Process -FilePath $exe -ArgumentList '--exit' -WindowStyle Hidden -Wait|Out-Null}
 $deadline=[DateTime]::UtcNow.AddSeconds(20)
 do {
  $owned=@(Get-Process -ErrorAction SilentlyContinue|Where-Object {$_.Path -and $_.Path.StartsWith($AppPath+'\',[StringComparison]::OrdinalIgnoreCase)})
  if(-not $owned.Count){return}
  Start-Sleep -Milliseconds 250
 }while([DateTime]::UtcNow -lt $deadline)
 throw 'The application did not close cleanly; no update was installed'
}
function Start-PhotosAfterUpdate {
 Start-Process -FilePath (Join-Path $AppPath 'native\GooglePhotosWidget.exe') -ArgumentList '--minimized' -WindowStyle Hidden
}
if($LibraryOnly){return}
$AppPath=[IO.Path]::GetFullPath($AppPath).TrimEnd('\')
$StatePath=[IO.Path]::GetFullPath($StatePath).TrimEnd('\')
$script:installed='unknown';$script:available=$null;$cache=$null;$backup=$null;$stopped=$false;$failureExit=0
$mutex=New-Object Threading.Mutex($false,'Local\Showmetech.GooglePhotos.DesktopUpdate')
if(-not $mutex.WaitOne(0)){$mutex.Dispose();exit 0}
try {
 # Store editions are updated by the Store, never by the independent EXE installer.
 if(Get-AppxPackage -Name Showmetech.GooglePhotosUploader -ErrorAction SilentlyContinue){Write-UpdateStatus 'store_managed';return}
 $exe=Join-Path $AppPath 'native\GooglePhotosWidget.exe'
 if(-not(Test-Path -LiteralPath $exe)){throw 'Desktop installation not found'}
 $script:installed=(Get-Item -LiteralPath $exe).VersionInfo.FileVersion
 try {$release=Get-PublicApi 'releases/latest'}catch {
  if($_.Exception.Response.StatusCode.value__ -eq 404){Write-UpdateStatus 'publication_unavailable' 'No stable public release is available yet';return}
  throw
 }
 $plan=Get-ReleasePlan $release ([version]$script:installed)
 if(-not $plan){Write-UpdateStatus 'up_to_date';return}
 $script:available=$plan.Version
 $runs=Get-PublicApi ('actions/runs?head_sha='+$plan.Commit+'&per_page=20')
 $run=@($runs.workflow_runs|Where-Object {$_.head_sha -ceq $plan.Commit -and $_.path -eq '.github/workflows/release.yml' -and $_.conclusion -eq 'success'}|Sort-Object id -Descending|Select-Object -First 1)
 if(-not $run.Count){throw 'No successful release workflow; update blocked'}
 $jobs=Get-PublicApi ('actions/runs/'+$run[0].id+'/jobs?per_page=100')
 Assert-ReleaseJobs $runs $jobs $plan.Commit
 if(-not $Install){Write-UpdateStatus 'update_available';return}
 if(Test-UploadBusy $StatePath){Write-UpdateStatus 'deferred_upload';return}
 $cache=Join-Path $StatePath ('updates\download-'+[guid]::NewGuid().ToString('N'))
 New-Item -ItemType Directory $cache|Out-Null
 $installer=Join-Path $cache $plan.Name;$manifest=Join-Path $cache 'SHA256SUMS.txt'
 Invoke-WebRequest -Uri $plan.Checksums -OutFile $manifest -UseBasicParsing -TimeoutSec 60
 Invoke-WebRequest -Uri $plan.Installer -OutFile $installer -UseBasicParsing -TimeoutSec 600
 Assert-InstallerDigest $installer $manifest $plan.Name
 if(Test-UploadBusy $StatePath){Write-UpdateStatus 'deferred_upload';return}
 Stop-PhotosForUpdate;$stopped=$true
 $backup=Join-Path $StatePath ('backups\auto-update-'+$script:installed+'-'+[guid]::NewGuid().ToString('N'))
 New-Item -ItemType Directory $backup|Out-Null
 Copy-Item -LiteralPath $AppPath -Destination (Join-Path $backup 'installation') -Recurse
 foreach($file in Get-ChildItem -LiteralPath $AppPath -Recurse -File){
  $relative=$file.FullName.Substring($AppPath.Length+1)
  if((Get-FileHash -LiteralPath $file.FullName).Hash -ne (Get-FileHash -LiteralPath (Join-Path $backup ('installation\'+$relative))).Hash){throw 'Rollback backup verification failed'}
 }
 # State stays outside Programs. The installer does not replace it.
 Copy-Item -LiteralPath (Join-Path $StatePath 'config.json') -Destination (Join-Path $backup 'config.json')
 @{ready=$true;version=$script:installed}|ConvertTo-Json|Set-Content -LiteralPath (Join-Path $backup 'backup-ready.json')
 $result=Start-Process -FilePath $installer -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=startup,desktopicon' -WindowStyle Hidden -Wait -PassThru
 if($result.ExitCode -ne 0){throw "Installer failed with exit code $($result.ExitCode)"}
 & (Join-Path $PSScriptRoot 'audit-installation.ps1') -AppPath $AppPath -StatePath $StatePath
 if(-not $?){throw 'Installation audit failed'}
 if((Get-Item -LiteralPath $exe).VersionInfo.FileVersion -ne $plan.Version){throw 'Installed version does not match release'}
 Start-PhotosAfterUpdate;$stopped=$false
 $deadline=[DateTime]::UtcNow.AddSeconds(30);$healthy=$false
 do {
  Start-Sleep -Seconds 1
  $s=Get-Content -LiteralPath (Join-Path $StatePath 'data\ui-service-status.json') -Raw|ConvertFrom-Json
  $n=Get-Content -LiteralPath (Join-Path $StatePath 'data\ui-native-status.json') -Raw|ConvertFrom-Json
  $native=@(Get-Process GooglePhotosWidget -ErrorAction SilentlyContinue|Where-Object Path -EQ $exe)
  if([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()-$s.heartbeat -lt 10 -and (Get-Process -Id $s.pid -ErrorAction SilentlyContinue) -and $native.Count -eq 1 -and $n.TrayRegistered){$healthy=$true;break}
 }while([DateTime]::UtcNow -lt $deadline)
 if(-not $healthy){throw 'New version did not report healthy service'}
 $script:installed=$plan.Version;Write-UpdateStatus 'updated' ('Rollback backup: '+$backup)
}catch {
 $failureExit=1
 $failure=$_.Exception.Message
 if($backup -and (Test-Path -LiteralPath (Join-Path $backup 'backup-ready.json'))){
  try {
   Stop-PhotosForUpdate
   # Preserve the failed version as evidence; never delete unknown directories.
   Move-Item -LiteralPath $AppPath -Destination (Join-Path $backup 'failed-installation')
   Copy-Item -LiteralPath (Join-Path $backup 'installation') -Destination $AppPath -Recurse
   Start-PhotosAfterUpdate;$stopped=$false
   Write-UpdateStatus 'rolled_back' $failure
  }catch {Write-UpdateStatus 'recovery_required' ($failure+'; recovery: '+$_.Exception.Message)}
 }else {Write-UpdateStatus 'blocked' $failure}
}finally {
 if($stopped){try{Start-PhotosAfterUpdate}catch{}}
 # Remove only the unique updater-owned download directory, never user state/backups.
 if($cache -and (Test-Path -LiteralPath $cache)){
  $expected=[IO.Path]::GetFullPath((Join-Path $StatePath 'updates'))+'\'
  $resolved=[IO.Path]::GetFullPath($cache)
  if($resolved.StartsWith($expected,[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $resolved -Leaf) -match '^download-[a-f0-9]{32}$'){Remove-Item -LiteralPath $resolved -Recurse -Force}
 }
 $mutex.ReleaseMutex();$mutex.Dispose()
}
if($failureExit){exit $failureExit}

