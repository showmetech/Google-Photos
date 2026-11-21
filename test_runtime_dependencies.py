"""Regression: the isolated dependency copy must load native HEIF code."""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from runtime_dependencies import copy_pinned_distributions


class RuntimeTests(unittest.TestCase):
    def test_native_codec_and_missing_extension_are_detected(self):
        seed = Path(os.environ.get('RUNTIME_TEST_SEED', sys.prefix))
        interpreter = seed / 'python.exe'
        if not interpreter.is_file():
            self.skipTest('Windows runtime integration test')
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / 'site-packages'
            copy_pinned_distributions(seed, target, ROOT / 'requirements.txt')
            code = ('import sys,runpy; '
                    'sys.path=[p for p in sys.path if "site-packages" not in p.lower()]; '
                    'sys.path.insert(0,sys.argv[1]); '
                    'runpy.run_path(sys.argv[2],run_name="__main__")')
            command = [str(interpreter), '-B', '-S', '-c', code, str(target),
                       str(ROOT / 'scripts/verify_runtime.py')]
            healthy = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(healthy.returncode, 0, healthy.stderr)
            extension = next(target.glob('_pillow_heif*.pyd'))
            extension.unlink()
            broken = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(broken.returncode, 0)
            self.assertIn('_pillow_heif', broken.stderr)


if __name__ == '__main__':
    unittest.main()
