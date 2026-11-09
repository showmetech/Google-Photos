"""Native UI bridge. Reuses the existing scheduler, validation and worker guards."""
import json, os, runpy, sys, time, traceback, subprocess
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root))
os.chdir(root)
from app_paths import bootstrap
state_root=bootstrap()
from app_config import source_folders,save_settings,account_configured,prepare_account
from reliable_history import atomic_json,io_path
log=(state_root/'logs'/'native-service.log').open('a',encoding='utf-8',buffering=1)
sys.stdout=sys.stderr=log
module=runpy.run_path(str(root/'google_photos_upload_manager.pyw'),run_name='photos_backend')
if not module['acquire_single_instance']():raise SystemExit(0)
tk=module['tk']
Base=module['ManagerApp']
class Service(Base):
    def _build_ui(self):
        self.withdraw()
        self.retiring=False
        self.active_request=None
        self.last_exit_code=None
        self.operation=''
        self.baseline_recorded=self.read_baseline()
        self.preview_key=''
        self.logged_lines=0
        self.log_text=tk.Text(self)
        self.inbox=state_root/'data'/'ui-commands';self.inbox.mkdir(parents=True,exist_ok=True)
        self.receipts=state_root/'data'/'ui-receipts';self.receipts.mkdir(parents=True,exist_ok=True)
        self.after(250,self.bridge_tick)
    def create_tray_icon(self):pass
    def refresh_view(self):pass
    def poll_status(self):pass
    def poll_activation_signal(self):pass
    def show_window(self):pass
    def open_settings(self):pass
    def hide_to_tray(self):self.withdraw()
    def save_ui_preferences(self):pass
    def update_log(self):
        for line in self.output_lines[self.logged_lines:]:print(line)
        self.logged_lines=len(self.output_lines)
    def native_preview(self):
        from PIL import Image,ImageOps
        state=module['load_json'](state_root/'data'/'current_status.json',{})
        path=state.get('last_uploaded_file','')
        key=path+'|'+str(state.get('last_uploaded_fingerprint') or state.get('last_uploaded_at',''))
        if not path or key==self.preview_key:return
        original=Path(path)
        expected=state.get('last_uploaded_fingerprint')
        if expected:
            import hashlib
            try:
                stat=io_path(original).stat();value=str(original)+str(stat.st_size)+str(stat.st_mtime_ns)
                if hashlib.sha1(value.encode('utf-8','surrogatepass')).hexdigest()!=expected:
                    atomic_json(state_root/'data'/'native-preview-source.json',{'source':path,'ready':False,'at':time.time()});self.preview_key=key;return
            except OSError:
                atomic_json(state_root/'data'/'native-preview-source.json',{'source':path,'ready':False,'at':time.time()});self.preview_key=key;return
        temporary=state_root/'data'/'native-last-preview.tmp.jpg'
        ready=False
        if original.suffix.lower() in module['IMAGE_EXTENSIONS']:
            try:
                with Image.open(io_path(original)) as opened:
                    image=ImageOps.exif_transpose(opened);image.thumbnail((1280,960))
                    image.convert('RGB').save(temporary,'JPEG',quality=92)
                    temporary.replace(state_root/'data'/'native-last-preview.jpg')
                    ready=True
            except (OSError,ValueError):traceback.print_exc()
        elif original.suffix.lower() in module['VIDEO_EXTENSIONS'] and module['FFMPEG']:
            try:
                subprocess.run([str(module['FFMPEG']),'-hide_banner','-loglevel','error','-y','-ss','0',
                    '-i',str(original),'-frames:v','1','-vf',"scale='min(1280,iw)':-2",str(temporary)],
                    timeout=25,check=True,capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                temporary.replace(state_root/'data'/'native-last-preview.jpg')
                ready=True
            except (OSError,subprocess.SubprocessError):traceback.print_exc()
        receipt={'source':path,'ready':ready,'at':time.time()}
        # Associate the thumbnail with the confirmed source, never a pending file.
        atomic_json(state_root/'data'/'native-preview-source.json',receipt)
        self.preview_key=key
    def run_command(self,args):
        self.last_exit_code=None
        self.operation=args[0]
        started=super().run_command(args)
        if not started:self.last_exit_code=2
        return started
    def is_busy(self):
        return self.command_starting or bool(self.process and self.process.poll() is None) or bool(self.auth_process and self.auth_process.poll() is None) or module['existing_worker_running']()
    def read_baseline(self):
        import sqlite3
        database=Path(self.cfg.get('database','data/gphotos_uploader.sqlite'))
        if not database.is_absolute():database=state_root/database
        if not database.exists():return False
        try:
            with sqlite3.connect(f'file:{database.as_posix()}?mode=ro',uri=True) as db:
                return bool(db.execute("select 1 from events where event_type like '%baseline%' limit 1").fetchone())
        except sqlite3.Error:return False
    def command_finished(self,code):
        super().command_finished(code)
        self.last_exit_code=code;self.baseline_recorded=self.read_baseline()
        if self.active_request:
            target=self.receipts/(self.active_request+'.json')
            receipt=module['load_json'](target,{})
            receipt.update(completed=True,exit_code=code,completed_at=time.time())
            atomic_json(target,receipt)
            self.active_request=None
        if self.operation=='upload' and self.auto_monitor_enabled and account_configured(self.cfg,root):
            self.after(2000,self.reconcile_when_idle)
    def reconcile_when_idle(self):
        if self.retiring or not self.auto_monitor_enabled or not account_configured(self.cfg,root):return
        previous=module['load_json'](state_root/'data'/'online-reconciliation-summary.json',{})
        interval=86400 if previous.get('albums_complete') and previous.get('library_complete') else 3600
        if time.time()-previous.get('checked_at',0)<interval:return
        if self.is_busy():return
        self.run_command(['reconcile'])
    def bridge_tick(self):
        try:
            self.native_preview()
            busy=self.is_busy()
            for path in sorted(self.inbox.glob('*.json')):
                try:
                    if path.stat().st_size>65536:raise ValueError('Invalid command size')
                    request=json.loads(path.read_text(encoding='utf-8-sig'))
                    command=request.get('command')
                    if command=='shutdown':
                        self.retiring=True;self.auto_monitor_enabled=False
                        if self.auth_process and self.auth_process.poll() is None:self.cancel_connection()
                    elif command=='automatic':self.apply_settings(self.cfg['photos_root'],bool(request['enabled']))
                    elif command=='configure':
                        if busy:raise ValueError('Wait for the current operation before changing sources.')
                        cfg=dict(self.cfg)
                        cfg['photos_roots']=request['folders'];cfg['photos_root']=request['folders'][0] if request['folders'] else ''
                        source_folders(cfg)
                        cfg['auto_monitor_enabled']=False;cfg['setup_completed']=True
                        save_settings(state_root/'config.json',cfg)
                        self.cfg=cfg;self.auto_monitor_enabled=False;self.source_var.set(cfg['photos_root'])
                    elif command=='import-client':
                        if busy:raise ValueError('Wait for the current operation.')
                        if account_configured(self.cfg,root):raise ValueError('The existing OAuth client is protected. Use reconnect instead.')
                        client=json.loads(Path(request['file']).read_text(encoding='utf-8-sig')).get('installed',{})
                        if not str(client.get('client_id','')).endswith('.apps.googleusercontent.com') or not client.get('client_secret'):
                            raise ValueError('Choose an OAuth desktop client JSON exported by Google Cloud.')
                        prepare_account(self.cfg,root,client['client_id'],client['client_secret'])
                    elif command=='connect':
                        if busy:raise ValueError('Wait for the current operation.')
                        if account_configured(self.cfg,root):self.connect_account()
                        else:
                            import configparser
                            from app_config import profile_path
                            profile=configparser.ConfigParser(interpolation=None);profile.read(profile_path(self.cfg,root),encoding="utf-8-sig")
                            remote=profile[self.cfg.get("rclone_remote","gphotos")]
                            self.connect_account(remote.get("client_id",""),remote.get("client_secret",""))
                        busy=self.auth_process is not None and self.auth_process.poll() is None
                        if not busy:raise ValueError(self.banner_var.get())
                    elif command in ('scan','upload','doctor','mark-baseline','reconcile','repair-online'):
                        if busy:raise ValueError('Another operation is already running. Wait for completion.')
                        if command=='mark-baseline' and request.get('confirmed_existing') is not True:
                            raise ValueError('An explicit declaration is required before recording an existing library.')
                        if command in ('upload','reconcile','repair-online') and not account_configured(self.cfg,root):raise ValueError('Connect your Google Photos account first.')
                        self.active_request=path.stem;self.operation=command
                        arguments=[command]+(['--live'] if command=='upload' else [])
                        if command=='reconcile' and request.get('inventory'):
                            arguments+=['--inventory',str(Path(request['inventory']).resolve())]
                        if not self.run_command(arguments):raise ValueError(self.banner_var.get())
                        busy=True
                    else:raise ValueError('Unknown command')
                    receipt={'id':path.stem,'ok':True,'command':command,'at':time.time()}
                except Exception as exc:
                    if self.active_request==path.stem:self.active_request=None
                    receipt={'id':path.stem,'ok':False,'error':str(exc),'at':time.time()}
                target=self.receipts/path.name
                atomic_json(target,receipt)
                path.replace(self.receipts/(path.stem+'.request.json'))
            state={'pid':os.getpid(),'heartbeat':time.time(),'busy':busy,'banner':self.banner_var.get(),'automatic':self.auto_monitor_enabled,'account_configured':account_configured(self.cfg,root),'folders':self.cfg.get('photos_roots') or [self.cfg.get('photos_root','')],'baseline_recorded':self.baseline_recorded,'operation':self.operation,'last_exit_code':self.last_exit_code,'authenticating':bool(self.auth_process and self.auth_process.poll() is None)}
            target=state_root/'data'/'ui-service-status.json';tmp=target.with_suffix('.tmp')
            tmp.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8');tmp.replace(target)
            if self.retiring and not busy:self.quit_app();return
        except Exception:traceback.print_exc()
        self.after(1000,self.bridge_tick)
try:
    app=Service(minimized=True)
    app.mainloop()
except Exception:traceback.print_exc();raise
