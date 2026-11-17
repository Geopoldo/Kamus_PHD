import array
import json
from pathlib import Path
import tempfile
import time
import unittest
import uuid

import embeddings as index
import embedding_worker as worker


class FakeEngine:
    calls = []
    fail = False
    def __init__(self, *args): pass
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def embed(self, text):
        self.calls.append(text)
        if self.fail:
            raise RuntimeError('Synthetic engine interruption')
        return [1.] + [0.] * 1023, len(text.split()), .01


class EmbeddingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.output = self.root / 'documents/example'
        self.output.mkdir(parents=True)
        self.doc = dict(source='Folder/Subfolder/Example.pdf', folder='Folder/Subfolder', output=str(self.output), page_count=2)
        index.write(self.root / 'progress.json', dict(documents=[self.doc]))
        (self.output / 'page_0001.md').write_text('Carlos Gómez llegó al río. ' * 200)
        (self.output / 'page_0002.md').write_text('Una segunda página conservada.')
        self.ident = index.digest(self.doc['source'])
        FakeEngine.calls = []; FakeEngine.fail = False

    def run_index(self):
        key = uuid.uuid4().hex
        index.write(self.root / 'embeddings/runs' / key / 'manifest.json', dict(run_id=key, status='queued', started=time.time()))
        index.write(self.root / 'embeddings/latest.json', dict(run_id=key))
        return worker.execute(self.root, key, factory=FakeEngine)

    def test_provenance_offsets_normalization_and_noop(self):
        run = self.run_index()
        self.assertGreater(run['generated_vectors'], 0)
        value = index.status(self.root)
        self.assertEqual(value['current_pages'], 2); self.assertFalse(value['stale'])
        db = index.connect(self.root)
        self.addCleanup(db.close)
        for row in db.execute('SELECT record FROM readings'):
            record = json.loads(row[0])
            self.assertEqual(record['document'], self.doc['source'])
            self.assertEqual(record['folder'], 'Folder/Subfolder')
        snapshot = index.scan(self.root)
        records = {r['key']:r for r in snapshot['records']}
        for row in db.execute('SELECT c.*,v.text_sha256,v.vector FROM chunks c JOIN vectors v ON v.key=c.vector_key'):
            text = records[row['reading_key']]['text'][row['start']:row['end']]
            self.assertEqual(index.digest(text), row['text_sha256'])
            self.assertAlmostEqual(sum(x*x for x in array.array('f', row['vector'])), 1.)
        calls = len(FakeEngine.calls)
        again = self.run_index()
        self.assertEqual(again['generated_vectors'], 0)
        self.assertEqual(len(FakeEngine.calls), calls)

    def test_changed_fragment_human_version_and_metadata(self):
        first = self.run_index()
        original = (self.output/'page_0001.md').read_text()
        # Correction near the end retains every preceding chunk.
        index.write(self.root/'reviews'/self.ident/'1.json', dict(text=original[:-6]+'corregido.', original_hash=index.digest(original),status='draft',revision=1))
        self.assertTrue(index.status(self.root)['stale'])
        changed = self.run_index()
        self.assertEqual(changed['changed_readings'], 1)
        self.assertEqual(changed['generated_vectors'], 1)
        self.assertEqual(index.status(self.root)['total_readings'], 3)
        path = self.root/'reviews'/self.ident/'1.json'
        data = index.read(path); data.update(status='validated', revision=2); index.write(path,data)
        meta = self.run_index()
        self.assertEqual(meta['generated_vectors'], 0)
        self.assertFalse(index.status(self.root)['stale'])

    def test_retired_sources_removed_and_cache_restorable(self):
        first = self.run_index()
        index.write(self.root/'progress.json', dict(documents=[]))
        retired = self.run_index()
        self.assertEqual(retired['removed_readings'], 2)
        self.assertEqual(index.status(self.root)['current_pages'], 0)
        index.write(self.root/'progress.json', dict(documents=[self.doc]))
        restored = self.run_index()
        self.assertEqual(restored['generated_vectors'], 0)

    def test_failed_run_keeps_previous_generation_and_recovers(self):
        first = self.run_index()
        (self.output/'page_0002.md').write_text('Una modificación nueva')
        FakeEngine.fail = True
        with self.assertRaises(RuntimeError): self.run_index()
        value = index.status(self.root)
        self.assertTrue(value['stale']); self.assertEqual(value['current_pages'], 1)
        self.assertEqual(value['job']['status'], 'failed')
        FakeEngine.fail = False
        self.assertEqual(self.run_index()['generated_vectors'], 1)
        self.assertFalse(index.status(self.root)['stale'])

    def test_empty_invalid_vectors_and_corrupted_inventory(self):
        for v in ([0.]*1024, [float('nan')]*1024, [1.]*3):
            with self.assertRaises(ValueError): worker.encode(v)
        self.run_index()
        (self.root/'progress.json').write_text('{broken')
        with self.assertRaises(ValueError): self.run_index()
        db = index.connect(self.root)
        self.assertEqual(db.execute('SELECT count(*) FROM readings').fetchone()[0],2)
        db.close()

    def test_secondary_reading_and_missing_page(self):
        path = self.root/'second_reading/run_a/case_1'
        index.write(path/'metadata.json',dict(document=self.doc['source'],page=1))
        (path/'transcription.md').write_text('Una segunda interpretación')
        (self.output/'page_0002.md').unlink()
        self.run_index()
        value = index.status(self.root)
        self.assertEqual(value['total_readings'], 2)
        self.assertEqual(value['current_pages'], 1)
        self.assertEqual(value['pages_without_text'], 1)

    def test_abandoned_worker_is_reported_as_interrupted(self):
        key=uuid.uuid4().hex
        index.write(self.root/'embeddings/latest.json',dict(run_id=key))
        index.write(self.root/'embeddings/runs'/key/'manifest.json',dict(run_id=key,status='running',pid=999999999,pid_start=None,updated=0))
        self.assertEqual(index.current(self.root)['status'],'interrupted')


if __name__ == '__main__': unittest.main()
