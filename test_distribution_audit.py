import importlib.util,tempfile,unittest,zipfile
from unittest.mock import patch
from pathlib import Path
spec=importlib.util.spec_from_file_location('distribution_audit',Path(__file__).parent/'scripts/distribution_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)

class DistributionTests(unittest.TestCase):
 def test_generic_source_is_allowed(self):
  self.assertFalse(audit.inspect_file('app_config.py',b"token = profile.get('access_token')"))
 def test_state_file_blocked(self):
  self.assertTrue(audit.inspect_file('data/config.json',b'{}'))
 def test_private_database_blocked(self):
  self.assertTrue(audit.inspect_file('history.sqlite',b'database'))
 def test_unexpected_photo_is_blocked(self):
  self.assertTrue(audit.inspect_file('portrait.jpg',b'photo'))
 def test_personalized_defaults_are_blocked(self):
  self.assertTrue(audit.inspect_file('config.example.json',b'{"photos_root":"personal path"}'))
 def test_private_path_in_binary_blocked(self):
  with patch.dict('os.environ',{'USERPROFILE':r'C:\Users\FixturePerson'}):
   self.assertTrue(audit.inspect_file('native.dll','C:\\Users\\FixturePerson\\project\\app.pdb'.encode('utf-16-le')))
 def test_token_blocked(self):
  self.assertTrue(audit.inspect_file('main.py',b'ya29.'+b'X'*40))
 def test_secret_value_blocked_without_printing_it(self):
  secret='fixture-sensitive-value';result=audit.inspect_file('data.bin',secret.encode(),[secret])
  self.assertTrue(result);self.assertNotIn(secret,str(result))
 def test_cache_and_debug_are_blocked(self):
  self.assertTrue(audit.inspect_file('runtime/__pycache__/module.pyc',b'code'))
  self.assertTrue(audit.inspect_file('native/widget.pdb',b'debug'))
 def test_msix_contents_are_audited(self):
  with tempfile.TemporaryDirectory() as folder:
   archive=Path(folder)/'test.msix'
   with zipfile.ZipFile(archive,'w') as stream:stream.writestr('rclone.conf','fixture')
   self.assertFalse(audit.audit(archive)['passed'])
 def test_clean_tree_passes(self):
  with tempfile.TemporaryDirectory() as folder:
   (Path(folder)/'config.example.json').write_text('{}')
   self.assertTrue(audit.audit(folder)['passed'])

if __name__=='__main__':unittest.main()

