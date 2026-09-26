#!/usr/bin/env python3
"""Persistent local image libraries. Python 3.10+, standard library only."""
import argparse
import base64
import binascii
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import secrets
import shlex
import signal
import sqlite3
import subprocess
import sys
import threading
import time
import tempfile
from types import SimpleNamespace
from urllib.parse import urlsplit, quote
import urllib.request
import uuid
import webbrowser
import gallery

DEFAULT_DATA = Path.home() / 'Pictures/ImageCollectionViewer'
ASSETS = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[1])) / 'assets'
APP_INFO = json.loads((ASSETS / 'app-info.json').read_text())
VERSION = APP_INFO['version']
gallery.TEMPLATE = ASSETS / 'viewer.html'
MAX_BYTES = 256 * 1024 ** 2
UNSET = object()
IMPORT_DEFAULTS = {'folder_id': None, 'tags': [], 'hierarchy': False, 'auto_export': True}
PREFERENCE_DEFAULTS = {'theme': 'light', 'layout': 'grid', 'thumbnail': 260, 'inspector': True, 'sort': 'name'}


def asset_kind(filename):
    ext = Path(filename).suffix.lower()
    if ext in gallery.MIMES:
        return 'image'
    if ext in ('.mp4', '.mov', '.webm', '.mkv'):
        return 'video'
    if ext in ('.mp3', '.wav', '.m4a', '.flac', '.ogg'):
        return 'audio'
    if ext in ('.pdf', '.csv', '.tsv', '.json', '.txt', '.md', '.docx', '.xlsx', '.pptx', '.html'):
        return 'document'
    return 'file'


def tags_value(value):
    if not isinstance(value, list) or len(value) > 100:
        raise ValueError('tags must be a list of at most 100 names')
    return list(dict.fromkeys(text(t, 'tag', 80).strip() for t in value if isinstance(t, str) and t.strip()))


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False)


def uid():
    return uuid.uuid4().hex


def text(value, label, maximum=20000):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError(f'{label}: expected text, at most {maximum} characters')
    return value


def boolean(value):
    if type(value) is not bool:
        raise ValueError('expected true or false')
    return int(value)


