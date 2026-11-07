import csv
import json
import os
import subprocess
import sys
import threading
import tkinter as tk
import shutil
import time
import webbrowser
from pathlib import Path
from tkinter import ttk, filedialog, messagebox

from app_config import load_settings, save_settings, source_folder, rclone_args, account_configured, prepare_account

import psutil
from PIL import Image, ImageOps, ImageTk
try:
    import pystray
except ImportError:
    pystray = None

try:
    from pillow_heif import register_heif_opener
except ImportError:
    register_heif_opener = None

try:
    import msvcrt
except ImportError:
    msvcrt = None


if getattr(sys, "frozen", False):
    frozen_dir = Path(sys.executable).resolve().parent
    if frozen_dir.parent.name == "dist":
        APP_DIR = frozen_dir.parent.parent
    else:
        APP_DIR = frozen_dir
else:
    APP_DIR = Path(__file__).resolve().parent
from app_paths import bootstrap
STATE_DIR = bootstrap()
CONFIG_PATH = STATE_DIR / "config.json"
AUDIT_DIR = STATE_DIR / "audit"
DATA_DIR = STATE_DIR / "data"
STATUS_PATH = DATA_DIR / "current_status.json"
PREVIEW_PATH = DATA_DIR / "current_preview.jpg"
LAST_PREVIEW_PATH = DATA_DIR / "last_uploaded_preview.jpg"
LOCK_PATH = DATA_DIR / "manager.lock"
ACTIVATE_PATH = DATA_DIR / "activate_window.signal"
ICON_PATH = APP_DIR / "AppIconYellow.ico"
TRAY_ICON_PATH = APP_DIR / "AppIconTray.png"
TRAY_ERROR_PATH = DATA_DIR / "tray_error.log"
PYTHON = APP_DIR / "runtime" / "python.exe"
if not PYTHON.exists():
    PYTHON = APP_DIR / ".venv" / "Scripts" / "python.exe"
if not PYTHON.exists():
    PYTHON = Path(sys.executable).with_name("python.exe")

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".gif", ".heic", ".heif", ".webp", ".bmp", ".tif", ".tiff", ".avif", ".ico",
    ".dng", ".cr2", ".cr3", ".crw", ".nef", ".arw", ".rw2", ".orf", ".raf", ".srw", ".pef",
}
VIDEO_EXTENSIONS = {
    ".mp4", ".mov", ".avi", ".m4v", ".mts", ".m2ts", ".m2t", ".3gp", ".3g2", ".wmv", ".mpg", ".mpeg",
    ".webm", ".asf", ".divx", ".mkv", ".mmv", ".mod", ".tod",
}


def find_ffmpeg():
    bundled = APP_DIR / "tools" / "ffmpeg" / "ffmpeg.exe"
    if bundled.is_file():
        return bundled
    found = shutil.which("ffmpeg")
    if found:
        return Path(found)
    return None


FFMPEG = find_ffmpeg()
LOCK_HANDLE = None

if register_heif_opener:
    register_heif_opener()


def acquire_single_instance():
    global LOCK_HANDLE
    if not msvcrt:
        return True
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_HANDLE = LOCK_PATH.open("a+b")
    try:
        LOCK_HANDLE.seek(0)
        msvcrt.locking(LOCK_HANDLE.fileno(), msvcrt.LK_NBLCK, 1)
        LOCK_HANDLE.seek(0)
        LOCK_HANDLE.truncate()
        LOCK_HANDLE.write(str(time.time()).encode("ascii"))
        LOCK_HANDLE.flush()
        return True
    except OSError:
        return False


