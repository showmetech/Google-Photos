$ErrorActionPreference='Stop'
$temp=Join-Path ([IO.Path]::GetTempPath()) ('photos-appx-failure-'+[guid]::NewGuid().ToString('N'))
$global:PhotosAppxEffects=@{network=0;process=0}
function Get-AppxPackage { [CmdletBinding()]param([string]$Name) throw 'SIMULATED_APPX_QUERY_FAILURE' }
function Invoke-WebRequest { param($Uri,$Headers,$OutFile,$TimeoutSec,[switch]$UseBasicParsing) $global:PhotosAppxEffects.network++;throw 'Unexpected network request' }
function Invoke-RestMethod { param($Uri,$Headers,$TimeoutSec) $global:PhotosAppxEffects.network++;throw 'Unexpected API request' }
function Start-Process { param($FilePath,$ArgumentList,$WindowStyle,[switch]$Wait,[switch]$PassThru) $global:PhotosAppxEffects.process++;throw 'Unexpected process launch' }
try {
 foreach($script in 'auto-update.ps1','audit-installation.ps1'){
  $rejected=$false
  try{
   $parameters=@{AppPath=(Join-Path $temp 'app');StatePath=(Join-Path $temp 'state')}
   if($script -eq 'auto-update.ps1'){$parameters.Install=$true}
   & (Join-Path $PSScriptRoot $script) @parameters | Out-Null
  }catch{if($_.Exception.Message -ne 'SIMULATED_APPX_QUERY_FAILURE'){throw};$rejected=$true}
  if(-not $rejected){throw "$script treated an AppX failure as absence"}
  if(Test-Path -LiteralPath $temp){throw "$script wrote files after an uncertain AppX query"}
 }
 if($global:PhotosAppxEffects.network -ne 0 -or $global:PhotosAppxEffects.process -ne 0){throw 'Unexpected side effects'}
 Write-Output 'Passed AppX query failure checks: both scripts fail before filesystem, network or process side effects'
}finally{Remove-Variable PhotosAppxEffects -Scope Global -ErrorAction SilentlyContinue}
