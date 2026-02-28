param(
  [string]$Python = "py",
  [string]$AppName = "GooglePhotosUploader"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Criando/atualizando ambiente virtual..."
& $Python -m venv .venv

Write-Host "[2/4] Instalando PyInstaller..."
& .\.venv\Scripts\python.exe -m pip install --upgrade pip pyinstaller

Write-Host "[3/4] Gerando EXE..."
& .\.venv\Scripts\pyinstaller.exe `
  --noconfirm `
  --clean `
  --onefile `
  --windowed `
  --name $AppName `
  --add-data "gphotos_allinone.ps1;." `
  app\gphotos_uploader_gui.py

Write-Host "[4/4] Build concluído: dist\\$AppName.exe"
