import unittest
from graphrag_eta import estimate


class ETATests(unittest.TestCase):
    def setUp(self):
        self.old = dict(status='complete', run_id='old', total=10, started=1,
                        workflows=[dict(name='create_community_reports', elapsed_seconds=100)],
                        phases=[dict(name='embeddings', elapsed_seconds=10), dict(name='query', elapsed_seconds=20)])
        self.run = dict(status='graph', total=20, total_text_units=100, extracted_chunks=90,
                        reused_extraction_chunks=87, fresh_chunk_seconds=[10, 20, 30], phases=[], workflows=[])

    def test_cache_does_not_inflate_speed_and_includes_downstream_work(self):
        result=estimate(self.run, [self.old], now=1000)
        self.assertEqual(result['remaining_seconds'], 200+200+20+40)
        self.assertEqual(result['estimated_finish'], 1460)
        self.assertLess(result['lower_seconds'], 460)
        self.assertGreater(result['upper_seconds'], 460)

    def test_pauses_failures_and_gpu_queue_have_no_countdown(self):
        for state in ['paused','failed','interrupted']:
            self.assertIsNone(estimate(dict(self.run, status=state), [self.old])['estimated_finish'])
        self.assertEqual(estimate(dict(self.run, phases=[dict(status='waiting_gpu')]), [self.old])['status'], 'waiting_gpu')

    def test_tail_and_overruns_do_not_claim_completion(self):
        run=dict(self.run, extracted_chunks=100, workflow='extract_graph')
        self.assertEqual(estimate(run, [self.old])['status'], 'reestimating')
        run.update(workflow='create_community_reports', workflows=[dict(name='create_community_reports',started=1)])
        self.assertIsNone(estimate(run, [self.old], now=1000)['remaining_seconds'])

    def test_no_baseline_is_not_zero_and_completion_is_zero(self):
        self.assertIsNone(estimate(self.run)['remaining_seconds'])
        self.assertEqual(estimate(dict(self.run,status='complete'))['remaining_seconds'],0)


if __name__=='__main__': unittest.main()
