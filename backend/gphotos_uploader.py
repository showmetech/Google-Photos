#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
from app_config import load_settings, source_folder, source_folders, rclone_args
from app_paths import bootstrap,home
from reliable_history import io_path, enumerate_media, atomic_json, prepare_schema, atomic_csv

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff", ".avif", ".ico",
    ".dng", ".cr2", ".cr3", ".crw", ".nef", ".arw", ".rw2", ".orf", ".raf", ".srw", ".pef",
    ".mp4", ".mov", ".avi", ".m4v", ".mts", ".m2ts", ".m2t", ".3gp", ".3g2", ".wmv", ".mpg", ".mpeg",
    ".webm", ".asf", ".divx", ".mkv", ".mmv", ".mod", ".tod",
}

COPIED_LINE_RE = re.compile(r"^(?:\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2} \S+\s+: )?(?P<name>.+?): (?:Copied|Skipped|Failed)")
EMPTY_FILE_ERROR = "Arquivo vazio (0 bytes): recupere o original antes de enviar."


def app_root() -> Path:
    return Path(__file__).resolve().parent


def load_config() -> dict:
    cfg_path = bootstrap() / "config.json"
    cfg = load_settings(cfg_path)
    for key in ("database", "logs_dir", "audit_dir", "rclone_exe", "rclone_config"):
        if key not in cfg:
            continue
        cfg[key] = str(((app_root() if key == "rclone_exe" else home()) / cfg[key]).resolve()) if not Path(cfg[key]).is_absolute() else cfg[key]
    return cfg


def ensure_dirs(cfg: dict) -> None:
    Path(cfg["database"]).parent.mkdir(parents=True, exist_ok=True)
    Path(cfg["logs_dir"]).mkdir(parents=True, exist_ok=True)
    Path(cfg["audit_dir"]).mkdir(parents=True, exist_ok=True)


def status_file(cfg: dict) -> Path:
    return Path(cfg["database"]).parent / "current_status.json"


