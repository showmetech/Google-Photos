"""Read-only online comparison. API invisibility is never proof of absence.

Only previously observed stable IDs, bound to the same authorization and an
unchanged confirmed local receipt, can authorize a repair. Names/counts alone
never authorize re-uploading the historical library.
"""
import configparser
import hashlib
import html
import json
import subprocess
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from app_config import profile_path, rclone_args
from reliable_history import atomic_json, atomic_csv, io_path

RECEIPTS = {'rclone_individual_confirmation', 'google_photos_web_upload_confirmed'}
LABELS = {
    'receipt_and_online': 'Recibo e presença online conferidos',
    'name_match_only': 'Nome correspondente; conteúdo não comprovado',
    'historical_not_visible': 'Histórico não acessível pela API',
    'receipt_not_visible': 'Recibo preservado; confirmação online indisponível',
    'not_verified': 'Ainda sem comprovação online',
    'ambiguous': 'Correspondência ambígua',
    'local_changed': 'Arquivo local modificado; comparar conteúdo',
    'outside_album': 'Item online fora do álbum esperado',
    'missing_observed_item': 'Item antes conferido não encontrado online',
    'unavailable': 'Consulta online incompleta ou indisponível',
    'empty_local': 'Original local vazio; envio bloqueado',
    'authorization_changed': 'Conexão alterada; recibo anterior não transferido para outra conta',
    'historical_snapshot_name_match': 'Histórico: nome localizado no inventário importado; conteúdo não comprovado',
    'historical_snapshot_no_match': 'Histórico: nome não localizado no inventário importado; conferir no navegador',
}


def import_inventory(cfg, source):
    """Advisory historical inventory only; it never changes media or repairs."""
    source=Path(source)
    if source.stat().st_size>64*1024*1024:raise ValueError('Inventory exceeds 64 MiB')
    data=json.loads(source.read_text(encoding='utf-8-sig'))
    if data.get('schema')!=1 or not isinstance(data.get('albums'),list):raise ValueError('Expected inventory schema 1 with albums')
    for album in data['albums']:
        if not isinstance(album,dict) or not isinstance(album.get('title'),str) or not isinstance(album.get('items'),list):raise ValueError('Invalid album inventory')
        for item in album['items']:
            if not isinstance(item,dict) or not isinstance(item.get('filename'),str) or not item['filename']:raise ValueError('Missing original filename')
        if album.get('complete') and album.get('expected_count')!=len(album['items']):raise ValueError('Incomplete album inventory')
    data['imported_at']=time.time()
    data['advisory_only']=True
    atomic_json(Path(cfg['database']).parent/'historical-online-inventory.json',data)


def authority(cfg, app):
    """Opaque account-session binding; no credentials in reports or logs."""
    try:
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(profile_path(cfg, app), encoding='utf-8-sig')
        remote = parser[cfg['rclone_remote']]
        refresh = json.loads(remote.get('token', '{}')).get('refresh_token')
        if not refresh:
            return ''
        return hashlib.sha256((remote.get('client_id', '')+'|'+refresh).encode()).hexdigest()
    except (OSError, ValueError, KeyError, configparser.Error):
        return ''


