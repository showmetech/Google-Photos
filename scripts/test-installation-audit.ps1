$ErrorActionPreference='Stop'
$temp=Join-Path ([IO.Path]::GetTempPath()) ('photos-audit-test-'+[guid]::NewGuid().ToString('N'))
$legacy=Join-Path $temp 'Programs\Google Photos Upload Manager'
$app=Join-Path $temp 'StorePackage'
$state=Join-Path $temp 'State'
$global:PhotosAuditPackage=[pscustomobject]@{InstallLocation=$app;PackageFamilyName='PhotosAuditFixture';Status='Ok'}
# Run in a dedicated test process. Only discovery is mocked; the production
# audit reads the actual fixture filesystem and never changes the registry.
function Get-AppxPackage { [CmdletBinding()]param([string]$Name) $global:PhotosAuditPackage }
function Get-Process { [CmdletBinding()]param([string]$Name) @() }
function Get-ScheduledTask { [CmdletBinding()]param([string]$TaskName) $null }
try {
 New-Item -ItemType Directory -Path (Join-Path $app 'native') -Force | Out-Null
 Set-Content -LiteralPath (Join-Path $app 'native\GooglePhotosWidget.exe') -Value 'inert audit fixture, never execute'
 $result=(& (Join-Path $PSScriptRoot 'audit-installation.ps1') -AppPath $legacy -StatePath $state | Out-String | ConvertFrom-Json)
 if(-not $result.passed -or -not $result.setupPending){throw 'Clean first-use Store should not be classified as broken'}
 New-Item -ItemType Directory -Path (Join-Path $legacy 'native') -Force | Out-Null
 Set-Content -LiteralPath (Join-Path $legacy 'native\GooglePhotosWidget.exe') -Value 'inert legacy fixture, never execute'
 $rejected=$false
 try { & (Join-Path $PSScriptRoot 'audit-installation.ps1') -AppPath $legacy -StatePath $state | Out-Null }catch{if($_.Exception.Message -notlike 'Installation audit failed*'){throw};$rejected=$true}
 if(-not $rejected){throw 'Duplicate Store/classic installation was not detected'}
 Remove-Item -LiteralPath (Join-Path $legacy 'native\GooglePhotosWidget.exe')
 $global:PhotosAuditPackage.Status='Tampered';$rejected=$false
 try { & (Join-Path $PSScriptRoot 'audit-installation.ps1') -AppPath $legacy -StatePath $state | Out-Null }catch{if($_.Exception.Message -notlike 'Installation audit failed*'){throw};$rejected=$true}
 if(-not $rejected){throw 'Damaged package was not detected'}
 Write-Output 'Passed 3 installation audit scenarios; no application, registry or startup modified'
}finally{
 Remove-Variable PhotosAuditPackage -Scope Global -ErrorAction SilentlyContinue
 $full=[IO.Path]::GetFullPath($temp)
 if($full.StartsWith([IO.Path]::GetFullPath([IO.Path]::GetTempPath()),[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $full -Leaf) -match '^photos-audit-test-[a-f0-9]{32}$'){Remove-Item -LiteralPath $full -Recurse -Force}
}