def signal_existing_instance():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVATE_PATH.write_text(str(time.time()), encoding="utf-8")


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def append_tray_error(message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with TRAY_ERROR_PATH.open("a", encoding="utf-8") as f:
        f.write(f"[{stamp}] {message}\n")


def read_albums_status():
    path = AUDIT_DIR / "albums_status.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def read_pending_media():
    path = AUDIT_DIR / "pending_media.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def summarize_albums():
    rows = read_albums_status()
    found = len(rows)
    completed = sum(1 for row in rows if int(row.get("pending") or 0) == 0)
    pending = sum(1 for row in rows if int(row.get("pending") or 0) > 0)
    pending_files = sum(int(row.get("pending") or 0) for row in rows)
    return found, completed, pending, pending_files


def uploadable_pending_count():
    cfg = load_json(CONFIG_PATH, {})
    blocked = set(cfg.get("blocked_albums", []))
    return sum(1 for row in read_pending_media() if row.get("album") not in blocked and int(row.get("size") or 0)>0 and not (row.get("last_error") or "").startswith("Álbum histórico"))


def existing_worker_running():
    """Also recognize workers started by the legacy packaged manager."""
    script = os.path.normcase(str(APP_DIR / "gphotos_uploader.py"))
    for process in psutil.process_iter(["cmdline"]):
        try:
            if any(os.path.normcase(arg) == script for arg in (process.info["cmdline"] or [])):
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


from widget_ui import WidgetUI


class ManagerApp(WidgetUI, tk.Tk):
    def __init__(self, auto_start=False, minimized=False):
        super().__init__()
        self.title("Google Photos Upload Manager")
        self.geometry("1260x820")
        self.minsize(980, 650)
        self.configure(bg="#1f1f1f")
        self.process = None
        self.command_starting = False
        self.output_lines = []
        self.preview_image = None
        self.current_preview_path = ""
        self.current_preview_label = ""
        self.next_auto_run_at = 0
        self.last_auto_run_at = 0
        self.tray_icon = None
        self.tray_thread = None
        self.quit_requested = False
        self.last_activate_signal = time.time()

        self.cfg = load_settings(CONFIG_PATH)
        self.auto_monitor_enabled = bool(self.cfg.get("auto_monitor_enabled", False))
        self.auth_process = None
        self.settings_dialog = None
        self.auto_monitor_interval_ms = int(self.cfg.get("auto_monitor_interval_minutes", 15)) * 60 * 1000
        self.auto_monitor_interval_ms = max(60_000, self.auto_monitor_interval_ms)
        self.source_var = tk.StringVar(value=self.cfg.get("photos_root", ""))
        self.banner_var = tk.StringVar(value="Pronto para verificar uploads.")
        self.auto_var = tk.StringVar(value="")
        self.current_album_var = tk.StringVar(value="-")
        self.current_file_var = tk.StringVar(value="-")
        self.summary_var = tk.StringVar(value="-")
        self.progress_var = tk.DoubleVar(value=0)
        self.file_progress_var = tk.DoubleVar(value=0)

        if ICON_PATH.exists():
            self.iconbitmap(str(ICON_PATH))
        self.protocol("WM_DELETE_WINDOW", self.hide_to_tray)
        self._build_ui()
        self.create_tray_icon()
        self.refresh_view()
        self.after(1500, self.poll_status)
        self.after(1000, self.poll_activation_signal)
        self.after(10_000, self.auto_monitor_tick)
        if not self.cfg.get("photos_root") or "--settings" in sys.argv:
            self.banner_var.set("Primeiro uso: escolha a pasta e conecte sua conta em Configurar.")
            self.after(200, self.open_settings)
        if auto_start:
            self.after(1200, self.start_upload)
        if minimized:
            self.after(500, self.hide_to_tray)

    def _label(self, parent, text, size=10, bold=False, fg="#f5f5f5"):
        font = ("Segoe UI", size, "bold" if bold else "normal")
        label = tk.Label(parent, text=text, bg=parent["bg"], fg=fg, font=font)
        return label

    def _stat_card(self, parent, title, color):
        frame = tk.Frame(parent, bg="#262626", highlightbackground="#3a3a3a", highlightthickness=1)
        label = self._label(frame, title, 10, True)
        label.pack(anchor="w", padx=14, pady=(12, 4))
        value = tk.Label(frame, text="0", bg="#262626", fg=color, font=("Segoe UI", 24, "bold"))
        value.pack(anchor="w", padx=14, pady=(0, 10))
        return frame, value

    def open_settings(self):
        if self.settings_dialog and self.settings_dialog.winfo_exists():
            self.settings_dialog.lift()
            return
        dialog = self.settings_dialog = tk.Toplevel(self)
        dialog.title("Google Photos Uploader · Configurações")
        dialog.geometry(f"{self.px(620)}x{self.px(650)}")
        dialog.transient(self.details if self.details.state() != "withdrawn" else self)
        canvas = tk.Canvas(dialog, highlightthickness=0)
        scrollbar = ttk.Scrollbar(dialog, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        frame = ttk.Frame(canvas, padding=20)
        content = canvas.create_window((0, 0), window=frame, anchor="nw")
        frame.bind("<Configure>", lambda event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda event: canvas.itemconfigure(content, width=event.width))
        canvas.bind("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"))
        ttk.Label(frame, text="1. Escolha suas fotos", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        folder_var = tk.StringVar(value=self.cfg.get("photos_root", ""))
        ttk.Entry(frame, textvariable=folder_var).pack(fill="x", pady=8)
        def browse():
            selected = filedialog.askdirectory(parent=dialog, title="Escolha a pasta de fotos e vídeos")
            if selected:
                folder_var.set(selected)
        ttk.Button(frame, text="Escolher pasta…", command=browse).pack(anchor="w")
        ttk.Label(frame, text="2. Acesso ao Google Fotos", font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(18, 6))
        connected_var = tk.StringVar(value="Conta configurada neste PC" if account_configured(self.cfg, APP_DIR) else "Conta ainda não conectada")
        ttk.Label(frame, textvariable=connected_var).pack(anchor="w")
        ttk.Label(frame, text="A configuração existente será preservada. Use a reconexão somente se houver\n"
                             "uma falha de acesso. Não é necessário preencher o cliente OAuth novamente.").pack(anchor="w", pady=8)
        ttk.Button(frame, text="Abrir guia de acesso ao Google Fotos", command=lambda:
                   webbrowser.open("https://rclone.org/googlephotos/#making-your-own-client-id")).pack(anchor="w")
        client_id_var, client_secret_var = tk.StringVar(), tk.StringVar()
        ttk.Label(frame, text="ID do cliente OAuth (Aplicativo para computador)").pack(anchor="w", pady=(10, 2))
        ttk.Entry(frame, textvariable=client_id_var).pack(fill="x")
        ttk.Label(frame, text="Segredo do cliente").pack(anchor="w", pady=(8, 2))
        ttk.Entry(frame, textvariable=client_secret_var, show="●").pack(fill="x")
        account_row = ttk.Frame(frame)
        account_row.pack(fill="x", pady=8)
        ttk.Button(account_row, text="Conectar / reconectar", command=lambda: self.connect_account(
            client_id_var.get(), client_secret_var.get(), connected_var)).pack(side="left")
        ttk.Button(account_row, text="Cancelar conexão", command=self.cancel_connection).pack(side="left", padx=8)
        automatic_var = tk.BooleanVar(value=self.auto_monitor_enabled)
        ttk.Checkbutton(frame, text="Verificar e enviar automaticamente a cada 15 minutos",
                        variable=automatic_var).pack(anchor="w", pady=(12, 6))
        ttk.Label(frame, text="Ative o automático depois de conferir a conta e o histórico de uploads.").pack(anchor="w")
        bottom = ttk.Frame(frame)
        bottom.pack(fill="x", pady=15)
        self.theme_settings(dialog)
        def apply():
            try:
                self.apply_settings(folder_var.get(), automatic_var.get())
            except (ValueError, OSError) as exc:
                messagebox.showerror("Configuração não salva", str(exc), parent=dialog)
                return
            dialog.destroy()
        ttk.Button(bottom, text="Salvar configuração", command=apply).pack(side="left")
        ttk.Button(bottom, text="Testar conexão", command=lambda: self.run_command(["doctor"])).pack(side="left", padx=8)
        ttk.Button(bottom, text="Fechar", command=dialog.destroy).pack(side="right")

    def apply_settings(self, folder, automatic):
        if self.command_starting or (self.process and self.process.poll() is None) or existing_worker_running():
            raise ValueError("Aguarde a operação atual terminar antes de alterar a configuração.")
        cfg = load_settings(CONFIG_PATH)
        cfg["photos_root"] = folder.strip()
        cfg["photos_root"] = str(source_folder(cfg))
        if automatic and not account_configured(cfg, APP_DIR):
            raise ValueError("Conecte sua conta Google antes de ativar o envio automático.")
        cfg["auto_monitor_enabled"] = bool(automatic)
        cfg["auto_monitor_interval_minutes"] = 15
        save_settings(CONFIG_PATH, cfg)
        self.cfg = cfg
        self.auto_monitor_enabled = bool(automatic)
        self.auto_monitor_interval_ms = 15 * 60_000
        self.next_auto_run_at = 0
        self.source_var.set(cfg["photos_root"])
        self.refresh_view()
        self.banner_var.set("Configuração salva. Verifique os arquivos antes de iniciar o envio.")

    def connect_account(self, client_id="", client_secret="", status_var=None):
        if self.auth_process and self.auth_process.poll() is None:
            return
        try:
            if self.command_starting or (self.process and self.process.poll() is None) or existing_worker_running():
                raise ValueError("Aguarde a operação atual terminar antes de reconectar a conta.")
            cfg = load_settings(CONFIG_PATH)
            if client_id or client_secret:
                prepare_account(cfg, APP_DIR, client_id, client_secret)
            elif not account_configured(cfg, APP_DIR):
                raise ValueError("Informe os dados do cliente OAuth para a primeira conexão.")
            command = rclone_args(cfg, APP_DIR, "config", "reconnect", cfg.get("rclone_remote", "gphotos") + ":", "--auto-confirm")
            # Credentials stay in the private profile, never in command arguments or logs.
            self.auth_process = subprocess.Popen(command, cwd=APP_DIR, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.auth_deadline = time.monotonic() + 300
            self.banner_var.set("Conclua a autorização da sua conta Google no navegador.")
            self.after(500, lambda: self.poll_connection(status_var))
        except (ValueError, OSError) as exc:
            self.banner_var.set(str(exc))
            if status_var:
                status_var.set(str(exc))

    def poll_connection(self, status_var=None):
        if not self.auth_process:
            return
        code = self.auth_process.poll()
        if code is None and time.monotonic() < self.auth_deadline:
            self.after(500, lambda: self.poll_connection(status_var))
            return
        if code is None:
            self.cancel_connection()
        successful = code == 0 and account_configured(load_settings(CONFIG_PATH), APP_DIR)
        text = "Conta conectada. Use Testar conexão para conferir o acesso." if successful else "Conexão não concluída. Confira o cliente OAuth e tente novamente."
        self.banner_var.set(text)
        try:
            if status_var:
                status_var.set(text)
        except tk.TclError:
            pass

    def cancel_connection(self):
        if self.auth_process and self.auth_process.poll() is None:
            self.auth_process.terminate()
        self.banner_var.set("Conexão cancelada.")

    def run_command(self, args):
        if self.auth_process and self.auth_process.poll() is None:
            self.banner_var.set("Conclua a conexão da conta antes de verificar ou enviar.")
            return False
        try:
            source_folder(load_settings(CONFIG_PATH))
        except (ValueError, OSError) as exc:
            self.banner_var.set(str(exc))
            return False
        if self.command_starting or (self.process and self.process.poll() is None):
            self.banner_var.set("Ja existe uma execucao em andamento.")
            return False
        if existing_worker_running():
            self.banner_var.set("Envio existente em andamento. Aguardando sua conclusao.")
            return False
        self.command_starting = True

        def worker():
            try:
                self.process = subprocess.Popen(
                    [str(PYTHON), "-X", "utf8", "-u", str(APP_DIR / "gphotos_uploader.py"), *args],
                    cwd=str(APP_DIR),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                for line in self.process.stdout or []:
                    self.output_lines.append(line.rstrip())
                    self.after(0, self.update_log)
                code = self.process.wait()
            except OSError as exc:
                self.output_lines.append(f"Nao foi possivel iniciar a verificacao: {exc}")
                self.after(0, self.update_log)
                code = 1
            finally:
                self.command_starting = False
            self.after(0, lambda: self.command_finished(code))

        threading.Thread(target=worker, daemon=True).start()
        return True

    def scan(self):
        self.banner_var.set("Verificando uploads...")
        self.run_command(["scan"])

    def start_upload(self):
        self.banner_var.set("Upload em andamento...")
        if self.run_command(["upload", "--live"]):
            now = time.time()
            self.last_auto_run_at = now
            self.next_auto_run_at = now + (self.auto_monitor_interval_ms / 1000)

    def stop_upload(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.banner_var.set("Upload interrompido.")

    def command_finished(self, code):
        state = load_json(STATUS_PATH, {})
        self.banner_var.set("Concluído sem pendências." if code == 0 and not state.get("pending_files") else (state.get("last_error") or "Operação terminou com pendências. Veja o histórico."))
        self.refresh_view()
        if self.auto_monitor_enabled and uploadable_pending_count() > 0:
            retry_seconds = 30 if code == 0 else 60
            self.banner_var.set("Ainda ha pendencias. Nova tentativa automatica agendada...")
            self.next_auto_run_at = time.time() + retry_seconds
            self.after(retry_seconds * 1000, self.auto_monitor_tick)

    def update_log(self):
        self.log_text.delete("1.0", "end")
        self.log_text.insert("end", "\n".join(self.output_lines[-200:]))
        self.log_text.see("end")

    def refresh_view(self):
        found, completed, pending, pending_files = summarize_albums()
        blocked = sum(1 for row in read_pending_media() if row.get("last_error") or int(row.get("size") or 0)==0)
        self.value_found.configure(text=str(found))
        self.value_done.configure(text=str(completed))
        self.value_pending.configure(text=str(pending))
        self.value_errors.configure(text=str(blocked))
        self.summary_var.set(f"Pendentes: {pending_files} | Bloqueados: {blocked}")
        self.refresh_pending_details(read_pending_media())
        interval = max(1, self.auto_monitor_interval_ms // 60000)
        state = "ligado" if self.auto_monitor_enabled else "desligado"
        self.auto_var.set(f"Automatico {state}: verifica e envia a cada {interval} min. Arquivos recentes aguardam estabilizar.")

    def auto_monitor_tick(self):
        if not self.auto_monitor_enabled:
            self.after(self.auto_monitor_interval_ms, self.auto_monitor_tick)
            return
        if self.command_starting or (self.process and self.process.poll() is None):
            self.after(60_000, self.auto_monitor_tick)
            return
        if existing_worker_running():
            self.banner_var.set("Envio existente em andamento. Aguardando sua conclusao.")
            self.after(60_000, self.auto_monitor_tick)
            return
        now = time.time()
        if self.next_auto_run_at and now < self.next_auto_run_at:
            wait_ms = max(30_000, int((self.next_auto_run_at - now) * 1000))
            self.after(wait_ms, self.auto_monitor_tick)
            return
        self.banner_var.set("Verificacao automatica em andamento...")
        started = self.run_command(["upload", "--live"])
        if started:
            self.last_auto_run_at = now
        self.next_auto_run_at = now + (self.auto_monitor_interval_ms / 1000)
        self.after(self.auto_monitor_interval_ms, self.auto_monitor_tick)

    def create_tray_icon(self):
        if self.tray_icon:
            return
        if pystray is None:
            append_tray_error("Componente da bandeja indisponivel; janela permanecera acessivel.")
            return
        icon_source = TRAY_ICON_PATH if TRAY_ICON_PATH.exists() else ICON_PATH
        if not icon_source.exists():
            append_tray_error("Icone nao encontrado para a bandeja.")
            return
        try:
            image = Image.open(icon_source).convert("RGBA")
            image.thumbnail((64, 64), Image.Resampling.LANCZOS)
            menu = pystray.Menu(
                pystray.MenuItem("Abrir", self.tray_show, default=True),
                pystray.MenuItem("Iniciar upload", self.tray_start_upload),
                pystray.MenuItem("Sair", self.tray_quit),
            )
            self.tray_icon = pystray.Icon("Google Photos Upload Manager", image, "Google Photos Upload Manager", menu)
            self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
            self.tray_thread.start()
        except Exception as exc:
            append_tray_error(f"Falha ao criar icone da bandeja: {exc!r}")
            self.tray_icon = None

    def tray_show(self, icon=None, item=None):
        self.after(0, self.show_window)

    def tray_start_upload(self, icon=None, item=None):
        self.after(0, self.start_upload)

    def tray_quit(self, icon=None, item=None):
        self.after(0, self.quit_app)

    def show_window(self):
        self.deiconify()
        self._interaction()
        self.update_idletasks()
        self.lift()
        self.update_pin()
        self.focus_force()

    def hide_to_tray(self):
        if not self.tray_icon or not self.tray_icon.visible:
            self.iconify()
            self.banner_var.set("Bandeja indisponivel. App minimizado na barra de tarefas.")
            return
        self.save_ui_preferences()
        self.withdraw()

    def poll_activation_signal(self):
        try:
            if ACTIVATE_PATH.exists():
                value = float(ACTIVATE_PATH.read_text(encoding="utf-8").strip() or "0")
                if value > self.last_activate_signal:
                    self.last_activate_signal = value
                    self.show_window()
        except Exception:
            pass
        self.after(1000, self.poll_activation_signal)

    def quit_app(self):
        self.quit_requested = True
        if self.auth_process and self.auth_process.poll() is None:
            self.auth_process.terminate()
        if self.process and self.process.poll() is None:
            self.process.terminate()
        if self.tray_icon:
            self.tray_icon.stop()
        self.save_ui_preferences()
        self.destroy()

    def poll_status(self):
        status = load_json(STATUS_PATH, {})
        album = status.get("current_album") or "-"
        current = status.get("current_file") or ""
        last_uploaded = status.get("last_uploaded_file") or ""
        last_uploaded_name = status.get("last_uploaded_file_name") or Path(last_uploaded).name
        phase = status.get("phase") or "idle"
        self.current_album_var.set(album)
        self.current_file_var.set(current or "-")
        total = status.get("album_total") or 0
        index = status.get("album_index") or 0
        if total:
            self.progress_var.set(max(0, min(100, (index - 1) / total * 100)))
        else:
            self.progress_var.set(0)
        self.file_progress_var.set(100 if phase == "idle" and not status.get("pending_files") else 0)
        if current:
            self.preview_title.configure(text="Previa do upload")
            if current != self.current_preview_path or self.current_preview_label != "current":
                self.show_preview(Path(current), label="current")
        elif last_uploaded:
            self.preview_title.configure(text="Ultimo enviado")
            if last_uploaded != self.current_preview_path or self.current_preview_label != "last":
                self.show_preview(Path(last_uploaded), label="last", display_name=last_uploaded_name)
        else:
            self.preview_title.configure(text="Ultimo enviado")
            self.preview_label.configure(image="", text="Nenhum envio registrado")
            self.current_preview_path = ""
            self.current_preview_label = ""
        self.after(1500, self.poll_status)

    def set_preview_image(self, image: Image.Image, label: str) -> None:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((self.px(220), self.px(125)))
        if label == "last":
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            image.convert("RGB").save(LAST_PREVIEW_PATH, "JPEG", quality=88)
        thumb = ImageOps.fit(image.copy(), (self.px(48), self.px(48)), method=Image.Resampling.LANCZOS)
        self.widget_thumb_image = ImageTk.PhotoImage(thumb)
        self.widget_thumb.configure(image=self.widget_thumb_image, text="", width=self.px(48), height=self.px(48))
        self.preview_image = ImageTk.PhotoImage(image)
        self.preview_label.configure(image=self.preview_image, text="")

    def show_preview(self, path: Path, label: str = "current", display_name: str | None = None):
        self.current_preview_path = str(path)
        self.current_preview_label = label
        name = display_name or path.name
        suffix = path.suffix.lower()
        if suffix in IMAGE_EXTENSIONS and path.exists():
            try:
                image = Image.open(path)
                self.set_preview_image(image, label)
                return
            except Exception:
                if self.show_ffmpeg_preview(path, is_video=False, label=label):
                    return
        if suffix in VIDEO_EXTENSIONS and path.exists():
            self.preview_label.configure(image="", text=f"Gerando previa do video...\n{path.name}")
            self.update_idletasks()
            if self.show_ffmpeg_preview(path, is_video=True, label=label):
                return
        kind = "Video" if suffix in VIDEO_EXTENSIONS else "Arquivo"
        size = ""
        try:
            size = f"\n{path.stat().st_size / (1024 * 1024):.1f} MB"
        except OSError:
            pass
        status_text = "Ultimo enviado" if label == "last" else f"{kind} em envio"
        self.preview_label.configure(image="", text=f"{status_text}\n{name}{size}")

    def show_ffmpeg_preview(self, path: Path, is_video: bool, label: str = "current"):
        if not FFMPEG:
            return False
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y"]
        if is_video:
            cmd.extend(["-ss", "00:00:01"])
        cmd.extend([
            "-i", str(path),
            "-frames:v", "1",
            "-vf", "scale='min(300,iw)':-2",
            str(PREVIEW_PATH),
        ])
        try:
            subprocess.run(cmd, capture_output=True, timeout=20, check=True)
            image = Image.open(PREVIEW_PATH)
            self.set_preview_image(image, label)
            return True
        except Exception:
            return False


if __name__ == "__main__":
    try:
        import ctypes
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except (AttributeError, OSError):
        pass
    if not acquire_single_instance():
        if "--minimized" not in sys.argv:
            signal_existing_instance()
        raise SystemExit(0)
    auto = "--auto" in sys.argv
    minimized = "--minimized" in sys.argv
    app = ManagerApp(auto_start=auto, minimized=minimized)
    app.mainloop()
