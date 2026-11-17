import hashlib
from pathlib import Path
import tempfile
import unittest

import inventory_audit
import embeddings
import process_telemetry
from test_sources import fixture,uploaded


class InventoryAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=fixture(self.temp.name)

    def test_readonly_recursive_inventory_and_measured_history(self):
        uploaded(self.root,'Nested/Sub/First.pdf');uploaded(self.root,'Nested/Second.PDF')
        before=(self.root/'progress.json').read_bytes()
        run=inventory_audit.execute(self.root)
        self.assertEqual(run['status'],'complete');self.assertEqual(run['documents'],2)
        self.assertEqual(run['inventory_pages'],2);self.assertGreater(run['elapsed_seconds'],0)
        self.assertEqual((self.root/'progress.json').read_bytes(),before)
        self.assertFalse(run['changed_from_catalog']);self.assertFalse(run['missing_from_disk'])
        self.assertGreaterEqual(run['telemetry_samples'],2)
        detail=process_telemetry.detail(self.root,'inventory',run['run_id'])
        self.assertEqual(len(detail['pages']),2)
        self.assertTrue(detail['summary']['resources']['process_rss_mib']['peak']>0)
        self.assertEqual(detail['summary']['reason'],'remeasurement')

    def test_invalid_pdf_and_symlink_are_reported(self):
        uploaded(self.root)
        source=inventory_audit.sources.base(self.root)
        (source/'broken.pdf').write_bytes(b'not a pdf')
        (source/'linked.pdf').symlink_to(source/'broken.pdf')
        run=inventory_audit.execute(self.root)
        self.assertEqual(run['status'],'partial');self.assertEqual(run['documents'],1)
        self.assertEqual(len(run['errors']),1);self.assertIn('linked.pdf',run['skipped_links'])


if __name__=='__main__':unittest.main()
