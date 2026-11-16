import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent / "backend"))
import tempfile
import unittest
from pathlib import Path
from compare_originals import compare


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.local = Path(self.temp.name) / 'a.jpg'
        self.local.write_bytes(b'original')
        self.remote = Path(self.temp.name) / 'download.jpg'
        self.remote.write_bytes(b'original')
        self.rows = [{'path': str(self.local), 'album': 'Album'}]
        self.item = {'filename': 'a.jpg', 'id': 'id-1', 'originalBackup': True}
        self.album = {'title': 'Album', 'complete': True, 'expected_count': 1, 'items': [self.item]}
        self.inventory = {'schema': 1, 'account': 'account', 'albums': [self.album]}

    def result(self, originals=None):
        result = compare(self.rows, self.inventory, 'account', originals)['results'][0]
        self.assertFalse(result['upload_confirmed'])
        self.assertFalse(result['repair'])
        self.assertFalse(result['delete'])
        return result

    def test_presence_does_not_claim_binary_equality(self):
        result = self.result()
        self.assertTrue(result['presence_confirmed'])
        self.assertFalse(result['binary_integrity_verified'])

    def test_originals_match(self):
        self.assertTrue(self.result({'id-1': str(self.remote)})['binary_integrity_verified'])

    def test_same_size_different_bytes(self):
        self.remote.write_bytes(b'different'[:8])
        result = self.result({'id-1': str(self.remote)})
        self.assertEqual(result['state'], 'different_bytes_review_required')
        self.assertFalse(result['binary_integrity_verified'])

    def test_account_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            compare(self.rows, self.inventory, 'other-account')

    def test_incomplete_album_does_not_confirm_presence(self):
        self.album['expected_count'] = 2
        self.assertFalse(self.result()['presence_confirmed'])

    def test_duplicate_ids_rejected(self):
        self.album['items'].append(dict(self.item, filename='b.jpg'))
        self.album['expected_count'] = 2
        self.assertEqual(self.result()['state'], 'ambiguous')

    def test_duplicate_names_rejected(self):
        self.album['items'].append(dict(self.item, id='id-2'))
        self.album['expected_count'] = 2
        self.assertEqual(self.result()['state'], 'ambiguous')

    def test_missing_local_keeps_online_presence_but_no_deletion(self):
        self.local.unlink()
        result = self.result()
        self.assertTrue(result['presence_confirmed'])
        self.assertEqual(result['state'], 'local_or_original_unavailable')

    def test_zero_bytes_not_verified(self):
        self.local.write_bytes(b'')
        self.assertFalse(self.result({'id-1': str(self.remote)})['binary_integrity_verified'])

    def test_local_cannot_be_passed_as_remote_original(self):
        self.assertEqual(self.result({'id-1': str(self.local)})['state'], 'local_or_original_unavailable')


if __name__ == '__main__':
    unittest.main()
