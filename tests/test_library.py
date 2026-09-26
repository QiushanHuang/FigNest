import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="200" height="100"><text x="10" y="40">test</text></svg>'


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        (self.source / 'Group A').mkdir(parents=True)
        (self.source / 'Group A/a.svg').write_bytes(SVG)
        (self.source / 'Group A/b.svg').write_bytes(SVG.replace(b'test', b'other'))
        self.store = self.base / 'store'

    def module(self):
        self.assertTrue((SCRIPTS / 'library.py').exists(), 'persistent library program not implemented')
        sys.path.insert(0, str(SCRIPTS))
        import library
        return library

    def imported(self):
        m = self.module()
        db = m.Store(self.store)
        result = db.import_directory(self.source, name='Experiment A')
        return m, db, result['library_id']

    def test_persistence_and_repeat_import_preserve_identity_and_annotations(self):
        m, db, lid = self.imported()
        images = db.state()['images']
        ident = images[0]['id']
        db.annotate(ident, {'favorite': True, 'hidden': True, 'note': '中文 note'})
        db.set_group(lid, 'Group A', {'favorite': True, 'note': 'group note'})
        folder = db.folder('汇报/重点')
        db.membership(folder, ident, True)
        db.import_directory(self.source, library_id=lid)
        fresh = m.Store(self.store).state()
        self.assertEqual(len(fresh['images']), 2)
        row = next(r for r in fresh['images'] if r['id'] == ident)
        self.assertTrue(row['favorite'] and row['hidden'])
        self.assertEqual(row['note'], '中文 note')
        self.assertIn(folder, row['folders'])
        self.assertTrue(fresh['groups'][0]['favorite'])
        self.assertEqual(len(fresh['imports']), 2)

    def test_changed_and_missing_sources_keep_versions_and_state(self):
        m, db, lid = self.imported()
        first = db.state()['images'][0]
        db.annotate(first['id'], {'note': 'keep'})
        (self.source / 'Group A/a.svg').write_bytes(SVG.replace(b'test', b'changed'))
        (self.source / 'Group A/b.svg').rename(self.source / 'Group A/renamed.svg')
        result = db.import_directory(self.source, library_id=lid)
        self.assertEqual(result['changed'], 1)
        self.assertEqual(result['added'], 1)
        self.assertEqual(result['missing'], 1)
        row = next(r for r in db.state()['images'] if r['id'] == first['id'])
        self.assertEqual(row['note'], 'keep')
        self.assertEqual(row['version_count'], 2)

    def test_two_libraries_and_cross_library_custom_folder(self):
        m, db, lid = self.imported()
        second = db.import_directory(self.source, name='Experiment B')['library_id']
        state = db.state()
        self.assertEqual(len(state['libraries']), 2)
        self.assertEqual(len({r['id'] for r in state['images']}), 4)
        folder = db.folder('Compare')
        ids = [next(r['id'] for r in state['images'] if r['library_id'] == x) for x in (lid, second)]
        for ident in ids:
            db.membership(folder, ident, True)
        db.folder('Renamed', folder)
        self.assertEqual(sum(folder in r['folders'] for r in db.state()['images']), 2)
        db.membership(folder, ids[0], False)
        self.assertEqual(len(db.state()['images']), 4)

    def test_export_default_hides_and_keeps_notes_with_immutable_versions(self):
        m, db, lid = self.imported()
        ids = [r['id'] for r in db.state()['images']]
        db.annotate(ids[0], {'hidden': True})
        db.annotate(ids[1], {'note': 'export note', 'favorite': True})
        first = db.export(library_id=lid)
        html = Path(first['path']).read_text()
        self.assertIn('export note', html)
        self.assertEqual(first['count'], 1)
        second = db.export(library_id=lid, include_hidden=True)
        self.assertNotEqual(first['path'], second['path'])
        self.assertEqual(second['count'], 2)
        self.assertTrue(Path(first['path']).is_file())
        self.assertIn(base64.b64encode(SVG).decode(), Path(second['path']).read_text())
        db.annotate(ids[1], {'note': 'new'})
        self.assertTrue(next(r for r in db.state()['libraries'] if r['id'] == lid)['export_stale'])

    def test_invalid_upload_does_not_mutate_or_escape_store(self):
        m, db, lid = self.imported()
        before = db.state()
        with self.assertRaises(ValueError):
            db.import_uploads('bad', [{'path': '../escape.svg', 'data': base64.b64encode(SVG).decode()}])
        self.assertEqual(len(db.state()['libraries']), len(before['libraries']))
        self.assertFalse((self.base / 'escape.svg').exists())
        with self.assertRaises(ValueError):
            db.annotate(before['images'][0]['id'], {'hidden': 'false'})

    def test_uploaded_library_refresh_and_missing_policy(self):
        m = self.module()
        db = m.Store(self.store)
        files = [{'path': 'Example/a.svg', 'data': base64.b64encode(SVG).decode()}]
        lid = db.import_uploads('Uploaded', files)['library_id']
        ident = db.state()['images'][0]['id']
        db.annotate(ident, {'favorite': True})
        db.import_uploads('Uploaded', files, library_id=lid)
        self.assertEqual(len(db.state()['images']), 1)
        self.assertTrue(db.state()['images'][0]['favorite'])
        self.assertEqual(len(db.state()['exports']), 2)

    def test_path_library_accepts_browser_images_and_refresh_preserves_them(self):
        m, db, lid = self.imported()
        entry = {'path': 'Dropped/extra.svg', 'data': base64.b64encode(SVG).decode()}
        added = db.import_uploads('Experiment A', [entry], library_id=lid)
        self.assertEqual(added['added'], 1)
        self.assertEqual(len(db.state()['images']), 3)
        refreshed = db.refresh(lid)
        self.assertEqual(refreshed['missing'], 0)
        self.assertEqual(len(db.state()['images']), 3)
        self.assertTrue(next(x for x in db.state()['libraries'] if x['id'] == lid)['can_refresh'])
        repeated = db.import_uploads('Experiment A', [entry], library_id=lid)
        self.assertEqual(repeated['added'], 0)

    def test_delete_restore_image_keeps_original_and_offline_history(self):
        m, db, lid = self.imported()
        before = db.state()
        target = before['images'][0]
        db.annotate(target['id'], {'favorite': True, 'note': 'keep after delete'})
        old_html = Path(before['exports'][0]['path'])
        db.delete('image', target['id'])
        self.assertEqual(len(db.state()['images']), 1)
        self.assertEqual(len(db.state()['trash']['images']), 1)
        self.assertEqual((self.source / target['relative_path']).read_bytes(), SVG)
        self.assertTrue(old_html.exists())
        with self.assertRaises(ValueError):
            db.image(target['id'])
        db.restore('image', target['id'])
        restored = next(x for x in db.state()['images'] if x['id'] == target['id'])
        self.assertEqual(restored['note'], 'keep after delete')
        self.assertTrue(restored['favorite'])

    def test_delete_restore_library_isolated_from_other_library(self):
        m, db, lid = self.imported()
        second = db.import_directory(self.source, name='Second')['library_id']
        db.delete('library', lid)
        self.assertEqual([l['id'] for l in db.state()['libraries']], [second])
        self.assertEqual(len(db.state()['images']), 2)
        self.assertEqual(len(db.state()['trash']['libraries']), 1)
        with self.assertRaises(ValueError):
            db.refresh(lid)
        db.restore('library', lid)
        self.assertEqual(len(db.state()['libraries']), 2)
        self.assertEqual(len(db.state()['images']), 4)

    def test_delete_restore_custom_folder_keeps_membership(self):
        m, db, lid = self.imported()
        ident = db.state()['images'][0]['id']
        fid = db.folder('Presentation')
        db.membership(fid, ident, True)
        db.delete('folder', fid)
        self.assertEqual(db.state()['folders'], [])
        self.assertEqual(db.state()['images'][0]['folders'], [])
        self.assertEqual(len(db.state()['trash']['folders']), 1)
        db.restore('folder', fid)
        self.assertEqual(db.state()['images'][0]['folders'], [fid])

    def test_permanent_image_delete_removes_managed_bytes_but_not_source_or_old_export(self):
        m, db, lid = self.imported()
        target = next(r for r in db.state()['images'] if r['relative_path'] == 'Group A/a.svg')
        original = self.source / 'Group A/a.svg'
        old_export = Path(db.state()['exports'][0]['path'])
        db.annotate(target['id'], {'note': 'only in the library'})
        db.delete('image', target['id'])
        summary = db.purge('image', target['id'])
        self.assertEqual(summary['images'], 1)
        self.assertFalse(db.blob_path(target['blob']).exists())
        self.assertEqual(original.read_bytes(), SVG)
        self.assertIn(base64.b64encode(SVG).decode(), old_export.read_text())
        self.assertFalse(db.state()['trash']['images'])

    def test_purge_keeps_blob_shared_with_another_library(self):
        m, db, lid = self.imported()
        second = db.import_directory(self.source, name='B')['library_id']
        first_image = next(r for r in db.state()['images'] if r['library_id'] == lid and r['filename'] == 'a.svg')
        other = next(r for r in db.state()['images'] if r['library_id'] == second and r['filename'] == 'a.svg')
        db.purge('image', first_image['id'])
        self.assertEqual(db.image(other['id'])[0], SVG)
        self.assertTrue(db.blob_path(other['blob']).exists())

    def test_purge_library_cleans_its_catalogue_and_retains_other_library(self):
        m, db, lid = self.imported()
        second = db.import_directory(self.source, name='B')['library_id']
        ident = next(r['id'] for r in db.state()['images'] if r['library_id'] == lid)
        db.add_attachment('image', ident, 'readme.txt', b'unrelated file type')
        db.purge('library', lid)
        state = db.state()
        self.assertEqual([r['id'] for r in state['libraries']], [second])
        self.assertEqual(len(state['images']), 2)
        self.assertEqual(len(state['attachments']), 0)
        with self.assertRaises(ValueError):
            db.restore('library', lid)

    def test_purge_folder_removes_membership_without_deleting_picture(self):
        m, db, lid = self.imported()
        ident = db.state()['images'][0]['id']
        fid = db.folder('Meeting')
        db.membership(fid, ident, True)
        db.purge('folder', fid)
        self.assertEqual(len(db.state()['images']), 2)
        self.assertEqual(db.state()['folders'], [])
        self.assertEqual(db.state()['images'][0]['folders'], [])

    def test_empty_trash_purges_only_trashed_items_and_is_idempotent(self):
        m, db, lid = self.imported()
        second = db.import_directory(self.source, name='Still active')['library_id']
        ident = next(r['id'] for r in db.state()['images'] if r['library_id'] == lid)
        fid = db.folder('Archived folder')
        db.membership(fid, ident, True)
        db.delete('folder', fid)
        db.delete('library', lid)
        preview = db.preview_purge('trash')
        self.assertEqual(preview['libraries'], 1)
        self.assertEqual(preview['images'], 2)
        self.assertEqual(preview['folders'], 1)
        summary = db.empty_trash()
        self.assertEqual(summary['libraries'], 1)
        self.assertEqual(summary['folders'], 1)
        self.assertEqual([r['id'] for r in db.state()['libraries']], [second])
        self.assertEqual(db.empty_trash()['libraries'], 0)
        self.assertEqual((self.source / 'Group A/a.svg').read_bytes(), SVG)

    def test_renamed_library_and_picture_survive_refresh_and_export(self):
        m, db, lid = self.imported()
        target = next(r for r in db.state()['images'] if r['filename'] == 'a.svg')
        db.rename('library', lid, '改名后的实验')
        db.rename('image', target['id'], '我挑出的主图')
        db.refresh(lid)
        state = db.state()
        self.assertEqual(next(l for l in state['libraries'] if l['id'] == lid)['name'], '改名后的实验')
        renamed = next(r for r in state['images'] if r['id'] == target['id'])
        self.assertEqual(renamed['title'], '我挑出的主图')
        self.assertEqual(renamed['filename'], 'a.svg')
        self.assertEqual(renamed['source_key'], target['source_key'])
        exported = db.export(library_id=lid)
        self.assertIn('我挑出的主图', Path(exported['path']).read_text())
        with self.assertRaises(ValueError):
            db.rename('image', target['id'], '   ')

    def test_image_and_group_notes_accept_arbitrary_file_attachments(self):
        m, db, lid = self.imported()
        ident = db.state()['images'][0]['id']
        pdf = b'%PDF-1.7\n' + bytes(range(256))
        aid = db.add_attachment('image', ident, 'paper.pdf', pdf)['id']
        gid = lid + '::Group A'
        bid = db.add_attachment('group', gid, 'data set.bin', b'\x00\x01\xff')['id']
        fresh = m.Store(self.store)
        self.assertEqual(fresh.get_attachment(aid)['bytes'], pdf)
        self.assertEqual(fresh.get_attachment(bid)['bytes'], b'\x00\x01\xff')
        self.assertEqual({a['filename'] for a in fresh.state()['attachments']}, {'paper.pdf', 'data set.bin'})
        fresh.delete('attachment', aid)
        self.assertEqual(len(fresh.state()['attachments']), 1)
        self.assertEqual(len(fresh.state()['trash']['attachments']), 1)
        fresh.restore('attachment', aid)
        self.assertEqual(fresh.get_attachment(aid)['bytes'], pdf)

    def test_note_attachment_rejects_unsafe_name_and_deleted_target(self):
        m, db, lid = self.imported()
        ident = db.state()['images'][0]['id']
        with self.assertRaises(ValueError):
            db.add_attachment('image', ident, '../escape.pdf', b'hi')
        db.delete('image', ident)
        with self.assertRaises(ValueError):
            db.add_attachment('image', ident, 'allowed.bin', b'hi')

    def test_reveal_uses_original_when_unchanged_and_managed_copy_for_upload(self):
        m, db, lid = self.imported()
        image = next(x for x in db.state()['images'] if x['relative_path'] == 'Group A/a.svg')
        self.assertEqual(db.reveal_path(image['id']), (self.source / 'Group A/a.svg').resolve())
        db.import_uploads('Experiment A', [{'path': 'Dropped/extra.svg', 'data': base64.b64encode(SVG).decode()}], library_id=lid)
        uploaded = next(x for x in db.state()['images'] if x['source_key'] == 'browser:Dropped/extra.svg')
        managed = db.reveal_path(uploaded['id'])
        self.assertTrue(managed.is_relative_to(db.root))
        self.assertEqual(managed.name, 'extra.svg')
        self.assertEqual(managed.read_bytes(), SVG)
        (self.source / 'Group A/a.svg').write_bytes(SVG.replace(b'test', b'new'))
        self.assertTrue(db.reveal_path(image['id']).is_relative_to(db.root))

    def test_reveal_can_pin_an_original_source_outside_an_import_snapshot(self):
        m, db, lid = self.imported()
        target = next(r for r in db.state()['images'] if r['relative_path'] == 'Group A/a.svg')
        original = self.base / 'real-original.svg'
        original.write_bytes(SVG)
        db.pin_original_source(target['id'], original)
        self.assertEqual(db.reveal_path(target['id']), original.resolve())
        self.assertNotIn(str(original.resolve()), Path(db.export(library_id=lid)['path']).read_text())
        original.write_bytes(b'changed after import')
        self.assertEqual(db.reveal_path(target['id']), (self.source / 'Group A/a.svg').resolve())

    def test_migration_preserves_v1_data_and_writes_recovery_backup(self):
        import sqlite3
        m, db, lid = self.imported()
        identity = db.state()['images'][0]['id']
        db.annotate(identity, {'note': 'before schema migration'})
        # Construct a genuine v1 schema from this test store, then open it with the new program.
        with sqlite3.connect(self.store / 'library.sqlite3') as connection:
            connection.execute('DROP INDEX IF EXISTS folder_sibling_names')
            for table in ('libraries', 'images', 'folders'):
                connection.execute(f'ALTER TABLE {table} DROP COLUMN deleted_at')
            connection.execute('ALTER TABLE images DROP COLUMN renamed_title')
            connection.execute('DROP TABLE IF EXISTS attachments')
            connection.execute('PRAGMA user_version=1')
        upgraded = m.Store(self.store)
        self.assertEqual(upgraded.state()['images'][0]['note'], 'before schema migration')
        with sqlite3.connect(self.store / 'library.sqlite3') as connection:
            self.assertEqual(connection.execute('PRAGMA user_version').fetchone()[0], 6)
        self.assertTrue(list((self.store / 'backups').glob('*.sqlite3')))

    def test_migration_from_installed_v3_preserves_existing_library(self):
        import sqlite3
        m, db, lid = self.imported()
        ident = db.state()['images'][0]['id']
        db.annotate(ident, {'note': 'saved in v3'})
        with sqlite3.connect(self.store / 'library.sqlite3') as connection:
            connection.execute('DROP TABLE attachments')
            connection.execute('ALTER TABLE images DROP COLUMN renamed_title')
            connection.execute('PRAGMA user_version=3')
        after = m.Store(self.store).state()
        self.assertEqual(after['version'], m.VERSION)
        self.assertEqual(after['images'][0]['note'], 'saved in v3')
        self.assertEqual(after['libraries'][0]['id'], lid)
        self.assertTrue(list((self.store / 'backups').glob('*.sqlite3')))

    def test_purge_rejects_preview_after_target_content_changes(self):
        m, db, lid = self.imported()
        target = next(r for r in db.state()['images'] if r['filename'] == 'a.svg')
        preview = db.preview_purge('image', target['id'])
        (self.source / 'Group A/a.svg').write_bytes(SVG.replace(b'test', b'new-content'))
        db.refresh(lid)
        with self.assertRaisesRegex(ValueError, 'changed'):
            db.purge('image', target['id'], expected_fingerprint=preview['fingerprint'])
        self.assertEqual(len(db.state()['images']), 2)

    def test_backup_retains_independent_snapshot(self):
        import sqlite3
        m, db, lid = self.imported()
        path = db.backup()
        ident = db.state()['images'][0]['id']
        db.annotate(ident, {'note': 'after backup'})
        copy = sqlite3.connect(path)
        try:
            self.assertEqual(copy.execute('SELECT note FROM images WHERE id=?', (ident,)).fetchone()[0], '')
        finally:
            copy.close()

    def test_export_uses_captured_immutable_content_if_another_import_finishes(self):
        import threading
        m, db, lid = self.imported()
        captured_state = db.state
        snapshot_ready = threading.Event()
        release_export = threading.Event()
        other_store = m.Store(self.store)
        results = {}
        def boundary():
            captured = captured_state()
            snapshot_ready.set()
            self.assertTrue(release_export.wait(timeout=5))
            return captured
        db.state = boundary
        (self.source / 'Group A/a.svg').write_bytes(SVG.replace(b'test', b'updated concurrently'))
        def export():
            results['export'] = db.export(library_id=lid)
        def importing():
            results['import'] = other_store.import_directory(self.source, library_id=lid)
        exporting = threading.Thread(target=export)
        exporting.start()
        self.assertTrue(snapshot_ready.wait(timeout=5))
        importing_thread = threading.Thread(target=importing)
        importing_thread.start()
        release_export.set()
        exporting.join(timeout=5)
        importing_thread.join(timeout=5)
        self.assertFalse(exporting.is_alive() or importing_thread.is_alive())
        self.assertIn(base64.b64encode(SVG).decode(), Path(results['export']['path']).read_text())
        self.assertEqual(results['import']['changed'], 1)

    def test_http_origin_token_and_media_access(self):
        import http.client
        import threading
        m, db, lid = self.imported()
        server = m.make_server(db)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            origin = f'http://127.0.0.1:{server.server_port}'
            def request(method, path, body=None, token=True, from_origin=origin, host=None):
                c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
                headers = {'Origin': from_origin, 'Content-Type': 'application/json'}
                if token: headers['X-Viewer-Token'] = server.token
                if host: headers['Host'] = host
                c.request(method, path, json.dumps(body) if body is not None else None, headers)
                r = c.getresponse()
                result = r.status, r.read()
                c.close()
                return result
            self.assertEqual(request('GET', '/api/state', token=False)[0], 403)
            self.assertEqual(request('GET', '/', host='attacker.example')[0], 403)
            ident = db.state()['images'][0]['id']
            patch = {'id': ident, 'patch': {'note': 'saved through API'}}
            self.assertEqual(request('POST', '/api/image', patch, from_origin='https://attacker.example')[0], 403)
            self.assertEqual(request('POST', '/api/image', patch, token=False)[0], 403)
            self.assertEqual(request('POST', '/api/image', patch)[0], 200)
            self.assertEqual(db.state()['images'][0]['note'], 'saved through API')
            self.assertEqual(request('GET', '/media/'+ident)[1], SVG)
            self.assertEqual(request('GET', '/media/../../library.sqlite3')[0], 404)
            self.assertEqual(request('GET', '/library.sqlite3')[0], 404)
            status, payload = request('POST', '/api/export', {'library_id': lid})
            self.assertEqual(status, 200)
            exported = json.loads(payload)
            self.assertEqual(request('GET', exported['url'])[0], 200)
            denied = {'kind': 'image', 'id': ident}
            self.assertEqual(request('POST', '/api/delete', denied, token=False)[0], 403)
            self.assertEqual(request('POST', '/api/delete', denied)[0], 200)
            self.assertEqual(request('GET', '/media/'+ident)[0], 404)
            self.assertEqual(request('POST', '/api/restore', denied)[0], 200)
            self.assertEqual(request('GET', '/media/'+ident)[1], SVG)
            code, raw = request('POST', '/api/purge/preview', denied)
            self.assertEqual(code, 200)
            preview = json.loads(raw)
            self.assertEqual(preview['images'], 1)
            self.assertEqual(request('POST', '/api/purge', {**denied, 'fingerprint': preview['fingerprint']})[0], 400)
            self.assertEqual(request('POST', '/api/purge', {**denied, 'confirm': '永久删除', 'fingerprint': preview['fingerprint']}, token=False)[0], 403)
            self.assertEqual(request('POST', '/api/purge', {**denied, 'confirm': '永久删除', 'fingerprint': preview['fingerprint']})[0], 200)
            self.assertEqual(request('GET', '/media/'+ident)[0], 404)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_http_streams_arbitrary_note_file_and_rejects_bad_chunks(self):
        import http.client
        import threading
        m, db, lid = self.imported()
        target = db.state()['images'][0]['id']
        payload = b'%PDF-1.7\n' + bytes(range(256)) * 50
        server = m.make_server(db)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(method, path, body=None, token=True):
            c = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            headers = {'Origin': f'http://127.0.0.1:{server.server_port}', 'Content-Type': 'application/json'}
            if token: headers['X-Viewer-Token'] = server.token
            c.request(method, path, json.dumps(body) if body is not None else None, headers)
            r = c.getresponse()
            code, data = r.status, r.read()
            c.close()
            return code, data
        try:
            begin = {'kind': 'image', 'target_id': target, 'filename': 'report.pdf', 'size': len(payload)}
            self.assertEqual(request('POST', '/api/attachment/begin', begin, token=False)[0], 403)
            code, raw = request('POST', '/api/attachment/begin', begin)
            self.assertEqual(code, 200)
            upload = json.loads(raw)['id']
            first = {'id': upload, 'sequence': 0, 'data': base64.b64encode(payload[:5000]).decode()}
            self.assertEqual(request('POST', '/api/attachment/chunk', first)[0], 200)
            self.assertEqual(request('POST', '/api/attachment/chunk', first)[0], 200)
            self.assertEqual(request('POST', '/api/attachment/finish', {'id': upload})[0], 400)
            rest = {'id': upload, 'sequence': 1, 'data': base64.b64encode(payload[5000:]).decode()}
            self.assertEqual(request('POST', '/api/attachment/chunk', rest)[0], 200)
            code, raw = request('POST', '/api/attachment/finish', {'id': upload})
            self.assertEqual(code, 200)
            ident = json.loads(raw)['id']
            self.assertEqual(request('GET', '/attachments/' + ident), (200, payload))
            self.assertEqual(db.state()['attachments'][0]['filename'], 'report.pdf')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == '__main__':
    unittest.main()