def write_status(cfg: dict, **updates) -> None:
    path = status_file(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {}
    if path.exists():
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
    state.update(updates)
    state["updated_at"] = datetime.now().isoformat(timespec="seconds")
    atomic_json(path, state)


def connect_db(cfg: dict) -> sqlite3.Connection:
    ensure_dirs(cfg)
    db = sqlite3.connect(cfg["database"])
    db.execute("""
        create table if not exists media (
            path text primary key,
            album text not null,
            size integer not null,
            mtime_ns integer not null,
            ext text not null,
            fingerprint text not null,
            status text not null default 'pending',
            last_seen text not null,
            uploaded_at text,
            last_error text
        )
    """)
    db.execute("""
        create table if not exists runs (
            id integer primary key autoincrement,
            started_at text not null,
            finished_at text,
            command text not null,
            result text
        )
    """)
    db.execute("""
        create table if not exists events (
            id integer primary key autoincrement,
            created_at text not null,
            event_type text not null,
            note text not null,
            media_count integer,
            album_count integer,
            bytes integer
        )
    """)
    roots=source_folders(cfg)
    def in_sources(value):
        path=Path(value)
        return int(any(path==r or path.is_relative_to(r) for r in roots))
    db.create_function("in_sources",1,in_sources)
    prepare_schema(db)
    return db


def album_for(root: Path, file_path: Path) -> str:
    rel = file_path.relative_to(root)
    parts = rel.parts
    if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4:
        return parts[1]
    if len(parts) >= 2:
        return parts[0]
    return "(raiz)"


def album_source_dir(root: Path, file_path: Path, album: str) -> Path:
    rel = file_path.relative_to(root)
    parts = rel.parts
    if len(parts) == 1:
        return root
    if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4:
        return root / parts[0] / album
    return root / album


def fingerprint(path: Path, stat: os.stat_result) -> str:
    h = hashlib.sha1()
    h.update(str(path).encode("utf-8", "surrogatepass"))
    h.update(str(stat.st_size).encode("ascii"))
    h.update(str(stat.st_mtime_ns).encode("ascii"))
    return h.hexdigest()


def iter_media(root: Path, min_file_age_seconds: int = 0):
    yield from enumerate_media(root, MEDIA_EXTENSIONS, min_file_age_seconds)


def source_pattern(cfg: dict) -> str:
    if len(source_folders(cfg))>1:return "%"
    prefix = str(source_folder(cfg)).rstrip("/\\") + os.sep
    return prefix.replace("!", "!!").replace("%", "!%").replace("_", "!_") + "%"


def scan(cfg: dict) -> dict:
    try:
        root = source_folder(cfg)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    now = datetime.now().isoformat(timespec="seconds")
    db = connect_db(cfg)
    seen = 0
    inserted_or_updated = 0
    albums = {}
    min_age = int(cfg.get("min_file_age_seconds", 120))
    # Complete enumeration before modifying presence; an inaccessible tree must not
    # turn an incomplete scan into a successful inventory.
    roots=source_folders(cfg)
    snapshot=[(r,path,stat) for r in roots for path,stat in iter_media(r,min_age)]
    cutoff_ns = time.time_ns() - max(0, min_age) * 1_000_000_000
    db.execute("update media set present=0 where in_sources(path) and path like ? escape '!' and mtime_ns <= ?", (source_pattern(cfg), cutoff_ns))
    for media_root, path, stat in snapshot:
        seen += 1
        album = album_for(media_root, path)
        if album == "(raiz)" and cfg.get("upload_root_files", False):
            album = media_root.name
        if media_root != roots[0]:
            label=media_root.name
            if sum(r.name.casefold()==label.casefold() for r in roots)>1:label += " ["+hashlib.sha1(str(media_root).encode()).hexdigest()[:6]+"]"
            album=label+" — "+album
        albums[album] = albums.get(album, 0) + 1
        fp = fingerprint(path, stat)
        row = db.execute("select fingerprint, status from media where path = ?", (str(path),)).fetchone()
        status = row[1] if row and row[0] == fp and row[1] == "uploaded" else "pending"
        if stat.st_size == 0:
            status = "invalid"
        db.execute("""
            insert into media(path, album, size, mtime_ns, ext, fingerprint, status, last_seen, last_error)
            values(?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(path) do update set
                album=excluded.album,
                size=excluded.size,
                mtime_ns=excluded.mtime_ns,
                ext=excluded.ext,
                fingerprint=excluded.fingerprint,
                status=case when excluded.size = 0 then 'invalid' when media.fingerprint = excluded.fingerprint then media.status else 'pending' end,
                uploaded_at=case when excluded.size = 0 or media.fingerprint != excluded.fingerprint then null else media.uploaded_at end,
                last_error=case when excluded.size = 0 then excluded.last_error when media.fingerprint != excluded.fingerprint then null else media.last_error end,
                last_seen=excluded.last_seen,
                present=1,
                evidence_kind=case when media.fingerprint != excluded.fingerprint then null else media.evidence_kind end,
                content_sha256=case when media.fingerprint != excluded.fingerprint then null else media.content_sha256 end
        """, (str(path), album, stat.st_size, stat.st_mtime_ns, path.suffix.lower(), fp, status, now, EMPTY_FILE_ERROR if stat.st_size == 0 else None))
        inserted_or_updated += 1
    db.commit()
    write_audit_exports(cfg, db)
    pattern = source_pattern(cfg)
    pending = db.execute("select count(*) from media where status != 'uploaded' and size>0 and present=1 and in_sources(path) and path like ? escape '!'", (pattern,)).fetchone()[0]
    invalid = db.execute("select count(*) from media where size = 0 and present=1 and in_sources(path) and path like ? escape '!'", (pattern,)).fetchone()[0]
    blocking_invalid = db.execute("select count(*) from media where size=0 and present=1 and coalesce(evidence_kind,'') != 'online_existing_declared_local_invalid' and in_sources(path) and path like ? escape '!'", (pattern,)).fetchone()[0]
    total_bytes = db.execute("select coalesce(sum(size), 0) from media where present=1 and in_sources(path) and path like ? escape '!'", (pattern,)).fetchone()[0]
    write_status(
        cfg,
        phase="error" if blocking_invalid else "idle",
        current_album="",
        current_file="",
        current_file_name="",
        pending_files=pending,
        album_index=0,
        album_total=0,
        album_pending=0,
        last_error=f"{blocking_invalid} arquivo(s) vazio(s). {EMPTY_FILE_ERROR}" if blocking_invalid else "",
        known_local_invalid_files=invalid-blocking_invalid,
    )
    db.close()
    return {"media_files": seen, "albums": len(albums), "pending_files": pending, "invalid_files": invalid, "unresolved_invalid_files": blocking_invalid, "bytes": total_bytes}


def write_audit_exports(cfg: dict, db: sqlite3.Connection) -> None:
    audit_dir = Path(cfg["audit_dir"])
    rows = db.execute("""
        select album, count(*) files, sum(size) bytes,
               sum(case when status = 'uploaded' or evidence_kind='online_existing_declared_local_invalid' then 1 else 0 end) uploaded,
               sum(case when status != 'uploaded' and size>0 then 1 else 0 end) pending
        from media where present=1 and in_sources(path) and path like ? escape '!' group by album order by album
    """, (source_pattern(cfg),)).fetchall()
    with atomic_csv(audit_dir / "albums_status.csv") as f:
        writer = csv.writer(f)
        writer.writerow(["album", "files", "bytes", "uploaded", "pending"])
        writer.writerows(rows)
    with atomic_csv(audit_dir / "pending_media.csv") as f:
        writer = csv.writer(f)
        writer.writerow(["album", "path", "size", "ext", "last_error"])
        writer.writerows(db.execute("select album, path, size, ext, last_error from media where status != 'uploaded' and present=1 and in_sources(path) and path like ? escape '!' order by album, path", (source_pattern(cfg),)))
    with atomic_csv(audit_dir / "baseline_history.csv") as f:
        writer = csv.writer(f)
        writer.writerow(["created_at", "event_type", "note", "media_count", "album_count", "bytes"])
        writer.writerows(db.execute("select created_at, event_type, note, media_count, album_count, bytes from events order by id"))


def quiet_run(*args,**kwargs):
    kwargs.setdefault("creationflags",getattr(subprocess,"CREATE_NO_WINDOW",0))
    return subprocess.run(*args,**kwargs)

def rclone_path(cfg: dict) -> str:
    configured = Path(cfg["rclone_exe"])
    if configured.exists():
        return str(configured)
    return "rclone"


def run(cmd: list[str], log_file: Path | None = None, cfg: dict | None = None, file_lookup: dict[str, str] | None = None, on_confirmed=None) -> subprocess.CompletedProcess:
    with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0)) as proc:
        lines = []
        for line in proc.stdout or []:
            lines.append(line)
            print(line, end="")
            if cfg and file_lookup:
                match = COPIED_LINE_RE.search(line.strip())
                if match:
                    name = Path(match.group("name")).name
                    current = file_lookup.get(name)
                    if current:
                        updates = {"current_file": current, "current_file_name": name}
                        confirmed = copied_files_from_rclone_output(line,file_lookup)
                        if confirmed and (on_confirmed is None or on_confirmed(current)):
                            updates["last_uploaded_file"] = current
                            updates["last_uploaded_file_name"] = name
                            updates["last_uploaded_at"] = datetime.now().isoformat(timespec="seconds")
                            updates["last_uploaded_fingerprint"] = fingerprint(Path(current),io_path(current).stat())
                        write_status(cfg, **updates)
            if log_file:
                with log_file.open("a", encoding="utf-8") as f:
                    f.write(line)
        return subprocess.CompletedProcess(cmd, proc.wait(), "".join(lines), None)


