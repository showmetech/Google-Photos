"""Compact Photos surface; UI only. Upload and history remain in the manager."""
import ctypes
import json
import os
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from PIL import Image, ImageDraw, ImageTk


class WidgetUI:
    def _build_ui(self):
        self.ui_dir = Path(__file__).resolve().parent / 'data'
        self.ui_path = self.ui_dir / 'widget_preferences.json'
        try:
            self.ui_prefs = json.loads(self.ui_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            self.ui_prefs = {}
        self.ui_scale = self.winfo_fpixels('1i') / 96
        self.bg, self.tile, self.ink, self.muted = '#202020', '#303030', '#f3f3f3', '#bcbebe'
        self.accent, self.line = '#cec681', '#414141'
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\DWM') as key:
                color = winreg.QueryValueEx(key, 'AccentColor')[0]
                self.accent = '#%02x%02x%02x' % (color & 255, color >> 8 & 255, color >> 16 & 255)
        except OSError:
            pass
        self.pinned = bool(self.ui_prefs.get('pinned', False))
        self._last_interaction = time.monotonic()
        self.details = None
        self.widget_status = tk.StringVar(value='Verificando estado…')
        self.widget_subtitle = tk.StringVar(value='Lendo o registro de sincronização')
        self.widget_pending = tk.StringVar(value='—')
        self.widget_last = tk.StringVar(value='Nenhum envio registrado')
        self.widget_last_date = tk.StringVar(value='')
        self.widget_auto = tk.StringVar(value='')
        self.widget_check = tk.StringVar(value='')
        self.title('Google Photos Uploader')
        self.overrideredirect(True)
        self.configure(bg='#010203')
        self.attributes('-transparentcolor', '#010203')
        width, height = self.px(360), self.px(478)
        x = self.ui_prefs.get('x', self.winfo_screenwidth() - width - self.px(24))
        y = self.ui_prefs.get('y', self.winfo_screenheight() - height - self.px(64))
        x = max(0, min(int(x), self.winfo_screenwidth() - width))
        y = max(0, min(int(y), self.winfo_screenheight() - height - self.px(48)))
        self.minsize(width, height)
        self.geometry(f'{width}x{height}+{x}+{y}')
        self.surface = tk.Canvas(self, bg='#010203', highlightthickness=0)
        self.surface.pack(fill='both', expand=True)
        image = Image.new('RGB', (width, height), '#010203')
        ImageDraw.Draw(image).rounded_rectangle((0, 0, width-1, height-1), radius=self.px(8), fill=self.bg, outline=self.line)
        self.surface_image = ImageTk.PhotoImage(image)
        self.surface.create_image(0, 0, anchor='nw', image=self.surface_image)
        content = tk.Frame(self.surface, bg=self.bg)
        self.surface.create_window(self.px(20), self.px(8), window=content, anchor='nw', width=self.px(320), height=self.px(454))
        head = tk.Frame(content, bg=self.bg, height=self.px(42))
        head.pack(fill='x'); head.pack_propagate(False)
        title = self.text(head, 'Google Fotos', 15, bold=True)
        title.pack(side='left')
        self.pin_button = self.button(head, '\ue718', self.toggle_pin, icon=True, hint='Fixar / recolher após 20 segundos')
        self.pin_button.pack(side='right')
        self.button(head, '\ue70e', self.open_details, icon=True, hint='Abrir aplicativo e detalhes').pack(side='right', padx=self.px(4))
        for target in (head, title):
            target.bind('<ButtonPress-1>', self._drag_start)
            target.bind('<B1-Motion>', self._drag_move)
            target.bind('<ButtonRelease-1>', lambda e: self.save_ui_preferences())
        self.text(content, 'SINCRONIZAÇÃO', 9, color=self.muted).pack(anchor='w', pady=(self.px(16), self.px(10)))
        status_row = tk.Frame(content, bg=self.bg); status_row.pack(fill='x')
        self.status_dot = self.text(status_row, '●', 14, color=self.accent)
        self.status_dot.pack(side='left', padx=(0, self.px(8)))
        self.text(status_row, variable=self.widget_status, size=13, bold=True).pack(side='left')
        self.text(content, variable=self.widget_subtitle, size=10, color=self.muted, wrap=320).pack(anchor='w', pady=(self.px(6), self.px(12)))
        strip = tk.Frame(content, bg=self.tile)
        strip.pack(fill='x')
        self.text(strip, variable=self.widget_pending, size=20, bold=True, color=self.accent).pack(side='left', padx=self.px(12), pady=self.px(8))
        self.text(strip, 'arquivos na fila', 10).pack(side='left')
        self.widget_sync = self.button(content, 'Sincronizar agora', self.start_upload, primary=True)
        self.widget_sync.pack(fill='x', pady=(self.px(12), self.px(8)))
        automatic = tk.Frame(content, bg=self.bg); automatic.pack(fill='x')
        self.text(automatic, 'Envio automático', 10).pack(side='left')
        self.auto_button = self.button(automatic, '', self.toggle_automatic, hint='Ativar ou pausar futuras verificações automáticas')
        self.auto_button.pack(side='right')
        self.text(content, variable=self.widget_auto, size=9, color=self.muted).pack(anchor='w', pady=(self.px(4), self.px(14)))
        tk.Frame(content, bg=self.line, height=1).pack(fill='x')
        last = tk.Frame(content, bg=self.bg); last.pack(fill='x', pady=(self.px(12), self.px(12)))
        self.widget_thumb = tk.Label(last, bg=self.tile, fg=self.muted, text='\ue91b', font=('Segoe Fluent Icons', 19), width=3, height=2)
        self.widget_thumb.pack(side='left', padx=(0, self.px(10)))
        info = tk.Frame(last, bg=self.bg); info.pack(side='left', fill='x', expand=True)
        self.text(info, 'Último envio confirmado', 9, color=self.muted).pack(anchor='w')
        self.text(info, variable=self.widget_last, size=10, wrap=238).pack(anchor='w', pady=self.px(2))
        self.text(info, variable=self.widget_last_date, size=9, color=self.muted).pack(anchor='w')
        tk.Frame(content, bg=self.line, height=1).pack(fill='x')
        foot = tk.Frame(content, bg=self.bg); foot.pack(fill='x', pady=(self.px(7), 0))
        self.text(foot, variable=self.widget_check, size=9, color=self.muted).pack(side='left')
        self.button(foot, '\ue713', self.open_settings, icon=True, hint='Configurações').pack(side='right')
        self.button(foot, '\ue8a7', self.hide_to_tray, icon=True, hint='Recolher para a bandeja').pack(side='right')
        self.bind('<Escape>', lambda e: self.hide_to_tray())
        self.bind_all('<Motion>', self._interaction, add='+')
        self.bind_all('<KeyPress>', self._interaction, add='+')
        self._build_details()
        self.update_pin()
        self.after(1000, self.widget_tick)

    def px(self, value):
        return round(value * self.ui_scale)

    def text(self, parent, text='', size=10, bold=False, color=None, variable=None, wrap=None):
        opts = dict(text=text, bg=parent['bg'], fg=color or self.ink, font=('Segoe UI Variable', size, 'bold' if bold else 'normal'), anchor='w', justify='left')
        if variable is not None: opts['textvariable'] = variable
        if wrap: opts['wraplength'] = self.px(wrap)
        return tk.Label(parent, **opts)

    def button(self, parent, title, command, primary=False, icon=False, hint=''):
        fill = self.accent if primary else parent['bg']
        b = tk.Button(parent, text=title, command=command, bg=fill, fg='#171717' if primary else self.ink,
                      activebackground=self.accent if primary else self.tile, activeforeground='#171717' if primary else self.ink,
                      relief='flat', bd=0, highlightthickness=1, highlightbackground=fill, highlightcolor=self.accent,
                      font=('Segoe Fluent Icons' if icon else 'Segoe UI Variable', 12 if icon else 10),
                      padx=self.px(8 if icon else 12), pady=self.px(5 if icon else 7), cursor='hand2', takefocus=True)
        if hint:
            tip = [None]
            def show(event):
                self._interaction(event)
                if tip[0]: return
                w = tip[0] = tk.Toplevel(self); w.overrideredirect(True)
                w.geometry(f'+{b.winfo_rootx()}+{b.winfo_rooty()+b.winfo_height()+4}')
                tk.Label(w, text=hint, bg=self.tile, fg=self.ink, padx=8, pady=4, font=('Segoe UI', 9)).pack()
            def hide(event):
                if tip[0]: tip[0].destroy(); tip[0] = None
            b.bind('<Enter>', show); b.bind('<Leave>', hide); b.bind('<ButtonPress>', hide, add='+')
        return b

    def _build_details(self):
        w = self.details = tk.Toplevel(self)
        w.withdraw(); w.title('Google Photos Uploader · Aplicativo')
        w.geometry(f'{self.px(820)}x{self.px(650)}'); w.minsize(self.px(650), self.px(540))
        w.configure(bg=self.bg); w.protocol('WM_DELETE_WINDOW', w.withdraw)
        shell = tk.Frame(w, bg=self.bg); shell.pack(fill='both', expand=True, padx=self.px(24), pady=self.px(20))
        head = tk.Frame(shell, bg=self.bg); head.pack(fill='x')
        self.text(head, 'Google Photos Uploader', 20, bold=True).pack(side='left')
        self.button(head, 'Configurações', self.open_settings).pack(side='right')
        self.text(shell, 'Origem, atividade e registros de sincronização', 10, color=self.muted).pack(anchor='w', pady=(0, self.px(20)))
        style = ttk.Style(self); style.theme_use('clam')
        style.configure('.', background=self.bg, foreground=self.ink, font=('Segoe UI', 10))
        style.configure('TNotebook', background=self.bg, borderwidth=0)
        style.configure('TNotebook.Tab', background=self.tile, foreground=self.ink, padding=(16,8))
        style.map('TNotebook.Tab', background=[('selected', self.accent)], foreground=[('selected','#171717')])
        style.configure('TProgressbar', background=self.accent, troughcolor=self.tile, borderwidth=0, thickness=4)
        style.configure('TEntry', fieldbackground=self.tile, foreground=self.ink, insertcolor=self.ink)
        style.map('TEntry', fieldbackground=[('readonly',self.tile)])
        style.configure('TButton', background=self.tile, foreground=self.ink, padding=(10,6))
        style.map('TButton', background=[('active',self.line)])
        tabs = ttk.Notebook(shell); tabs.pack(fill='both', expand=True)
        overview, activity, pending = [tk.Frame(tabs,bg=self.bg) for _ in range(3)]
        tabs.add(overview,text='Visão geral'); tabs.add(activity,text='Atividade'); tabs.add(pending,text='Pendências')
        self.text(overview, 'Pasta monitorada', 10, bold=True).pack(anchor='w', pady=(self.px(16),self.px(6)))
        ttk.Entry(overview,textvariable=self.source_var,state='readonly').pack(fill='x')
        self.text(overview, variable=self.auto_var, size=9, color=self.muted,wrap=740).pack(anchor='w',pady=self.px(8))
        row=tk.Frame(overview,bg=self.bg);row.pack(fill='x',pady=self.px(8))
        self.button(row,'Verificar arquivos',self.scan).pack(side='left')
        self.button(row,'Sincronizar agora',self.start_upload,primary=True).pack(side='left',padx=self.px(8))
        self.button(row,'Interromper envio',self.stop_upload).pack(side='left')
        cards=tk.Frame(overview,bg=self.bg);cards.pack(fill='x',pady=self.px(12))
        values=[]
        for title in ('Álbuns no catálogo','Sem pendências','Com pendências','Bloqueados'):
            card=tk.Frame(cards,bg=self.tile);card.pack(side='left',fill='both',expand=True,padx=(0,self.px(8)))
            self.text(card,title,9,color=self.muted).pack(anchor='w',padx=self.px(10),pady=(self.px(8),0))
            value=self.text(card,'0',20,bold=True,color=self.accent);value.pack(anchor='w',padx=self.px(10),pady=(0,self.px(8)));values.append(value)
        self.value_found,self.value_done,self.value_pending,self.value_errors=values
        current=tk.Frame(overview,bg=self.bg);current.pack(fill='both',expand=True)
        left=tk.Frame(current,bg=self.bg);left.pack(side='left',fill='both',expand=True,padx=(0,self.px(16)))
        self.text(left,'Operação atual',11,bold=True).pack(anchor='w')
        self.text(left,variable=self.banner_var,size=10,wrap=430).pack(anchor='w',pady=self.px(8))
        self.text(left,variable=self.current_album_var,size=10,color=self.muted,wrap=430).pack(anchor='w')
        ttk.Progressbar(left,maximum=100,variable=self.progress_var).pack(fill='x',pady=self.px(8))
        self.text(left,variable=self.current_file_var,size=9,color=self.muted,wrap=430).pack(anchor='w')
        ttk.Progressbar(left,maximum=100,variable=self.file_progress_var).pack(fill='x',pady=self.px(8))
        self.preview_frame=tk.Frame(current,bg=self.tile,width=self.px(240),height=self.px(180));self.preview_frame.pack(side='right',anchor='n');self.preview_frame.pack_propagate(False)
        self.preview_title=self.text(self.preview_frame,'Último envio confirmado',9,color=self.muted);self.preview_title.pack(anchor='w',padx=self.px(8),pady=self.px(8))
        self.preview_label=self.text(self.preview_frame,'Nenhuma prévia',10,wrap=220);self.preview_label.pack(fill='both',expand=True,padx=self.px(8))
        self.text(overview,'O histórico anterior a 20/10/2026 foi reconhecido por sua declaração. Sem pendências não significa nova conferência online do acervo.',9,color=self.muted,wrap=740).pack(anchor='w',pady=self.px(12))
        self.text(activity,'Saída da sessão atual',11,bold=True).pack(anchor='w',pady=self.px(16))
        self.log_text=tk.Text(activity,bg=self.tile,fg=self.ink,relief='flat',font=('Consolas',10),wrap='word',height=12)
        self.log_text.pack(fill='both',expand=True)
        self.button(activity,'Abrir logs e recibos locais',lambda:os.startfile(str(Path(__file__).resolve().parent/'logs'))).pack(anchor='w',pady=self.px(8))
        self.text(pending,'Arquivos que exigem atenção',11,bold=True).pack(anchor='w',pady=self.px(16))
        self.pending_text=tk.Text(pending,bg=self.tile,fg=self.ink,relief='flat',font=('Segoe UI',10),wrap='word',height=12)
        self.pending_text.pack(fill='both',expand=True)
        self.button(pending,'Abrir auditoria',lambda:os.startfile(str(Path(__file__).resolve().parent/'audit'))).pack(anchor='w',pady=self.px(8))
        self.text(shell,'Arquivos originais e álbuns existentes são preservados.',9,color=self.muted).pack(anchor='w',pady=(self.px(12),0))

    def open_details(self):
        self._interaction()
        width,height=self.px(820),self.px(650)
        left=self.winfo_x()-width-self.px(12)
        right=self.winfo_x()+self.winfo_width()+self.px(12)
        x=left if left>=0 else right
        x=max(0,min(x,self.winfo_screenwidth()-width))
        y=max(0,min(self.winfo_y(),self.winfo_screenheight()-height-self.px(48)))
        self.details.geometry(f'{width}x{height}+{x}+{y}')
        self.details.deiconify();self.details.lift();self.details.focus_force()
        self.native_title(self.details)
        self.refresh_view()

    def native_title(self,window):
        try:
            window.update_idletasks()
            api=ctypes.windll.user32
            api.GetParent.restype=ctypes.c_void_p
            handle=api.GetParent(window.winfo_id())
            for attribute,value in ((20,1),(33,2)):
                setting=ctypes.c_int(value)
                ctypes.windll.dwmapi.DwmSetWindowAttribute(ctypes.c_void_p(handle),attribute,ctypes.byref(setting),4)
        except (AttributeError,OSError):pass

    def _interaction(self, event=None):
        self._last_interaction=time.monotonic()

    def _drag_start(self,event):
        self._drag_offset=(event.x_root-self.winfo_x(),event.y_root-self.winfo_y())
        self._interaction()

    def _drag_move(self,event):
        dx,dy=self._drag_offset
        self.geometry(f'+{max(0,event.x_root-dx)}+{max(0,event.y_root-dy)}')

    def save_ui_preferences(self):
        self.ui_prefs.update(pinned=self.pinned,x=self.winfo_x(),y=self.winfo_y())
        self.ui_dir.mkdir(parents=True,exist_ok=True)
        temporary=self.ui_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.ui_prefs,indent=2),encoding='utf-8');temporary.replace(self.ui_path)

    def update_pin(self):
        self.pin_button.configure(bg=self.accent if self.pinned else self.bg,fg='#171717' if self.pinned else self.ink)
        self.attributes('-topmost',self.pinned)

    def toggle_pin(self):
        self.pinned=not self.pinned;self.update_pin();self.save_ui_preferences();self._interaction()

    def toggle_automatic(self):
        # Pausing affects future runs. It never terminates an upload already running.
        from app_config import load_settings,save_settings,account_configured
        root=Path(__file__).resolve().parent
        cfg=load_settings(root/'config.json')
        enabled=not self.auto_monitor_enabled
        if enabled and not account_configured(cfg,root):
            self.open_settings();return
        cfg['auto_monitor_enabled']=enabled;save_settings(root/'config.json',cfg)
        self.cfg=cfg;self.auto_monitor_enabled=enabled
        if enabled:self.next_auto_run_at=time.time()+self.auto_monitor_interval_ms/1000
        self.refresh_view();self._interaction()

    def widget_tick(self):
        root=Path(__file__).resolve().parent
        try: status=json.loads((root/'data'/'current_status.json').read_text(encoding='utf-8'))
        except (OSError,ValueError): status={}
        running=self.command_starting or bool(self.process and self.process.poll() is None)
        pending=int(status.get('pending_files') or 0)
        error=status.get('last_error') or ''
        phase=status.get('phase','idle')
        self.widget_pending.set(str(pending))
        self.widget_status.set('Atenção necessária' if error else 'Verificando arquivos…' if phase=='scan' else 'Sincronizando…' if running or phase not in ('idle','complete','completed') else 'Novos arquivos na fila' if pending else 'Nenhum envio pendente')
        self.widget_subtitle.set('Abra o aplicativo para ver o diagnóstico.' if error else 'Enviando apenas arquivos novos ou modificados.' if running else 'Sua pasta Fotos está sendo monitorada.' if self.auto_monitor_enabled else 'Verificações automáticas pausadas.')
        self.status_dot.configure(fg='#ffbcab' if error else self.accent)
        self.widget_sync.configure(state='disabled' if running else 'normal')
        self.auto_button.configure(text='Ligado' if self.auto_monitor_enabled else 'Pausado',fg=self.accent if self.auto_monitor_enabled else self.muted)
        self.widget_auto.set(f'A cada {self.auto_monitor_interval_ms//60000} min · aguarda arquivos estabilizarem' if self.auto_monitor_enabled else 'Use Sincronizar agora para enviar manualmente')
        name=status.get('last_uploaded_file_name') or ''
        self.widget_last.set((name[:30]+'…') if len(name)>31 else (name or 'Nenhum envio registrado'))
        stamp=status.get('last_uploaded_at','')
        try: stamp=time.strftime('%d/%m/%Y às %H:%M',time.strptime(stamp[:19],'%Y-%m-%dT%H:%M:%S'))
        except ValueError: pass
        self.widget_last_date.set(stamp)
        checked=status.get('updated_at','')
        self.widget_check.set('Verificado às '+checked[11:16] if len(checked)>15 else 'Aguardando verificação')
        if not self.pinned and self.state()!='withdrawn' and time.monotonic()-self._last_interaction>20:
            if not (self.details and self.details.state()!='withdrawn') and not (self.settings_dialog and self.settings_dialog.winfo_exists()):
                self.hide_to_tray()
        self.after(1000,self.widget_tick)

    def refresh_pending_details(self,rows):
        self.pending_text.delete('1.0','end')
        if not rows:self.pending_text.insert('end','Nenhuma pendência de envio.\n')
        for row in rows[:200]:
            name=row.get('path') or row.get('file_path') or row.get('relative_path') or str(row.get('album',''))
            error=row.get('last_error') or 'Aguardando envio'
            if int(row.get('size') or 0)==0:error='Original local vazio · envio bloqueado; a declaração da cópia online antiga foi preservada.'
            self.pending_text.insert('end',f'{name}\n{error}\n\n')
        if len(rows)>200:self.pending_text.insert('end','Lista limitada a 200 itens. Consulte a auditoria para o inventário completo.')

    def theme_settings(self,dialog):
        dialog.configure(bg=self.bg)
        anchor=self.details if self.details.state()!='withdrawn' else self
        x=max(0,anchor.winfo_x()-self.px(620)-self.px(12)) if anchor is self else anchor.winfo_x()+self.px(40)
        y=max(0,min(anchor.winfo_y()+self.px(20),self.winfo_screenheight()-self.px(700)))
        dialog.geometry(f'+{x}+{y}')
        self.native_title(dialog)
        def walk(w):
            if isinstance(w,tk.Canvas):w.configure(bg=self.bg)
            for child in w.winfo_children():walk(child)
        walk(dialog)

