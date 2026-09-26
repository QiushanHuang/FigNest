#!/usr/bin/env python3
"""Read-only image importer and offline gallery builder. Python 3.10+, stdlib only."""
import argparse
import base64
import collections
import datetime as dt
import fnmatch
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import uuid
import xml.etree.ElementTree as ET

VERSION = '1.0.0'
OWNER = 'image-collection-viewer/v1'
MIMES = {'.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
         '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.gif': 'image/gif', '.bmp': 'image/bmp'}
TEMPLATE = Path(__file__).resolve().parents[1] / 'assets/viewer.html'


def dump(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def configure(args):
    config_path = Path(args.config).expanduser().resolve() if args.config else None
    cfg = json.loads(config_path.read_text()) if config_path else {}
    if not isinstance(cfg, dict):
        raise ValueError('config must be an object')
    unknown = set(cfg) - {'title', 'description', 'roots', 'filters', 'rules', 'overrides', 'groups', 'exclude'}
    if unknown:
        raise ValueError(f'unknown config keys: {sorted(unknown)}')
    if args.input and cfg.get('roots'):
        raise ValueError('use --input OR config roots, not both')
    roots = cfg.get('roots') or [{'id': f'root{i+1}', 'path': str(p)} for i, p in enumerate(args.input or [])]
    if not isinstance(roots, list) or not roots:
        raise ValueError('provide --input DIRECTORY or config roots')
    ids, locations = set(), set()
    for root in roots:
        if not isinstance(root, dict) or not isinstance(root.get('id'), str) or not isinstance(root.get('path'), str) or ('label' in root and not isinstance(root['label'], str)):
            raise ValueError('each root requires text id/path and optional text label')
        rid = root['id']
        if not re.fullmatch(r'[A-Za-z0-9_-]+', rid) or rid in ids:
            raise ValueError('root ids must be unique ASCII letters/digits/underscore/hyphen')
        p = Path(root['path']).expanduser()
        p = ((config_path.parent / p) if config_path and not p.is_absolute() else p).resolve()
        if not p.is_dir():
            raise ValueError(f'missing directory: {p}')
        if any(p == other or p.is_relative_to(other) or other.is_relative_to(p) for other in locations):
            raise ValueError('roots must be unique and non-overlapping')
        root['path'] = str(p)
        root.setdefault('label', rid)
        ids.add(rid)
        locations.add(p)
    cfg['roots'] = roots
    cfg['title'] = args.title or cfg.get('title', '图片分类看图器')
    cfg.setdefault('description', '按目录分类、筛选与并排比较；展示原图，不重新计算图内数据。')
    if not isinstance(cfg['title'], str) or not isinstance(cfg['description'], str):
        raise ValueError('title and description must be text')
    if not isinstance(cfg.get('groups', {}), dict) or not all(isinstance(v, str) for v in cfg.get('groups', {}).values()):
        raise ValueError('groups must map names to text descriptions')
    for key in ('filters', 'rules', 'exclude'):
        if key in cfg and not isinstance(cfg[key], list):
            raise ValueError(f'{key} must be a list')
    if not all(isinstance(g, str) for g in cfg.get('exclude', [])):
        raise ValueError('exclude patterns must be strings')
    if not isinstance(cfg.get('overrides', {}), dict):
        raise ValueError('overrides must be an object')
    filters = cfg.setdefault('filters', [])
    keys = set()
    for f in filters:
        if not isinstance(f, dict) or not isinstance(f.get('key'), str) or not f['key'] or f['key'].startswith('__') or f['key'] in keys or not isinstance(f.get('label'), str):
            raise ValueError('filters require unique key and text label')
        keys.add(f['key'])
    for rule in cfg.get('rules', []):
        if not isinstance(rule, dict) or not isinstance(rule.get('glob'), str) or not isinstance(rule.get('set'), dict):
            raise ValueError('each rule requires glob and set object')
        if 'root' in rule and rule['root'] not in ids:
            raise ValueError('rule root must match a configured root id')
    for patch in [r['set'] for r in cfg.get('rules', [])] + list(cfg.get('overrides', {}).values()):
        if not isinstance(patch, dict):
            raise ValueError('metadata patches must be objects')
        if set(patch) - {'title', 'group', 'caption', 'tags', 'fields'}:
            raise ValueError('rules may set only title, group, caption, tags, fields')
        for key in ('title', 'group', 'caption'):
            if key in patch and not isinstance(patch[key], str):
                raise ValueError(f'{key} must be text')
        if 'tags' in patch and (not isinstance(patch['tags'], list) or not all(isinstance(t, str) for t in patch['tags'])):
            raise ValueError('tags must be a list of strings')
        if 'fields' in patch and (not isinstance(patch['fields'], dict) or not all(isinstance(v, (str, int, float, bool)) for v in patch['fields'].values())):
            raise ValueError('fields must contain scalar metadata values')
    return cfg


def valid_image(data, ext):
    if ext == '.svg':
        root = ET.fromstring(data)
        return root.tag in ('svg', '{http://www.w3.org/2000/svg}svg')
    if ext == '.png':
        return data.startswith(b'\x89PNG\r\n\x1a\n') and len(data) >= 24
    if ext in ('.jpg', '.jpeg'):
        return data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9')
    if ext == '.webp':
        return data.startswith(b'RIFF') and data[8:12] == b'WEBP'
    if ext == '.gif':
        return data[:6] in (b'GIF87a', b'GIF89a')
    if ext == '.bmp':
        return data.startswith(b'BM')
    return False


def apply_metadata(row, patch):
    for key, value in patch.items():
        if key == 'fields':
            row['fields'].update({k: str(v) for k, v in value.items()})
        else:
            row[key] = value


def collect(cfg, output, max_images, max_bytes, allow_files=False):
    rows, assets, skipped = [], {}, []
    total = 0
    seen_keys = set()
    for root in cfg['roots']:
        base = Path(root['path'])
        if output and (base == output or base.is_relative_to(output)):
            raise ValueError('output cannot contain an input root')
        for directory, dirs, files in os.walk(base, followlinks=False):
            directory = Path(directory)
            retained = []
            for name in sorted(dirs):
                p = directory / name
                rel = p.relative_to(base).as_posix()
                reason = ('symlink' if p.is_symlink() else 'hidden directory' if name.startswith('.') else
                          'output directory' if output and p.resolve() == output else
                          'excluded' if any(fnmatch.fnmatchcase(rel, g) for g in cfg.get('exclude', [])) else None)
                if reason:
                    skipped.append({'source_key': root['id'] + ':' + rel, 'reason': reason})
                else:
                    retained.append(name)
            dirs[:] = retained
            for name in sorted(files):
                p = directory / name
                rel = p.relative_to(base).as_posix()
                key = root['id'] + ':' + rel
                ext = p.suffix.lower()
                reason = ('symlink' if p.is_symlink() else 'hidden file' if name.startswith('.') else
                          'excluded' if any(fnmatch.fnmatchcase(rel, g) for g in cfg.get('exclude', [])) else
                          'unsupported extension' if ext not in MIMES and not allow_files else None)
                if reason:
                    skipped.append({'source_key': key, 'reason': reason})
                    continue
                stat = p.stat()
                if total + stat.st_size > max_bytes:
                    raise ValueError('source byte limit exceeded; split the collection or explicitly raise --max-mib')
                try:
                    data = p.read_bytes()
                    if ext in MIMES and not valid_image(data, ext):
                        raise ValueError('signature/root check failed')
                except (ValueError, ET.ParseError) as exc:
                    skipped.append({'source_key': key, 'reason': f'invalid image: {exc}'})
                    continue
                if total + len(data) > max_bytes:
                    raise ValueError('source byte limit exceeded during read')
                if len(rows) >= max_images:
                    raise ValueError('image count limit exceeded; split the collection or explicitly raise --max-images')
                ident = uuid.uuid5(uuid.NAMESPACE_URL, key).hex
                row = {'id': ident, 'source_key': key, 'root_id': root['id'], 'root_label': root['label'],
                       'relative_path': rel, 'filename': name, 'title': p.stem,
                       'group': Path(rel).parts[0] if len(Path(rel).parts) > 1 else '未分组',
                       'caption': '', 'tags': [], 'fields': {}, 'format': ext[1:].upper(),
                       'bytes': len(data), 'modified_ns': stat.st_mtime_ns,
                       'download_name': ident[:10] + '_' + name}
                for rule in cfg.get('rules', []):
                    if fnmatch.fnmatchcase(rel, rule['glob']) and rule.get('root', root['id']) == root['id']:
                        apply_metadata(row, rule['set'])
                apply_metadata(row, cfg.get('overrides', {}).get(key, {}))
                row['group'] = row['group'] or '未分组'
                rows.append(row)
                assets[ident] = 'data:' + MIMES.get(ext, 'application/octet-stream') + ';base64,' + base64.b64encode(data).decode('ascii')
                total += len(data)
                seen_keys.add(key)
    if not rows:
        raise ValueError('no readable supported images found; inspect paths/extensions')
    unknown_overrides = sorted(set(cfg.get('overrides', {})) - seen_keys)
    return rows, assets, skipped, total, unknown_overrides


def build(args):
    cfg = configure(args)
    output = Path(args.output).expanduser().resolve() if args.output else None
    rows, assets, skipped, total, unknown = collect(cfg, output, args.max_images, int(args.max_mib * 1024 ** 2))
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    manifest = {'owner': OWNER, 'version': VERSION, 'generated_at': stamp, 'title': cfg['title'],
                'description': cfg['description'], 'roots': cfg['roots'], 'count': len(rows), 'source_bytes': total,
                'by_group': dict(collections.Counter(r['group'] for r in rows)), 'images': rows,
                'filters': cfg['filters'], 'groups': cfg.get('groups', {}), 'skipped': skipped,
                'warnings': ([f'Unmatched override: {x}' for x in unknown] +
                             ['Original SVG bytes are preserved; scripts/external resources are not sanitized. Preview uses an isolated image context.']),
                'validation': 'SVG XML and raster signatures checked; full raster decoding is a browser check.'}
    if args.command == 'inspect':
        print(dump(manifest))
        return
    if output.exists() and any(output.iterdir()):
        marker = output / '.image-collection-viewer.json'
        if not marker.is_file() or json.loads(marker.read_text()).get('owner') != OWNER:
            raise ValueError('output contains foreign files; choose a new empty directory')
        if not args.update:
            raise ValueError('existing gallery: use --update to retain history and refresh current view')
    output.mkdir(parents=True, exist_ok=True)
    lock = output / '.build.lock'
    try:
        lock_fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('build lock exists; verify no build is active before recovering the lock')
    try:
        os.close(lock_fd)
        revision = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        dest = output / 'revisions' / revision
        dest.mkdir(parents=True)
        payload = {k: v for k, v in manifest.items() if k not in ('roots', 'skipped', 'warnings')}
        payload['assets'] = assets
        # JSON in an inert script element; untrusted labels never enter HTML markup.
        encoded = json.dumps(payload, ensure_ascii=False).replace('<', '\\u003c').replace('&', '\\u0026')
        html = TEMPLATE.read_text().replace('<!-- CATALOG_JSON -->', encoded)
        (dest / 'index.html').write_text(html)
        (dest / 'manifest.json').write_text(dump(manifest))
        (dest / 'config.json').write_text(dump(cfg))
        for name, text in [('index.html', html), ('manifest.json', dump(manifest)),
                           ('config.json', dump(cfg)), ('.image-collection-viewer.json', dump({'owner': OWNER, 'revision': revision}))]:
            temporary = output / (name + '.tmp')
            temporary.write_text(text)
            temporary.replace(output / name)
        print(dump({'index': str(output / 'index.html'), 'revision': revision, 'count': len(rows),
                    'source_bytes': total, 'html_bytes': len(html.encode()), 'skipped': len(skipped),
                    'warnings': manifest['warnings'], 'by_group': manifest['by_group']}))
    finally:
        lock.unlink()


def serve(args):
    root = Path(args.output).expanduser().resolve()
    if not (root / 'index.html').is_file():
        raise ValueError('build a gallery before serving it')

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(root), **kw)

        def send_head(self):
            from urllib.parse import unquote, urlsplit
            relative = unquote(urlsplit(self.path).path).lstrip('/') or 'index.html'
            target = (root / relative).resolve()
            # Only gallery HTML, not local configs, source paths, directory listings or symlinks.
            if not target.is_relative_to(root) or target.name != 'index.html' or not target.is_file():
                self.send_error(404)
                return None
            return super().send_head()

    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'http://127.0.0.1:{server.server_port}/', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('inspect', 'build'):
        p = sub.add_parser(name)
        p.add_argument('--input', action='append', help='image directory; repeat for multiple non-overlapping roots')
        p.add_argument('--config', help='JSON configuration; relative root paths resolve from this file')
        p.add_argument('--title')
        p.add_argument('--output', required=name == 'build')
        p.add_argument('--max-images', type=int, default=5000)
        p.add_argument('--max-mib', type=float, default=256)
        p.add_argument('--update', action='store_true')
    p = sub.add_parser('serve')
    p.add_argument('--output', required=True)
    p.add_argument('--port', type=int, default=0, help='0 chooses a free loopback port')
    args = parser.parse_args()
    try:
        serve(args) if args.command == 'serve' else build(args)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
