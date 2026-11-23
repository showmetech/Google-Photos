param([string[]]$Scripts=@('auto-update.ps1','audit-installation.ps1','enable-auto-update.ps1'),[string]$FixtureParent=[IO.Path]::GetTempPath())
$ErrorActionPreference='Stop'
$temp=Join-Path $FixtureParent ('photos-appx-failure-'+[guid]::NewGuid().ToString('N'))
$previousLocalAppData=$env:LOCALAPPDATA
$env:LOCALAPPDATA=Join-Path $temp 'Local'
$global:PhotosAppxEffects=@{network=0;process=0}
function Get-AppxPackage { [CmdletBinding()]param([string]$Name) Write-Error -Message 'SIMULATED_APPX_QUERY_FAILURE' -ErrorId 'SyntheticAppxFailure' -Category PermissionDenied }
function Invoke-WebRequest { param($Uri,$Headers,$OutFile,$TimeoutSec,[switch]$UseBasicParsing) $global:PhotosAppxEffects.network++;throw 'Unexpected network request' }
function Invoke-RestMethod { param($Uri,$Headers,$TimeoutSec) $global:PhotosAppxEffects.network++;throw 'Unexpected API request' }
function Start-Process { param($FilePath,$ArgumentList,$WindowStyle,[switch]$Wait,[switch]$PassThru) $global:PhotosAppxEffects.process++;throw 'Unexpected process launch' }
function Register-ScheduledTask { throw 'Unexpected task registration; blocked by test fixture' }
try {
 # The mock must reproduce a non-terminating error which an older query could suppress.
 Get-AppxPackage -Name 'fixture' -ErrorAction SilentlyContinue | Out-Null
 foreach($script in $Scripts){
  $rejected=$false
  try{
   $parameters=if($script -eq 'enable-auto-update.ps1'){@{}}else{@{AppPath=(Join-Path $temp 'app');StatePath=(Join-Path $temp 'state')}}
   if($script -eq 'auto-update.ps1'){$parameters.Install=$true}
   & (Join-Path $PSScriptRoot $script) @parameters | Out-Null
  }catch{if($_.Exception.Message -ne 'SIMULATED_APPX_QUERY_FAILURE'){throw};$rejected=$true}
  if(-not $rejected){throw "$script treated an AppX failure as absence"}
  if(Test-Path -LiteralPath $temp){throw "$script wrote files after an uncertain AppX query"}
 }
 if($global:PhotosAppxEffects.network -ne 0 -or $global:PhotosAppxEffects.process -ne 0){throw 'Unexpected side effects'}
 Write-Output 'Passed AppX query failure checks: all scripts fail before filesystem, network or process side effects'
}finally{
 $env:LOCALAPPDATA=$previousLocalAppData
 Remove-Variable PhotosAppxEffects -Scope Global -ErrorAction SilentlyContinue
 $full=[IO.Path]::GetFullPath($temp)
 if((Test-Path -LiteralPath $full) -and $full.StartsWith([IO.Path]::GetFullPath([IO.Path]::GetTempPath()),[StringComparison]::OrdinalIgnoreCase) -and (Split-Path $full -Leaf) -match '^photos-appx-failure-[a-f0-9]{32}$'){Remove-Item -LiteralPath $full -Recurse -Force}
}
