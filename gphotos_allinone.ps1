<#
gphotos_allinone.ps1 (Bruno | 2026 | Windows PowerShell)

Objetivo:
- Criar álbuns no Google Fotos baseados nos nomes das pastas locais e enviar fotos/vídeos.

Estrutura:
C:\Users\bruno\Meu Drive\Imagens\Fotos
  - Pastas na raiz que NÃO são ano (ex.: "0 Diversos - Best Shots") => viram ÁLBUNS
  - Pastas de ano "YYYY" (ex.: "2026")
      - Subpastas (ex.: "2026-01 - Tema") => viram ÁLBUNS

Requisitos:
- Criar álbuns (gphotos:album/<nome>)
- Enviar fotos e vídeos
- Evitar duplicidade/retomar: --ignore-existing + --size-only
- Log por álbum + relatório CSV mestre
- Progresso: -P + --stats 30s
- Corrigir automaticamente filtro com UTF-8 BOM (erro \uFEFF)

Uso:
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1"
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1" -MaxAlbums 5
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1" -MaxAlbums 1 -DryRun
#>

param(
  [string]$SourceRoot = "C:\Users\bruno\Meu Drive\Imagens\Fotos",
  [string]$ScriptsDir = "C:\rclone\scripts",
  [string]$LogsDir    = "C:\rclone\logs",
  [string]$Remote     = "gphotos:",
  [string]$FilterFile = "C:\rclone\scripts\rclone_gphotos_filter.txt",
  [int]$Transfers     = 4,
  [int]$Checkers      = 8,
  [int]$MaxAlbums     = 0,   # 0 = sem limite
  [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

function Ensure-Dir([string]$p) {
  if (!(Test-Path $p)) { New-Item -ItemType Directory -Path $p | Out-Null }
}

function NowStamp() { (Get-Date).ToString("yyyyMMdd-HHmmss") }

function Sanitize-AlbumName([string]$name) {
  $n = $name.Trim()
  $n = $n -replace "[/\\:*\?\""<>|]", " -"
  $n = $n -replace "\s+", " "
  return $n
}

function Write-Utf8NoBom([string]$path, [string]$content) {
  $enc = New-Object System.Text.UTF8Encoding($false) # sem BOM
  [System.IO.File]::WriteAllText($path, $content, $enc)
}

function File-StartsWithBom([string]$path) {
  if (!(Test-Path $path)) { return $false }
  $bytes = [System.IO.File]::ReadAllBytes($path)
  if ($bytes.Length -lt 3) { return $false }
  return ($bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF)
}

function Ensure-FilterNoBom([string]$path) {
  if (!(Test-Path $path)) {
    $content = @"
# rclone filter (Google Photos) - UTF-8 sem BOM

# imagens
+ *.jpg
+ *.jpeg
+ *.png
+ *.gif
+ *.webp
+ *.heic
+ *.heif
+ *.tif
+ *.tiff
+ *.bmp
+ *.dng
+ *.arw
+ *.cr2
+ *.cr3
+ *.nef
+ *.orf
+ *.rw2

# vídeos
+ *.mp4
+ *.mov
+ *.m4v
+ *.mkv
+ *.avi
+ *.webm
+ *.mts
+ *.m2ts
+ *.3gp

# excluir lixo
- *.db
- *.ini
- *.tmp
- *.temp
- *.ds_store
- thumbs.db
- desktop.ini
- *.aae
- *.xmp
- *.json

# por padrão exclui o resto
- *
"@
    Write-Utf8NoBom $path $content
    return
  }

  if (File-StartsWithBom $path) {
    $txt = [System.IO.File]::ReadAllText($path)
    Write-Host "AVISO: filtro com BOM detectado. Regravando sem BOM: $path"
    Write-Utf8NoBom $path $txt
  }
}

function Invoke-Rclone([string[]]$rcloneArgs) {
  & rclone @rcloneArgs
  return $LASTEXITCODE
}

# Preparação
Ensure-Dir $ScriptsDir
Ensure-Dir $LogsDir
Ensure-FilterNoBom $FilterFile

$stamp = NowStamp
$masterCsv = Join-Path $LogsDir "gphotos_allinone_$stamp.csv"
"timestamp,group,folder_path,album_name,status,exit_code" | Out-File -Encoding utf8 $masterCsv

Write-Host ""
Write-Host "=== Google Photos Upload (rclone) ==="
Write-Host "Origem:  $SourceRoot"
Write-Host "Scripts: $ScriptsDir"
Write-Host "Logs:    $LogsDir"
Write-Host "Remote:  $Remote"
Write-Host "Filtro:  $FilterFile"
Write-Host "DryRun:  $($DryRun.IsPresent)"
Write-Host "===================================="
Write-Host ""

if (!(Test-Path $SourceRoot)) { throw "Pasta de origem não existe: $SourceRoot" }

$topDirs = Get-ChildItem -Path $SourceRoot -Directory -ErrorAction Stop | Sort-Object Name
if ($topDirs.Count -eq 0) { throw "Não encontrei pastas dentro de: $SourceRoot" }

# Lista fortemente tipada (evita bugs de coerção)
$list = New-Object 'System.Collections.Generic.List[psobject]'

foreach ($d in $topDirs) {
  if ($d.Name -match "^\d{4}$") {
    $subs = Get-ChildItem -Path $d.FullName -Directory -ErrorAction SilentlyContinue | Sort-Object Name
    foreach ($s in $subs) {
      $list.Add([PSCustomObject]@{
        Group      = $d.Name
        FolderPath = $s.FullName
        AlbumName  = (Sanitize-AlbumName $s.Name)
      })
    }
  } else {
    $list.Add([PSCustomObject]@{
      Group      = "ROOT"
      FolderPath = $d.FullName
      AlbumName  = (Sanitize-AlbumName $d.Name)
    })
  }
}

# Conversão robusta para array (evita ArgumentException do @($list))
$albumsAll = $list.ToArray()

if ($albumsAll.Count -eq 0) { throw "Não encontrei nenhuma pasta para virar álbum." }

# Aplica MaxAlbums sem Select-Object (e sem -First 0)
if ($MaxAlbums -gt 0) {
  $take = [Math]::Min($MaxAlbums, $albumsAll.Count)
  $albums = $albumsAll[0..($take-1)]
  Write-Host "AVISO: MaxAlbums=$MaxAlbums ativado. Processando os primeiros $take álbuns."
  Write-Host ""
} else {
  $albums = $albumsAll
}

$albumTotal = $albums.Count

$idx = 0
foreach ($item in $albums) {
  $idx++
  $folder    = $item.FolderPath
  $albumName = $item.AlbumName
  $group     = $item.Group

  if (!(Test-Path $folder)) {
    Write-Host "SKIP: Pasta não existe: $folder"
    "$stamp,$group,\"$folder\",\"$albumName\",SKIP,0" | Add-Content -Encoding utf8 $masterCsv
    continue
  }

  $safeAlbumForFile = ($albumName -replace "\s+", "_")
  $albumLog = Join-Path $LogsDir ("gphotos_{0}_{1:000}_{2}.log" -f $stamp,$idx,$safeAlbumForFile)

  Write-Host ""
  Write-Host "------------------------------------------------------------"
  Write-Host "[$idx/$albumTotal] Grupo: $group | Álbum: $albumName"
  Write-Host "Pasta: $folder"
  Write-Host "Log:   $albumLog"
  Write-Host "------------------------------------------------------------"

  $dest = ($Remote + "album/" + $albumName)

  $rcloneArgs = @(
    "copy",
    $folder,
    $dest,
    "--transfers", "$Transfers",
    "--checkers", "$Checkers",
    "--retries", "10",
    "--retries-sleep", "10s",
    "--low-level-retries", "50",
    "--log-file", $albumLog,
    "--log-level", "INFO",
    "--stats", "30s",
    "-P",
    "--ignore-existing",
    "--size-only",
    "--filter-from", $FilterFile
  )

  if ($DryRun.IsPresent) { $rcloneArgs += "--dry-run" }

  $exit = Invoke-Rclone $rcloneArgs
  $status = if ($exit -eq 0) { "OK" } else { "ERROR" }

  "$stamp,$group,\"$folder\",\"$albumName\",$status,$exit" | Add-Content -Encoding utf8 $masterCsv

  if ($exit -ne 0) {
    Write-Host ""
    Write-Host ">>> ERRO no álbum '$albumName' (exit=$exit). Veja o final do log:"
    Write-Host "Get-Content \"$albumLog\" -Tail 120"
    Write-Host ""
  }
}

Write-Host ""
Write-Host "=== Concluído ==="
Write-Host "Relatório CSV: $masterCsv"
Write-Host ""