def copied_files_from_rclone_output(output: str, file_lookup: dict[str, str]) -> list[str]:
    uploaded: list[str] = []
    for line in output.splitlines():
        match = re.search(r"INFO\s+: (.+?): Copied(?: \([^)]*\))?(?:$|\s)", line)
        if not match:
            continue
        original = file_lookup.get(match.group(1))
        if original:
            uploaded.append(original)
    return uploaded


def stage_pending_files(album: str, pending_paths: list[Path], expected_fingerprints=None) -> tuple[tempfile.TemporaryDirectory, Path, dict[str, str]]:
    temp_dir = tempfile.TemporaryDirectory(prefix="gphotos_pending_")
    stage_root = Path(temp_dir.name)
    used_names: set[str] = set()
    lookup: dict[str, str] = {}
    for source in pending_paths:
        target_name = source.name
        if target_name in used_names:
            stem = source.stem
            suffix = source.suffix
            n = 2
            while f"{stem} ({n}){suffix}" in used_names:
                n += 1
            target_name = f"{stem} ({n}){suffix}"
        used_names.add(target_name)
        target = stage_root / target_name
        before = io_path(source).stat()
        if expected_fingerprints is not None and expected_fingerprints.get(str(source))!=fingerprint(source,before):raise RuntimeError(f"Source changed after inventory: {source}")
        if before.st_size == 0:
            raise ValueError(EMPTY_FILE_ERROR)
        shutil.copy2(io_path(source), target)
        after = io_path(source).stat()
        if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f"Arquivo alterado durante a preparação: {source}")
        lookup[target_name] = str(source)
    return temp_dir, stage_root, lookup


