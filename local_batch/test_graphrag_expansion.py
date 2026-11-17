import tempfile
import unittest
from pathlib import Path

from embeddings import read, write
from graphrag_state import available_run, preserve_available, current_pages, coverage_changes
import graphrag_review
import graphrag_queries


class ExpansionTests(unittest.TestCase):
    def test_all_pages_prefer_current_corrections_without_requiring_review(self):
        rows = [dict(document_id='a', document='folder/a.pdf', page=p, version='original',
                     text_sha256=str(p), review_status='unreviewed') for p in range(1, 75)]
        rows += [dict(rows[0], version='human', text_sha256='correction', review_status='saved'),
                 dict(rows[1], version='human', text_sha256='stale edit', review_status='stale')]
        result = current_pages(dict(records=rows))
        self.assertEqual(len(result), 74)
        self.assertEqual(result[0]['version'], 'human')
        self.assertEqual(result[1]['version'], 'original')
        changes = coverage_changes(result, rows[:30])
        self.assertEqual(changes, dict(new_pages=44, changed_pages=1, unchanged_pages=29, removed_pages=0))
        self.assertNotIn('selection_reason', rows[0])

    def test_old_graph_and_queries_remain_available_during_expansion_and_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = root/'knowledge_graph/pilot_30'
            old, new = '20261116T120000', '20261116T130000'
            write(directory/'latest.json', dict(run_id=old))
            write(directory/'runs'/old/'manifest.json', dict(status='complete', total=30, run_id=old, input_sha256='old'))
            write(directory/'runs'/old/'review.json', dict(pages=30))
            write(directory/'runs'/old/'index_manifest.json', dict(files={'entities.parquet':'hash'}))
            preserve_available(directory)
            write(directory/'latest.json', dict(run_id=new))
            for state in ('graph', 'failed'):
                write(directory/'runs'/new/'manifest.json', dict(status=state, total=645, run_id=new))
                preserve_available(directory)
                self.assertEqual(available_run(directory), old)
                self.assertEqual(graphrag_review.get(root)['result']['pages'], 30)
                status = graphrag_review.status(root)
                self.assertEqual(status['status'], state)
                self.assertEqual(status['available_pages'], 30)
                self.assertTrue(status['result_ready'])
                self.assertFalse(status['build_result_ready'])
            job = graphrag_queries.create(root, dict(question='Which places are mentioned?', auto_fishbone=False), launch=False)
            self.assertEqual(job['pilot_run'], old)
            self.assertEqual(job['input_sha256'], 'old')
            self.assertEqual(job['corpus_pages'], 30)

    def test_partial_build_does_not_become_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory=Path(tmp)
            write(directory/'latest.json', dict(run_id='20261116T120000'))
            write(directory/'runs/20261116T120000/manifest.json', dict(status='complete'))
            preserve_available(directory)
            self.assertEqual(read(directory/'active.json'), {})

    def test_archived_sources_are_flagged_without_mutating_historical_graph(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); directory = root/'knowledge_graph/pilot_30'
            key = '20261116T120000'
            records = [dict(document='keep.pdf', page=1), dict(document='duplicate.pdf', page=1), dict(document='duplicate.pdf', page=2)]
            write(directory/'runs'/key/'inputs.json', dict(records=records))
            write(root/'progress.json', dict(documents=[dict(source='keep.pdf')]))
            result = graphrag_review.source_availability(root, key)
            self.assertEqual(result, dict(known=True, archived_pages=2, archived_documents=1))
            self.assertEqual(read(directory/'runs'/key/'inputs.json')['records'], records)


if __name__ == '__main__': unittest.main()