class Store:
    def __init__(self, directory):
        self.root = Path(directory).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        for name in ('blobs', 'exports', 'backups', 'managed', 'incoming'):
            (self.root / name).mkdir(exist_ok=True)
        self.database = self.root / 'library.sqlite3'
        with self.db() as c:
            version = c.execute('PRAGMA user_version').fetchone()[0]
            if version not in (0, 1, 2, 3, 4, 5, 6):
                raise ValueError('unsupported database version; preserve it and use its matching program')
            if version in (1, 2, 3, 4, 5):
                self.backup()
            if version == 0:
                c.executescript('''
                CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT);
                CREATE TABLE IF NOT EXISTS libraries(id TEXT PRIMARY KEY,name TEXT NOT NULL,description TEXT,
                  source_config TEXT,created TEXT,updated TEXT,revision INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY,library_id TEXT REFERENCES libraries(id),
                  source_key TEXT,metadata TEXT,blob TEXT,favorite INTEGER DEFAULT 0,hidden INTEGER DEFAULT 0,
                  note TEXT DEFAULT '',missing INTEGER DEFAULT 0,created TEXT,updated TEXT,
                  UNIQUE(library_id,source_key));
                CREATE TABLE IF NOT EXISTS versions(id TEXT PRIMARY KEY,image_id TEXT REFERENCES images(id),
                  blob TEXT,metadata TEXT,created TEXT);
                CREATE TABLE IF NOT EXISTS groups(library_id TEXT REFERENCES libraries(id),name TEXT,
                  favorite INTEGER DEFAULT 0,note TEXT DEFAULT '',PRIMARY KEY(library_id,name));
                CREATE TABLE IF NOT EXISTS folders(id TEXT PRIMARY KEY,name TEXT UNIQUE,created TEXT);
                CREATE TABLE IF NOT EXISTS membership(folder_id TEXT REFERENCES folders(id),
                  image_id TEXT REFERENCES images(id),PRIMARY KEY(folder_id,image_id));
                CREATE TABLE IF NOT EXISTS imports(id TEXT PRIMARY KEY,library_id TEXT REFERENCES libraries(id),
                  created TEXT,summary TEXT);
                CREATE TABLE IF NOT EXISTS exports(id TEXT PRIMARY KEY,created TEXT,library_id TEXT,
                  folder_id TEXT,include_hidden INTEGER,count INTEGER,path TEXT,revisions TEXT);
                PRAGMA user_version=1;
            ''')
            if version in (0, 1, 2):
                for table in ('libraries', 'images', 'folders'):
                    if not any(x['name'] == 'deleted_at' for x in c.execute(f'PRAGMA table_info({table})')):
                        c.execute(f'ALTER TABLE {table} ADD COLUMN deleted_at TEXT')
            if version in (0, 1, 2, 3):
                if not any(x['name'] == 'renamed_title' for x in c.execute('PRAGMA table_info(images)')):
                    c.execute('ALTER TABLE images ADD COLUMN renamed_title TEXT')
                c.execute('PRAGMA user_version=4')
            if version in (0, 1, 2, 3, 4):
                c.execute('''CREATE TABLE IF NOT EXISTS attachments(
                  id TEXT PRIMARY KEY,kind TEXT NOT NULL,target_id TEXT NOT NULL,
                  filename TEXT NOT NULL,blob TEXT NOT NULL,size INTEGER NOT NULL,
                  created TEXT NOT NULL,deleted_at TEXT)''')
                c.execute('PRAGMA user_version=5')
            if version < 6:
                c.executescript('''
                  BEGIN IMMEDIATE;
                  CREATE TEMP TABLE saved_folders AS SELECT * FROM folders;
                  CREATE TEMP TABLE saved_membership AS SELECT * FROM membership;
                  DROP TABLE membership;
                  DROP TABLE folders;
                  CREATE TABLE folders(id TEXT PRIMARY KEY,name TEXT NOT NULL,created TEXT,deleted_at TEXT,
                    parent_id TEXT,kind TEXT NOT NULL DEFAULT 'manual',query TEXT NOT NULL DEFAULT '{}');
                  INSERT INTO folders(id,name,created,deleted_at) SELECT id,name,created,deleted_at FROM saved_folders;
                  CREATE UNIQUE INDEX folder_sibling_names ON folders(COALESCE(parent_id,''),name) WHERE deleted_at IS NULL;
                  CREATE TABLE membership(folder_id TEXT REFERENCES folders(id),image_id TEXT REFERENCES images(id),
                    PRIMARY KEY(folder_id,image_id));
                  INSERT INTO membership SELECT * FROM saved_membership;
                  DROP TABLE saved_membership;
                  DROP TABLE saved_folders;
                  COMMIT;
                ''')
                for table, column, declaration in [('images', 'user_tags', "TEXT NOT NULL DEFAULT '[]'"),
                                                   ('libraries', 'import_options', "TEXT NOT NULL DEFAULT '{}'" )]:
                    if not any(x['name'] == column for x in c.execute(f'PRAGMA table_info({table})')):
                        c.execute(f'ALTER TABLE {table} ADD COLUMN {column} {declaration}')
                c.execute('PRAGMA user_version=6')
            c.execute('INSERT OR IGNORE INTO meta VALUES (?,?)', ('store_id', uid()))
            self.store_id = c.execute('SELECT value FROM meta WHERE key=?', ('store_id',)).fetchone()[0]

    @contextmanager
    def db(self):
        with self.lock:
            c = sqlite3.connect(self.database, timeout=30)
            c.row_factory = sqlite3.Row
            c.execute('PRAGMA foreign_keys=ON')
            try:
                with c:
                    yield c
            finally:
                c.close()

    @contextmanager
    def write_lock(self):
        with self.lock:
            depth = getattr(self, '_write_lock_depth', 0)
            if depth:
                self._write_lock_depth = depth + 1
                try:
                    yield
                finally:
                    self._write_lock_depth -= 1
                return
            with (self.root / '.content-write.lock').open('a+b') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX)
                self._write_lock_depth = 1
                try:
                    yield
                finally:
                    self._write_lock_depth = 0
                    fcntl.flock(lock, fcntl.LOCK_UN)

    def backup(self):
        path = self.root / 'backups' / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.sqlite3')
        with self.db() as source:
            dest = sqlite3.connect(path)
            try:
                source.backup(dest)
            finally:
                dest.close()
        return str(path)

    def storage_info(self):
        with self.db() as c:
            libraries = c.execute('SELECT COUNT(*) FROM libraries WHERE deleted_at IS NULL').fetchone()[0]
            assets = c.execute('SELECT COUNT(*) FROM images i JOIN libraries l ON i.library_id=l.id WHERE i.deleted_at IS NULL AND l.deleted_at IS NULL').fetchone()[0]
        managed_bytes = sum(p.stat().st_size for p in (self.root/'blobs').iterdir() if p.is_file() and not p.is_symlink())
        return {'path':str(self.root), 'database':str(self.database), 'managed_bytes':managed_bytes,
                'database_bytes':self.database.stat().st_size, 'libraries':libraries, 'assets':assets,
                'app':APP_INFO}

    @staticmethod
    def require(c, table, ident, with_deleted=False):
        if table not in ('images', 'libraries', 'folders', 'attachments'):
            raise ValueError('invalid table')
        row = c.execute(f'SELECT * FROM {table} WHERE id=?', (ident,)).fetchone()
        if not row:
            raise ValueError(f'unknown {table} id')
        if row['deleted_at'] and not with_deleted:
            raise ValueError(f'{table} is in the library trash')
        if table == 'images' and not with_deleted:
            parent = c.execute('SELECT deleted_at FROM libraries WHERE id=?', (row['library_id'],)).fetchone()
            if not parent or parent['deleted_at']:
                raise ValueError('image library is in the trash')
        if table == 'folders' and not with_deleted:
            parent = row['parent_id']
            seen = {ident}
            while parent:
                ancestor = c.execute('SELECT * FROM folders WHERE id=?', (parent,)).fetchone()
                if not ancestor or ancestor['deleted_at'] or parent in seen:
                    raise ValueError('folder parent is unavailable')
                seen.add(parent)
                parent = ancestor['parent_id']
        return row

    @staticmethod
    def validate_attachment_target(c, kind, target_id):
        if kind == 'image':
            image = Store.require(c, 'images', target_id)
            return image['library_id']
        if kind == 'group':
            lid, separator, name = target_id.partition('::')
            if not separator or not name:
                raise ValueError('invalid group attachment target')
            Store.require(c, 'libraries', lid)
            if not c.execute('SELECT 1 FROM groups WHERE library_id=? AND name=?', (lid, name)).fetchone():
                raise ValueError('unknown group attachment target')
            return lid
        raise ValueError('attachments may be added to images or groups')

    @staticmethod
    def validate_attachment_name(filename):
        name = text(filename, 'attachment filename', 300)
        if not name or name in ('.', '..') or '/' in name or '\\' in name or '\x00' in name:
            raise ValueError('attachment requires a plain filename without path separators')
        return name

    def add_attachment(self, kind, target_id, filename, data):
        self.validate_attachment_name(filename)
        if not isinstance(data, bytes) or len(data) > 2 * 1024 ** 3:
            raise ValueError('attachment must be bytes up to 2 GiB')
        with self.write_lock():
            with self.db() as c:
                lid = self.validate_attachment_target(c, kind, target_id)
                digest = self.save_blob(data)
                ident = uid()
                c.execute('INSERT INTO attachments(id,kind,target_id,filename,blob,size,created) VALUES (?,?,?,?,?,?,?)',
                          (ident, kind, target_id, filename, digest, len(data), now()))
                self.bump(c, lid)
        return {'id': ident, 'filename': filename, 'size': len(data)}

    def add_attachment_file(self, kind, target_id, filename, source, digest, size):
        self.validate_attachment_name(filename)
        source = Path(source).resolve()
        if not source.is_relative_to((self.root / 'incoming').resolve()) or not source.is_file():
            raise ValueError('invalid temporary attachment')
        if size < 0 or size > 2 * 1024 ** 3 or source.stat().st_size != size:
            raise ValueError('attachment size changed during upload')
        with self.write_lock():
            with self.db() as c:
                lid = self.validate_attachment_target(c, kind, target_id)
                target = self.blob_path(digest)
                if target.exists():
                    source.unlink()
                else:
                    source.replace(target)
                ident = uid()
                c.execute('INSERT INTO attachments(id,kind,target_id,filename,blob,size,created) VALUES (?,?,?,?,?,?,?)',
                          (ident, kind, target_id, filename, digest, size, now()))
                self.bump(c, lid)
        return {'id': ident, 'filename': filename, 'size': size}

    def attachment_info(self, ident):
        with self.db() as c:
            item = self.require(c, 'attachments', ident)
            self.validate_attachment_target(c, item['kind'], item['target_id'])
            result = dict(item)
        result['path'] = self.blob_path(result['blob'])
        return result

    def get_attachment(self, ident):
        item = self.attachment_info(ident)
        return {**item, 'bytes': item['path'].read_bytes()}

    def reveal_attachment(self, ident):
        item = self.attachment_info(ident)
        home = (self.root / 'managed' / 'attachments' / item['target_id'].replace('::', '_')).resolve()
        path = (home / (item['id'] + '-' + item['filename'])).resolve()
        if not path.is_relative_to(home):
            raise ValueError('attachment path escapes managed storage')
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != item['blob']:
            shutil.copyfile(item['path'], path)
        subprocess.run(['/usr/bin/open', '-R', str(path)], check=True, timeout=10)
        return {'path': str(path), 'source': 'managed attachment'}

    @staticmethod
    def bump(c, lid):
        c.execute('UPDATE libraries SET revision=revision+1,updated=? WHERE id=?', (now(), lid))

    def blob_path(self, digest):
        if len(digest) != 64 or any(ch not in '0123456789abcdef' for ch in digest):
            raise ValueError('invalid blob identity')
        return self.root / 'blobs' / digest

    def save_blob(self, data):
        digest = hashlib.sha256(data).hexdigest()
        path = self.blob_path(digest)
        if not path.exists():
            tmp = path.with_suffix('.' + uid() + '.tmp')
            tmp.write_bytes(data)
            tmp.replace(path)
        return digest

    def collect_files(self, cfg):
        return gallery.collect(cfg, self.root, 5000, MAX_BYTES, allow_files=True)

    def import_directory(self, directory=None, name=None, library_id=None, config=None, all_files=False, options=None):
        args = SimpleNamespace(config=str(config) if config else None, input=[str(directory)] if directory else None, title=name)
        cfg = gallery.configure(args)
        if all_files:
            cfg['asset_mode'] = 'all'
        rows, assets, skipped, total, unknown = (self.collect_files(cfg) if cfg.get('asset_mode') == 'all' else
                                                gallery.collect(cfg, self.root, 5000, MAX_BYTES))
        records = [(r, base64.b64decode(assets[r['id']].split(',', 1)[1])) for r in rows]
        return self.ingest(records, name or cfg['title'], cfg['description'], library_id, cfg, skipped, unknown, True, options)

    def refresh(self, lid):
        with self.db() as c:
            lib = dict(self.require(c, 'libraries', lid))
        if not lib['source_config']:
            raise ValueError('browser-imported library: select its files/folder again to update')
        cfg = json.loads(lib['source_config'])
        rows, assets, skipped, total, unknown = (self.collect_files(cfg) if cfg.get('asset_mode') == 'all' else
                                                gallery.collect(cfg, self.root, 5000, MAX_BYTES))
        return self.ingest([(r, base64.b64decode(assets[r['id']].split(',', 1)[1])) for r in rows],
                           lib['name'], lib['description'], lid, cfg, skipped, unknown, True)

    def import_uploads(self, name, files, library_id=None, replace=False, options=None):
        text(name, 'name', 300)
        if not name.strip() or not isinstance(files, list) or not files or len(files) > 5000:
            raise ValueError('a name and 1–5000 files are required')
        if library_id:
            with self.db() as c:
                self.require(c, 'libraries', library_id)
        rows, seen, total, skipped = [], set(), 0, []
        for item in files:
            name_path = text(item.get('path'), 'relative path', 2000)
            path = PurePosixPath(name_path)
            if path.is_absolute() or '..' in path.parts or '\\' in name_path or ':' in name_path or not path.name:
                raise ValueError('invalid relative upload path')
            rel = str(path)
            if rel in seen:
                raise ValueError('duplicate upload path')
            seen.add(rel)
            ext = path.suffix.lower()
            if '\x00' in name_path or any(ord(ch) < 32 for ch in name_path):
                raise ValueError('invalid control character in upload path')
            if any(p.startswith('.') for p in path.parts):
                skipped.append({'source_key': 'browser:' + rel, 'reason': 'hidden'})
                continue
            try:
                data = base64.b64decode(item['data'], validate=True)
                valid = gallery.valid_image(data, ext) if ext in gallery.MIMES else True
            except Exception as e:
                raise ValueError(f'invalid uploaded image: {rel}') from e
            if not valid:
                raise ValueError(f'invalid uploaded image: {rel}')
            total += len(data)
            if total > MAX_BYTES:
                raise ValueError('upload exceeds 256 MiB; split the library')
            meta = {'source_key': 'browser:' + rel, 'root_id': 'browser', 'root_label': '页面导入',
                    'relative_path': rel, 'filename': path.name, 'title': path.stem,
                    'group': path.parts[0] if len(path.parts) > 1 else '未分组', 'fields': {}, 'tags': [],
                    'caption': '', 'format': ext[1:].upper() or 'FILE', 'bytes': len(data), 'modified_ns': 0,
                    'asset_kind': asset_kind(path.name)}
            rows.append((meta, data))
        if not rows:
            raise ValueError('no visible files selected')
        return self.ingest(rows, name, '', library_id, None, skipped, [], replace, options)

    def ingest(self, records, name, description, library_id, config, skipped, warnings, mark_missing, options=None):
        with self.write_lock():
            # Validate the target before writing managed copies or starting a transaction.
            if library_id:
                with self.db() as c:
                    self.require(c, 'libraries', library_id)
            lid = library_id or uid()
            with self.db() as c:
                prior_options = json.loads(self.require(c, 'libraries', lid)['import_options']) if library_id else {}
                import_options = self.validate_import_options(c, {**IMPORT_DEFAULTS, **prior_options, **(options or {})})
            prepared = [(meta, self.save_blob(data)) for meta, data in records]
            summary = {'library_id': lid, 'added': 0, 'changed': 0, 'unchanged': 0, 'missing': 0,
                       'count': len(records), 'skipped': skipped, 'warnings': warnings}
            with self.db() as c:
                if not library_id:
                    c.execute('INSERT INTO libraries(id,name,description,source_config,created,updated,revision) VALUES (?,?,?,?,?,?,0)',
                              (lid, text(name, 'name', 300), description, encoded(config) if config else None, now(), now()))
                elif config is not None:
                    c.execute('UPDATE libraries SET source_config=? WHERE id=?', (encoded(config), lid))
                c.execute('UPDATE libraries SET import_options=? WHERE id=?', (encoded(import_options), lid))
                seen = set()
                for meta, blob in prepared:
                    source_key = meta['source_key']
                    ident = uuid.uuid5(uuid.UUID(lid), source_key).hex
                    seen.add(ident)
                    meta = {**meta, 'id': ident, 'download_name': ident[:10] + '_' + meta['filename']}
                    prior = c.execute('SELECT * FROM images WHERE id=?', (ident,)).fetchone()
                    if prior:
                        changed = prior['blob'] != blob
                        summary['changed' if changed else 'unchanged'] += 1
                        c.execute('UPDATE images SET metadata=?,blob=?,missing=0,updated=? WHERE id=?', (encoded(meta), blob, now(), ident))
                    else:
                        changed = True
                        summary['added'] += 1
                        c.execute('INSERT INTO images(id,library_id,source_key,metadata,blob,created,updated) VALUES (?,?,?,?,?,?,?)',
                                  (ident, lid, source_key, encoded(meta), blob, now(), now()))
                    if changed:
                        c.execute('INSERT INTO versions VALUES (?,?,?,?,?)', (uid(), ident, blob, encoded(meta), now()))
                    c.execute('INSERT OR IGNORE INTO groups(library_id,name) VALUES (?,?)', (lid, meta['group']))
                    user_tags = tags_value([*(json.loads(prior['user_tags']) if prior else []), *import_options['tags']])
                    c.execute('UPDATE images SET user_tags=? WHERE id=?', (encoded(user_tags), ident))
                    target_folder = import_options['folder_id']
                    if import_options['hierarchy']:
                        # Scope generated hierarchy to this library, keeping repeat imports idempotent.
                        if not target_folder:
                            target_folder = self.ensure_library_root(c, lid)
                        for part in PurePosixPath(meta['relative_path']).parts[:-1]:
                            target_folder = self.ensure_folder(c, part, target_folder)
                    if target_folder:
                        c.execute('INSERT OR IGNORE INTO membership VALUES (?,?)', (target_folder, ident))
                if mark_missing:
                    subset = "source_key LIKE 'browser:%'" if config is None else "source_key NOT LIKE 'browser:%'"
                    for row in c.execute(f'SELECT id FROM images WHERE library_id=? AND {subset}', (lid,)).fetchall():
                        if row['id'] not in seen:
                            c.execute('UPDATE images SET missing=1 WHERE id=?', (row['id'],))
                            summary['missing'] += 1
                self.bump(c, lid)
                c.execute('INSERT INTO imports VALUES (?,?,?,?)', (uid(), lid, now(), encoded(summary)))
            if import_options['auto_export']:
                try:
                    summary['export'] = self.export(library_id=lid)
                except (ValueError, OSError) as exc:
                    summary['export_error'] = str(exc)  # Import is committed; do not retry the import as failed.
            return summary

    def annotate(self, image_id, patch):
        if not isinstance(patch, dict) or not patch or set(patch) - {'favorite', 'hidden', 'note'}:
            raise ValueError('image patch supports favorite, hidden, note')
        values = {k: text(v, 'note') if k == 'note' else boolean(v) for k, v in patch.items()}
        with self.db() as c:
            image = self.require(c, 'images', image_id)
            c.execute('UPDATE images SET ' + ','.join(k + '=?' for k in values) + ',updated=? WHERE id=?',
                      (*values.values(), now(), image_id))
            self.bump(c, image['library_id'])

    def set_group(self, lid, group, patch):
        if not isinstance(patch, dict) or not patch or set(patch) - {'favorite', 'note'}:
            raise ValueError('group patch supports favorite, note')
        values = {k: text(v, 'note') if k == 'note' else boolean(v) for k, v in patch.items()}
        with self.db() as c:
            if not c.execute('SELECT 1 FROM groups WHERE library_id=? AND name=?', (lid, group)).fetchone():
                raise ValueError('unknown source group')
            c.execute('UPDATE groups SET ' + ','.join(k + '=?' for k in values) + ' WHERE library_id=? AND name=?',
                      (*values.values(), lid, group))
            self.bump(c, lid)

    @staticmethod
    def validate_query(query):
        keys = {'search', 'library_id', 'tags', 'kind', 'favorite', 'fields', 'group'}
        if not isinstance(query, dict) or set(query) - keys:
            raise ValueError('unsupported smart folder condition')
        result = dict(query)
        for key in ('search', 'library_id', 'group'):
            if key in query:
                text(query[key], key, 500)
        if 'favorite' in query:
            boolean(query['favorite'])
        if 'tags' in query:
            result['tags'] = tags_value(query['tags'])
        if 'kind' in query and query['kind'] not in ('', 'image', 'document', 'video', 'audio', 'file'):
            raise ValueError('unknown asset kind')
        if 'fields' in query:
            if not isinstance(query['fields'], dict) or len(query['fields']) > 30:
                raise ValueError('fields must be a small object')
            for key, value in query['fields'].items():
                text(key, 'field name', 100)
                text(value, 'field value', 500)
        return result

    @staticmethod
    def query_matches(row, query):
        words = query.get('search', '').casefold().split()
        haystack = ' '.join(str(row.get(k, '')) for k in ('title', 'filename', 'relative_path', 'note', 'caption', 'group'))
        haystack += ' ' + ' '.join(row.get('tags', [])) + ' ' + ' '.join(str(v) for v in row.get('fields', {}).values())
        return (all(word in haystack.casefold() for word in words)
                and (not query.get('library_id') or row['library_id'] == query['library_id'])
                and (not query.get('group') or row['group'] == query['group'])
                and (not query.get('kind') or row['asset_kind'] == query['kind'])
                and ('favorite' not in query or bool(row['favorite']) == query['favorite'])
                and all(tag in row.get('tags', []) for tag in query.get('tags', []))
                and all(row.get('fields', {}).get(k) == v for k, v in query.get('fields', {}).items() if v))

    @staticmethod
    def folder_descendants(folders, ident):
        result = {ident}
        while True:
            children = {r['id'] for r in folders if r.get('parent_id') in result}
            if children <= result:
                return result
            result.update(children)

    @staticmethod
    def ensure_folder(c, name, parent_id):
        row = c.execute('SELECT id FROM folders WHERE name=? AND parent_id IS ? AND deleted_at IS NULL', (name, parent_id)).fetchone()
        if row:
            folder = Store.require(c, 'folders', row['id'])
            if folder['kind'] != 'manual':
                raise ValueError('import hierarchy conflicts with a smart folder')
            return row['id']
        ident = uid()
        c.execute('INSERT INTO folders(id,name,created,parent_id) VALUES (?,?,?,?)', (ident, name, now(), parent_id))
        return ident

    @staticmethod
    def ensure_library_root(c, lid):
        key = 'hierarchy_root:' + lid
        prior = c.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
        if prior:
            try:
                row = Store.require(c, 'folders', prior[0])
                if row['kind'] == 'manual':
                    return row['id']
            except ValueError:
                pass  # A retired generated root is not reused or silently restored.
        base = c.execute('SELECT name FROM libraries WHERE id=?', (lid,)).fetchone()[0]
        name, number = base, 2
        while c.execute('SELECT 1 FROM folders WHERE parent_id IS NULL AND name=? AND deleted_at IS NULL', (name,)).fetchone():
            name = base + f' ({number})'
            number += 1
        ident = Store.ensure_folder(c, name, None)
        c.execute('INSERT OR REPLACE INTO meta VALUES (?,?)', (key, ident))
        return ident

    @staticmethod
    def folder_libraries(c, ident):
        scope = Store.folder_descendants([dict(r) for r in c.execute('SELECT id,parent_id FROM folders')], ident)
        return {r['library_id'] for r in c.execute('SELECT m.folder_id,i.library_id FROM membership m JOIN images i ON i.id=m.image_id')
                if r['folder_id'] in scope}

    @staticmethod
    def detach_import_destinations(c, scope):
        for row in c.execute('SELECT id,import_options FROM libraries').fetchall():
            options = json.loads(row['import_options'])
            if options.get('folder_id') in scope:
                options['folder_id'] = None
                c.execute('UPDATE libraries SET import_options=? WHERE id=?', (encoded(options), row['id']))

    def folder(self, name, folder_id=None, parent_id=UNSET, kind=None, query=None):
        name = text(name, 'folder name', 300).strip()
        if not name:
            raise ValueError('folder name cannot be empty')
        with self.db() as c:
            prior = self.require(c, 'folders', folder_id) if folder_id else None
            parent_id = (prior['parent_id'] if prior else None) if parent_id is UNSET else parent_id or None
            kind = kind or (prior['kind'] if prior else 'manual')
            if kind not in ('manual', 'smart'):
                raise ValueError('folder kind must be manual or smart')
            if prior and kind != prior['kind']:
                raise ValueError('folder kind cannot be changed; create another folder')
            query = self.validate_query(query if query is not None else json.loads(prior['query']) if prior else {})
            if parent_id:
                parent = self.require(c, 'folders', parent_id)
                if parent['kind'] != 'manual':
                    raise ValueError('smart folders cannot contain child folders')
            rows = [dict(r) for r in c.execute('SELECT id,parent_id FROM folders')]
            if folder_id and parent_id in self.folder_descendants(rows, folder_id):
                raise ValueError('cannot move a folder into itself or its descendants')
            if c.execute('SELECT 1 FROM folders WHERE name=? AND parent_id IS ? AND deleted_at IS NULL AND id!=?',
                         (name, parent_id, folder_id or '')).fetchone():
                raise ValueError('a sibling folder already has this name')
            if folder_id:
                c.execute('UPDATE folders SET name=?,parent_id=?,query=? WHERE id=?', (name, parent_id, encoded(query), folder_id))
                for lid in self.folder_libraries(c, folder_id):
                    self.bump(c, lid)
            else:
                folder_id = uid()
                c.execute('INSERT INTO folders(id,name,created,parent_id,kind,query) VALUES (?,?,?,?,?,?)',
                          (folder_id, name, now(), parent_id, kind, encoded(query)))
        return folder_id

    @staticmethod
    def validate_import_options(c, options):
        if not isinstance(options, dict) or set(options) - set(IMPORT_DEFAULTS):
            raise ValueError('unknown import option')
        result = {**IMPORT_DEFAULTS, **options}
        for key in ('hierarchy', 'auto_export'):
            boolean(result[key])
        result['tags'] = tags_value(result['tags'])
        result['folder_id'] = result['folder_id'] or None
        if result['folder_id']:
            folder = Store.require(c, 'folders', result['folder_id'])
            if folder['kind'] != 'manual':
                raise ValueError('import destination must be a manual folder')
        return result

    def set_import_options(self, lid, options):
        with self.db() as c:
            row = self.require(c, 'libraries', lid)
            result = self.validate_import_options(c, {**json.loads(row['import_options']), **options})
            c.execute('UPDATE libraries SET import_options=? WHERE id=?', (encoded(result), lid))
        return result

    def set_preferences(self, values):
        if not isinstance(values, dict) or set(values) - set(PREFERENCE_DEFAULTS):
            raise ValueError('unknown workspace preference')
        for key, value in values.items():
            if key == 'thumbnail' and (type(value) is not int or not 180 <= value <= 420):
                raise ValueError('thumbnail size must be 180–420')
            if key == 'theme' and value not in ('light', 'dark') or key == 'layout' and value not in ('grid', 'list'):
                raise ValueError('invalid display preference')
            if key == 'sort' and value not in ('name', 'updated', 'size', 'kind'):
                raise ValueError('invalid sort order')
            if key == 'inspector':
                boolean(value)
        with self.db() as c:
            row = c.execute("SELECT value FROM meta WHERE key='preferences'").fetchone()
            prefs = {**PREFERENCE_DEFAULTS, **(json.loads(row[0]) if row else {}), **values}
            c.execute("INSERT OR REPLACE INTO meta VALUES ('preferences',?)", (encoded(prefs),))
        return prefs

    def batch(self, image_ids, action):
        if not isinstance(image_ids, list) or not image_ids or len(image_ids) > 5000 or not all(isinstance(x, str) for x in image_ids):
            raise ValueError('select 1–5000 assets')
        if not isinstance(action, dict) or not action or set(action) - {'favorite', 'hidden', 'add_tags', 'remove_tags', 'folder_id', 'present'}:
            raise ValueError('unknown batch action')
        for key in ('favorite', 'hidden', 'present'):
            if key in action:
                boolean(action[key])
        additions = tags_value(action.get('add_tags', []))
        removals = tags_value(action.get('remove_tags', []))
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            rows = [self.require(c, 'images', ident) for ident in dict.fromkeys(image_ids)]
            if 'folder_id' in action:
                folder = self.require(c, 'folders', action['folder_id'])
                if folder['kind'] != 'manual' or 'present' not in action:
                    raise ValueError('manual folder and present flag required')
            for row in rows:
                for key in ('favorite', 'hidden'):
                    if key in action:
                        c.execute(f'UPDATE images SET {key}=?,updated=? WHERE id=?', (int(action[key]), now(), row['id']))
                tags = tags_value([*json.loads(row['user_tags']), *additions])
                tags = [t for t in tags if t not in removals]
                c.execute('UPDATE images SET user_tags=?,updated=? WHERE id=?', (encoded(tags), now(), row['id']))
                if 'folder_id' in action:
                    c.execute('INSERT OR IGNORE INTO membership VALUES (?,?)' if action['present'] else
                              'DELETE FROM membership WHERE folder_id=? AND image_id=?', (action['folder_id'], row['id']))
            for lid in {r['library_id'] for r in rows}:
                self.bump(c, lid)
        return {'count': len(rows)}

    def membership(self, folder_id, image_id, present):
        boolean(present)
        with self.db() as c:
            if self.require(c, 'folders', folder_id)['kind'] != 'manual':
                raise ValueError('smart folders are populated by their query')
            image = self.require(c, 'images', image_id)
            if present:
                c.execute('INSERT OR IGNORE INTO membership VALUES (?,?)', (folder_id, image_id))
            else:
                c.execute('DELETE FROM membership WHERE folder_id=? AND image_id=?', (folder_id, image_id))
            self.bump(c, image['library_id'])

    def delete(self, kind, ident):
        self.delete_batch([{'kind': kind, 'id': ident}])
        return {'kind': kind, 'id': ident, 'recoverable': True}

    def delete_batch(self, targets):
        if not isinstance(targets, list) or not 1 <= len(targets) <= 5000:
            raise ValueError('select 1–5000 recovery targets')
        with self.db() as c:
            c.execute('BEGIN IMMEDIATE')
            prepared, affected, folders = [], set(), set()
            for target in targets:
                if not isinstance(target, dict):
                    raise ValueError('invalid recovery target')
                kind, ident = target.get('kind'), target.get('id')
                table = {'image':'images','library':'libraries','folder':'folders','attachment':'attachments'}.get(kind)
                if not table:
                    raise ValueError('unknown recovery target kind')
                row = self.require(c, table, ident)
                if kind == 'attachment':
                    affected.add(self.validate_attachment_target(c, row['kind'], row['target_id']))
                elif kind == 'folder':
                    affected.update(self.folder_libraries(c, ident))
                    folders.update(self.folder_descendants([dict(r) for r in c.execute('SELECT id,parent_id FROM folders')], ident))
                else:
                    affected.add(row['library_id'] if kind == 'image' else ident)
                prepared.append((table, ident))
            for table, ident in prepared:
                c.execute(f'UPDATE {table} SET deleted_at=? WHERE id=?', (now(), ident))
            self.detach_import_destinations(c, folders)
            for lid in affected:
                self.bump(c, lid)
        return {'count': len(prepared), 'recoverable': True}

    def restore(self, kind, ident):
        table = {'image': 'images', 'library': 'libraries', 'folder': 'folders', 'attachment': 'attachments'}.get(kind)
        if not table:
            raise ValueError('restore accepts image, library, folder, or attachment')
        with self.db() as c:
            row = self.require(c, table, ident, with_deleted=True)
            if not row['deleted_at']:
                raise ValueError('item is not in the trash')
            if kind == 'image':
                self.require(c, 'libraries', row['library_id'])
            if kind == 'attachment':
                affected = [self.validate_attachment_target(c, row['kind'], row['target_id'])]
            else:
                affected = ([row['library_id']] if kind == 'image' else
                            [row['id']] if kind == 'library' else
                            self.folder_libraries(c, ident))
            if kind == 'folder':
                if row['parent_id']:
                    self.require(c, 'folders', row['parent_id'])
                if c.execute('SELECT 1 FROM folders WHERE parent_id IS ? AND name=? AND deleted_at IS NULL',
                             (row['parent_id'], row['name'])).fetchone():
                    raise ValueError('restore conflict: an active sibling has the same name')
            c.execute(f'UPDATE {table} SET deleted_at=NULL WHERE id=?', (ident,))
            for lid in affected:
                self.bump(c, lid)
        return {'kind': kind, 'id': ident, 'restored': True}

    @staticmethod
    def purge_targets(c, kind, ident=None, trash_only=False):
        if kind not in ('trash', 'library', 'image', 'folder', 'attachment'):
            raise ValueError('permanent removal accepts a library, image, folder, attachment, or trash')
        all_libraries = {r['id']: r for r in c.execute('SELECT * FROM libraries')}
        all_images = {r['id']: r for r in c.execute('SELECT * FROM images')}
        all_folders = {r['id']: r for r in c.execute('SELECT * FROM folders')}
        all_attachments = {r['id']: r for r in c.execute('SELECT * FROM attachments')}
        selected = {'libraries': set(), 'images': set(), 'folders': set(), 'attachments': set()}
        if kind == 'trash':
            selected['libraries'] = {k for k, r in all_libraries.items() if r['deleted_at']}
            selected['images'] = {k for k, r in all_images.items() if r['deleted_at'] or r['library_id'] in selected['libraries']}
            selected['folders'] = {k for k, r in all_folders.items() if r['deleted_at']}
            selected['attachments'] = {k for k, r in all_attachments.items() if r['deleted_at']}
        else:
            table, key = {'library': ('libraries', 'libraries'), 'image': ('images', 'images'),
                          'folder': ('folders', 'folders'), 'attachment': ('attachments', 'attachments')}[kind]
            row = {'libraries': all_libraries, 'images': all_images, 'folders': all_folders,
                   'attachments': all_attachments}[table].get(ident)
            if not row:
                raise ValueError('permanent removal target does not exist')
            if trash_only and not row['deleted_at']:
                raise ValueError('target is not in the recovery bin')
            selected[key].add(ident)
            if kind == 'library':
                selected['images'] = {k for k, r in all_images.items() if r['library_id'] == ident}
        for folder_id in list(selected['folders']):
            selected['folders'].update(Store.folder_descendants([dict(r) for r in all_folders.values()], folder_id))
        selected['attachments'].update(k for k, r in all_attachments.items()
            if (r['kind'] == 'image' and r['target_id'] in selected['images'])
            or (r['kind'] == 'group' and r['target_id'].partition('::')[0] in selected['libraries']))
        return selected, all_images, all_attachments

    @staticmethod
    def purge_fingerprint(selected, images, attachments):
        evidence = {key: sorted(ids) for key, ids in selected.items()}
        evidence['image_content'] = sorted((key, images[key]['blob']) for key in selected['images'])
        evidence['attachment_content'] = sorted((key, attachments[key]['blob']) for key in selected['attachments'])
        return hashlib.sha256(encoded(evidence).encode()).hexdigest()

    def preview_purge(self, kind, ident=None, trash_only=False):
        with self.db() as c:
            selected, images, attachments = self.purge_targets(c, kind, ident, trash_only)
            return {**{key: len(ids) for key, ids in selected.items()},
                    'image_bytes': sum(json.loads(images[key]['metadata']).get('bytes', 0) for key in selected['images']),
                    'attachment_bytes': sum(attachments[key]['size'] for key in selected['attachments']),
                    'fingerprint': self.purge_fingerprint(selected, images, attachments),
                    'source_files_untouched': True,
                    'existing_offline_exports_untouched': True}

    def purge(self, kind, ident=None, trash_only=False, expected_fingerprint=None):
        with self.write_lock():
            with self.db() as c:
                c.execute('BEGIN IMMEDIATE')
                selected, images, attachments = self.purge_targets(c, kind, ident, trash_only)
                if expected_fingerprint is not None and expected_fingerprint != self.purge_fingerprint(selected, images, attachments):
                    raise ValueError('permanent removal target changed; inspect it again before confirming')
                candidate_blobs = {images[key]['blob'] for key in selected['images']}
                if selected['images']:
                    candidate_blobs.update(r['blob'] for r in c.execute('SELECT image_id,blob FROM versions')
                                           if r['image_id'] in selected['images'])
                candidate_blobs.update(attachments[key]['blob'] for key in selected['attachments'])
                image_metadata = [(key, images[key]['library_id'], json.loads(images[key]['metadata']))
                                  for key in selected['images']]
                note_metadata = [(key, attachments[key]['target_id'], attachments[key]['filename'])
                                 for key in selected['attachments']]
                changed_libraries = {images[key]['library_id'] for key in selected['images']
                                     if images[key]['library_id'] not in selected['libraries']}
                for key in selected['attachments']:
                    item = attachments[key]
                    lid = (images[item['target_id']]['library_id'] if item['kind'] == 'image'
                           else item['target_id'].partition('::')[0])
                    if lid not in selected['libraries']:
                        changed_libraries.add(lid)
                for key in selected['folders']:
                    changed_libraries.update(r['library_id'] for r in c.execute(
                        'SELECT DISTINCT i.library_id FROM membership m JOIN images i ON i.id=m.image_id WHERE m.folder_id=?', (key,))
                        if r['library_id'] not in selected['libraries'])
                self.detach_import_destinations(c, selected['folders'])
                for key in selected['attachments']:
                    c.execute('DELETE FROM attachments WHERE id=?', (key,))
                for key in selected['images']:
                    c.execute('DELETE FROM membership WHERE image_id=?', (key,))
                    c.execute('DELETE FROM versions WHERE image_id=?', (key,))
                    c.execute('DELETE FROM images WHERE id=?', (key,))
                for key in selected['folders']:
                    c.execute('DELETE FROM membership WHERE folder_id=?', (key,))
                    c.execute('DELETE FROM folders WHERE id=?', (key,))
                for key in selected['libraries']:
                    c.execute('DELETE FROM groups WHERE library_id=?', (key,))
                    c.execute('DELETE FROM imports WHERE library_id=?', (key,))
                    c.execute('DELETE FROM libraries WHERE id=?', (key,))
                for key in changed_libraries:
                    self.bump(c, key)
            # The database committed. Cleanup is restricted to known app-owned paths.
            with self.db() as c:
                referenced = {r['blob'] for table in ('images', 'versions', 'attachments')
                              for r in c.execute(f'SELECT blob FROM {table}')}
            summary = {key: len(ids) for key, ids in selected.items()}
            summary.update({'freed_bytes': 0, 'cleanup_errors': []})
            for digest in candidate_blobs - referenced:
                path = self.blob_path(digest)
                try:
                    if path.is_file():
                        size = path.stat().st_size
                        path.unlink()
                        summary['freed_bytes'] += size
                except OSError as exc:
                    summary['cleanup_errors'].append(str(exc))
            managed = (self.root / 'managed').resolve()
            for key in selected['libraries']:
                target = (managed / key).resolve()
                try:
                    if target.is_relative_to(managed) and target.is_dir():
                        shutil.rmtree(target)
                except OSError as exc:
                    summary['cleanup_errors'].append(str(exc))
            for key, lid, meta in image_metadata:
                if lid in selected['libraries']:
                    continue
                relative = PurePosixPath(meta['relative_path'])
                home = (managed / lid / meta['root_id']).resolve()
                target = (home / str(relative)).resolve()
                try:
                    if target.is_relative_to(managed) and target.is_file():
                        target.unlink()
                except OSError as exc:
                    summary['cleanup_errors'].append(str(exc))
            for key, target_id, filename in note_metadata:
                home = (managed / 'attachments' / target_id.replace('::', '_')).resolve()
                target = (home / (key + '-' + filename)).resolve()
                try:
                    if target.is_relative_to(managed) and target.is_file():
                        target.unlink()
                except OSError as exc:
                    summary['cleanup_errors'].append(str(exc))
            return summary

    def empty_trash(self, expected_fingerprint=None):
        return self.purge('trash', trash_only=True, expected_fingerprint=expected_fingerprint)

    def rename(self, kind, ident, name):
        if kind not in ('image', 'library'):
            raise ValueError('rename accepts image or library')
        name = text(name, 'display name', 300).strip()
        if not name:
            raise ValueError('display name cannot be empty')
        with self.db() as c:
            if kind == 'library':
                self.require(c, 'libraries', ident)
                c.execute('UPDATE libraries SET name=? WHERE id=?', (name, ident))
                lid = ident
            else:
                row = self.require(c, 'images', ident)
                c.execute('UPDATE images SET renamed_title=?,updated=? WHERE id=?', (name, now(), ident))
                lid = row['library_id']
            self.bump(c, lid)
        return {'kind': kind, 'id': ident, 'name': name}

    def pin_original_source(self, image_id, source_path):
        source = Path(source_path).expanduser().resolve()
        with self.db() as c:
            image = self.require(c, 'images', image_id)
            if not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != image['blob']:
                raise ValueError('Finder source must exist and match the stored image')
            metadata = json.loads(image['metadata'])
            metadata['preferred_source_path'] = str(source)
            c.execute('UPDATE images SET metadata=? WHERE id=?', (encoded(metadata), image_id))
            self.bump(c, image['library_id'])

    def reveal_path(self, ident):
        with self.db() as c:
            row = self.require(c, 'images', ident)
            library = self.require(c, 'libraries', row['library_id'])
            metadata = json.loads(row['metadata'])
        preferred = metadata.get('preferred_source_path')
        if preferred:
            source = Path(preferred).resolve()
            if source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == row['blob']:
                return source
        if library['source_config'] and metadata['root_id'] != 'browser':
            config = json.loads(library['source_config'])
            root = next((Path(x['path']).resolve() for x in config['roots'] if x['id'] == metadata['root_id']), None)
            if root:
                source = (root / metadata['relative_path']).resolve()
                if source.is_relative_to(root) and source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest() == row['blob']:
                    return source
        relative = PurePosixPath(metadata['relative_path'])
        if relative.is_absolute() or '..' in relative.parts or '\\' in str(relative):
            raise ValueError('invalid managed image path')
        home = (self.root / 'managed' / row['library_id'] / metadata['root_id']).resolve()
        target = (home / str(relative)).resolve()
        if not target.is_relative_to(home):
            raise ValueError('managed image path escapes its library')
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_file() or hashlib.sha256(target.read_bytes()).hexdigest() != row['blob']:
            shutil.copyfile(self.blob_path(row['blob']), target)
        return target

    def reveal(self, ident):
        path = self.reveal_path(ident)
        subprocess.run(['/usr/bin/open', '-R', str(path)], check=True, timeout=10)
        return {'path': str(path), 'source': 'managed copy' if path.is_relative_to(self.root) else 'original source'}

    def state(self):
        with self.db() as c:
            c.execute('BEGIN')  # One consistent read snapshot, including concurrent CLI imports.
            libraries = [dict(x) for x in c.execute('SELECT * FROM libraries WHERE deleted_at IS NULL ORDER BY created')]
            all_folders = {r['id']: dict(r) for r in c.execute('SELECT * FROM folders ORDER BY name')}
            def folder_active(ident, seen=None):
                seen = seen or set()
                row = all_folders.get(ident)
                return bool(row and not row['deleted_at'] and ident not in seen and
                            (not row['parent_id'] or folder_active(row['parent_id'], seen | {ident})))
            folders = [r for key, r in all_folders.items() if folder_active(key)]
            for f in folders:
                names, parent = [f['name']], f['parent_id']
                while parent:
                    names.insert(0, all_folders[parent]['name'])
                    parent = all_folders[parent]['parent_id']
                f['path'] = ' / '.join(names)
                f['query'] = json.loads(f['query'])
            active_libraries = {x['id'] for x in libraries}
            active_folders = {x['id'] for x in folders}
            members = {}
            for row in c.execute('SELECT * FROM membership'):
                if row['folder_id'] in active_folders:
                    members.setdefault(row['image_id'], []).append(row['folder_id'])
            counts = dict(c.execute('SELECT image_id,COUNT(*) FROM versions GROUP BY image_id').fetchall())
            images = []
            for row in c.execute('SELECT * FROM images WHERE deleted_at IS NULL ORDER BY library_id,source_key'):
                if row['library_id'] not in active_libraries:
                    continue
                meta = json.loads(row['metadata'])
                images.append({**meta, **{k: row[k] for k in ('id', 'library_id', 'blob', 'favorite', 'hidden', 'note', 'missing', 'updated')},
                               'title': row['renamed_title'] or meta['title'],
                               'asset_kind': asset_kind(meta['filename']), 'user_tags': json.loads(row['user_tags']),
                               'tags': list(dict.fromkeys([*meta.get('tags', []), *json.loads(row['user_tags'])])),
                               'folders': members.get(row['id'], []), 'version_count': counts[row['id']], 'url': '/media/' + row['id']})
            blob_counts = {}
            for r in images:
                blob_counts[r['blob']] = blob_counts.get(r['blob'], 0) + 1
            for r in images:
                r['duplicate_count'] = blob_counts[r['blob']]
                r['smart_folders'] = [f['id'] for f in folders if f['kind'] == 'smart' and self.query_matches(r, f['query'])]
            for f in folders:
                descendants = self.folder_descendants(folders, f['id'])
                f['count'] = sum(not r['hidden'] and (bool(descendants.intersection(r['folders'])) or
                                     bool(descendants.intersection(r['smart_folders']))) for r in images)
            exports = [dict(x) for x in c.execute('SELECT * FROM exports ORDER BY created DESC')]
            for export in exports:
                export['url'] = '/exports/' + export['id']
            for lib in libraries:
                lib['import_options'] = {**IMPORT_DEFAULTS, **json.loads(lib['import_options'])}
                lib['can_refresh'] = bool(lib.pop('source_config'))
                lib['count'] = sum(i['library_id'] == lib['id'] for i in images)
                lib['hidden_count'] = sum(i['library_id'] == lib['id'] and i['hidden'] for i in images)
                lib['missing_count'] = sum(i['library_id'] == lib['id'] and i['missing'] for i in images)
                latest = next((e for e in exports if e['library_id'] == lib['id'] and not e['folder_id']), None)
                lib['latest_export'] = latest
                lib['export_stale'] = not latest or json.loads(latest['revisions']).get(lib['id']) != lib['revision']
            groups = [dict(g) for g in c.execute('SELECT * FROM groups ORDER BY library_id,name') if g['library_id'] in active_libraries]
            active_images = {x['id'] for x in images}
            attachments = []
            for item in c.execute('SELECT id,kind,target_id,filename,size,created FROM attachments WHERE deleted_at IS NULL ORDER BY created'):
                if item['kind'] == 'image' and item['target_id'] not in active_images:
                    continue
                if item['kind'] == 'group' and item['target_id'].partition('::')[0] not in active_libraries:
                    continue
                attachments.append({**dict(item), 'url': '/attachments/' + item['id']})
            batches = [{**dict(b), 'summary': json.loads(b['summary'])} for b in c.execute('SELECT * FROM imports ORDER BY created DESC LIMIT 100')]
            trash = {
                'libraries': [dict(x) for x in c.execute('SELECT id,name,deleted_at FROM libraries WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC')],
                'images': [{'id': x['id'], 'library_id': x['library_id'], 'title': x['renamed_title'] or json.loads(x['metadata'])['title'],
                            'deleted_at': x['deleted_at']} for x in c.execute('SELECT * FROM images WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC')],
                'folders': [dict(x) for x in c.execute('SELECT id,name,deleted_at FROM folders WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC')],
                'attachments': [dict(x) for x in c.execute('SELECT id,kind,target_id,filename,deleted_at FROM attachments WHERE deleted_at IS NOT NULL ORDER BY deleted_at DESC')]}
            preferences = c.execute("SELECT value FROM meta WHERE key='preferences'").fetchone()
            return {'version': VERSION, 'api_version': 1, 'store_id': self.store_id, 'libraries': libraries, 'images': images,
                    'groups': groups, 'folders': folders, 'exports': exports, 'imports': batches, 'trash': trash,
                    'attachments': attachments,
                    'preferences': {**PREFERENCE_DEFAULTS, **(json.loads(preferences[0]) if preferences else {})}}

    def image(self, ident):
        with self.write_lock():
            with self.db() as c:
                row = self.require(c, 'images', ident)
                meta = json.loads(row['metadata'])
                return self.blob_path(row['blob']).read_bytes(), gallery.MIMES.get(Path(meta['filename']).suffix.lower(), 'application/octet-stream'), meta

    def export(self, library_id=None, folder_id=None, include_hidden=False):
        with self.write_lock():
            state = self.state()
            libs = {l['id']: l for l in state['libraries']}
            folders = {f['id']: f['path'] for f in state['folders']}
            if library_id and library_id not in libs or folder_id and folder_id not in folders:
                raise ValueError('unknown export scope')
            scope = self.folder_descendants(state['folders'], folder_id) if folder_id else set()
            rows = [r for r in state['images'] if (not library_id or r['library_id'] == library_id)
                    and (not scope or scope.intersection(r['folders'] + r['smart_folders'])) and (include_hidden or not r['hidden'])]
            title = folders[folder_id] if folder_id else libs[library_id]['name'] if library_id else '全部图库'
            payload_rows, assets = [], {}
            group_notes = {(g['library_id'], g['name']): g for g in state['groups']}
            attached_names = {}
            for item in state['attachments']:
                attached_names.setdefault((item['kind'], item['target_id']), []).append(item['filename'])
            for r in rows:
                content = self.blob_path(r['blob']).read_bytes()
                mime = gallery.MIMES.get(Path(r['filename']).suffix.lower(), 'application/octet-stream')
                meta = {k: v for k, v in r.items() if k not in ('blob', 'url', 'version_count', 'preferred_source_path')}
                group = group_notes.get((r['library_id'], r['group']), {})
                row = {**meta, 'fields': {**meta.get('fields', {}), '个人收藏': '已收藏' if r['favorite'] else '未收藏',
                                        '隐藏状态': '已隐藏' if r['hidden'] else '可见', '图库': libs[r['library_id']]['name']},
                       'tags': [*meta.get('tags', []), *[folders[f] for f in r['folders']],
                                *(['★ 收藏组'] if group.get('favorite') else []), *(['来源缺失，保留副本'] if r['missing'] else [])],
                       'caption': '\n'.join(x for x in [meta.get('caption', ''),
                             '个人备注：' + r['note'] if r['note'] else '',
                             '组别备注：' + group.get('note', '') if group.get('note') else '',
                             '备注附件（请在主图库打开）：' + '、'.join(attached_names.get(('image', r['id']), []))
                             if attached_names.get(('image', r['id'])) else '',
                             '组别附件（请在主图库打开）：' + '、'.join(attached_names.get(('group', r['library_id'] + '::' + r['group']), []))
                             if attached_names.get(('group', r['library_id'] + '::' + r['group'])) else ''] if x)}
                if not library_id:
                    row['group'] = libs[r['library_id']]['name'] + ' / ' + r['group']
                payload_rows.append(row)
                assets[r['id']] = 'data:' + mime + ';base64,' + base64.b64encode(content).decode()
            group_counts = {}
            for r in payload_rows:
                group_counts[r['group']] = group_counts.get(r['group'], 0) + 1
            keys = sorted({key for r in payload_rows for key in r['fields']})
            payload = {'title': title + ' · 离线快照', 'description': '图片及收藏、分类、备注为导出时的只读快照；编辑请回到本地图库管理器。',
                       'generated_at': now(), 'version': VERSION, 'count': len(rows), 'source_bytes': sum(r['bytes'] for r in rows),
                       'images': payload_rows, 'assets': assets, 'by_group': group_counts, 'groups': {},
                       'filters': [{'key': key, 'label': key} for key in keys]}
            eid = uid()
            folder = self.root / 'exports' / eid
            folder.mkdir()
            path = folder / 'index.html'
            safe_json = encoded(payload).replace('<', '\\u003c').replace('&', '\\u0026')
            path.write_text(gallery.TEMPLATE.read_text().replace('<!-- CATALOG_JSON -->', safe_json))
            revisions = {l['id']: l['revision'] for l in state['libraries'] if not library_id or l['id'] == library_id}
            receipt = {'id': eid, 'created': now(), 'library_id': library_id, 'folder_id': folder_id,
                       'include_hidden': bool(include_hidden), 'count': len(rows), 'path': str(path),
                       'revisions': encoded(revisions), 'url': '/exports/' + eid}
            (folder / 'manifest.json').write_text(encoded({**receipt, 'images': [{k: r[k] for k in ('id', 'source_key', 'library_id', 'hidden', 'favorite', 'note', 'folders')} for r in rows]}))
            with self.db() as c:
                c.execute('INSERT INTO exports VALUES (?,?,?,?,?,?,?,?)', tuple(receipt[k] for k in ('id', 'created', 'library_id', 'folder_id', 'include_hidden', 'count', 'path', 'revisions')))
            return receipt


