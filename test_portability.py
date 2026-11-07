import contextlib,io,json,os,runpy,sqlite3,sys,tempfile,time
from pathlib import Path
stage=Path(__file__).parent/'backend'
sys.path.insert(0,str(stage))
import app_config
from reliable_history import io_path
results={}
with tempfile.TemporaryDirectory(prefix='photos-portability-') as temp:
    state=Path(temp)/'state';os.environ['GOOGLE_PHOTOS_HOME']=str(state)
    import app_paths
    app_paths.bootstrap()
    cfg=json.loads((state/'config.json').read_text(encoding='utf-8'))
    assert not cfg['auto_monitor_enabled'] and not cfg['photos_root']
    results['clean_install_no_automatic_upload']=True
    roots=[Path(temp)/'Pictures العربية',Path(temp)/'Vídeos 日本語']
    for root in roots:root.mkdir()
    deep=roots[0]/('long-directory-'*9)/('long-directory-'*9)
    io_path(deep).mkdir(parents=True)
    io_path(deep/'épreuve_日本.jpg').write_bytes(b'fixture-image-not-for-upload')
    (roots[1]/'clip.mp4').write_bytes(b'fixture-video-not-for-upload')
    (roots[0]/'empty.jpg').write_bytes(b'')
    cfg.update(photos_root=str(roots[0]),photos_roots=list(map(str,roots)),min_file_age_seconds=0)
    for key in ('database','logs_dir','audit_dir'):cfg[key]=str(state/cfg[key])
    app_config.save_settings(state/'config.json',cfg)
    module=runpy.run_path(str(stage/'gphotos_uploader.py'),run_name='test_backend')
    with contextlib.redirect_stdout(io.StringIO()):
        stats=module['scan'](cfg)
        assert stats['media_files']==3 and stats['pending_files']==2
        results['multiple_unicode_roots_and_long_paths']=True
        module['mark_baseline'](cfg,'Explicit fixture declaration')
        stats=module['scan'](cfg)
        assert stats['pending_files']==0 and stats['unresolved_invalid_files']==0 and stats['invalid_files']==1
        results['declaration_keeps_empty_original_blocked']=True
        (roots[1]/'clip.mp4').write_bytes(b'modified fixture-video-not-for-upload')
        stats=module['scan'](cfg)
        assert stats['pending_files']==1
        results['modified_only_requeued']=True
        with contextlib.closing(sqlite3.connect(cfg['database'])) as db:before=list(db.execute('select path,status,present,evidence_kind from media order by path'))
        roots[1].rename(Path(temp)/'unavailable')
        try:module['scan'](cfg)
        except (ValueError,SystemExit):pass
        else:raise AssertionError('Missing source was accepted')
        with contextlib.closing(sqlite3.connect(cfg['database'])) as db:assert before==list(db.execute('select path,status,present,evidence_kind from media order by path'))
        results['unavailable_source_preserves_history']=True
        cfg['photos_roots']=[str(roots[0]),str(deep)]
        try:app_config.source_folders(cfg)
        except ValueError:pass
        else:raise AssertionError('Overlapping roots were accepted')
        results['overlapping_roots_rejected']=True
    # Remove long fixture paths through their explicit extended-path spellings.
    import shutil
    shutil.rmtree(io_path(deep.parent))
print(json.dumps(results,indent=2))
(Path(__file__).parent/'backend-portability-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