def collect(cfg, app, runner=subprocess.run):
    snapshot = {'at': time.time(), 'authority': authority(cfg, app),
                'albums_complete': False, 'library_complete': False,
                'tree': [], 'library': [], 'errors': []}
    for key, remote, recursive in (
        ('tree', ':album', True), ('library', ':media/all', False)):
        args = ['lsjson', cfg['rclone_remote']+remote, '--contimeout', '10s',
                '--timeout', '30s', '--retries', '1', '--low-level-retries', '1',
                '--log-level', 'ERROR', '--gphotos-include-archived']
        args += ['--recursive'] if recursive else ['--files-only']
        try:
            result = runner(rclone_args(cfg, app, *args), capture_output=True,
                            text=True, encoding='utf-8', errors='replace', timeout=600,
                            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise ValueError('rclone returned '+str(result.returncode))
            entries = json.loads(result.stdout)
            if not isinstance(entries, list) or any(
                not isinstance(e, dict) or not isinstance(e.get('Path'), str)
                or not isinstance(e.get('Name'), str) or not isinstance(e.get('IsDir'), bool)
                for e in entries):
                raise ValueError('Invalid online inventory')
            snapshot[key] = entries
            snapshot['albums_complete' if key == 'tree' else 'library_complete'] = True
            if key == 'library' and any(not e.get('ID') for e in entries):
                snapshot['library_complete'] = False
                snapshot['errors'].append('library: stable IDs unavailable')
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            snapshot['errors'].append(key+': '+type(exc).__name__)
    return snapshot


def key(name):
    return unicodedata.normalize('NFC', name)


def compare(rows, snapshot, observations):
    directories = defaultdict(list)
    files = defaultdict(list)
    album_ids = defaultdict(set)
    for item in snapshot.get('tree', []):
        if item['IsDir']:
            directories[key(item['Path'])].append(item)
        else:
            files[(key(str(PurePosixPath(item['Path']).parent)), key(item['Name']))].append(item)
            album_ids[key(str(PurePosixPath(item['Path']).parent))].add(item.get('ID'))
    library = {i.get('ID') for i in snapshot.get('library', []) if i.get('ID')}
    local_names = Counter((r['album'], key(Path(r['path']).name)) for r in rows)
    results = []
    for row in rows:
        prior = observations.get(row['path'], {})
        album_dirs = directories[key(row['album'])]
        candidates = files[(key(row['album']), key(Path(row['path']).name))]
        receipt = row.get('evidence_kind') in RECEIPTS and row['status'] == 'uploaded'
        bound = (bool(snapshot.get('authority')) and prior.get('authority') == snapshot['authority']
                 and prior.get('fingerprint') == row['fingerprint'] and receipt)
        current_ids = album_ids[key(row['album'])]
        observed_id = prior.get('remote_id') if bound else None
        item = candidates[0] if len(candidates) == 1 else None
        result = dict(path=row['path'], album=row['album'], fingerprint=row['fingerprint'],
                      remote_id='', remote_album_id='', state='not_verified', repair=False)
        if not row['size']:
            result['state'] = 'empty_local'
        elif prior and snapshot.get('authority') and prior.get('authority') != snapshot['authority']:
            result['state'] = 'authorization_changed'
        elif not snapshot.get('albums_complete'):
            result['state'] = 'unavailable'
        elif len(album_dirs) > 1 or len(candidates) > 1 or local_names[(row['album'], key(Path(row['path']).name))] > 1:
            result['state'] = 'ambiguous'
        elif observed_id and observed_id in current_ids and receipt:
            result['state'] = 'receipt_and_online'
            result.update(remote_id=observed_id, remote_album_id=prior.get('remote_album_id', ''))
        elif observed_id and snapshot.get('library_complete') and observed_id in library:
            result.update(state='outside_album', remote_id=observed_id)
        elif (observed_id and snapshot.get('library_complete') and observed_id not in library
              and len(album_dirs) == 1 and album_dirs[0].get('ID') == prior.get('remote_album_id')):
            # A same-name replacement makes identity ambiguous: do not re-upload.
            result.update(state='ambiguous' if candidates else 'missing_observed_item',
                          repair=(not candidates and prior.get('missing_since',0)>0
                                  and snapshot.get('at',time.time())-prior['missing_since']>=3600
                                  and prior.get('missing_checks',0)>=1), remote_id=observed_id,
                          remote_album_id=prior['remote_album_id'])
        elif item:
            state = 'receipt_and_online' if receipt and item.get('ID') and len(album_dirs) == 1 and album_dirs[0].get('ID') else 'name_match_only'
            result.update(state=state, remote_id=item.get('ID', ''),
                          remote_album_id=album_dirs[0].get('ID', '') if len(album_dirs) == 1 else '')
        elif row['status'] == 'pending' and (row.get('baseline_changed') or (prior and prior.get('fingerprint') != row['fingerprint'])):
            result['state'] = 'local_changed'
        elif not album_dirs:
            result['state'] = 'receipt_not_visible' if receipt else 'historical_not_visible'
        results.append(result)
    return results


def schema(db):
    db.execute('''create table if not exists online_observations (
        path text primary key, fingerprint text not null, remote_id text not null,
        remote_album_id text not null, authority text not null, observed_at real not null,
        missing_since real not null default 0, missing_checks integer not null default 0)''')
    columns={row[1] for row in db.execute('pragma table_info(online_observations)')}
    for name,kind in (('missing_since','real'),('missing_checks','integer')):
        if name not in columns:db.execute('alter table online_observations add column '+name+' '+kind+' not null default 0')
    db.commit()


def reconcile(cfg, app, connect_db, collector=collect):
    db = connect_db(cfg)
    try:
        schema(db)
        names = ('path', 'album', 'size', 'fingerprint', 'status', 'evidence_kind')
        rows = [dict(zip(names, row)) for row in db.execute(
            'select path,album,size,fingerprint,status,evidence_kind from media where present=1 and in_sources(path)')]
        previous = {r[0]: dict(zip(('fingerprint', 'remote_id', 'remote_album_id', 'authority', 'observed_at','missing_since','missing_checks'), r[1:]))
                    for r in db.execute('select path,fingerprint,remote_id,remote_album_id,authority,observed_at,missing_since,missing_checks from online_observations')}
        snapshot = collector(cfg, app)
        results = compare(rows, snapshot, previous)
        historical_path=Path(cfg['database']).parent/'historical-online-inventory.json'
        historical={}
        try:
            imported=json.loads(historical_path.read_text(encoding='utf-8'))
            for album in imported.get('albums',[]):
                historical.setdefault(key(album['title']),[]).append(album)
        except (OSError,ValueError):pass
        for result in results:
            if result['state'] not in ('historical_not_visible','receipt_not_visible','not_verified'):continue
            matches=historical.get(key(result['album']),[])
            if len(matches)!=1:continue
            album=matches[0];names=Counter(key(item['filename']) for item in album['items'])
            if names[key(Path(result['path']).name)]==1:result['state']='historical_snapshot_name_match'
            elif names[key(Path(result['path']).name)]>1:result['state']='ambiguous'
            elif album.get('complete'):result['state']='historical_snapshot_no_match'
        now = time.time()
        with db:
            for result in results:
                if result['state'] == 'receipt_and_online' and snapshot.get('authority'):
                    db.execute('insert or replace into online_observations values(?,?,?,?,?,?,0,0)',
                               (result['path'], result['fingerprint'], result['remote_id'],
                                result['remote_album_id'], snapshot['authority'], now))
                elif result['state']=='missing_observed_item':
                    db.execute('update online_observations set missing_since=case when missing_since=0 then ? else missing_since end,missing_checks=missing_checks+1 where path=?',(snapshot.get('at',now),result['path']))
                elif result['state']=='outside_album':
                    db.execute('update online_observations set missing_since=0,missing_checks=0 where path=?',(result['path'],))
        counts = dict(Counter(r['state'] for r in results))
        summary = {'schema': 1, 'checked_at': now, 'local_files': len(rows),
                   'counts': counts, 'repair_candidates': sum(r['repair'] for r in results),
                   'api_scope': 'app_created_content_only', 'binary_integrity_verified': False,
                   'albums_complete': snapshot['albums_complete'], 'library_complete': snapshot['library_complete'],
                   'errors': snapshot['errors'], 'report': str(Path(cfg['audit_dir'])/'online-reconciliation.html')}
        summary['historical_inventory_imported']=historical_path.exists()
        summary['historical_snapshot_at']=imported.get('captured_at','não informado') if historical_path.exists() and historical else None
        audit = Path(cfg['audit_dir']);audit.mkdir(parents=True, exist_ok=True)
        with atomic_csv(audit/'online-reconciliation-files.csv') as stream:
            import csv
            writer = csv.DictWriter(stream, fieldnames=list(results[0]) if results else ['path','state'])
            writer.writeheader();writer.writerows(results)
        totals = defaultdict(Counter)
        for result in results:
            totals[result['album']][result['state']] += 1
        table = ''.join('<tr><td>'+html.escape(album)+'</td><td>'+html.escape('; '.join(
            LABELS[state]+': '+str(count) for state, count in states.items()))+'</td></tr>'
            for album, states in sorted(totals.items()))
        document = ('<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
                    '<title>Conferência online — Google Fotos</title><style>body{font:16px Segoe UI,sans-serif;max-width:1100px;margin:32px auto;padding:16px}td,th{padding:10px;border-bottom:1px solid #999;text-align:left}table{border-collapse:collapse;width:100%}</style>'
                    '<h1>Conferência online</h1><p>'+html.escape(datetime.fromtimestamp(now,timezone.utc).isoformat())+'</p>'
                    '<p>A API só mostra conteúdo criado por este cliente. Histórico não visível não significa ausente. '
                    'Recibo e nome correspondente não equivalem a comparação binária. Esta conferência não apaga nem reenvia o histórico.</p>'
                    '<p>Inventário histórico: '+html.escape(str(summary['historical_snapshot_at'] or 'não importado'))+'. '
                    'Inventários importados são fotografias de uma data, não uma consulta online atual; nunca autorizam reenvios automáticos.</p>'
                    '<p><a href="online-reconciliation-files.csv">Resultado por arquivo (CSV)</a></p><table><tr><th>Pasta / álbum</th><th>Evidências</th></tr>'+table+'</table>')
        target = audit/'online-reconciliation.html';temporary=target.with_suffix('.tmp');temporary.write_text(document,encoding='utf-8');temporary.replace(target)
        atomic_json(Path(cfg['database']).parent/'online-reconciliation-summary.json', summary)
        # Keep the last successful observations even when this read is unavailable.
        print(json.dumps(summary, ensure_ascii=False))
        return summary, results
    finally:
        db.close()


def repair(cfg, app, uploader):
    summary, results = reconcile(cfg, app, uploader['connect_db'])
    if not summary['albums_complete'] or not summary['library_complete']:
        return 4
    candidates = [r for r in results if r['repair']]
    if not candidates:
        return 0
    db = uploader['connect_db'](cfg)
    changed = 0
    try:
        db.execute('create table if not exists online_repair_requests (id integer primary key, created_at real not null, path text not null, prior_json text not null)')
        for item in candidates:
            path = Path(item['path'])
            try:
                if uploader['fingerprint'](path, io_path(path).stat()) != item['fingerprint']:
                    continue
            except OSError:
                continue
            previous=db.execute('select status,uploaded_at,evidence_kind,fingerprint from media where path=?',(str(path),)).fetchone()
            if not previous or previous[0]!='uploaded' or previous[2] not in RECEIPTS or previous[3]!=item['fingerprint']:continue
            db.execute('insert into online_repair_requests(created_at,path,prior_json) values(?,?,?)',(time.time(),str(path),json.dumps({'media':previous,'remote_id':item['remote_id'],'remote_album_id':item['remote_album_id']})))
            changed += db.execute("update media set status='pending',uploaded_at=null,last_error='Item previamente observado ausente na consulta online completa' where path=? and fingerprint=? and status='uploaded'", (str(path),item['fingerprint'])).rowcount
        db.commit()
    finally:
        db.close()
    # The CLI worker lock remains held throughout verification and upload.
    return uploader['upload'](cfg, None) if changed else 0
