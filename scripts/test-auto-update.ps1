$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'auto-update.ps1') -LibraryOnly
$script:checks=0
function Check($Condition,$Name){if(-not $Condition){throw "Failed: $Name"};$script:checks++}
function Rejected([scriptblock]$Action,$Name){$rejected=$false;try{& $Action|Out-Null}catch{$rejected=$true};Check $rejected $Name}
$sha='a'*40;$tag='2026.11.18.1';$base="https://github.com/showmetech/Google-Photos/releases/download/v$tag/"
function Fixture { [pscustomobject]@{draft=$false;prerelease=$false;tag_name="v$tag";target_commitish=$sha;assets=@([pscustomobject]@{name="Google-Photos-Uploader-$tag-Setup.exe";browser_download_url=$base+"Google-Photos-Uploader-$tag-Setup.exe"},[pscustomobject]@{name='SHA256SUMS.txt';browser_download_url=$base+'SHA256SUMS.txt'})} }
$release=Fixture
Check ((Get-ReleasePlan $release ([version]'2026.11.17.1')).Version -eq $tag) 'newer stable release'
Check ($null -eq (Get-ReleasePlan $release ([version]$tag))) 'no reinstall'
Check ($null -eq (Get-ReleasePlan $release ([version]'2026.12.1.1'))) 'no downgrade'
$r=Fixture;$r.prerelease=$true;Rejected {Get-ReleasePlan $r ([version]'1.0.0.0')} 'prerelease rejected'
$r=Fixture;$r.draft=$true;Rejected {Get-ReleasePlan $r ([version]'1.0.0.0')} 'draft rejected'
$r=Fixture;$r.assets[0].browser_download_url='https://example.com/installer.exe';Rejected {Get-ReleasePlan $r ([version]'1.0.0.0')} 'foreign installer rejected'
$r=Fixture;$r.target_commitish='main';Rejected {Get-ReleasePlan $r ([version]'1.0.0.0')} 'mutable branch rejected'
$r=Fixture;$r.assets=@($r.assets[0]);Rejected {Get-ReleasePlan $r ([version]'1.0.0.0')} 'missing sums rejected'
$runs=[pscustomobject]@{workflow_runs=@([pscustomobject]@{head_sha=$sha;path='.github/workflows/release.yml';status='completed';conclusion='success'})}
$jobs=[pscustomobject]@{jobs=@('build','github-release','microsoft-store'|ForEach-Object {[pscustomobject]@{name=$_;conclusion='success'}})}
Assert-ReleaseJobs $runs $jobs $sha;Check $true 'full release gate'
$jobs.jobs[2].conclusion='skipped';Rejected {Assert-ReleaseJobs $runs $jobs $sha} 'Store gate mandatory'
$jobs.jobs[2].conclusion='success';Rejected {Assert-ReleaseJobs $runs $jobs ('b'*40)} 'wrong commit rejected'
$temp=Join-Path ([IO.Path]::GetTempPath()) ('photos-update-test-'+[guid]::NewGuid().ToString('N'))
try {
 New-Item -ItemType Directory (Join-Path $temp 'data') -Force|Out-Null
 $file=Join-Path $temp 'setup.exe';$sums=Join-Path $temp 'sums.txt';[IO.File]::WriteAllText($file,'fixture')
 ((Get-FileHash $file).Hash+'  setup.exe')|Set-Content $sums
 Assert-InstallerDigest $file $sums 'setup.exe';Check $true 'valid checksum'
 [IO.File]::WriteAllText($file,'modified');Rejected {Assert-InstallerDigest $file $sums 'setup.exe'} 'corrupt installer rejected'
 Check (-not(Test-UploadBusy $temp)) 'idle'
 @{heartbeat=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds();busy=$true}|ConvertTo-Json|Set-Content (Join-Path $temp 'data\ui-service-status.json')
 Check (Test-UploadBusy $temp) 'busy heartbeat defers'
 @{heartbeat=0;busy=$true}|ConvertTo-Json|Set-Content (Join-Path $temp 'data\ui-service-status.json')
 Check (-not(Test-UploadBusy $temp)) 'stale heartbeat alone is insufficient'
 $lock=Join-Path $temp 'data\worker.lock';$held=[IO.File]::Open($lock,'OpenOrCreate','ReadWrite','None')
 try {Check (Test-UploadBusy $temp) 'locked worker defers'}finally{$held.Dispose()}
}finally{
 $resolved=[IO.Path]::GetFullPath($temp);$expected=[IO.Path]::GetFullPath([IO.Path]::GetTempPath())
 if($resolved.StartsWith($expected,[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $resolved -Leaf) -match '^photos-update-test-[a-f0-9]{32}$'){Remove-Item -LiteralPath $resolved -Recurse -Force}
}
"Passed $script:checks automatic update guard checks"