def make_server(store, port=0):
    token = secrets.token_urlsafe(32)
    pending, attachment_pending, upload_lock = {}, {}, threading.RLock()

    class Handler(BaseHTTPRequestHandler):
        def allowed_host(self):
            return self.headers.get('Host') == f'127.0.0.1:{self.server.server_port}'

        def send(self, content, mime='application/json', code=200, extra=None):
            data = content if isinstance(content, bytes) else content.encode()
            self.send_response(code)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('X-Frame-Options', 'DENY')
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def send_attachment(self, item):
            self.send_response(200)
            self.send_header('Content-Type', 'application/octet-stream')
            self.send_header('Content-Disposition', "attachment; filename*=UTF-8''" + quote(item['filename']))
            self.send_header('Content-Length', str(item['size']))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            with item['path'].open('rb') as source:
                shutil.copyfileobj(source, self.wfile, 1024 * 1024)

        def do_GET(self):
            if not self.allowed_host():
                return self.send(encoded({'error': 'invalid Host'}), code=403)
            path = urlsplit(self.path).path
            try:
                if path == '/':
                    page = (ASSETS / 'library.html').read_text().replace('__CSRF_TOKEN__', token)
                    return self.send(page, 'text/html; charset=utf-8')
                if path == '/logo.svg':
                    return self.send((ASSETS / 'logo.svg').read_bytes(), 'image/svg+xml',
                                     extra={'Content-Security-Policy': "sandbox; default-src 'none'"})
                if path == '/logo.png':
                    return self.send((ASSETS / 'icon.png').read_bytes(), 'image/png')
                if path in ('/workspace.css', '/workspace.js', '/workspace-core.js', '/settings.js'):
                    return self.send((ASSETS / path[1:]).read_bytes(), 'text/css' if path.endswith('.css') else 'application/javascript')
                if path == '/health':
                    return self.send(encoded({'store_id': store.store_id, 'version': VERSION, 'pid':os.getpid()}))
                if path == '/api/state':
                    if self.headers.get('X-Viewer-Token') != token:
                        return self.send(encoded({'error': 'token required'}), code=403)
                    return self.send(encoded(store.state()))
                if path == '/api/storage':
                    if self.headers.get('X-Viewer-Token') != token:
                        return self.send(encoded({'error':'token required'}),code=403)
                    return self.send(encoded(store.storage_info()))
                if path.startswith('/media/'):
                    data, mime, meta = store.image(path.removeprefix('/media/'))
                    headers = {'Content-Security-Policy': "sandbox; default-src 'none'; style-src 'unsafe-inline'"}
                    if mime == 'application/octet-stream':
                        headers['Content-Disposition'] = "attachment; filename*=UTF-8''" + quote(meta['filename'])
                    return self.send(data, mime, extra=headers)
                if path.startswith('/attachments/'):
                    return self.send_attachment(store.attachment_info(path.removeprefix('/attachments/')))
                if path.startswith('/exports/'):
                    eid = path.removeprefix('/exports/')
                    with store.db() as c:
                        row = c.execute('SELECT path FROM exports WHERE id=?', (eid,)).fetchone()
                    if not row:
                        raise ValueError('unknown export')
                    return self.send(Path(row['path']).read_bytes(), 'text/html; charset=utf-8')
                return self.send(encoded({'error': 'not found'}), code=404)
            except (ValueError, OSError) as exc:
                return self.send(encoded({'error': str(exc)}), code=404)

        def do_POST(self):
            expected = f'http://127.0.0.1:{self.server.server_port}'
            if not self.allowed_host() or self.headers.get('Origin') != expected or self.headers.get('X-Viewer-Token') != token:
                return self.send(encoded({'error': 'request origin/token denied'}), code=403)
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 < size <= 32 * 1024 ** 2 or self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                    raise ValueError('expected bounded JSON body (max 32 MiB per chunk)')
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError('expected JSON object')
                path = urlsplit(self.path).path
                result = {'ok': True}
                if path == '/api/image':
                    store.annotate(body['id'], body['patch'])
                elif path == '/api/group':
                    store.set_group(body['library_id'], body['name'], body['patch'])
                elif path == '/api/folder':
                    result['id'] = store.folder(body['name'], body.get('id'), body.get('parent_id', UNSET), body.get('kind'), body.get('query'))
                elif path == '/api/batch':
                    result = store.batch(body['ids'], body['action'])
                elif path == '/api/preferences':
                    result = store.set_preferences(body)
                elif path == '/api/import-options':
                    result = store.set_import_options(body['library_id'], body['options'])
                elif path == '/api/membership':
                    store.membership(body['folder_id'], body['image_id'], body['present'])
                elif path == '/api/export':
                    result = store.export(body.get('library_id'), body.get('folder_id'), bool(body.get('include_hidden', False)))
                elif path == '/api/refresh':
                    result = store.refresh(body['library_id'])
                elif path == '/api/backup':
                    result = {'path': store.backup()}
                elif path == '/api/storage/reveal':
                    subprocess.run(['/usr/bin/open', str(store.root)], check=True, timeout=10)
                    result = {'path':str(store.root)}
                elif path == '/api/delete':
                    result = store.delete(body['kind'], body['id'])
                elif path == '/api/delete/batch':
                    result = store.delete_batch(body['targets'])
                elif path == '/api/restore':
                    result = store.restore(body['kind'], body['id'])
                elif path == '/api/purge/preview':
                    if type(body.get('trash_only', False)) is not bool:
                        raise ValueError('invalid recovery-bin selection')
                    result = store.preview_purge(body['kind'], body.get('id'), body.get('trash_only', False))
                elif path == '/api/purge':
                    kind = body['kind']
                    phrase = '清空回收区' if kind == 'trash' else '永久删除'
                    if body.get('confirm') != phrase or type(body.get('trash_only', False)) is not bool:
                        raise ValueError('permanent removal requires the displayed confirmation phrase')
                    fingerprint = body.get('fingerprint')
                    if not isinstance(fingerprint, str) or len(fingerprint) != 64:
                        raise ValueError('inspect the current removal preview first')
                    result = store.purge(kind, body.get('id'), body.get('trash_only', False), fingerprint)
                elif path == '/api/reveal':
                    result = store.reveal(body['id'])
                elif path == '/api/rename':
                    result = store.rename(body['kind'], body['id'], body['name'])
                elif path == '/api/attachment/reveal':
                    result = store.reveal_attachment(body['id'])
                elif path == '/api/attachment/begin':
                    kind = body['kind']
                    target_id = body['target_id']
                    filename = store.validate_attachment_name(body['filename'])
                    size = body['size']
                    if type(size) is not int or size < 0 or size > 2 * 1024 ** 3:
                        raise ValueError('attachment exceeds 2 GiB limit')
                    with store.db() as c:
                        store.validate_attachment_target(c, kind, target_id)
                    with upload_lock:
                        for key in list(attachment_pending):
                            expired = attachment_pending[key]
                            if time.monotonic() - expired['time'] > 3600:
                                if expired['path'].exists():
                                    expired['path'].unlink()
                                attachment_pending.pop(key)
                        if len(attachment_pending) >= 3:
                            raise ValueError('finish or cancel an existing attachment first')
                        file = tempfile.NamedTemporaryFile(dir=store.root / 'incoming', prefix='attachment-', delete=False)
                        file.close()
                        upload_id = uid()
                        attachment_pending[upload_id] = {'path': Path(file.name), 'kind': kind,
                            'target_id': target_id, 'filename': filename, 'size': size, 'received': 0,
                            'sequence': 0, 'digest': hashlib.sha256(), 'time': time.monotonic()}
                        result = {'id': upload_id, 'chunk_limit': 4 * 1024 ** 2}
                elif path == '/api/attachment/chunk':
                    with upload_lock:
                        session = attachment_pending[body['id']]
                        sequence = body['sequence']
                        if type(sequence) is not int or sequence < 0:
                            raise ValueError('invalid attachment chunk sequence')
                        if sequence < session['sequence']:
                            result = {'next_sequence': session['sequence'], 'received': session['received']}
                        else:
                            if sequence != session['sequence']:
                                raise ValueError('attachment chunk arrived out of order')
                            data = base64.b64decode(body['data'], validate=True)
                            if len(data) > 4 * 1024 ** 2 or session['received'] + len(data) > session['size']:
                                raise ValueError('attachment chunk exceeds declared size')
                            with session['path'].open('ab') as target:
                                target.write(data)
                            session['digest'].update(data)
                            session['received'] += len(data)
                            session['sequence'] += 1
                            session['time'] = time.monotonic()
                            result = {'next_sequence': session['sequence'], 'received': session['received']}
                elif path == '/api/attachment/finish':
                    with upload_lock:
                        session = attachment_pending[body['id']]
                        if session['received'] != session['size']:
                            raise ValueError('attachment upload is incomplete')
                        result = store.add_attachment_file(session['kind'], session['target_id'],
                            session['filename'], session['path'], session['digest'].hexdigest(), session['size'])
                        attachment_pending.pop(body['id'])
                elif path == '/api/attachment/cancel':
                    with upload_lock:
                        session = attachment_pending.pop(body['id'], None)
                        if session and session['path'].exists():
                            session['path'].unlink()
                elif path == '/api/import/begin':
                    with upload_lock:
                        for key in list(pending):
                            if time.monotonic() - pending[key]['time'] > 3600:
                                pending.pop(key)
                        if len(pending) >= 2:
                            raise ValueError('finish or cancel the current import first')
                        key = uid()
                        pending[key] = {'name': text(body['name'], 'name', 300), 'library_id': body.get('library_id'),
                                        'replace': bool(body.get('replace')), 'files': [], 'bytes': 0, 'time': time.monotonic(),
                                        'options': body.get('options')}
                        result = {'id': key}
                elif path == '/api/import/add':
                    with upload_lock:
                        session = pending[body['id']]
                        if not isinstance(body['files'], list):
                            raise ValueError('files must be a list')
                        incoming = sum(len(f['data']) for f in body['files'])
                        if session['bytes'] + incoming > MAX_BYTES * 1.4 or len(session['files']) + len(body['files']) > 5000:
                            raise ValueError('import limit exceeded')
                        session['files'].extend(body['files'])
                        session['bytes'] += incoming
                        session['time'] = time.monotonic()
                elif path == '/api/import/cancel':
                    with upload_lock:
                        pending.pop(body['id'], None)
                elif path == '/api/import/commit':
                    with upload_lock:
                        session = pending.pop(body['id'])
                    result = store.import_uploads(session['name'], session['files'], session['library_id'], session['replace'], session['options'])
                else:
                    return self.send(encoded({'error': 'not found'}), code=404)
                return self.send(encoded(result))
            except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, subprocess.SubprocessError, binascii.Error) as exc:
                return self.send(encoded({'error': str(exc)}), code=400)

    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.token = token
    return server


