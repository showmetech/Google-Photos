param([switch]$Publish,[switch]$Install)
$ErrorActionPreference='Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
$release=Get-Content release.json | ConvertFrom-Json
$version=$release.version
if((([xml](Get-Content PhotosNative/PhotosNative.csproj)).Project.PropertyGroup.Version) -ne $version){throw 'Version mismatch'}
if(-not (Get-Command gh -ErrorAction SilentlyContinue)){throw 'GitHub CLI is required for the local release command'}
gh auth status
if($LASTEXITCODE -ne 0){throw 'Authenticate GitHub CLI as the authorized repository owner. Do not copy connector tokens.'}
if($Publish){
  if(git status --porcelain){throw 'Review and commit the release changes before publishing'}
  git push origin main
  if($LASTEXITCODE -ne 0){throw 'GitHub push failed; desktop was not changed'}
}
git fetch origin main
if($LASTEXITCODE -ne 0){throw 'Cannot verify the remote source'}
$commit=git rev-parse HEAD
if($commit -ne (git rev-parse origin/main)){throw 'Desktop release source differs from GitHub main'}
$runs=gh run list --repo $release.repository --workflow release.yml --commit $commit --json databaseId,status,conclusion | ConvertFrom-Json
if(-not $runs){throw 'No release workflow exists for this commit'}
gh run watch $runs[0].databaseId --repo $release.repository --exit-status
if($LASTEXITCODE -ne 0){throw 'Release pipeline incomplete (including Store submission). Desktop was not changed.'}
if($Install){
  $location=Join-Path $env:TEMP ('PhotosRelease-'+[guid]::NewGuid().ToString('N'))
  New-Item -ItemType Directory $location | Out-Null
  gh release download "v$version" --repo $release.repository --dir $location --pattern '*Setup.exe' --pattern SHA256SUMS.txt
  if($LASTEXITCODE -ne 0){throw 'Release download failed'}
  $installer=Get-ChildItem $location -Filter '*Setup.exe' | Select-Object -First 1
  $digest=(Get-FileHash $installer.FullName -Algorithm SHA256).Hash.ToLower()
  if(-not (Select-String -LiteralPath (Join-Path $location 'SHA256SUMS.txt') -SimpleMatch "$digest  $($installer.Name)" -Quiet)){throw 'Installer SHA-256 mismatch'}
  $result=Start-Process -FilePath $installer.FullName -ArgumentList '/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/TASKS=startup,desktopicon' -WindowStyle Hidden -Wait -PassThru
  if($result.ExitCode -ne 0){throw "Installer failed: $($result.ExitCode)"}
  & (Join-Path $PSScriptRoot 'audit-installation.ps1')
  # Open the app's usual launcher; the app owns recovery and synchronization.
  $exe=Join-Path $env:LOCALAPPDATA 'Programs\Google Photos Upload Manager\native\GooglePhotosWidget.exe'
  Start-Process -FilePath $exe -ArgumentList '--minimized' -WindowStyle Hidden
}
@{version=$version;commit=$commit;github='verified';store='submitted; certification and public availability must be checked in Partner Center';desktopInstalled=[bool]$Install} | ConvertTo-Json | Set-Content release-receipt.json
