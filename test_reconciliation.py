import json,sqlite3,subprocess,sys,tempfile,unittest,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parent/'backend'))
import online_reconciliation as online

def row(**values):
    return dict(dict(path='a.jpg',album='Album',size=12,fingerprint='f1',status='uploaded',evidence_kind='rclone_individual_confirmation'),**values)

def snapshot(items=None,**values):
    entries=[{'Path':'Album','Name':'Album','IsDir':True,'ID':'album-id'}]
    if items is None:items=[{'Path':'Album/a.jpg','Name':'a.jpg','IsDir':False,'ID':'media-id'}]
    return dict(dict(authority='account-1',albums_complete=True,library_complete=True,
                     tree=entries+items,library=items,errors=[]),**values)

def prior(**values):
    return {'a.jpg':dict(dict(fingerprint='f1',remote_id='media-id',remote_album_id='album-id',authority='account-1',missing_since=time.time()-7200,missing_checks=1),**values)}

class ComparisonTests(unittest.TestCase):
    def state(self,local=None,remote=None,previous=None):
        return online.compare([local or row()],remote or snapshot(),previous or {})[0]
    def test_receipt_and_remote_id_association(self):
        result=self.state();self.assertEqual(result['state'],'receipt_and_online');self.assertEqual(result['remote_id'],'media-id');self.assertFalse(result['repair'])
    def test_history_invisible_never_missing_or_requeued(self):
        result=self.state(row(evidence_kind='online_existing_declared_by_user'),snapshot(tree=[],library=[]))
        self.assertEqual(result['state'],'historical_not_visible');self.assertFalse(result['repair'])
    def test_matching_names_do_not_upgrade_declaration(self):
        self.assertEqual(self.state(row(evidence_kind='online_existing_declared_by_user'))['state'],'name_match_only')
    def test_equal_counts_with_different_names_are_not_complete(self):
        other={'Path':'Album/b.jpg','Name':'b.jpg','IsDir':False,'ID':'other'}
        self.assertNotEqual(self.state(remote=snapshot([other]))['state'],'receipt_and_online')
    def test_duplicates_are_ambiguous(self):
        items=snapshot()['library']*2
        self.assertEqual(self.state(remote=snapshot(items))['state'],'ambiguous')
        rows=[row(),row(path='other/a.jpg')]
        self.assertTrue(all(r['state']=='ambiguous' for r in online.compare(rows,snapshot(),{})))
    def test_partial_failure_is_not_absence(self):
        for flag in ('albums_complete','library_complete'):
            result=self.state(remote=snapshot([],**{flag:False}),previous=prior())
            self.assertFalse(result['repair']);self.assertNotEqual(result['state'],'missing_observed_item')
    def test_only_stable_id_absence_from_same_session_is_repairable(self):
        result=self.state(remote=snapshot([]),previous=prior())
        self.assertEqual(result['state'],'missing_observed_item');self.assertTrue(result['repair'])
    def test_first_read_missing_receipt_does_not_reupload(self):
        self.assertFalse(self.state(remote=snapshot([]))['repair'])
        self.assertFalse(self.state(remote=snapshot([]),previous=prior(missing_since=0,missing_checks=0))['repair'])
        self.assertFalse(self.state(remote=snapshot([]),previous=prior(missing_since=time.time()-60))['repair'])
    def test_account_change_does_not_reuse_receipt(self):
        result=self.state(remote=snapshot([],authority='account-2'),previous=prior())
        self.assertEqual(result['state'],'authorization_changed');self.assertFalse(result['repair'])
    def test_local_change_and_empty_files_are_not_auto_repaired(self):
        self.assertFalse(self.state(row(fingerprint='f2',status='pending'),snapshot([]),prior())['repair'])
        self.assertEqual(self.state(row(size=0),snapshot([]),prior())['state'],'empty_local')
    def test_moved_item_links_existing_media_instead_of_reupload(self):
        result=self.state(remote=snapshot([],library=[{'ID':'media-id'}]),previous=prior())
        self.assertEqual(result['state'],'outside_album');self.assertFalse(result['repair'])
    def test_known_id_with_changed_display_name_is_still_present(self):
        item={'Path':'Album/renamed.jpg','Name':'renamed.jpg','IsDir':False,'ID':'media-id'}
        self.assertEqual(self.state(remote=snapshot([item]),previous=prior())['state'],'receipt_and_online')
    def test_same_name_replacement_never_reuploaded(self):
        item={'Path':'Album/a.jpg','Name':'a.jpg','IsDir':False,'ID':'replacement'}
        self.assertFalse(self.state(remote=snapshot([item]),previous=prior())['repair'])
    def test_deleted_album_is_not_silently_recreated(self):
        self.assertFalse(self.state(remote=snapshot(tree=[],library=[]),previous=prior())['repair'])
    def test_missing_auth_binding_disables_repair(self):
        self.assertFalse(self.state(remote=snapshot([],authority=''),previous=prior())['repair'])
    def test_unicode_normalization(self):
        item={'Path':'Album/cafe\u0301.heic','Name':'cafe\u0301.heic','IsDir':False,'ID':'media-id'}
        self.assertEqual(self.state(row(path='café.heic'),snapshot([item]))['state'],'receipt_and_online')
    def test_failed_collector_keeps_partial_scope_explicit(self):
        calls=[]
        def runner(cmd,**kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd,1,'partial','error')
        got=online.collect({'rclone_remote':'gphotos'},Path('.'),runner)
        self.assertFalse(got['albums_complete']);self.assertFalse(got['library_complete']);self.assertEqual(len(calls),1)
        self.assertFalse(any(':media/all' in part for cmd in calls for part in cmd))
    def test_first_inventory_uses_album_reads_without_full_library_scan(self):
        calls=[]
        def runner(cmd,**kwargs):
            calls.append(cmd);return subprocess.CompletedProcess(cmd,0,json.dumps(snapshot()['tree']),'')
        got=online.collect({'rclone_remote':'gphotos'},Path('.'),runner)
        self.assertTrue(got['library_complete']);self.assertEqual(len(calls),1)
    def test_official_batch_lookup_not_found_and_denied_are_distinct(self):
        import io
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);profile=root/'rclone.conf';profile.write_text('[gphotos]\ntoken = '+json.dumps({'access_token':'offline-fixture'})+'\n')
            cfg={'rclone_remote':'gphotos','rclone_config':str(profile)}
            def opener(request,**kwargs):
                self.assertTrue(request.full_url.startswith('https://photoslibrary.googleapis.com/v1/mediaItems:batchGet?'))
                return io.StringIO(json.dumps({'mediaItemResults':[{'mediaItem':{'id':'present'}},{'status':{'code':5}}]}))
            self.assertEqual(online.lookup_ids(cfg,root,['present','missing'],opener),[{'ID':'present'}])
            def denied(*args,**kwargs):return io.StringIO(json.dumps({'mediaItemResults':[{'status':{'code':7}}]}))
            with self.assertRaises(ValueError):online.lookup_ids(cfg,root,['private'],denied)
    def test_import_rejects_incomplete_claim_and_never_changes_media(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cfg={'database':str(root/'state.db')};source=root/'input.json'
            original={'schema':1,'albums':[{'title':'Album','complete':True,'expected_count':1,'items':[{'filename':'a.jpg'}]}]}
            source.write_text(json.dumps(original));online.import_inventory(cfg,source)
            saved=(root/'historical-online-inventory.json').read_bytes()
            original['albums'][0]['expected_count']=2;source.write_text(json.dumps(original))
            with self.assertRaises(ValueError):online.import_inventory(cfg,source)
            self.assertEqual((root/'historical-online-inventory.json').read_bytes(),saved)
            self.assertFalse((root/'state.db').exists())
    def test_real_repair_transaction_preserves_other_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);photo=root/'a.jpg';photo.write_bytes(b'fixture')
            cfg={'database':str(root/'state.db'),'audit_dir':str(root/'audit')}
            def connect(cfg):
                db=sqlite3.connect(cfg['database']);db.create_function('in_sources',1,lambda p:1)
                db.execute('create table if not exists media(path text primary key,album text,size integer,fingerprint text,status text,evidence_kind text,present integer,uploaded_at text,last_error text)');return db
            db=connect(cfg)
            db.execute('insert into media values(?,?,?,?,?,?,1,?,null)',(str(photo),'Album',7,'f1','uploaded','rclone_individual_confirmation','2026-01-01'))
            db.execute('insert into media values(?,?,?,?,?,?,1,?,null)',('history.jpg','History',7,'f1','uploaded','online_existing_declared_by_user','2026-01-01'));db.commit();db.close()
            online.reconcile(cfg,root,connect,lambda *args:snapshot())
            db=connect(cfg);db.execute('update online_observations set missing_since=?,missing_checks=1',(time.time()-7200,));db.commit();db.close()
            calls=[];original=online.reconcile
            def upload(*args):
                db=connect(cfg);self.assertEqual(db.execute('select status,uploaded_at from media where path=?',(str(photo),)).fetchone(),('pending',None));db.close();calls.append(True);return 0
            online.reconcile=lambda cfg,app,connector:original(cfg,app,connector,lambda *args:snapshot([]))
            try:
                self.assertEqual(online.repair(cfg,root,{'connect_db':connect,'fingerprint':lambda *args:'f1','upload':upload}),0)
            finally:online.reconcile=original
            self.assertEqual(calls,[True]);db=connect(cfg)
            self.assertEqual(db.execute("select status,evidence_kind from media where path='history.jpg'").fetchone(),('uploaded','online_existing_declared_by_user'))
            self.assertEqual(db.execute('select count(*) from online_repair_requests').fetchone()[0],1);db.close()
    def test_integration_persists_observations_not_upload_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cfg={'database':str(root/'state.db'),'audit_dir':str(root/'audit')}
            def connect(cfg):
                db=sqlite3.connect(cfg['database']);db.create_function('in_sources',1,lambda p:1)
                db.execute('create table if not exists media(path text,album text,size integer,fingerprint text,status text,evidence_kind text,present integer)')
                return db
            db=connect(cfg);db.execute('insert into media values(?,?,?,?,?,?,1)',tuple(row().values()));db.commit();db.close()
            summary,results=online.reconcile(cfg,root,connect,lambda *args:snapshot())
            self.assertEqual(summary['counts'],{'receipt_and_online':1});self.assertFalse(summary['binary_integrity_verified'])
            db=connect(cfg);self.assertEqual(db.execute('select status from media').fetchone()[0],'uploaded');self.assertEqual(db.execute('select remote_id from online_observations').fetchone()[0],'media-id');db.close()
            self.assertTrue((root/'audit/online-reconciliation.html').is_file())

if __name__=='__main__':unittest.main()