def serve(store, port):
    with (store.root / '.server.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('this library already has a server; use launch')
        server = make_server(store, port)
        receipt = {'url': f'http://127.0.0.1:{server.server_port}/', 'pid': os.getpid(), 'store_id': store.store_id, 'version': VERSION}
        (store.root / 'server.json').write_text(encoded(receipt))
        print(encoded(receipt), flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()


def running(store):
    try:
        row = json.loads((store.root / 'server.json').read_text())
        url = urlsplit(row['url'])
        if url.scheme != 'http' or url.hostname != '127.0.0.1':
            return None
        with urllib.request.urlopen(row['url'] + 'health', timeout=1) as response:
            health = json.load(response)
        return row['url'] if health['store_id'] == store.store_id and health['version'] == VERSION else None
    except (OSError, ValueError, KeyError):
        return None


def stop(store):
    """Stop only a same-user FigNest service whose live identity matches this store."""
    receipt_path = store.root / 'server.json'
    if not receipt_path.exists():
        return {'stopped': False, 'reason': 'no service receipt'}
    receipt = json.loads(receipt_path.read_text())
    pid = receipt.get('pid')
    url = urlsplit(receipt.get('url', ''))
    if type(pid) is not int or pid <= 1 or pid == os.getpid() or receipt.get('store_id') != store.store_id:
        raise ValueError('service receipt identity does not match; no process was stopped')
    if url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or url.username or url.password or url.path != '/' or url.query:
        raise ValueError('invalid local service address; no process was stopped')
    try:
        with urllib.request.urlopen(receipt['url'] + 'health', timeout=2) as response:
            health = json.load(response)
    except OSError:
        return {'stopped': False, 'reason': 'service is not reachable; no signal sent'}
    if health.get('store_id') != store.store_id or health.get('pid', pid) != pid:
        raise ValueError('live service belongs to another store; no process was stopped')
    process = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'uid=', '-o', 'args='], capture_output=True, text=True, check=False)
    fields = process.stdout.strip().split(None, 1)
    if len(fields) != 2 or fields[0] != str(os.getuid()):
        raise ValueError('service process owner could not be verified; no signal sent')
    command = fields[1]
    if not command.endswith(f' --data {store.root} serve') or not any(name in command for name in ('library-backend', 'library.py')):
        raise ValueError('receipt PID is not a FigNest service; no signal sent')
    # The live store identity, account and program have all been checked.
    os.kill(pid, signal.SIGTERM)
    for _ in range(100):
        with (store.root / '.server.lock').open('a') as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                time.sleep(.05)
                continue
            fcntl.flock(lock, fcntl.LOCK_UN)
            return {'stopped': True, 'pid': pid, 'data_preserved': True}
    raise ValueError('service has not released its lock; preserve files and inspect before retrying')


