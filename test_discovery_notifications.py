import json,os,runpy,sqlite3,sys,tempfile,unittest
from pathlib import Path

backend=Path(__file__).parent/'backend'
sys.path.insert(0,str(backend))


class DiscoveryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
  self.root=Path(self.temp.name).resolve();self.state=self.root/'state'
  self.previous=os.environ.get('GOOGLE_PHOTOS_HOME');os.environ['GOOGLE_PHOTOS_HOME']=str(self.state)
  self.addCleanup(self.restore)
  from app_paths import bootstrap
  bootstrap();self.cfg=json.loads((self.state/'config.json').read_text(encoding='utf-8'))
  self.photos=self.root/'Pictures';self.photos.mkdir()
  self.cfg.update(photos_root=str(self.photos),min_file_age_seconds=0)
  for name in ('database','logs_dir','audit_dir'):self.cfg[name]=str(self.state/self.cfg[name])
  self.app=runpy.run_path(str(backend/'gphotos_uploader.py'),run_name='discovery_test')
  self.target=Path(self.cfg['database']).parent/'new-media-notification.json'
 def restore(self):
  if self.previous is None:os.environ.pop('GOOGLE_PHOTOS_HOME',None)
  else:os.environ['GOOGLE_PHOTOS_HOME']=self.previous
 def baseline(self):
  db=self.app['connect_db'](self.cfg)
  db.execute("insert into events(created_at,event_type,note) values('now','baseline','fixture')");db.commit();db.close()
 def file(self,album='New folder',name='photo.jpg',data=b'photo'):
  path=self.photos/album/name;path.parent.mkdir(exist_ok=True);path.write_bytes(data);os.utime(path,(1600000000,1600000000));return path
 def scan(self):return self.app['scan'](self.cfg)
 def event(self):return json.loads(self.target.read_text(encoding='utf-8'))
 def test_historical_initial_inventory_is_not_announced(self):
  self.file();self.scan();self.assertFalse(self.target.exists())
 def test_new_folder_is_announced_once(self):
  self.baseline();self.file();self.scan();event=self.event()
  self.assertEqual(event['media_count'],1);self.assertEqual(event['albums'][0]['name'],'New folder')
  self.scan();self.assertEqual(self.event()['id'],event['id'])
 def test_added_media_in_existing_folder_gets_new_event(self):
  self.baseline();self.file();self.scan();first=self.event()['id']
  self.file(name='video.mp4');self.scan();self.assertNotEqual(self.event()['id'],first)
  self.assertEqual(self.event()['media_count'],1)
 def test_empty_files_and_empty_folders_do_not_announce(self):
  self.baseline();self.file(data=b'');(self.photos/'Empty').mkdir();self.scan();self.assertFalse(self.target.exists())
 def test_config_blocked_album_does_not_announce(self):
  self.baseline();self.cfg['blocked_albums']=['New folder'];self.file();self.scan();self.assertFalse(self.target.exists())
 def test_modified_media_gets_new_event(self):
  self.baseline();p=self.file();self.scan();first=self.event()['id'];p.write_bytes(b'changed bytes');self.scan()
  self.assertNotEqual(self.event()['id'],first)
 def test_failed_export_is_recovered_from_database(self):
  self.baseline();self.file();self.scan();first=self.event()['id'];self.target.unlink();self.scan()
  self.assertEqual(self.event()['id'],first)
 def test_batch_counts_folders_and_media(self):
  self.baseline();self.file();self.file(name='b.mp4');self.file(album='Other');self.scan()
  self.assertEqual((self.event()['folder_count'],self.event()['media_count']),(2,3))

if __name__=='__main__':unittest.main()
