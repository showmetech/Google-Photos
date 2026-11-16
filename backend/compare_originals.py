"""Read-only evidence comparison. Never uploads, deletes or changes sync state."""
import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from reliable_history import io_path, atomic_json


def stable_hash(path):
    path = io_path(path)
    before = path.stat()
    if before.st_size == 0:
        raise ValueError('Empty original')
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    after = path.stat()
    signature = lambda s: (s.st_size, s.st_mtime_ns, s.st_ino, s.st_dev)
    if signature(before) != signature(after):
        raise ValueError('File changed during comparison')
    return {'sha256': digest.hexdigest(), 'size': after.st_size,
            'mtime_ns': after.st_mtime_ns}


def compare(rows, inventory, account, originals=None):
    """Presence and binary equality are independent evidence, never upload receipts.

    rows are explicit local paths and album titles. originals is an optional map
    from observed online ID to an individually downloaded file, supplied by the
    operator after an authenticated download. No filename-based download lookup.
    """
    if inventory.get('schema') != 1 or inventory.get('account') != account:
        raise ValueError('Inventory schema/account mismatch')
    albums = inventory.get('albums', [])
    titles = Counter(a['title'] for a in albums)
    ids = Counter(i.get('id') for a in albums for i in a['items'] if i.get('id'))
    output = []
    for row in rows:
        result = dict(path=row['path'], album=row['album'],
                      presence_confirmed=False, binary_integrity_verified=False,
                      upload_confirmed=False, repair=False, delete=False)
        found = [a for a in albums if a['title'] == row['album']]
        if titles[row['album']] != 1:
            result['state'] = 'album_unverified'
            output.append(result)
            continue
        album = found[0]
        complete = album.get('complete') is True and album.get('expected_count') == len(album['items'])
        matches = [i for i in album['items'] if i['filename'] == Path(row['path']).name]
        if not matches:
            result['state'] = 'not_in_snapshot' if complete else 'inventory_incomplete'
        elif len(matches) != 1 or not matches[0].get('id') or ids[matches[0]['id']] != 1:
            result['state'] = 'ambiguous'
        else:
            item = matches[0]
            result['online_id'] = item['id']
            result['presence_confirmed'] = complete and item.get('originalBackup') is True
            result['state'] = 'web_presence_confirmed' if result['presence_confirmed'] else 'name_match_only'
            try:
                local = stable_hash(row['path'])
                result['local'] = local
                if originals and item['id'] in originals:
                    remote_file = originals[item['id']]
                    if io_path(remote_file).resolve() == io_path(row['path']).resolve():
                        raise ValueError('Downloaded original cannot be the local source')
                    downloaded = stable_hash(remote_file)
                    # Recheck local source after both hashes to reject mutations.
                    stat = io_path(row['path']).stat()
                    if (stat.st_size, stat.st_mtime_ns) != (local['size'], local['mtime_ns']):
                        raise ValueError('Local source changed during comparison')
                    result['downloaded_original'] = downloaded
                    result['binary_integrity_verified'] = local['sha256'] == downloaded['sha256']
                    result['state'] = 'identical_original' if result['binary_integrity_verified'] else 'different_bytes_review_required'
            except (OSError, ValueError) as exc:
                result['state'] = 'local_or_original_unavailable'
                result['error'] = str(exc)
        output.append(result)
    return {'schema': 1, 'account': account, 'snapshot_at': inventory.get('captured_at'),
            'advisory_only': True, 'results': output,
            'counts': dict(Counter(r['state'] for r in output))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', required=True)
    parser.add_argument('--files', required=True, help='JSON list of path/album objects')
    parser.add_argument('--account', required=True)
    parser.add_argument('--originals', help='Optional JSON map: online ID -> downloaded original path')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    inputs = [args.inventory, args.files] + ([args.originals] if args.originals else [])
    if any(Path(args.output).resolve() == Path(p).resolve() for p in inputs):
        parser.error('Output must not overwrite evidence inputs')
    read = lambda p: json.loads(Path(p).read_text(encoding='utf-8-sig'))
    atomic_json(args.output, compare(read(args.files), read(args.inventory), args.account,
                                    read(args.originals) if args.originals else None))


if __name__ == '__main__':
    main()
