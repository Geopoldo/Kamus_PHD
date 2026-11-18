import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd
from embeddings import read,write
from graphrag_checkpoint import completed_pages,publish_checkpoint,json_lines,successful_extractions
from graphrag_state import available_run,visible_run
import graphrag_control


class Checkpoints(unittest.TestCase):
    def test_legacy_failed_empty_result_is_not_completed_evidence(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            origin=Path(tmp)/'attempt';run=Path(tmp)/'checkpoint'
            write(origin/'manifest.json',dict(extraction_errors=[dict(text_sha256=hashlib.sha256(b'failed').hexdigest())]))
            write(run/'manifest.json',dict(checkpoint_of='attempt'))
            rows=[dict(source_id=k,entities=[],relationships=[]) for k in ['bad','empty']]
            (run/'extractions.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            units=[dict(id='bad',text='failed'),dict(id='empty',text='actually empty')]
            self.assertEqual(successful_extractions(run,units),rows[1:])

    def test_page_requires_all_units_even_empty_successful_extraction(self):
        units=[dict(id='a',document_ids=['one']),dict(id='b',document_ids=['one']),dict(id='c',document_ids=['two'])]
        self.assertEqual(completed_pages(units,[dict(source_id='a'),dict(source_id='c')]),{'two'})
        self.assertEqual(completed_pages(units,[dict(source_id='a'),dict(source_id='b'),dict(source_id='c')]),{'one','two'})
        with self.assertRaises(ValueError):completed_pages([dict(id='z',document_ids=['one','two'])],[])

    def test_partial_publication_keeps_old_query_index_and_ignores_incomplete_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);d=root/'knowledge_graph/pilot_30';key='20261117T010000';run=d/'runs'/key
            records=[dict(id=str(i),document_id='doc',document='f/a.pdf',folder='f',page=i,version='original',review_status='unreviewed',text_sha256=str(i),text='John near Lake.') for i in (1,2)]
            write(d/'latest.json',dict(run_id=key));write(run/'inputs.json',dict(records=records,corpus_pages=2));write(run/'manifest.json',dict(status='interrupted'))
            old='20261116T010000';write(d/'active.json',dict(run_id=old));write(d/'runs'/old/'manifest.json',dict(total=0,status='complete'))
            (d/'output').mkdir(parents=True)
            units=[dict(id='a',document_id='1',text=records[0]['text']),dict(id='b',document_id='2',text=records[0]['text']),dict(id='c',document_id='2',text='Unfinished')]
            pd.DataFrame(units).to_parquet(d/'output/text_units.parquet')
            entity=dict(title='PERSON::JOHN',type='PERSON',description='QUOTE: «John»')
            (run/'extractions.jsonl').write_text(json.dumps(dict(source_id='a',entities=[entity],relationships=[]))+'\n'+json.dumps(dict(source_id='b',entities=[entity],relationships=[]))+'\n{"source_id":')
            self.assertEqual(len(json_lines(run/'extractions.jsonl')),2)
            result=publish_checkpoint(root)
            self.assertEqual(result['pages'],1);self.assertEqual(result['nodes'],1)
            self.assertEqual(available_run(d),old);self.assertEqual(visible_run(d),result['run_id'])
            saved=read(d/'runs'/result['run_id']/'review.json');self.assertEqual(saved['indexed_run'],old)
            self.assertEqual(saved['nodes'][0]['mentions'][0]['page']['page'],1)
            self.assertEqual(read(d/'runs'/result['run_id']/'inputs.json')['records'],records[:1])
            # Retry cannot duplicate mentions or mutate the complete question index.
            again=publish_checkpoint(root);self.assertEqual(again['nodes'],1);self.assertEqual(again['pages'],1)
            self.assertEqual(available_run(d),old)
            before=read(d/'visible.json')
            pd.DataFrame([dict(id='foreign',document_id='other',text='other')]).to_parquet(d/'output/text_units.parquet')
            with self.assertRaises(ValueError):publish_checkpoint(root)
            self.assertEqual(read(d/'visible.json'),before)

    def test_manual_pause_intent_survives_priority_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            graphrag_control.request(root,{'action':'pause'})
            self.assertEqual(graphrag_control.state(root)['desired'],'paused')
            with self.assertRaises(ValueError):graphrag_control.request(root,{'action':'kill everything'})
            self.assertEqual(read(graphrag_control.directory(root)/'control.json')['desired'],'paused')

    def test_abandoned_question_does_not_block_build(self):
        import graphrag_queries
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);write(root/'knowledge_graph/questions/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/question.json',dict(status='queued'))
            with patch.object(graphrag_queries,'get',return_value=dict(status='interrupted')):
                self.assertEqual(graphrag_control.interactive_jobs(root),[])
            with patch.object(graphrag_queries,'get',return_value=dict(status='query')):
                self.assertEqual(len(graphrag_control.interactive_jobs(root)),1)

if __name__=='__main__':unittest.main()
