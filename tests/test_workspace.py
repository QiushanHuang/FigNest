"""Behavioral regression tests for the FigNest 4 workspace (synthetic data only)."""
import base64
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import library

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="120" height="60"><text>one</text></svg>'


def upload(path, data=SVG):
    return {'path': path, 'data': base64.b64encode(data).decode()}


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = library.Store(self.root / 'data')

    def imported(self):
        result = self.store.import_uploads('Samples', [upload('a.svg'), upload('b.svg', SVG.replace(b'one', b'two'))])
        return result['library_id'], [r['id'] for r in self.store.state()['images']]

    def test_nested_folders_and_safe_reparent(self):
        with self.store.db() as c:
            self.assertIn('parent_id', [r['name'] for r in c.execute('PRAGMA table_info(folders)')])
        first = self.store.folder('Experiment')
        second = self.store.folder('Another')
        child = self.store.folder('Results', parent_id=first)
        self.store.folder('Results', parent_id=second)
        with self.assertRaises(ValueError):
            self.store.folder('Results', parent_id=first)
        with self.assertRaises(ValueError):
            self.store.folder('Experiment', first, parent_id=child)
        self.store.folder('Renamed', child)
        row = next(x for x in self.store.state()['folders'] if x['id'] == child)
        self.assertEqual(row['parent_id'], first)
        self.assertEqual(row['path'], 'Experiment / Renamed')

    def test_parent_trash_restore_and_purge_never_delete_member_assets(self):
        self.assertTrue(hasattr(self.store, 'folder_descendants'), 'nested folder support missing')
        lid, ids = self.imported()
        parent = self.store.folder('Parent')
        child = self.store.folder('Child', parent_id=parent)
        self.store.membership(child, ids[0], True)
        self.assertEqual(self.store.export(folder_id=parent)['count'], 1)
        self.store.delete('folder', parent)
        self.assertEqual(self.store.state()['folders'], [])
        self.store.restore('folder', parent)
        self.assertEqual(len(self.store.state()['folders']), 2)
        self.assertEqual(self.store.preview_purge('folder', parent)['folders'], 2)
        self.store.purge('folder', parent)
        self.assertEqual(len(self.store.state()['images']), 2)
        self.assertEqual(self.store.state()['folders'], [])

    def test_generic_file_import_retains_bytes_and_offline_download(self):
        result = self.store.import_uploads('Mixed', [upload('a.svg'), upload('data.csv', b'x,y\n1,2'), upload('readme.html', b'<script>evil()</script>')])
        self.assertEqual(result['count'], 3, 'general files should be first-class assets')
        rows = self.store.state()['images']
        csv = next(r for r in rows if r['filename'] == 'data.csv')
        self.assertEqual(csv['asset_kind'], 'document')
        data, mime, meta = self.store.image(csv['id'])
        self.assertEqual(data, b'x,y\n1,2')
        self.assertEqual(mime, 'application/octet-stream')
        page = Path(result['export']['path']).read_text()
        self.assertIn('data.csv', page)
        self.assertNotIn('<script>evil()</script>', page)

    def test_hierarchy_import_rules_are_repeatable(self):
        self.assertTrue(hasattr(self.store, 'set_import_options'), 'import presets missing')
        lid, ids = self.imported()
        parent = self.store.folder('Research')
        self.store.set_import_options(lid, {'folder_id': parent, 'tags': ['LC', 'draft'], 'hierarchy': True, 'auto_export': False})
        data = [upload('Run 1/plots/c.svg'), upload('Run 1/tables/result.csv', b'a,b')]
        first = self.store.import_uploads('Samples', data, lid)
        self.assertNotIn('export', first)
        self.store.import_uploads('Samples', data, lid)
        state = self.store.state()
        self.assertEqual(len(state['images']), 4)
        self.assertEqual(len(state['folders']), 4)
        csv = next(r for r in state['images'] if r['filename'] == 'result.csv')
        self.assertEqual(csv['user_tags'], ['LC', 'draft'])
        self.assertEqual(len(csv['folders']), 1)
        self.assertEqual(self.store.export(folder_id=parent)['count'], 2)

    def test_batch_is_atomic_and_smart_folders_are_live(self):
        self.assertTrue(hasattr(self.store, 'batch'), 'bulk actions missing')
        lid, ids = self.imported()
        self.store.batch(ids, {'favorite': True, 'add_tags': ['report']})
        with self.assertRaises(ValueError):
            self.store.batch([ids[0], 'missing'], {'hidden': True})
        self.assertFalse(self.store.state()['images'][0]['hidden'])
        fid = self.store.folder('Ready', kind='smart', query={'favorite': True, 'tags': ['report']})
        self.assertEqual(self.store.export(folder_id=fid)['count'], 2)
        self.store.batch([ids[0]], {'remove_tags': ['report']})
        self.assertEqual(self.store.export(folder_id=fid)['count'], 1)
        with self.assertRaises(ValueError):
            self.store.membership(fid, ids[0], True)

    def test_invalid_smart_queries_and_cycles_are_rejected(self):
        self.assertTrue(hasattr(self.store, 'validate_query'))
        for query in ({'unknown': True}, {'favorite': 'yes'}, {'tags': 'string'}, {'fields': []}):
            with self.assertRaises(ValueError):
                self.store.folder('bad', kind='smart', query=query)

    def test_preferences_are_database_backed_and_validated(self):
        self.assertTrue(hasattr(self.store, 'set_preferences'))
        self.store.set_preferences({'theme': 'dark', 'layout': 'list', 'thumbnail': 220})
        self.assertEqual(library.Store(self.store.root).state()['preferences']['layout'], 'list')
        with self.assertRaises(ValueError):
            self.store.set_preferences({'thumbnail': -5})

    def test_storage_settings_report_only_the_bound_store(self):
        self.assertTrue(hasattr(self.store,'storage_info'),'storage settings missing')
        self.imported()
        info=self.store.storage_info()
        self.assertEqual(info['path'],str(self.store.root))
        self.assertEqual(info['assets'],2)
        self.assertGreater(info['managed_bytes'],0)
        self.assertNotIn('token', info)

    def test_stop_closes_verified_service_without_removing_data(self):
        self.assertTrue(hasattr(library,'stop'),'scoped service stop missing')
        import subprocess
        child=subprocess.Popen([sys.executable,str(Path(library.__file__)),'--data',str(self.store.root),'serve'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
        try:
            receipt=json.loads(child.stdout.readline())
            self.assertEqual(receipt['store_id'],self.store.store_id)
            result=library.stop(self.store)
            self.assertTrue(result['stopped'])
            child.wait(timeout=5)
            self.assertTrue(self.store.database.exists())
        finally:
            if child.poll() is None: child.terminate();child.wait(timeout=5)
            child.stdout.close()

    def test_stop_rejects_invalid_pid_before_any_signal(self):
        self.assertTrue(hasattr(library,'stop'),'scoped service stop missing')
        import os
        (self.store.root/'server.json').write_text(json.dumps({'url':'http://127.0.0.1:1/','pid':os.getpid(),'store_id':self.store.store_id}))
        with self.assertRaises(ValueError): library.stop(self.store)

    def test_stop_rejects_receipt_pointing_at_another_live_store_pid(self):
        import subprocess
        other=library.Store(self.root/'other')
        children=[]
        try:
            receipts=[]
            for store in (self.store,other):
                child=subprocess.Popen([sys.executable,str(Path(library.__file__)),'--data',str(store.root),'serve'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True)
                children.append(child);receipts.append(json.loads(child.stdout.readline()))
            receipts[0]['pid']=receipts[1]['pid']
            (self.store.root/'server.json').write_text(json.dumps(receipts[0]))
            with self.assertRaises(ValueError): library.stop(self.store)
            self.assertTrue(all(child.poll() is None for child in children))
        finally:
            for child in children:
                if child.poll() is None: child.terminate()
                child.wait(timeout=5);child.stdout.close()

    def test_duplicate_content_is_reported_not_silently_dropped(self):
        self.store.import_uploads('Same', [upload('one.svg'), upload('two.svg')])
        state = self.store.state()
        self.assertIn('duplicate_count', state['images'][0])
        self.assertEqual([r['duplicate_count'] for r in state['images']], [2, 2])
        self.assertEqual(len(list((self.store.root / 'blobs').iterdir())), 1)

    def test_same_named_libraries_get_independent_hierarchy_roots(self):
        for _ in range(2):
            self.store.import_uploads('Same title', [upload('plots/a.svg')], options={'hierarchy':True,'auto_export':False})
        roots = [f for f in self.store.state()['folders'] if not f['parent_id']]
        self.assertEqual(len(roots), 2, 'distinct libraries must not silently share generated folders')
        self.assertEqual([self.store.export(folder_id=f['id'])['count'] for f in roots], [1,1])
        lid = self.store.state()['libraries'][0]['id']
        self.store.rename('library', lid, 'New title')
        self.store.import_uploads('ignored', [upload('plots/a.svg')], lid)
        self.assertEqual(len([f for f in self.store.state()['folders'] if not f['parent_id']]),2)

    def test_parent_rename_and_trash_invalidate_descendant_export(self):
        lid, ids = self.imported()
        parent = self.store.folder('Parent')
        child = self.store.folder('Child', parent_id=parent)
        self.store.membership(child, ids[0], True)
        self.store.export(library_id=lid)
        self.store.folder('Renamed parent', parent)
        self.assertTrue(self.store.state()['libraries'][0]['export_stale'])
        self.store.export(library_id=lid)
        self.store.delete('folder', parent)
        self.assertTrue(self.store.state()['libraries'][0]['export_stale'])

    def test_bulk_recovery_delete_validates_all_before_mutation(self):
        self.assertTrue(hasattr(self.store, 'delete_batch'))
        lid, ids = self.imported()
        with self.assertRaises(ValueError):
            self.store.delete_batch([{'kind':'image','id':ids[0]}, {'kind':'image','id':'unknown'}])
        self.assertEqual(len(self.store.state()['images']),2)
        self.store.delete_batch([{'kind':'image','id':ident} for ident in ids])
        self.assertEqual(len(self.store.state()['trash']['images']),2)

    def test_retired_import_folder_does_not_block_future_imports(self):
        lid, ids = self.imported()
        parent = self.store.folder('Parent')
        child = self.store.folder('Child', parent_id=parent)
        self.store.set_import_options(lid, {'folder_id':child,'tags':['keep'],'auto_export':False})
        self.store.delete('folder', parent)
        self.assertIsNone(self.store.state()['libraries'][0]['import_options']['folder_id'])
        self.store.import_uploads('More', [upload('another.svg')], lid)
        self.store.restore('folder', parent)
        self.store.set_import_options(lid, {'folder_id':child})
        self.store.purge('folder', parent)
        self.assertIsNone(self.store.state()['libraries'][0]['import_options']['folder_id'])
        self.assertEqual(self.store.state()['libraries'][0]['import_options']['tags'],['keep'])

    def test_cli_general_directory_refresh_and_symlink_boundary(self):
        self.assertTrue(hasattr(self.store, 'collect_files'), 'general directory adapter missing')
        source = self.root / 'source'
        source.mkdir()
        (source / 'one.csv').write_bytes(b'one,two')
        (source / 'plot.svg').write_bytes(SVG)
        (source / 'link.csv').symlink_to(source / 'one.csv')
        result = self.store.import_directory(source, name='Files', all_files=True)
        self.assertEqual(result['count'], 2)
        self.assertEqual(len(result['skipped']), 1)
        (source / 'one.csv').write_bytes(b'three,four')
        result = self.store.refresh(result['library_id'])
        self.assertEqual(result['changed'], 1)

    def test_v5_migration_preserves_folder_and_membership(self):
        # Reconstruct only the v5 folder shape; all other records stay intact.
        lid, ids = self.imported()
        folder = self.store.folder('legacy')
        self.store.membership(folder, ids[0], True)
        with sqlite3.connect(self.store.database) as c:
            c.execute('DROP TABLE membership')
            c.execute('DROP TABLE folders')
            c.execute('CREATE TABLE folders(id TEXT PRIMARY KEY,name TEXT UNIQUE,created TEXT,deleted_at TEXT)')
            c.execute('INSERT INTO folders VALUES (?,?,?,NULL)', (folder, 'legacy', '2020'))
            c.execute('CREATE TABLE membership(folder_id TEXT REFERENCES folders(id),image_id TEXT REFERENCES images(id),PRIMARY KEY(folder_id,image_id))')
            c.execute('INSERT INTO membership VALUES (?,?)', (folder, ids[0]))
            c.execute('PRAGMA user_version=5')
        migrated = library.Store(self.store.root)
        state = migrated.state()
        self.assertIn('parent_id', state['folders'][0])
        self.assertIn(folder, state['images'][0]['folders'])
        self.assertTrue(list((self.store.root / 'backups').glob('*.sqlite3')))

    def test_http_v4_interfaces_and_generic_file_is_download_only(self):
        import http.client
        import threading
        server = library.make_server(self.store)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        origin = f'http://127.0.0.1:{server.server_port}'
        def request(path, body=None):
            conn = http.client.HTTPConnection('127.0.0.1', server.server_port)
            conn.request('POST' if body is not None else 'GET', path, json.dumps(body) if body is not None else None,
                         {'X-Viewer-Token':server.token, 'Origin':origin, 'Content-Type':'application/json'})
            r = conn.getresponse()
            result = r.status, dict(r.getheaders()), r.read()
            conn.close()
            return result
        try:
            status, _, data = request('/api/import/begin', {'name':'HTTP','options':{'auto_export':False}})
            ident = json.loads(data)['id']
            self.assertEqual(status, 200)
            request('/api/import/add', {'id':ident,'files':[upload('file.html', b'<script>bad()</script>')]})
            status, _, data = request('/api/import/commit', {'id':ident})
            self.assertEqual(status, 200)
            row = self.store.state()['images'][0]
            status, headers, data = request('/media/'+row['id'])
            self.assertEqual(status, 200)
            self.assertEqual(headers['Content-Type'], 'application/octet-stream')
            self.assertTrue(headers['Content-Disposition'].startswith('attachment;'))
            self.assertEqual(data, b'<script>bad()</script>')
            self.assertEqual(request('/workspace.js')[0], 200)
            self.assertEqual(request('/api/batch', {'ids':[row['id']],'action':{'favorite':True}})[0], 200)
            self.assertTrue(self.store.state()['images'][0]['favorite'])
        finally:
            server.shutdown()
            server.server_close()
            worker.join()


if __name__ == '__main__':
    unittest.main()
