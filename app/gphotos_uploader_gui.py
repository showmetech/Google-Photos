import os
import queue
import re
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

APP_TITLE = "Google Photos Uploader"


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("980x700")

        self.proc: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.current_total = 0

        self._build_ui()
        self._prefill_defaults()
        self.after(120, self._drain_queue)

    def _build_ui(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        cfg = ttk.LabelFrame(frm, text="Configuração", padding=10)
        cfg.pack(fill=tk.X)

        self.script_var = tk.StringVar()
        self.source_var = tk.StringVar(value=r"C:\Users\bruno\Meu Drive\Imagens\Fotos")
        self.logs_var = tk.StringVar(value=r"C:\rclone\logs")
        self.remote_var = tk.StringVar(value="gphotos:")
        self.max_albums_var = tk.StringVar(value="0")
        self.transfers_var = tk.StringVar(value="4")
        self.checkers_var = tk.StringVar(value="8")
        self.dryrun_var = tk.BooleanVar(value=False)

        self._row_file(cfg, 0, "Script (.ps1)", self.script_var, self._pick_script)
        self._row_file(cfg, 1, "Pasta origem", self.source_var, self._pick_source, is_dir=True)
        self._row_file(cfg, 2, "Pasta de logs", self.logs_var, self._pick_logs, is_dir=True)
        self._row_entry(cfg, 3, "Remote", self.remote_var)
        self._row_entry(cfg, 4, "MaxAlbums (0=todos)", self.max_albums_var)
        self._row_entry(cfg, 5, "Transfers", self.transfers_var)
        self._row_entry(cfg, 6, "Checkers", self.checkers_var)

        ttk.Checkbutton(cfg, text="DryRun (simular sem enviar)", variable=self.dryrun_var).grid(
            row=7, column=1, sticky="w", pady=(6, 0)
        )

        ctrl = ttk.Frame(frm, padding=(0, 10, 0, 10))
        ctrl.pack(fill=tk.X)

        self.start_btn = ttk.Button(ctrl, text="Iniciar Upload", command=self.start)
        self.start_btn.pack(side=tk.LEFT)

        self.stop_btn = ttk.Button(ctrl, text="Parar", command=self.stop, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value="Pronto")
        ttk.Label(ctrl, textvariable=self.status_var).pack(side=tk.LEFT, padx=16)

        self.progress = ttk.Progressbar(frm, orient=tk.HORIZONTAL, mode="determinate", maximum=100)
        self.progress.pack(fill=tk.X)

        self.album_var = tk.StringVar(value="Álbum: -")
        ttk.Label(frm, textvariable=self.album_var).pack(anchor="w", pady=(6, 2))

        self.log_text = tk.Text(frm, height=28, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True)

        scroll = ttk.Scrollbar(self.log_text, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def _row_file(self, parent, row, label, variable, command, is_dir=False):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=95).grid(row=row, column=1, sticky="ew", padx=8)
        ttk.Button(parent, text="...", width=4, command=command).grid(row=row, column=2)
        parent.grid_columnconfigure(1, weight=1)

    def _row_entry(self, parent, row, label, variable):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=3)
        ttk.Entry(parent, textvariable=variable, width=30).grid(row=row, column=1, sticky="w", padx=8)

    def _prefill_defaults(self) -> None:
        runtime_dir = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        candidate = runtime_dir / "gphotos_allinone.ps1"
        if candidate.exists():
            self.script_var.set(str(candidate))
        else:
            self.script_var.set(r"C:\rclone\scripts\gphotos_allinone.ps1")

    def _pick_script(self) -> None:
        p = filedialog.askopenfilename(filetypes=[("PowerShell", "*.ps1"), ("All", "*.*")])
        if p:
            self.script_var.set(p)

    def _pick_source(self) -> None:
        p = filedialog.askdirectory()
        if p:
            self.source_var.set(p)

    def _pick_logs(self) -> None:
        p = filedialog.askdirectory()
        if p:
            self.logs_var.set(p)

    def _validate(self) -> bool:
        script = self.script_var.get().strip()
        if not script:
            messagebox.showerror(APP_TITLE, "Informe o caminho do script .ps1")
            return False
        if not Path(script).exists():
            messagebox.showerror(APP_TITLE, f"Script não encontrado:\n{script}")
            return False

        for name, value in [
            ("MaxAlbums", self.max_albums_var.get()),
            ("Transfers", self.transfers_var.get()),
            ("Checkers", self.checkers_var.get()),
        ]:
            if not re.match(r"^\d+$", value.strip()):
                messagebox.showerror(APP_TITLE, f"{name} precisa ser número inteiro >= 0")
                return False

        return True

    def _build_command(self) -> list[str]:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            self.script_var.get().strip(),
            "-SourceRoot",
            self.source_var.get().strip(),
            "-LogsDir",
            self.logs_var.get().strip(),
            "-Remote",
            self.remote_var.get().strip(),
            "-MaxAlbums",
            self.max_albums_var.get().strip(),
            "-Transfers",
            self.transfers_var.get().strip(),
            "-Checkers",
            self.checkers_var.get().strip(),
        ]
        if self.dryrun_var.get():
            cmd.append("-DryRun")
        return cmd

    def start(self) -> None:
        if self.proc:
            return
        if not self._validate():
            return

        cmd = self._build_command()
        self.log_text.delete("1.0", tk.END)
        self._append_log(f"Comando: {' '.join(cmd)}\n")

        self.progress["value"] = 0
        self.album_var.set("Álbum: -")
        self.status_var.set("Executando...")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        t = threading.Thread(target=self._run_proc, args=(cmd,), daemon=True)
        t.start()

    def stop(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            self._append_log("\n[INFO] Processo encerrado pelo usuário.\n")

    def _run_proc(self, cmd: list[str]) -> None:
        env = os.environ.copy()

        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
        )

        assert self.proc.stdout is not None
        for line in self.proc.stdout:
            self.log_queue.put(line)

        code = self.proc.wait()
        self.log_queue.put(f"\n[EXIT] Código de saída: {code}\n")
        self.log_queue.put("__PROCESS_DONE__")

    def _drain_queue(self) -> None:
        while True:
            try:
                item = self.log_queue.get_nowait()
            except queue.Empty:
                break

            if item == "__PROCESS_DONE__":
                self._on_done()
                continue

            self._append_log(item)
            self._process_progress_line(item)

        self.after(120, self._drain_queue)

    def _process_progress_line(self, line: str) -> None:
        album_match = re.search(r"\[(\d+)/(\d+)\].*Álbum:\s*(.+)$", line)
        if album_match:
            idx = int(album_match.group(1))
            total = int(album_match.group(2))
            name = album_match.group(3).strip()
            self.current_total = total
            self.album_var.set(f"Álbum atual: {name} ({idx}/{total})")
            if total > 0:
                self.progress["value"] = (idx / total) * 100

        if "ERRO no álbum" in line or "ERROR" in line.upper():
            self.status_var.set("Execução com erro(s)")

        if "=== Concluído ===" in line:
            self.status_var.set("Concluído")

    def _append_log(self, text: str) -> None:
        self.log_text.insert(tk.END, text)
        self.log_text.see(tk.END)

    def _on_done(self) -> None:
        code = self.proc.returncode if self.proc else 1
        if code == 0 and self.status_var.get() != "Execução com erro(s)":
            self.status_var.set("Concluído com sucesso")
        elif self.status_var.get() != "Execução com erro(s)":
            self.status_var.set("Finalizado com falhas")

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.proc = None


def main() -> None:
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
