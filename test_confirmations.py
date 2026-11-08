import contextlib,io,json,os,runpy,sqlite3,subprocess,sys,tempfile
from pathlib import Path
stage=Path(__file__).parent/'backend';sys.path.insert(0,str(stage))
results={}
with tempfile.TemporaryDirectory(prefix='photos-retry-') as temp:
    root=Path(temp);state=root/'state';os.environ['GOOGLE_PHOTOS_HOME']=str(state)
    from app_paths import bootstrap
    bootstrap();cfg=json.loads((state/'config.json').read_text(encoding='utf-8'))
    pictures=root/'Pictures';album=pictures/'Album';album.mkdir(parents=True)
    for name in ('a.jpg','b.jpg'):(album/name).write_bytes(b'fixture-'+name.encode())
    cfg.update(photos_root=str(pictures),min_file_age_seconds=0,dry_run=False,album_retries=2,rclone_exe='rclone')
    for name in ('database','logs_dir','audit_dir'):cfg[name]=str(state/cfg[name])
    module=runpy.run_path(str(stage/'gphotos_uploader.py'),run_name='retry_test');env=module['upload'].__globals__
    env['remote_album_names']=lambda cfg:{'Album'}
    env['quiet_run']=lambda *args,**kw:subprocess.CompletedProcess(args,0,'gphotos:\n','')
    env['time'].sleep=lambda value:None
    selections=[]
    def fake_run(cmd,log_file=None,cfg=None,file_lookup=None,on_confirmed=None):
        assert '--include' not in cmd and '--exclude' not in cmd,cmd
        # Exercise the real rclone parser with the generated flags, without
        # contacting Google or copying user media. This caught the production
        # include/files-from-raw conflict that mocked transfer output missed.
        executable=os.environ.get('RCLONE_TEST_EXE')
        if executable and not selections:
            offset=cmd.index('copy')
            probe=subprocess.run([executable,'copy',str(album),str(root/'probe')]+cmd[offset+3:]+['--dry-run'],capture_output=True,text=True)
            assert probe.returncode==0,probe.stderr
            assert 'a.jpg' in probe.stderr and 'b.jpg' in probe.stderr,probe.stderr
            results['real_rclone_accepts_generated_selection_flags']=True
        names=Path(cmd[cmd.index('--files-from-raw')+1]).read_text(encoding='utf-8').splitlines();selections.append(names)
        chosen='a.jpg' if len(selections)==1 else 'b.jpg'
        assert on_confirmed(file_lookup[chosen])
        with contextlib.closing(sqlite3.connect(cfg['database'])) as db:
            assert db.execute('select status from media where path=?',(file_lookup[chosen],)).fetchone()[0]=='uploaded'
        return subprocess.CompletedProcess(cmd,1 if len(selections)==1 else 0,f'2026/10/22 12:00:00 INFO  : {chosen}: Copied (new)\n','')
    env['run']=fake_run
    with contextlib.redirect_stdout(io.StringIO()):assert module['upload'](cfg,None)==0
    assert selections==[['a.jpg','b.jpg'],['b.jpg']],selections
    results['partial_retry_only_sends_remaining']=True
    results['confirmation_committed_before_attempt_finishes']=True
    old=module['fingerprint'](album/'a.jpg',(album/'a.jpg').stat())
    (album/'a.jpg').write_bytes(b'changed after inventory')
    try:module['stage_pending_files']('Album',[album/'a.jpg'],{str(album/'a.jpg'):old})
    except RuntimeError:results['changed_before_staging_is_blocked']=True
    else:raise AssertionError('Changed source accepted')
print(json.dumps(results,indent=2))
(Path(__file__).parent/'confirmation-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
