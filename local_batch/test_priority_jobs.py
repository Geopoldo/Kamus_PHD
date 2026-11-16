import tempfile
import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import priority_audit as audit
import priority_catalog as catalog
import priority_search as search


class RecalculationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.old_job=dict(search._job);search._job.clear();search._job['running']=False
        self.addCleanup(lambda:(search._job.clear(),search._job.update(self.old_job)))
        self.revision=1;self.threads=[];real_thread=threading.Thread
        def thread(**kwargs):
            t=real_thread(**kwargs);self.threads.append(t);return t
        for p in [patch.object(catalog,'settings',side_effect=lambda root:dict(revision=self.revision)),
                  patch.object(catalog,'catalog_for',side_effect=lambda root:dict(revision=self.revision)),
                  patch.object(search,'fingerprint',return_value='fixture'),
                  patch.object(search.threading,'Thread',side_effect=thread)]:
            p.start();self.addCleanup(p.stop)

    def test_new_revision_is_queued_and_recalculated_with_separate_logs(self):
        started=threading.Event();release=threading.Event();revisions=[]
        def run(root,progress,catalog_snapshot,input_fingerprint):
            revision=catalog_snapshot['revision'];revisions.append(revision)
            if revision==1:
                started.set()
                if not release.wait(3):raise RuntimeError('Test timed out')
            return dict(catalog=catalog_snapshot,summary=dict(pages=revision),coverage=dict(inventory_pages=2,searched_pages=2,versions=2,errors=[]),changed_during_run=revision!=self.revision,fingerprint=input_fingerprint)
        with patch.object(search,'run',side_effect=run):
            search.start(self.root,requested_revision=1,reason='catalog_saved')
            self.assertTrue(started.wait(2))
            self.revision=2
            queued=search.start(self.root,requested_revision=2,reason='catalog_saved')
            self.assertEqual(queued['pending_revision'],2)
            release.set();self.threads[0].join(3)
            self.assertFalse(self.threads[0].is_alive())
        self.assertEqual(revisions,[1,2]);self.assertFalse(search._job['running'])
        events=audit.history(self.root)['events']
        self.assertEqual([e['revision'] for e in events if e['event']=='search_completed'],[2,1])
        self.assertTrue(any(e['event']=='search_queued' and e['revision']==2 for e in events))
        self.assertEqual(len({e['run_id'] for e in events if e['event']=='search_started'}),2)

    def test_failure_is_logged_and_job_stops(self):
        with patch.object(search,'run',side_effect=RuntimeError('fixture failure')):
            search.start(self.root)
            self.threads[0].join(3)
        self.assertFalse(search._job['running'])
        self.assertEqual(search._job['error'],'fixture failure')
        self.assertEqual(audit.history(self.root)['events'][0]['event'],'search_failed')

    def test_opening_stale_analysis_recalculates_saved_text_once(self):
        (self.root/'priorities').mkdir()
        (self.root/'progress.json').write_text(json.dumps({'documents':[]}))
        (self.root/'priorities/latest.json').write_text(json.dumps(dict(engine=search.ENGINE,fingerprint='old-text',catalog=dict(revision=1),pages=[])))
        with patch.object(search,'start',return_value={'running':True}) as start:
            value=search.get(self.root)
            self.assertTrue(value['stale']);self.assertTrue(value['job']['running'])
            start.assert_called_once_with(self.root,requested_revision=1,reason='saved_text_or_inventory_changed')
            search._job.update(running=True);search.get(self.root)
            self.assertEqual(start.call_count,1)
            search._job.update(running=False,error='Do not retry indefinitely');search.get(self.root)
            self.assertEqual(start.call_count,1)

    def test_a_newer_saved_revision_still_runs_after_previous_failure(self):
        revisions=[]
        def run(root,progress,catalog_snapshot,input_fingerprint):
            revision=catalog_snapshot['revision'];revisions.append(revision)
            if revision==1:
                self.revision=2
                raise RuntimeError('older revision failed')
            return dict(catalog=catalog_snapshot,summary=dict(pages=2),coverage=dict(inventory_pages=2,searched_pages=2,versions=2,errors=[]),changed_during_run=False,fingerprint=input_fingerprint)
        with patch.object(search,'run',side_effect=run):
            search.start(self.root,requested_revision=1)
            self.threads[0].join(3)
        self.assertEqual(revisions,[1,2]);self.assertFalse(search._job['running'])
        self.assertNotIn('error',search._job)
        self.assertEqual(audit.history(self.root)['events'][0]['revision'],2)


if __name__=='__main__':unittest.main()
