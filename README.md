# Google-Photos

Script PowerShell para transformar a estrutura de pastas local em álbuns no Google Fotos via `rclone`.

## Arquivo principal

- `gphotos_allinone.ps1`

## O que faz

- Lê pastas em `C:\Users\bruno\Meu Drive\Imagens\Fotos`.
- Pastas de raiz que **não** são `YYYY` viram álbuns diretamente.
- Pastas `YYYY` são tratadas como agrupadores; suas subpastas viram álbuns.
- Executa `rclone copy` para `gphotos:album/<Nome do Álbum>`.
- Gera log por álbum e CSV mestre de execução.

## Requisitos

- Windows PowerShell.
- `rclone` instalado e no `PATH`.
- Remote `gphotos:` configurado e autenticado.
- Diretórios:
  - `C:\rclone\scripts`
  - `C:\rclone\logs`

## Execução

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1"
```

Teste com limite de álbuns:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1" -MaxAlbums 5
```

Simulação (sem envio):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "C:\rclone\scripts\gphotos_allinone.ps1" -MaxAlbums 1 -DryRun
```

## Retomada após travar/desligar

A retomada é idempotente: basta executar novamente o mesmo comando.

Isso funciona por causa de:

- `--ignore-existing`
- `--size-only`

Assim, os arquivos já existentes no destino são pulados e o restante continua.

## Logs e relatório

- Logs por álbum: `C:\rclone\logs\gphotos_<timestamp>_<seq>_<album>.log`
- Relatório mestre: `C:\rclone\logs\gphotos_allinone_<timestamp>.csv`

Para inspecionar erro de um álbum:

```powershell
Get-Content "C:\rclone\logs\<log-do-album>.log" -Tail 120
```
