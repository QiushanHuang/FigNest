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
    def test_image_download_origin_policy(self):
        import sys
        if sys.platform != 'darwin': self.skipTest('native policy compilation is macOS-only')
        source=path.parent/'ImageToolPolicy.swift'
        self.assertTrue(source.exists(),'native image export download policy is missing')
        import subprocess
        with tempfile.TemporaryDirectory() as d:
            binary=Path(d)/'policy-tests'
            subprocess.run(['/usr/bin/swiftc',str(source),str(path.parent/'ImageToolPolicyTests.swift'),'-o',str(binary)],check=True)
            subprocess.run([str(binary)],check=True)

    def test_system_requirement_covers_every_bundled_runtime_binary(self):
        with tempfile.TemporaryDirectory() as d:
            app = Path(d)
            for name in ('native', 'python', 'ssl'):
                (app / name).write_bytes(b'\xcf\xfa\xed\xfe' + b'fixture')
            (app / 'readme.txt').write_text('ordinary resource')
            versions = {'native': '13.0', 'python': '27.0', 'ssl': '26.0'}
            def build_info(command, **kwargs):
                return 'Load command 0\n      cmd LC_BUILD_VERSION\n platform MACOS\n    minos ' + versions[Path(command[-1]).name] + '\n      sdk 27.0\n'
            with patch.object(packager.subprocess, 'check_output', side_effect=build_info):
                self.assertEqual(packager.minimum_system_version(app), '27.0')
            for name in versions: versions[name] = '11.0'
            with patch.object(packager.subprocess, 'check_output', side_effect=build_info):
                self.assertEqual(packager.minimum_system_version(app), '13.0')

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

    def test_sync_supports_pyinstaller_internal_assets_layout(self):
        with tempfile.TemporaryDirectory() as d:
            app=Path(d)/'FigNest.app'
            target=app/'Contents/Resources/backend/_internal/assets'
            target.mkdir(parents=True)
            (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':'local.joshua.tuxia','CFBundleShortVersionString':packager.app_info()['version']}))
            (target/'library.html').write_text('previous internal UI')
            with patch.object(packager,'run'):
                packager.sync_ui(app)
            self.assertEqual((target/'image-tools.js').read_bytes(),(packager.SKILL/'assets/image-tools.js').read_bytes())
            saved=list((app/'Contents/Resources/previous-ui').rglob('library.html'))
            self.assertEqual(saved[0].read_text(),'previous internal UI')

if __name__ == '__main__': unittest.main()
