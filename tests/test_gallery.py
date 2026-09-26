import base64
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/gallery.py'
SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="240"><text x="20" y="40">Sample</text></svg>'
PNG = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=')


class GalleryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / '图片 source'
        (self.source / '对照 A').mkdir(parents=True)
        (self.source / '对照 B').mkdir()
        (self.source / '对照 A/same.svg').write_text(SVG)
        (self.source / '对照 B/same.svg').write_text(SVG)
        (self.source / '对照 A/photo.png').write_bytes(PNG)
        (self.source / 'notes.txt').write_text('not an image')
        self.output = self.base / 'viewer'

    def cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True)

    def build(self, *extra):
        result = self.cli('build', '--input', self.source, '--output', self.output, *extra)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((self.output / 'manifest.json').read_text())

    def test_nested_unicode_duplicates_preserve_bytes_and_stable_ids(self):
        manifest = self.build()
        self.assertEqual(manifest['count'], 3)
        self.assertEqual(len({r['id'] for r in manifest['images']}), 3)
        self.assertEqual(len({r['download_name'] for r in manifest['images']}), 3)
        self.assertEqual({r['group'] for r in manifest['images']}, {'对照 A', '对照 B'})
        html = (self.output / 'index.html').read_text()
        self.assertIn(base64.b64encode(SVG.encode()).decode(), html)
        self.assertEqual((self.source / '对照 A/same.svg').read_text(), SVG)
        again = self.build('--update')
        self.assertEqual([r['id'] for r in manifest['images']], [r['id'] for r in again['images']])
        self.assertEqual(len(list((self.output / 'revisions').iterdir())), 2)

    def test_refuses_existing_output_without_update_and_foreign_output(self):
        self.build()
        result = self.cli('build', '--input', self.source, '--output', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('--update', result.stderr)
        foreign = self.base / 'foreign'
        foreign.mkdir()
        (foreign / 'index.html').write_text('user work')
        result = self.cli('build', '--input', self.source, '--output', foreign, '--update')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual((foreign / 'index.html').read_text(), 'user work')

    def test_config_rules_filters_and_literal_unsafe_titles(self):
        config = self.base / 'config.json'
        config.write_text(json.dumps({'title': '</script><script>alert(1)</script>',
            'roots': [{'id': 'study', 'path': str(self.source)}],
            'filters': [{'key': 'metric', 'label': '指标'}],
            'rules': [{'glob': '*.svg', 'set': {'fields': {'metric': '曲线'}, 'caption': '仅文件分类'}}],
            'overrides': {'study:对照 B/same.svg': {'group': '人工分组', 'title': '手动标题'}}}))
        result = self.cli('build', '--config', config, '--output', self.output)
        self.assertEqual(result.returncode, 0, result.stderr)
        m = json.loads((self.output / 'manifest.json').read_text())
        row = next(r for r in m['images'] if r['group'] == '人工分组')
        self.assertEqual(row['fields']['metric'], '曲线')
        self.assertEqual(row['title'], '手动标题')
        self.assertNotIn('</script><script>alert(1)</script>', (self.output / 'index.html').read_text())

    def test_output_under_input_and_symlinks_are_not_ingested(self):
        outside = self.base / 'outside.svg'
        outside.write_text(SVG)
        (self.source / 'linked.svg').symlink_to(outside)
        self.output = self.source / 'viewer'
        self.build()
        m = self.build('--update')
        self.assertEqual(m['count'], 3)
        self.assertTrue(any(s['reason'] == 'symlink' for s in m['skipped']))

    def test_empty_missing_corrupt_and_limits_fail_before_output(self):
        result = self.cli('build', '--input', self.base / 'absent', '--output', self.output)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())
        result = self.cli('build', '--input', self.source, '--output', self.output, '--max-images', '1')
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.output.exists())
        (self.source / 'bad.svg').write_text('<not-svg/>')
        m = self.build()
        self.assertEqual(m['count'], 3)
        self.assertTrue(any(s['reason'].startswith('invalid image') for s in m['skipped']))

    def test_inspect_does_not_create_output_and_reports_ignored_files(self):
        r = self.cli('inspect', '--input', self.source)
        self.assertEqual(r.returncode, 0, r.stderr)
        m = json.loads(r.stdout)
        self.assertEqual(m['count'], 3)
        self.assertTrue(any(s['reason'] == 'unsupported extension' for s in m['skipped']))
        self.assertFalse(self.output.exists())

    def test_duplicate_root_or_bad_rule_is_rejected(self):
        config = self.base / 'bad.json'
        config.write_text(json.dumps({'roots': [{'id': 'x', 'path': str(self.source)}, {'id': 'x', 'path': str(self.source)}]}))
        r = self.cli('inspect', '--config', config)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('unique', r.stderr)

    def test_zero_images_byte_limit_and_overlapping_roots(self):
        empty = self.base / 'empty'
        empty.mkdir()
        r = self.cli('build', '--input', empty, '--output', self.output)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('no readable', r.stderr)
        r = self.cli('build', '--input', self.source, '--output', self.output, '--max-mib', '0.00001')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('byte limit', r.stderr)
        r = self.cli('inspect', '--input', self.source, '--input', self.source / '对照 A')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('non-overlapping', r.stderr)

    def test_unknown_metadata_and_stale_override_are_visible(self):
        config = self.base / 'config.json'
        config.write_text(json.dumps({'roots': [{'id': 'x', 'path': str(self.source)}], 'overrides': {'x:absent.svg': {'caption': 'old'}}}))
        r = self.cli('inspect', '--config', config)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('Unmatched override', r.stdout)
        config.write_text(json.dumps({'roots': [{'id': 'x', 'path': str(self.source)}], 'rules': [{'glob': '*', 'set': {'source': 'malicious'}}]}))
        r = self.cli('inspect', '--config', config)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('may set only', r.stderr)

    def test_rejects_reserved_filter_and_malformed_display_metadata(self):
        config = self.base / 'config.json'
        for addition in ({'filters': [{'key': '__format', 'label': 'duplicate'}]},
                         {'groups': None}, {'description': []}, {'exclude': [123]},
                         {'rules': [{'glob': '*', 'root': 'typo', 'set': {'group': 'x'}}]}):
            with self.subTest(addition=addition):
                config.write_text(json.dumps({'roots': [{'id': 'x', 'path': str(self.source)}], **addition}))
                r = self.cli('inspect', '--config', config)
                self.assertNotEqual(r.returncode, 0)

    def test_loopback_serves_html_not_manifest_or_source(self):
        import urllib.error
        import urllib.request
        self.build()
        process = subprocess.Popen([sys.executable, str(SCRIPT), 'serve', '--output', str(self.output), '--port', '0'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        try:
            url = process.stdout.readline().strip()
            self.assertTrue(url.startswith('http://127.0.0.1:'))
            with urllib.request.urlopen(url, timeout=5) as response:
                self.assertIn(b'IMAGE COLLECTION', response.read())
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(url + 'manifest.json', timeout=5)
            self.assertEqual(caught.exception.code, 404)
            caught.exception.close()
        finally:
            process.terminate()
            process.wait(timeout=5)
            process.stdout.close()


if __name__ == '__main__':
    unittest.main()
