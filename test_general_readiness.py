import ast,contextlib,io,json,os,runpy,sqlite3,subprocess,sys,tempfile,types,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'backend'))
import app_config

class ReadinessTests(unittest.TestCase):
 def test_interval_validation(self):
  self.assertEqual(app_config.monitor_interval_minutes({}),5)
  self.assertEqual(app_config.monitor_interval_minutes({'auto_monitor_interval_minutes':'bad'}),5)
  self.assertEqual(app_config.monitor_interval_minutes({'auto_monitor_interval_minutes':0}),1)
  self.assertEqual(app_config.monitor_interval_minutes({'auto_monitor_interval_minutes':2000}),1440)
 def test_toggling_automatic_preserves_interval(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);config=root/'config.json'
   config.write_text(json.dumps({'photos_root':str(root),'auto_monitor_interval_minutes':5}))
   tree=ast.parse((Path(__file__).parent/'backend/google_photos_upload_manager.pyw').read_text(encoding='utf-8'))
   cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='ManagerApp')
   method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='apply_settings')
   env={'CONFIG_PATH':config,'load_settings':app_config.load_settings,'save_settings':app_config.save_settings,
        'source_folder':app_config.source_folder,'monitor_interval_minutes':app_config.monitor_interval_minutes,
        'existing_worker_running':lambda:False}
   exec(compile(ast.Module(body=[method],type_ignores=[]),'<settings>','exec'),env)
   variable=types.SimpleNamespace(set=lambda value:None)
   app=types.SimpleNamespace(command_starting=False,process=None,source_var=variable,banner_var=variable,refresh_view=lambda:None)
   env['apply_settings'](app,str(root),False)
   self.assertEqual(app.auto_monitor_interval_ms,300000)
   self.assertEqual(json.loads(config.read_text())['auto_monitor_interval_minutes'],5)
 def test_root_files_are_uploaded_when_enabled(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);state=root/'state';previous=os.environ.get('GOOGLE_PHOTOS_HOME');os.environ['GOOGLE_PHOTOS_HOME']=str(state)
   try:
    from app_paths import bootstrap
    bootstrap();cfg=json.loads((state/'config.json').read_text(encoding='utf-8'))
    pictures=root/'Pictures';pictures.mkdir();file=pictures/'photo.jpg';file.write_bytes(b'fixture');os.utime(file,(1600000000,1600000000))
    cfg.update(photos_root=str(pictures),min_file_age_seconds=0,dry_run=False,upload_root_files=True)
    for name in ('database','logs_dir','audit_dir'):cfg[name]=str(state/cfg[name])
    app=runpy.run_path(str(Path(__file__).parent/'backend/gphotos_uploader.py'),run_name='root_file_test');env=app['upload'].__globals__
    env['remote_album_names']=lambda cfg:set()
    env['quiet_run']=lambda *args,**kw:subprocess.CompletedProcess(args,0,'gphotos:\n','')
    calls=[]
    def transfer(cmd,log_file=None,cfg=None,file_lookup=None,on_confirmed=None):
     self.assertIn('gphotos:album/Pictures',cmd);self.assertEqual(list(file_lookup),['photo.jpg'])
     self.assertTrue(on_confirmed(file_lookup['photo.jpg']));calls.append(cmd)
     return subprocess.CompletedProcess(cmd,0,'2026/11/17 12:00:00 INFO  : photo.jpg: Copied (new)\n','')
    env['run']=transfer
    with contextlib.redirect_stdout(io.StringIO()):code=app['upload'](cfg,None)
    self.assertEqual(code,0);self.assertEqual(len(calls),1)
    with contextlib.closing(sqlite3.connect(cfg['database'])) as db:self.assertEqual(db.execute('select status from media').fetchone()[0],'uploaded')
   finally:
    if previous is None:os.environ.pop('GOOGLE_PHOTOS_HOME',None)
    else:os.environ['GOOGLE_PHOTOS_HOME']=previous

if __name__=='__main__':unittest.main()

