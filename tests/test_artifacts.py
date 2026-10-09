import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'skills/artifact-handoff/scripts/artifacts.py'
spec = importlib.util.spec_from_file_location('artifacts', SCRIPT)
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


class ArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / 'source'
        self.root.mkdir()
        (self.root / 'editable.svg').write_text('<svg/>', encoding='utf-8')
        (self.root / '海报最终.txt').write_text('export', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def records(self):
        s = a.register(self.root, 'editable.svg', 'source')
        e = a.register(self.root, '海报最终.txt', 'export', 'final', s['id'], '<script>alert(1)</script>')
        return s, e

    def test_exact_duplicates_and_unknown_finality(self):
        (self.root / 'copy.txt').write_text('export', encoding='utf-8')
        result = a.scan(self.root)
        self.assertEqual(len(result['exact_duplicates']), 1)
        self.assertTrue(all(not f['matching_records'] for f in result['files']))
        self.assertFalse((self.root / a.STATE).exists())

    def test_noncanonical_root_is_normalized(self):
        nested = self.root / 'child'
        nested.mkdir()
        noncanonical = nested / '..'
        record = a.register(noncanonical, 'editable.svg', 'source', 'final')
        self.assertEqual(record['path'], 'editable.svg')
        self.assertEqual(len(a.scan(noncanonical)['files']), 2)
        a.package(noncanonical, [record['id']], self.base / 'normalized-delivery', [])

    def test_delivery_hashes_unicode_and_escaping(self):
        s, e = self.records()
        out = self.base / 'delivery'
        a.package(self.root, [s['id'], e['id']], out, ['source', 'export'])
        manifest = json.loads((out / 'manifest.json').read_text(encoding='utf-8'))
        for record in manifest['artifacts']:
            self.assertEqual(a.digest(out / record['packaged_path']), record['sha256'])
        preview = (out / 'index.html').read_text(encoding='utf-8')
        self.assertIn('海报最终.txt', preview)
        self.assertIn('&lt;script&gt;', preview)
        self.assertNotIn('<script>', preview)
        self.assertEqual((self.root / 'editable.svg').read_text(), '<svg/>')

    def test_missing_source_blocks_delivery(self):
        _, e = self.records()
        with self.assertRaisesRegex(ValueError, 'Missing required'):
            a.package(self.root, [e['id']], self.base / 'delivery', ['source', 'export'])

    def test_changed_ancestor_blocks_delivery(self):
        _, e = self.records()
        (self.root / 'editable.svg').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            a.package(self.root, [e['id']], self.base / 'delivery', [])

    def test_changed_export_blocks_delivery(self):
        s, e = self.records()
        (self.root / e['path']).write_text('changed')
        with self.assertRaisesRegex(ValueError, 'changed'):
            a.package(self.root, [s['id'], e['id']], self.base / 'delivery', [])

    def test_path_traversal_rejected(self):
        (self.base / 'outside.txt').write_text('outside')
        with self.assertRaises(ValueError):
            a.register(self.root, '../outside.txt', 'asset')
        with self.assertRaises(ValueError):
            a.register(self.root, str(self.base / 'outside.txt'), 'asset')

    def test_existing_and_nested_outputs_rejected(self):
        s, e = self.records()
        with self.assertRaises(ValueError):
            a.package(self.root, [s['id'], e['id']], self.root / 'delivery', [])
        out = self.base / 'existing'
        out.mkdir()
        (out / 'keep.txt').write_text('keep')
        with self.assertRaises(ValueError):
            a.package(self.root, [s['id'], e['id']], out, [])
        self.assertEqual((out / 'keep.txt').read_text(), 'keep')

    def test_draft_only_rejected(self):
        s = a.register(self.root, 'editable.svg', 'source')
        with self.assertRaisesRegex(ValueError, 'final'):
            a.package(self.root, [s['id']], self.base / 'delivery', [])

    def test_same_basename_does_not_collide(self):
        (self.root / 'sub').mkdir()
        (self.root / 'sub/editable.svg').write_text('second')
        first = a.register(self.root, 'editable.svg', 'source', 'final')
        second = a.register(self.root, 'sub/editable.svg', 'source')
        out = self.base / 'delivery'
        a.package(self.root, [first['id'], second['id']], out, ['source'])
        self.assertEqual(len(list((out / 'files').rglob('*.svg'))), 2)


if __name__ == '__main__':
    unittest.main()