def launch(store, open_browser=True):
    url = running(store)
    if not url:
        with (store.root / 'server.log').open('ab') as log:
            command = [sys.executable] if getattr(sys, 'frozen', False) else [sys.executable, str(Path(__file__).resolve())]
            child = subprocess.Popen([*command, '--data', str(store.root), 'serve'],
                                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
        for _ in range(60):
            url = running(store)
            if url:
                break
            if child.poll() is not None:
                raise ValueError('server did not start; inspect server.log')
            time.sleep(.1)
        if not url:
            raise ValueError('server startup timed out; inspect server.log')
    if open_browser:
        webbrowser.open(url)
    return url


def install_launcher(store, destination):
    target = Path(destination).expanduser().resolve()
    command = '#!/bin/zsh\n# ImageCollectionViewer launcher v2\nexec ' + ' '.join(shlex.quote(s) for s in
        [sys.executable, str(Path(__file__).resolve()), '--data', str(store.root), 'launch']) + '\n'
    if target.exists() and target.read_text() != command:
        raise ValueError('launcher destination exists with different contents; choose another name')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(command)
    target.chmod(0o755)
    return str(target)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data', default=str(DEFAULT_DATA))
    sub = p.add_subparsers(dest='command', required=True)
    for name in ('state', 'backup', 'stop'):
        sub.add_parser(name)
    imp = sub.add_parser('import')
    inp = imp.add_mutually_exclusive_group(required=True)
    inp.add_argument('--input')
    inp.add_argument('--config')
    imp.add_argument('--name')
    imp.add_argument('--library-id')
    imp.add_argument('--all-files', action='store_true', help='explicitly include general files; no conversion or execution')
    imp.add_argument('--options', help='JSON file containing folder_id, tags, hierarchy, auto_export import preset')
    ref = sub.add_parser('refresh')
    ref.add_argument('--library-id', required=True)
    exp = sub.add_parser('export')
    exp.add_argument('--library-id')
    exp.add_argument('--folder-id')
    exp.add_argument('--include-hidden', action='store_true')
    srv = sub.add_parser('serve')
    srv.add_argument('--port', type=int, default=0)
    launch_p = sub.add_parser('launch')
    launch_p.add_argument('--no-open', action='store_true')
    inst = sub.add_parser('install-launcher')
    inst.add_argument('--destination', required=True)
    args = p.parse_args()
    try:
        store = Store(args.data)
        if args.command == 'state': result = store.state()
        elif args.command == 'backup': result = {'path': store.backup()}
        elif args.command == 'stop': result = stop(store)
        elif args.command == 'import': result = store.import_directory(args.input, args.name, args.library_id, args.config,
            args.all_files, json.loads(Path(args.options).read_text()) if args.options else None)
        elif args.command == 'refresh': result = store.refresh(args.library_id)
        elif args.command == 'export': result = store.export(args.library_id, args.folder_id, args.include_hidden)
        elif args.command == 'launch': result = {'url': launch(store, not args.no_open)}
        elif args.command == 'install-launcher': result = {'path': install_launcher(store, args.destination)}
        else:
            serve(store, args.port)
            return
        print(encoded(result))
    except (ValueError, OSError, sqlite3.Error) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        sys.exit(2)


if __name__ == '__main__':
    main()
