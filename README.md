# Google-Photos

Aplicativo desktop para Windows que executa upload de mídia para Google Fotos via `rclone`, mapeando pastas locais para álbuns.

## O que existe no projeto

- `gphotos_allinone.ps1`: motor de upload (pastas -> álbuns + logs + CSV)
- `app/gphotos_uploader_gui.py`: interface gráfica (progresso, status e erros)
- `build_windows.ps1`: build do `.exe` via PyInstaller
- `installer/GooglePhotosUploader.iss`: instalador via Inno Setup

## Como funciona

Estrutura de origem (padrão):

`C:\Users\bruno\Meu Drive\Imagens\Fotos`

- Pastas na raiz que **não** são ano (`YYYY`) viram álbuns diretamente.
- Pastas `YYYY` são agrupadores; cada subpasta vira álbum.

Para cada álbum, o script chama `rclone copy` para:

`gphotos:album/<Nome do Álbum>`

Com proteção de retomada:

- `--ignore-existing`
- `--size-only`

## Rodar como script (modo atual)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1"
```

Teste seguro:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1" -MaxAlbums 1 -DryRun
```

## Rodar como programa `.exe` no Windows

### Pré-requisitos da máquina de build

- Python 3.10+
- PowerShell
- `rclone` instalado e com remote `gphotos:` já autenticado

### Build do executável

No PowerShell, dentro deste repositório:

```powershell
.\build_windows.ps1
```

Saída esperada:

- `dist\GooglePhotosUploader.exe`

### O que a interface mostra

- progresso por álbum (`[idx/total]`)
- álbum atual em execução
- log completo em tempo real
- status final (sucesso/falhas)
- linhas de erro destacadas no status

## Gerar instalador (`.exe` instalável)

1. Instale o **Inno Setup** na máquina Windows.
2. Abra `installer/GooglePhotosUploader.iss` no Inno Setup Compiler.
3. Compile.

Saída esperada:

- `installer\GooglePhotosUploaderSetup.exe`

Esse setup instala:

- `GooglePhotosUploader.exe`
- `gphotos_allinone.ps1`

## Logs e rastreabilidade

- Logs por álbum: `C:\rclone\logs\gphotos_<timestamp>_<seq>_<album>.log`
- CSV mestre: `C:\rclone\logs\gphotos_allinone_<timestamp>.csv`

Inspeção rápida de erro:

```powershell
Get-Content "C:\rclone\logs\<log-do-album>.log" -Tail 120
```
