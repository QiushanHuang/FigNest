"""Build a local macOS application with a bundled Python backend and WebKit window."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile

SKILL = Path(__file__).resolve().parents[1]


def app_info():
    return json.loads((SKILL / 'assets/app-info.json').read_text())


def run(command):
    subprocess.run(command, check=True)


def minimum_system_version(app, floor='13.0'):
    """Include the deployment requirements of Python and every bundled dylib."""
    versions = [floor]
    magic = {b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xce\xfa\xed\xfe',
             b'\xfe\xed\xfa\xce', b'\xca\xfe\xba\xbe', b'\xbe\xba\xfe\xca',
             b'\xca\xfe\xba\xbf', b'\xbf\xba\xfe\xca'}
    for binary in Path(app).rglob('*'):
        if not binary.is_file() or binary.is_symlink():
            continue
        with binary.open('rb') as file:
            if file.read(4) not in magic:
                continue
        info = subprocess.check_output(['xcrun', 'vtool', '-show-build', str(binary)], text=True)
        for block in re.split(r'Load command \d+', info):
            field = 'minos' if 'LC_BUILD_VERSION' in block else 'version' if 'LC_VERSION_MIN_MACOSX' in block else None
            if field:
                value = re.search(r'^\s*' + field + r'\s+(\d+(?:\.\d+)+)\s*$', block, re.M)
                if value:
                    versions.append(value.group(1))
    return max(versions, key=lambda value: tuple(int(part) for part in value.split('.')))


def sync_ui(output):
    output = Path(output).expanduser().resolve()
    info = output / 'Contents/Info.plist'
    if not info.is_file() or plistlib.loads(info.read_bytes()).get('CFBundleIdentifier') != 'local.joshua.tuxia':
        raise RuntimeError('UI sync requires the installed 图匣 application')
    if plistlib.loads(info.read_bytes()).get('CFBundleShortVersionString') != app_info()['version']:
        raise RuntimeError('Version changes require a full backend build before UI-only updates')
    backend = output / 'Contents/Resources/backend'
    target = next((folder for folder in (backend / 'assets', backend / '_internal/assets')
                   if (folder / 'library.html').is_file()), None)
    if target is None:
        raise RuntimeError('installed HTML asset is missing')
    history = output / 'Contents/Resources/previous-ui'
    history.mkdir(exist_ok=True)
    previous = history / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    previous.mkdir()
    for name in ('library.html', 'workspace.css', 'workspace.js', 'workspace-core.js', 'settings.js', 'viewer.html', 'logo.svg', 'icon.png', 'app-info.json', 'image-tools-core.js', 'image-tools.js', 'image-tools.css'):
        if (target / name).exists():
            shutil.copy2(target / name, previous / name)
        shutil.copy2(SKILL / 'assets' / name, target / name)
    run(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', str(output)])
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(output)])
    print(json.dumps({'application': str(output), 'previous_ui': str(previous), 'current_ui': str(target)}, ensure_ascii=False))


def build(output, replace=False):
    stage = Path(tempfile.mkdtemp(prefix='image-viewer-app-build-')).resolve()
    dist = stage / 'dist'
    work = stage / 'work'
    app = stage / '图匣.app'
    app_macos = app / 'Contents/MacOS'
    app_resources = app / 'Contents/Resources'
    app_macos.mkdir(parents=True)
    app_resources.mkdir(parents=True)
    python = Path(sys.executable)
    if not python.is_file():
        raise RuntimeError('Run this builder with Python 3.10+ and PyInstaller installed')
    run([str(python), '-m', 'PyInstaller', '--noconfirm', '--onedir', '--name', 'library-backend',
         '--distpath', str(dist), '--workpath', str(work), '--specpath', str(stage),
         '--add-data', str(SKILL / 'assets') + ':assets', str(SKILL / 'scripts/library.py')])
    shutil.copytree(dist / 'library-backend', app_resources / 'backend', symlinks=True)
    for link in (app_resources / 'backend').rglob('*'):
        if link.is_symlink() and not link.resolve().is_relative_to(app_resources / 'backend'):
            raise RuntimeError('Standalone backend contains an external symlink: ' + str(link))
    run(['/usr/bin/swiftc', '-target', 'arm64-apple-macosx13.0', '-framework', 'AppKit', '-framework', 'WebKit',
         str(SKILL / 'native/AppMenu.swift'), str(SKILL / 'native/ImageToolPolicy.swift'), str(SKILL / 'native/MacViewer.swift'), '-o', str(app_macos / '图匣')])
    iconset = stage / 'AppIcon.iconset'
    iconset.mkdir()
    for side in (16, 32, 128, 256, 512):
        run(['/usr/bin/sips', '-z', str(side), str(side), str(SKILL / 'assets/icon.png'),
             '--out', str(iconset / f'icon_{side}x{side}.png')])
        run(['/usr/bin/sips', '-z', str(side * 2), str(side * 2), str(SKILL / 'assets/icon.png'),
             '--out', str(iconset / f'icon_{side}x{side}@2x.png')])
    run(['/usr/bin/iconutil', '-c', 'icns', str(iconset), '-o', str(app_resources / 'AppIcon.icns')])
    release = app_info()
    notices = SKILL / 'THIRD_PARTY_NOTICES.md'
    if notices.is_file():
        shutil.copy2(notices, app_resources / notices.name)
        shutil.copytree(SKILL / 'assets/licenses', app_resources / 'assets/licenses')
    info = {'CFBundleName': release['name'], 'CFBundleDisplayName': release['display_name'],
            'CFBundleExecutable': '图匣', 'CFBundleIdentifier': 'local.joshua.tuxia',
            'CFBundleIconFile': 'AppIcon', 'CFBundlePackageType': 'APPL', 'CFBundleShortVersionString': release['version'],
            'CFBundleVersion': release['build'], 'NSHumanReadableCopyright': release['copyright'],
            'FigNestRepositoryURL': release['repository'], 'LSMinimumSystemVersion': minimum_system_version(app),
            'NSHighResolutionCapable': True}
    with (app / 'Contents/Info.plist').open('wb') as file:
        plistlib.dump(info, file)
    run(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', str(app)])
    run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)])
    output = Path(output).expanduser().resolve()
    previous = None
    if output.exists():
        if not replace:
            raise RuntimeError('Application destination exists; use --replace to preserve it as a versioned backup')
        old_info = output / 'Contents/Info.plist'
        if not old_info.is_file() or plistlib.loads(old_info.read_bytes()).get('CFBundleIdentifier') != info['CFBundleIdentifier']:
            raise RuntimeError('Application destination belongs to a different app; choose another path')
        previous = output.with_name(output.stem + '-backup-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '.app')
        if previous.exists():
            raise RuntimeError('Backup destination already exists; retry later')
        output.rename(previous)
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(app, output, symlinks=True)
    print(json.dumps({'application': str(output), 'previous_application': str(previous) if previous else None, 'build_stage': str(stage),
                      'backend': str(output / 'Contents/Resources/backend/library-backend'),
                      'signed': 'ad hoc local signature', 'notarized': False}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', required=True)
    parser.add_argument('--replace', action='store_true')
    parser.add_argument('--sync-ui', action='store_true')
    args = parser.parse_args()
    if args.sync_ui:
        sync_ui(args.output)
    else:
        build(args.output, args.replace)
