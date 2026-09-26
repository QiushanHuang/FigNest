"""UI-only packaging path: mock signing, exercise actual filesystem copies."""
import importlib.util
from pathlib import Path
import plistlib
import tempfile
import unittest
from unittest.mock import patch

path = Path(__file__).resolve().parents[1] / 'native/build_app.py'
spec = importlib.util.spec_from_file_location('packager', path)
packager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(packager)

class PackagingTests(unittest.TestCase):
    def test_release_metadata_is_shared_by_packager_and_backend(self):
        self.assertTrue(hasattr(packager,'app_info'), 'shared About/release metadata missing')
        import sys
        sys.path.insert(0,str(path.parents[1] / 'scripts'))
        import library
        info=packager.app_info()
        self.assertEqual(info['version'],library.VERSION)
        self.assertEqual(info['copyright'],'© 2026 Qiushan Huang')
        self.assertEqual(info['repository'],'https://github.com/QiushanHuang/FigNest')

    def test_native_settings_menu_contract(self):
        import sys
        if sys.platform != 'darwin': self.skipTest('AppKit is macOS-only')
        source=path.parent/'AppMenu.swift'
        self.assertTrue(source.exists(),'native Settings/About menu missing')
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'menu-tests'
            subprocess.run(['/usr/bin/swiftc','-framework','AppKit',str(source),str(path.parent/'MenuTests.swift'),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

    def test_sync_updates_all_workspace_assets_and_preserves_previous(self):
        with tempfile.TemporaryDirectory() as d:
            app = Path(d) / 'FigNest.app'
            target = app / 'Contents/Resources/backend/assets'
            target.mkdir(parents=True)
            (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'local.joshua.tuxia','CFBundleShortVersionString':packager.app_info()['version']}))
            for name in ('library.html','workspace.js','workspace.css','workspace-core.js','viewer.html','logo.svg'):
                (target / name).write_text('previous '+name)
            with patch.object(packager, 'run'):
                packager.sync_ui(app)
            self.assertEqual((target / 'workspace.js').read_bytes(), (packager.SKILL / 'assets/workspace.js').read_bytes())
            previous = list((app / 'Contents/Resources/previous-ui').rglob('workspace.js'))
            self.assertEqual(len(previous),1)
            self.assertEqual(previous[0].read_text(),'previous workspace.js')

if __name__ == '__main__': unittest.main()
