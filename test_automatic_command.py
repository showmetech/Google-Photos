import ast
import unittest
from pathlib import Path

manager = Path(__file__).parent / 'backend/google_photos_upload_manager.pyw'
if not manager.exists():
    manager = Path(__file__).parent / 'google_photos_upload_manager.pyw'
tree = ast.parse(manager.read_text(encoding='utf-8'))
function = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'automatic_command')
namespace = {}
exec(compile(ast.Module(body=[function], type_ignores=[]), '<scheduler>', 'exec'), namespace)
choose = namespace['automatic_command']


class SchedulerTests(unittest.TestCase):
    def test_only_blocked_pending_keeps_scanning(self):
        self.assertEqual(choose([{'last_error': 'historical block'}], 0), ['scan'])

    def test_new_file_discovered_after_scan_is_uploaded(self):
        self.assertEqual(choose([{}, {}], 1), ['upload', '--live'])

    def test_empty_previous_inventory_does_not_stop_discovery(self):
        self.assertEqual(choose([], 0), ['upload', '--live'])

    def test_retryable_upload_error_is_not_suppressed(self):
        self.assertEqual(choose([{'last_error': 'network'}], 1), ['upload', '--live'])


if __name__ == '__main__':
    unittest.main()
