"""Shared settings and account isolation for source and installed editions."""
import configparser
import json
import os
from pathlib import Path
import tempfile


def load_settings(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8-sig"))
    cfg = json.loads((path.parent / "config.example.json").read_text(encoding="utf-8-sig"))
    save_settings(path, cfg)
    return cfg


def save_settings(path: Path, cfg: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".settings-", suffix=".tmp", delete=False) as stream:
        json.dump(cfg, stream, ensure_ascii=False, indent=2)
        temporary = Path(stream.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def source_folders(cfg: dict) -> list[Path]:
    values=cfg.get("photos_roots") or [cfg.get("photos_root", "")]
    if not values or any(not str(v).strip() for v in values):
        raise ValueError("Choose the folders to monitor in Settings.")
    roots=[]
    for value in values:
        folder=Path(os.path.expandvars(str(value))).expanduser().resolve()
        if not folder.is_dir():raise ValueError(f"Source unavailable: {folder}")
        for previous in roots:
            if folder==previous or folder.is_relative_to(previous) or previous.is_relative_to(folder):
                raise ValueError("Source folders must not overlap.")
        roots.append(folder)
    return roots

def source_folder(cfg: dict) -> Path:
    return source_folders(cfg)[0]


def rclone_args(cfg: dict, app_dir: Path, *command: str) -> list[str]:
    executable = Path(cfg.get("rclone_exe", "tools/rclone/rclone.exe"))
    if not executable.is_absolute():
        executable = app_dir / executable
    args = [str(executable) if executable.is_file() else "rclone"]
    # Existing editions intentionally keep using their original rclone profile.
    if cfg.get("rclone_config"):
        profile = Path(cfg["rclone_config"])
        if not profile.is_absolute():
            profile = app_dir / profile
        args.extend(["--config", str(profile.resolve())])
    return args + list(command)


def profile_path(cfg: dict, app_dir: Path) -> Path:
    if cfg.get("rclone_config"):
        path = Path(cfg["rclone_config"])
        return path if path.is_absolute() else app_dir / path
    return Path(os.environ.get("RCLONE_CONFIG") or
                str(Path(os.environ.get("APPDATA", str(Path.home() / "AppData/Roaming"))) / "rclone/rclone.conf"))


def account_configured(cfg: dict, app_dir: Path) -> bool:
    try:
        profile = configparser.ConfigParser(interpolation=None)
        profile.read(profile_path(cfg, app_dir), encoding="utf-8-sig")
        section = profile[cfg.get("rclone_remote", "gphotos")]
        token = json.loads(section.get("token", "{}"))
        return section.get("type") == "google photos" and bool(token.get("access_token"))
    except (OSError, ValueError, KeyError, configparser.Error):
        return False


def prepare_account(cfg: dict, app_dir: Path, client_id: str, client_secret: str) -> None:
    client_id, client_secret = client_id.strip(), client_secret.strip()
    if not client_id.endswith(".apps.googleusercontent.com") or not client_secret:
        raise ValueError("Informe o ID e o segredo de um cliente OAuth do tipo Aplicativo para computador.")
    if not cfg.get("rclone_config"):
        raise ValueError("Use Reconectar para a conta existente. A troca de cliente exige uma configuração separada.")
    path = profile_path(cfg, app_dir)
    profile = configparser.ConfigParser(interpolation=None)
    if path.exists():
        profile.read(path, encoding="utf-8-sig")
    remote = cfg.get("rclone_remote", "gphotos")
    if profile.has_section(remote) and profile[remote].get("token"):
        raise ValueError("A conta já está configurada. Use Reconectar para preservar o histórico e o cliente OAuth.")
    profile[remote] = {"type": "google photos", "client_id": client_id, "client_secret": client_secret}
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                     prefix=".account-", suffix=".tmp", delete=False) as stream:
        profile.write(stream)
        temporary = Path(stream.name)
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
