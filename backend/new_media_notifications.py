"""App-owned durable discovery notifications. No upload or baseline changes."""
import json
import time
import uuid
from collections import Counter
from pathlib import Path
from reliable_history import atomic_json


def record_detection(db, items, cfg):
    db.execute('create table if not exists ui_discoveries (id text primary key, created_at real not null, payload text not null)')
    if items:
        counts = Counter(album for album in items)
        payload = {'schema': 1, 'id': uuid.uuid4().hex, 'created_at': time.time(),
                   'media_count': len(items), 'folder_count': len(counts),
                   'albums': [{'name': name, 'count': count} for name, count in sorted(counts.items())[:20]]}
        db.execute('insert into ui_discoveries values(?,?,?)',
                   (payload['id'], payload['created_at'], json.dumps(payload, ensure_ascii=False)))
    # A failed file export is retried on subsequent scans from the durable record.
    db.commit()
    row = db.execute('select payload from ui_discoveries order by created_at desc, rowid desc limit 1').fetchone()
    if row:
        target = Path(cfg['database']).parent / 'new-media-notification.json'
        try:
            payload = json.loads(row[0])
            current = json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
            if current.get('id') != payload['id']:
                atomic_json(target, payload)
        except (OSError, ValueError) as exc:
            print('Discovery notification export deferred: ' + type(exc).__name__)