def doctor(cfg: dict) -> int:
    print("Google Photos Uploader - diagnostico")
    try:
        print(f"Pasta de fotos: {source_folder(cfg)} -> OK")
    except ValueError as exc:
        print(str(exc))
        return 2
    exe = rclone_path(cfg)
    try:
        version = quiet_run(rclone_args(cfg, app_root(), "version"), capture_output=True, text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        print("rclone: NAO ENCONTRADO")
        print("Coloque rclone.exe em tools\\rclone\\rclone.exe ou instale rclone no Windows.")
        return 2
    if version.returncode != 0:
        print("rclone: NAO ENCONTRADO")
        print("Coloque rclone.exe em tools\\rclone\\rclone.exe ou instale rclone no Windows.")
        return 2
    print(version.stdout.splitlines()[0])
    remotes = quiet_run(rclone_args(cfg, app_root(), "listremotes"), capture_output=True, text=True, encoding="utf-8", errors="replace")
    remote = cfg["rclone_remote"] + ":"
    if remote not in remotes.stdout.splitlines():
        print(f"Remote '{remote}' nao configurado.")
        print(f"Execute: {exe} config")
        return 3
    try:
        probe = quiet_run(rclone_args(cfg, app_root(), "lsd", f"{cfg['rclone_remote']}:album", "--contimeout", "10s", "--timeout", "20s", "--retries", "1", "--low-level-retries", "1"), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60)
    except subprocess.TimeoutExpired:
        print("O teste de acesso excedeu 60 segundos. Verifique a rede e tente novamente; nenhuma midia foi enviada.")
        return 4
    if probe.returncode != 0:
        print("Remote existe, mas nao consegui listar albuns. Talvez precise reconectar.")
        print(f"Execute: {exe} config reconnect {cfg['rclone_remote']}:")
        print(probe.stdout + probe.stderr)
        return 4
    print("Google Photos/rclone: OK")
    return 0


def remote_album_names(cfg: dict) -> set[str]:
    exe = rclone_path(cfg)
    result = quiet_run(
        rclone_args(cfg, app_root(), "lsf", f"{cfg['rclone_remote']}:album", "--dirs-only", "--format", "p"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    return {line.rstrip("/").strip() for line in result.stdout.splitlines() if line.strip()}


def verify_remote(cfg: dict) -> int:
    stats = scan(cfg)
    db = connect_db(cfg)
    try:
        remote_names = remote_album_names(cfg)
    except Exception as exc:
        print("Nao consegui ler os albuns remotos via rclone.")
        print(str(exc)[-1000:])
        return 4
    local_rows = db.execute("""
        select album, count(*) files, sum(size) bytes
        from media group by album order by album
    """).fetchall()
    audit_dir = Path(cfg["audit_dir"])
    with atomic_csv(audit_dir / "remote_album_visibility.csv") as f:
        writer = csv.writer(f)
        writer.writerow(["album", "local_files", "local_bytes", "visible_in_rclone"])
        for album, files, bytes_ in local_rows:
            writer.writerow([album, files, bytes_, "yes" if album in remote_names else "no"])
    matched = sum(1 for album, _files, _bytes in local_rows if album in remote_names)
    print(f"Inventario local: {stats['media_files']} midias, {stats['albums']} albuns.")
    print(f"Albuns visiveis pelo rclone: {len(remote_names)}.")
    print(f"Albuns locais tambem visiveis pelo rclone: {matched}.")
    print(f"Relatorio: {audit_dir / 'remote_album_visibility.csv'}")
    if len(remote_names) == 0:
        print("Aviso: o rclone nao esta enxergando albuns existentes do Google Fotos. Upload real esta bloqueado para evitar duplicidade.")
    return 0


def mark_baseline(cfg: dict, note: str | None) -> int:
    stats = scan(cfg)
    now = datetime.now().isoformat(timespec="seconds")
    db = connect_db(cfg)
    db.execute("update media set evidence_kind='online_existing_declared_local_invalid' where size=0 and present=1 and in_sources(path)")
    baseline_note = note or (
        "Baseline criada por declaracao do usuario: todo o conteudo local existente "
        "nesta data ja esta no Google Fotos. Novos arquivos ou arquivos modificados "
        "devem voltar a ficar pendentes em scans futuros."
    )
    marked = db.execute("""
        update media
        set status = 'uploaded',
            evidence_kind = 'online_existing_declared_by_user',
            uploaded_at = coalesce(uploaded_at, ?),
            last_error = null
        where size > 0 and present=1 and in_sources(path) and path like ? escape '!'
    """, (now, source_pattern(cfg))).rowcount
    db.execute("""
        insert into events(created_at, event_type, note, media_count, album_count, bytes)
        values(?, 'baseline_assumed_uploaded', ?, ?, ?, ?)
    """, (now, baseline_note, marked, stats["albums"], stats["bytes"]))
    db.commit()
    write_audit_exports(cfg, db)
    db.close()
    print("Baseline registrada.")
    print(f"Midias marcadas como ja existentes no Google Fotos: {marked}")
    print(f"Albuns cobertos pela baseline: {stats['albums']}")
    print("A partir de agora, arquivos novos ou modificados aparecerao como pendentes.")
    print(f"Historico: {Path(cfg['audit_dir']) / 'baseline_history.csv'}")
    return 0


def upload(cfg: dict, album_filter: str | None) -> int:
    stats = scan(cfg)
    write_status(cfg, phase="scan", current_album="", current_file="", current_file_name="", pending_files=stats["pending_files"], last_error="")
    print(f"Inventario: {stats['media_files']} midias, {stats['albums']} albuns, {stats['pending_files']} pendentes.")
    db = connect_db(cfg)
    pattern = source_pattern(cfg)
    albums = [r[0] for r in db.execute("select distinct album from media where size > 0 and status != 'uploaded' and present=1 and in_sources(path) and path like ? escape '!' order by album", (pattern,))]
    blocked_albums = set(cfg.get("blocked_albums", []))
    if blocked_albums:
        blocked_pending = [album for album in albums if album in blocked_albums]
        for album in blocked_pending:
            print(f"Pulando '{album}': album bloqueado em config.json para evitar reenvio automatico.")
        albums = [album for album in albums if album not in blocked_albums]
    if album_filter:
        albums = [a for a in albums if a == album_filter]
    if not albums:
        invalid = stats.get("unresolved_invalid_files", stats.get("invalid_files", 0))
        write_status(cfg, phase="error" if invalid else "idle", current_album="", current_file="", current_file_name="", pending_files=stats["pending_files"], last_error=EMPTY_FILE_ERROR if invalid else "")
        print("Nenhuma midia valida pendente para enviar." if invalid else "Nada pendente para enviar.")
        db.close()
        return 1 if invalid else 0
    exe = rclone_path(cfg)
    try:
        quiet_run(rclone_args(cfg, app_root(), "version"), capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("rclone nao encontrado ou nao funcionando. Rode run_diagnostico.bat para ver o passo faltante.")
        return 2
    remotes = quiet_run(rclone_args(cfg, app_root(), "listremotes"), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if cfg["rclone_remote"] + ":" not in remotes.stdout.splitlines():
        print(f"Remote '{cfg['rclone_remote']}:' nao configurado. Rode run_diagnostico.bat e configure o rclone antes do upload.")
        return 3
    try:
        visible_remote_albums = remote_album_names(cfg)
    except Exception as exc:
        print("Nao consegui conferir albuns remotos. Upload bloqueado para evitar duplicidade.")
        print(str(exc)[-1000:])
        return 4
    root = Path(cfg["photos_root"])
    log_file = Path(cfg["logs_dir"]) / f"upload-{datetime.now().strftime('%Y%m%d-%H%M%S')}.log"
    dry = bool(cfg.get("dry_run", True))
    failed_albums: list[str] = []
    blocked_reasons: list[str] = []
    for index, album in enumerate(albums, start=1):
        album_files = db.execute("select path from media where album = ? and size > 0 and status != 'uploaded' and present=1 and in_sources(path) and path like ? escape '!'", (album, pattern)).fetchall()
        pending_paths = [Path(row[0]) for row in album_files]
        write_status(
            cfg,
            phase="upload",
            current_album=album,
            current_file=str(pending_paths[0]) if pending_paths else "",
            current_file_name=pending_paths[0].name if pending_paths else "",
            album_index=index,
            album_total=len(albums),
            album_pending=len(pending_paths),
        )
        print(f"[{index}/{len(albums)}] Album: {album} ({len(album_files)} pendentes)")
        if album == "(raiz)":
            print("Pulando arquivos soltos na raiz; organize-os em uma pasta/album.")
            continue
        existing_uploaded = db.execute("select count(*) from media where album = ? and status = 'uploaded' and present=1 and in_sources(path) and path like ? escape '!'", (album, pattern)).fetchone()[0]
        is_new_album = existing_uploaded == 0
        if album not in visible_remote_albums and not is_new_album and not cfg.get("allow_create_remote_albums", False):
            reason = "Álbum histórico não acessível pela API; requer reconciliação no navegador para preservar o álbum existente."
            print(f"Bloqueado '{album}': {reason}")
            blocked_reasons.append(album)
            db.execute("update media set last_error=? where album=? and status!='uploaded' and present=1", (reason, album))
            db.commit()
            continue
        if album not in visible_remote_albums and is_new_album:
            print(f"Album novo detectado: '{album}'. O rclone pode criar este album no Google Fotos.")
        sample = pending_paths[0]
        # Send precisely the inventoried files, including loose root files and
        # excluding other albums or media that are still changing on disk.
        staged, source_dir, file_lookup = stage_pending_files(album, pending_paths,{str(path):db.execute("select fingerprint from media where path=?",(str(path),)).fetchone()[0] for path in pending_paths})
        cmd = rclone_args(cfg, app_root(),
            "copy", str(source_dir), f"{cfg['rclone_remote']}:album/{album}",
            # The inventory already validates media extensions. files-from-raw
            # selects only pending files and cannot be combined with include.
            "--ignore-case",
            "--ignore-times",
            "--transfers", str(cfg.get("transfers", 8)),
            "--checkers", str(cfg.get("checkers", 1)),
            "--retries", str(cfg.get("retries", 1)),
            "--low-level-retries", str(cfg.get("low_level_retries", 1)),
            "--stats", "15s",
            "--stats-one-line",
            "--log-level", "INFO",
        )
        if dry:
            cmd.append("--dry-run")
        result = None
        attempt_outputs = []
        attempts = max(1, int(cfg.get("album_retries", 3)))
        try:
            for attempt in range(1, attempts + 1):
                acknowledged=set(copied_files_from_rclone_output("\n".join(attempt_outputs),file_lookup))
                remaining=[name for name,path in file_lookup.items() if path not in acknowledged]
                if not remaining:break
                selection=source_dir/".upload-selection.txt"
                selection.write_text("\n".join(remaining)+"\n",encoding="utf-8")
                def checkpoint(path):
                    try:
                        saved=db.execute("select fingerprint from media where path=?",(path,)).fetchone()
                        if not saved or saved[0]!=fingerprint(Path(path),io_path(path).stat()):return False
                    except OSError:return False
                    now=datetime.now().isoformat(timespec="seconds")
                    db.execute("update media set status='uploaded',uploaded_at=coalesce(uploaded_at,?),last_error=null,evidence_kind='rclone_individual_confirmation' where path=?",(now,path))
                    db.commit()
                    pending=db.execute("select count(*) from media where status!='uploaded' and size>0 and present=1 and in_sources(path) and path like ? escape '!'",(pattern,)).fetchone()[0]
                    write_status(cfg,pending_files=pending)
                    return True
                result = run(cmd+["--files-from-raw",str(selection)], log_file, cfg=cfg, file_lookup=file_lookup,on_confirmed=None if dry else checkpoint)

                attempt_outputs.append(result.stdout)
                if result.returncode == 0 or (not dry and set(copied_files_from_rclone_output("\n".join(attempt_outputs),file_lookup))==set(file_lookup.values())):
                    if result.returncode!=0:result=subprocess.CompletedProcess(result.args,0,result.stdout,result.stderr)
                    break
                if attempt < attempts:
                    delay = min(60, 15 * attempt)
                    print(f"Falha temporaria no album {album}. Nova tentativa {attempt + 1}/{attempts} em {delay}s.")
                    time.sleep(delay)
        finally:
            if staged:
                try:
                    staged.cleanup()
                except OSError as exc:
                    print(f"Aviso ao limpar arquivos temporarios de {album}: {exc}")
        if result is None:
            raise RuntimeError(f"Nenhuma tentativa executada para o album {album}")
        copied = list(dict.fromkeys(copied_files_from_rclone_output("\n".join(attempt_outputs), file_lookup))) if not dry else []
        unconfirmed = set(map(str, pending_paths)) - set(copied)
        confirmation_error = "O rclone terminou sem confirmar individualmente todos os arquivos; os itens sem confirmacao continuam pendentes."
        last_error = result.stdout[-1000:] if result.returncode else (confirmation_error if unconfirmed and not dry else None)
        db.execute("update media set status = 'pending', uploaded_at = null, last_error = ? where album = ? and size > 0 and status != 'uploaded' and present=1 and in_sources(path) and path like ? escape '!'",
                   (last_error, album, pattern))
        if not dry:
            stable_copied = []
            for path in copied:
                try:
                    stat = io_path(Path(path)).stat()
                    saved = db.execute("select fingerprint from media where path=?", (path,)).fetchone()
                    if saved and saved[0] == fingerprint(Path(path), stat):
                        stable_copied.append(path)
                except OSError:
                    pass
            copied = stable_copied
            if copied:
                now = datetime.now().isoformat(timespec="seconds")
                db.executemany(
                    "update media set status = 'uploaded', uploaded_at = coalesce(uploaded_at, ?), last_error = null, evidence_kind='rclone_individual_confirmation' where path = ?",
                    [(now, path) for path in copied],
                )
                write_status(
                    cfg,
                    last_uploaded_file=copied[-1],
                    last_uploaded_file_name=Path(copied[-1]).name,
                    last_uploaded_at=now,
                    last_uploaded_fingerprint=db.execute("select fingerprint from media where path=?",(copied[-1],)).fetchone()[0],
                )
        db.commit()
        write_audit_exports(cfg, db)
        if result.returncode != 0 or (unconfirmed and not dry):
            write_status(cfg, phase="error", current_album=album, last_error=last_error)
            print(f"Erro no album {album}. Veja {log_file}")
            failed_albums.append(album)
            continue
    print(f"Log: {log_file}")
    pending = db.execute("select count(*) from media where status != 'uploaded' and size>0 and present=1 and in_sources(path) and path like ? escape '!'", (pattern,)).fetchone()[0]
    final_phase = "error" if pending else "idle"
    final_error = (
        f"Falha temporaria em {len(failed_albums)} album(ns); nova tentativa automatica agendada."
        if failed_albums else (f"{len(blocked_reasons)} álbum(ns) bloqueados pela API; requerem reconciliação web." if blocked_reasons else (f"{stats['invalid_files']} arquivo(s) vazio(s). {EMPTY_FILE_ERROR}" if stats.get("unresolved_invalid_files", stats.get("invalid_files")) else (f"{pending} arquivo(s) pendentes; envio não concluído." if pending else "")))
    )
    write_status(
        cfg,
        phase=final_phase,
        current_album="",
        current_file="",
        current_file_name="",
        last_error=final_error,
        pending_files=pending,
        album_index=0,
        album_total=0,
        album_pending=0,
    )
    db.close()
    return 1 if pending or failed_albums or stats.get("unresolved_invalid_files", stats.get("invalid_files")) else 0


def dispatch() -> int:
    parser = argparse.ArgumentParser(description="Google Photos Uploader")
    parser.add_argument("command", choices=["scan", "doctor", "upload", "verify-remote", "mark-baseline", "reconcile", "repair-online"])
    parser.add_argument("--album")
    parser.add_argument("--dry-run", action="store_true", help="Simula sempre, independentemente da configuração.")
    parser.add_argument("--live", action="store_true", help="Faz upload real. Sem isso, upload roda em modo teste.")
    parser.add_argument("--note", help="Nota registrada no historico da baseline.")
    parser.add_argument("--inventory", help="Inventário JSON do histórico; somente comparação, sem alterar recibos.")
    args = parser.parse_args()
    cfg = load_config()
    if args.live and args.dry_run:
        parser.error("Use apenas --live ou --dry-run.")
    cfg["dry_run"] = not args.live
    if args.command == "scan":
        print(scan(cfg))
        return 0
    if args.command == "doctor":
        return doctor(cfg)
    if args.command in ("reconcile", "repair-online"):
        from online_reconciliation import reconcile, repair
        if args.inventory:
            from online_reconciliation import import_inventory
            import_inventory(cfg,args.inventory)
        if args.command == "repair-online":
            cfg['dry_run'] = False
            return repair(cfg, app_root(), globals())
        summary, _ = reconcile(cfg, app_root(), connect_db)
        return 0 if summary['albums_complete'] and summary['library_complete'] else 4
    if args.command == "verify-remote":
        return verify_remote(cfg)
    if args.command == "mark-baseline":
        return mark_baseline(cfg, args.note)
    if args.command == "upload":
        return upload(cfg, args.album)
    return 1


def main() -> int:
    import msvcrt
    state=bootstrap()
    with (state/"data"/"worker.lock").open("a+b") as handle:
        handle.seek(0)
        handle.seek(0)
        try:msvcrt.locking(handle.fileno(),msvcrt.LK_NBLCK,1)
        except OSError:
            print("Another worker is active. Wait for it to finish.")
            return 75
        try:return dispatch()
        finally:
            handle.seek(0);msvcrt.locking(handle.fileno(),msvcrt.LK_UNLCK,1)


if __name__ == "__main__":
    raise SystemExit(main())
