#!/usr/bin/env python3
"""Local artifact provenance and delivery packaging. Python 3.10+, stdlib only."""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import tempfile
from datetime import datetime, timezone
import uuid
from urllib.parse import quote

STATE = '.artifact-handoff.json'
ROLES = ('source', 'export', 'asset', 'other')


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def root_path(value):
    root = Path(value).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Root must be a directory')
    return root


def safe_file(root, value):
    rel = Path(value)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('File paths must be relative and cannot contain ..')
    current = root
    for part in rel.parts:
        current /= part
        if current.is_symlink() or (hasattr(current, 'is_junction') and current.is_junction()):
            raise ValueError('Symlinks and junctions are not supported')
        if os.path.islink(current) or bool(getattr(current.stat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Reparse points are not supported')
    path = current.resolve(strict=True)
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError('File must be inside root')
    return path


def load(root):
    path = root / STATE
    if path.exists():
        safe_file(root, STATE)
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema_version') != 1 or not isinstance(data.get('artifacts'), list):
            raise ValueError('Unsupported registry format')
        return data
    return {'schema_version': 1, 'artifacts': []}


def save(root, data):
    target = root / STATE
    if target.exists():
        safe_file(root, STATE)
    fd, name = tempfile.mkstemp(prefix='.artifact-', suffix='.tmp', dir=root)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        os.replace(name, target)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def checked_record(root, record):
    path = safe_file(root, record['path'])
    if digest(path) != record['sha256']:
        raise ValueError('Registered file changed: ' + record['path'] + '; register a new version')
    return path


def find(data, identity):
    for record in data['artifacts']:
        if record['id'] == identity:
            return record
    raise ValueError('Unknown artifact ID: ' + identity)


def register(root, file, role, status='draft', parent=None, note=''):
    if role not in ROLES or status not in ('draft', 'final'):
        raise ValueError('Invalid role or status')
    path = safe_file(root, file)
    if path.name == STATE:
        raise ValueError('Cannot register the registry itself')
    data = load(root)
    if parent:
        checked_record(root, find(data, parent))
    record = {'id': uuid.uuid4().hex[:12], 'path': path.relative_to(root).as_posix(),
              'sha256': digest(path), 'bytes': path.stat().st_size, 'role': role,
              'status': status, 'parent': parent, 'note': note,
              'recorded_at': datetime.now(timezone.utc).isoformat()}
    data['artifacts'].append(record)
    save(root, data)
    return record


def scan(root):
    data = load(root)
    records = data['artifacts']
    files, skipped = [], []
    for directory, dirs, names in os.walk(root, followlinks=False):
        kept = []
        for name in sorted(dirs):
            path = Path(directory) / name
            attrs = getattr(path.lstat(), 'st_file_attributes', 0)
            if name == '.git' or path.is_symlink() or attrs & 0x400:
                skipped.append(path.relative_to(root).as_posix())
            else:
                kept.append(name)
        dirs[:] = kept
        for name in sorted(names):
            if name == STATE:
                continue
            rel = (Path(directory) / name).relative_to(root).as_posix()
            try:
                path = safe_file(root, rel)
                sha = digest(path)
                matches = [r['id'] for r in records if r['path'] == rel and r['sha256'] == sha]
                files.append({'path': rel, 'bytes': path.stat().st_size, 'sha256': sha,
                              'matching_records': matches})
            except (ValueError, OSError) as exc:
                skipped.append({'path': rel, 'reason': str(exc)})
    groups = {}
    for item in files:
        groups.setdefault(item['sha256'], []).append(item['path'])
    health = []
    for record in records:
        try:
            checked_record(root, record)
            state = 'verified'
        except (ValueError, OSError) as exc:
            state = str(exc)
        health.append({'id': record['id'], 'path': record['path'], 'state': state})
    return {'files': files, 'exact_duplicates': [v for v in groups.values() if len(v) > 1],
            'registry_health': health, 'skipped': skipped,
            'note': 'Unregistered files have unknown roles and status. Names and timestamps do not establish finality.'}


def package(root, ids, output, required_roles):
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('Select unique artifact IDs')
    if any(role not in ROLES for role in required_roles):
        raise ValueError('Invalid required role')
    data = load(root)
    selected = [find(data, identity) for identity in ids]
    if not any(r['status'] == 'final' for r in selected):
        raise ValueError('Select at least one explicitly registered final artifact')
    missing = set(required_roles) - {r['role'] for r in selected}
    if missing:
        raise ValueError('Missing required roles: ' + ', '.join(sorted(missing)))
    sources = [(r, checked_record(root, r)) for r in selected]
    # Validate every ancestor, while distinguishing history from selected delivery files.
    for record in selected:
        seen = set()
        current = record
        while current.get('parent'):
            identity = current['parent']
            if identity in seen:
                raise ValueError('Cycle in artifact lineage')
            seen.add(identity)
            current = find(data, identity)
            checked_record(root, current)
    out = Path(output).absolute()
    resolved = out.resolve()
    if out.exists() or out.is_symlink():
        raise ValueError('Output already exists; choose a new directory')
    if resolved.is_relative_to(root) or root.is_relative_to(resolved):
        raise ValueError('Output must be outside the source directory')
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.handoff-', dir=out.parent))
    try:
        delivered = []
        rows = []
        for record, source in sources:
            relative = Path('files') / record['id'] / source.name
            target = stage / relative
            target.parent.mkdir(parents=True)
            shutil.copyfile(source, target)
            if digest(target) != record['sha256']:
                raise ValueError('File changed during copying: ' + record['path'])
            item = dict(record, packaged_path=relative.as_posix())
            delivered.append(item)
            url = '/'.join(quote(p) for p in relative.parts)
            label = html.escape(record['path'])
            preview = ''
            if source.suffix.lower() in ('.png', '.jpg', '.jpeg', '.gif', '.webp'):
                preview = '<br><img loading="lazy" alt="' + label + '" src="' + url + '">'
            rows.append('<tr><td><a href="' + url + '">' + label + '</a>' + preview +
                        '</td><td>' + record['role'] + '</td><td>' + record['status'] +
                        '</td><td>' + html.escape(record['note']) + '</td></tr>')
        manifest = {'schema_version': 1, 'required_roles': sorted(set(required_roles)),
                    'artifacts': delivered, 'checks': 'selected files and ancestors verified by SHA-256'}
        (stage / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        (stage / 'index.html').write_text(
            '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">'
            '<title>Artifact delivery</title><style>body{font:18px system-ui;margin:32px;line-height:1.5}'
            'table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccc;padding:12px;text-align:left}'
            'img{max-width:360px;max-height:240px}</style><h1>Artifact delivery</h1>'
            '<p>Final status was explicitly recorded. Source files were copied without modification. '
            'Only selected files are included; lineage history is not automatically bundled.</p>'
            '<table><tr><th>File</th><th>Role</th><th>Status</th><th>Note</th></tr>' +
            ''.join(rows) + '</table></html>', encoding='utf-8')
        # mkdir is exclusive, so an existing delivery is never replaced.
        out.mkdir()
        for child in stage.iterdir():
            shutil.move(str(child), str(out / child.name))
    finally:
        shutil.rmtree(stage)
    return {'output': str(out), 'artifact_count': len(selected), 'manifest': 'manifest.json', 'preview': 'index.html'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    scan_p = sub.add_parser('scan')
    scan_p.add_argument('--root', required=True)
    reg = sub.add_parser('register')
    reg.add_argument('--root', required=True)
    reg.add_argument('--file', required=True)
    reg.add_argument('--role', choices=ROLES, required=True)
    reg.add_argument('--status', choices=('draft', 'final'), default='draft')
    reg.add_argument('--parent')
    reg.add_argument('--note', default='')
    pack = sub.add_parser('package')
    pack.add_argument('--root', required=True)
    pack.add_argument('--ids', nargs='+', required=True)
    pack.add_argument('--out', required=True)
    pack.add_argument('--require-role', choices=ROLES, action='append', default=[])
    args = parser.parse_args()
    try:
        root = root_path(args.root)
        if args.command == 'scan':
            result = scan(root)
        elif args.command == 'register':
            result = register(root, args.file, args.role, args.status, args.parent, args.note)
        else:
            result = package(root, args.ids, args.out, args.require_role)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as exc:
        parser.exit(2, 'Error: ' + str(exc) + '\n')


if __name__ == '__main__':
    main()
