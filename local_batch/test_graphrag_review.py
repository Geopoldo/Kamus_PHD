import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import graphrag_review as graph


class EvidenceTests(unittest.TestCase):
    def test_citation_is_textual_not_semantic(self):
        text = 'John lived near the lake.\nHis brother was Peter.'
        checks = graph.quote_checks('QUOTE: «John lived near the lake.»', text)
        self.assertTrue(checks[0]['exact'])
        self.assertEqual(graph.quote_checks('QUOTE: «John owned the lake.»',text)[0]['whitespace_match'],False)
        self.assertEqual(graph.quote_checks('A relationship without quoted evidence',text),[])

    def test_only_whitespace_variation_is_tolerated(self):
        checks = graph.quote_checks('QUOTE: "John lived near the lake."', 'John lived\nnear the lake.')
        self.assertFalse(checks[0]['exact'])
        self.assertTrue(checks[0]['whitespace_match'])
        self.assertFalse(graph.quote_checks('QUOTE: «JOHN lived near the lake.»','John lived near the lake.')[0]['whitespace_match'])

    def test_source_uses_saved_version_and_reports_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);directory=root/'knowledge_graph/pilot_30';run=directory/'runs/20261116T120000';run.mkdir(parents=True)
            (directory/'latest.json').write_text(json.dumps(dict(run_id=run.name)))
            record=dict(document_id='doc',page=3,version='human',key='doc:3:human',text='Original claim',text_sha256='saved')
            (run/'inputs.json').write_text(json.dumps(dict(records=[record])))
            with patch.object(graph,'scan',return_value={'records':[dict(record,text='New claim',text_sha256='changed')]}):
                answer=graph.page(root,'doc',3,'human')
                self.assertEqual(answer['text'],'Original claim')
                self.assertTrue(answer['changed'])
                (directory/'latest.json').write_text(json.dumps(dict(run_id='20261116T130000')))
                self.assertEqual(graph.page(root,'doc',3,'human',run_id=run.name)['text'],'Original claim')
                (directory/'latest.json').write_text(json.dumps(dict(run_id=run.name)))
                with self.assertRaises(ValueError):graph.page(root,'../secret',3,'human')
                with self.assertRaises(ValueError):graph.page(root,'doc',3,'original')

    def test_inventory_keeps_entities_without_edges_and_each_page(self):
        page=dict(document_id='d',document='f.pdf',folder='f',page=1,version='original',review_status='unreviewed',text_sha256='fixed')
        units={'a':dict(document_id='p1',text='John near Lake.'),'b':dict(document_id='p2',text='John near Lake.')}
        entity=dict(title='PERSON::JOHN',type='PERSON',description='QUOTE: «John»')
        result=graph.entity_inventory([dict(source_id='a',entities=[entity],relationships=[]),dict(source_id='b',entities=[entity],relationships=[])],units,{'p1':page,'p2':dict(page,page=2)})
        self.assertEqual(len(result),1)
        self.assertEqual([m['page']['page'] for m in result['PERSON::JOHN']['mentions']],[1,2])
        self.assertTrue(result['PERSON::JOHN']['mentions'][0]['quotes'][0]['exact'])

    def test_engine_time_excludes_loading_and_cached_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            run=Path(tmp); (run/'graph').mkdir()
            (run/'manifest.json').write_text(json.dumps(dict(phases=[dict(name='graph',elapsed_seconds=20,load_seconds=3),dict(name='query')])) )
            (run/'graph/engine.log').write_text('I slot print_timing: id 0 | task 1 | prompt eval time = 250.00 ms / 100 tokens\nI slot print_timing: id 0 | task 1 |        eval time = 1250.00 ms / 40 tokens\nI slot print_timing: id 0 | task 1 | total time = 1500.00 ms / 140 tokens\n')
            value=graph.runtime_summary(run)
            self.assertEqual(value['inference_seconds'],1.5)
            self.assertEqual(value['phases'][0]['timed_calls'],1)
            self.assertEqual(value['phases'][0]['generated_tokens'],40)
            self.assertIsNone(value['phases'][1]['inference_seconds'])

    def test_live_status_rejects_foreign_plan_and_skips_partial_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); directory=root/'knowledge_graph/pilot_30'; run=directory/'runs/20261116T120000';(run/'graph').mkdir(parents=True)
            (directory/'latest.json').write_text(json.dumps(dict(run_id=run.name)))
            (directory/'plan.json').write_text(json.dumps(dict(input_sha256='another-input',text_units=999)))
            (run/'manifest.json').write_text(json.dumps(dict(status='graph',input_sha256='current-input',phases=[dict(name='graph')])))
            (run/'graph/telemetry.jsonl').write_text(json.dumps(dict(time=100,vram_used_mib=5000))+'\n{"time":')
            value=graph.status(root)
            self.assertEqual(value['plan'],{})
            self.assertEqual(value['resources']['vram_used_mib'],5000)
            self.assertEqual(value['attempts'],1)
            self.assertFalse(value['result_ready'])


if __name__=='__main__':unittest.main()
