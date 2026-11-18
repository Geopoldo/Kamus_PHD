import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import reading_matrix as matrix


class MatrixTests(unittest.TestCase):
    def test_snapshot_versions_and_immutable_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'documents'/'folder'/'file';out.mkdir(parents=True)
            source='folder/file.pdf';ident=hashlib.sha256(source.encode()).hexdigest()
            original='Rene met the council in 1950.'
            (out/'page_0001.md').write_text(original)
            (root/'progress.json').write_text(json.dumps({'documents':[dict(source=source,folder='folder',output=str(out),page_count=1)]}))
            human=root/'reviews'/ident;human.mkdir(parents=True)
            (human/'1.json').write_text(json.dumps(dict(text='René met the council in 1951.',status='validated',original_hash=hashlib.sha256(original.encode()).hexdigest())))
            records=[dict(document_id=ident,page=1,version=v) for v in ('original','human')]
            job=matrix.create(root,dict(records=records,questions=['When did René meet the council?']),launch=False)
            self.assertEqual(job['total'],2)
            other=matrix.create(root,dict(records=records,questions=['What happened?']),launch=False)
            self.assertNotEqual(other['id'],job['id'])
            self.assertEqual(matrix.get(root,job['id'])['status'],'queued')
            self.assertEqual([r['review_status'] for r in job['rows']],['unreviewed','validated'])
            (out/'page_0001.md').write_text('Changed later')
            saved=matrix.get(root,job['id'])
            self.assertEqual(saved['rows'][0]['text'],original)
            self.assertEqual(saved['rows'][1]['text'],'René met the council in 1951.')
            self.assertEqual(matrix.snapshot(root,records[1])['review_status'],'stale')
            with self.assertRaises(ValueError):matrix.job_path(root,'../escape')
            with self.assertRaises(ValueError):matrix.create(root,dict(records=[],questions=['question']))

    def test_grounded_answers_and_full_chunk_coverage(self):
        text='The council met in 1950.'
        with self.assertRaises(ValueError):matrix.parse_answer(json.dumps(dict(status='supported',answer='1951',evidence_quote='1951')),text)
        with self.assertRaises(ValueError):matrix.parse_answer(json.dumps(dict(status='not_found',answer='invented',evidence_quote='')),text)
        calls=[]
        def request(route,payload):
            if route=='/tokenize':return dict(tokens=[1]*20)
            part=''.join(p['text'] for p in json.loads(payload['messages'][1]['content'])['passages']);calls.append(part)
            answer=dict(status='supported',answer='1950',evidence_quote='1950') if '1950' in part else dict(status='not_found',answer='',evidence_quote='')
            return dict(choices=[dict(finish_reason='stop',message=dict(content=json.dumps(answer)))])
        large='x '*7000+text
        result=matrix.answer_cell(large,'When?',request)
        self.assertEqual(result['status'],'supported');self.assertGreater(len(calls),1)
        spans=list(matrix.chunks(large));self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][0]+len(spans[-1][1]),len(large))
        self.assertTrue(any(p['evidence_quote']=='1950' for p in result['parts']))
        def broken(route,payload):raise OSError('model unavailable')
        self.assertEqual(matrix.answer_cell(text,'When?',broken)['status'],'incomplete')

    def test_whitespace_is_recovered_but_translations_and_ellipsis_are_rejected(self):
        text='Edward  Trapper\nvisited Lake Abitibi.'
        value=matrix.parse_answer(json.dumps(dict(status='supported',answer='Visitó el lago.',evidence_quote='Edward Trapper visited Lake Abitibi.')),text)
        self.assertEqual(value['evidence_quote'],text)
        self.assertEqual(value['evidence_match'],'whitespace_normalized')
        for quote in ['Edward Trapper visitó Lake Abitibi.','Edward ... Lake Abitibi.','Peter Parker visited Lake Abitibi.']:
            with self.assertRaises(ValueError):matrix.parse_answer(json.dumps(dict(status='supported',answer='answer',evidence_quote=quote)),text)

    def test_failed_output_is_retained_and_one_repair_is_attempted(self):
        attempts=[]
        def request(route,payload):
            if route=='/tokenize':return {'tokens':[1]*20}
            attempts.append(payload)
            quote='Invented translation' if len(attempts)==1 else 'Original source'
            return dict(choices=[dict(finish_reason='stop',message=dict(content=json.dumps(dict(status='supported',answer='Answer',evidence_quote=quote))))])
        value=matrix.answer_cell('Original source','Question?',request)
        self.assertEqual(value['status'],'supported')
        self.assertEqual([a['status'] for a in value['attempts']],['rejected','accepted'])
        self.assertIn('Invented translation',value['attempts'][0]['response']['choices'][0]['message']['content'])
        self.assertEqual(matrix.answer_cell('Original source','Question?',lambda *a: self.fail('Valid fragment rerun'),value)['parts'],value['parts'])

    def test_retry_preserves_frozen_inputs_valid_answers_and_rejected_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);ident='a'*32;path=matrix.job_path(root,ident)
            valid=dict(row=0,question=0,status='supported',parts=[dict(answer='Saved')],errors=[])
            failed=dict(row=1,question=0,status='incomplete',parts=[],errors=[dict(error='quote')])
            original=dict(id=ident,created=1,status='complete_with_errors',questions=['Question?'],rows=[dict(text='frozen'),dict(text='also frozen')],cells=[valid,failed],completed=2,total=2)
            matrix.write(path,original)
            updated=matrix.retry(root,dict(id=ident),launch=False)
            self.assertEqual(updated['completed'],1)
            self.assertEqual(updated['rows'],original['rows'])
            self.assertEqual(updated['cells'][0],valid)
            self.assertEqual(matrix.get(root,ident)['status'],'queued')
            self.assertEqual(json.loads((path.parent/'attempts/before_retry_001.json').read_text()),original)
            with self.assertRaises(ValueError):matrix.retry(root,dict(id=ident),launch=False)

    def test_numbered_evidence_copies_multiple_original_spans_without_invention(self):
        text='Edward Trapper is listed here.\n'+('Other content. '*40)+'\nLake Abitibi is named separately.'
        passages=matrix.evidence_passages(text)
        self.assertEqual(''.join(p['text'] for p in passages),text)
        self.assertTrue(all(len(p['text'])<=400 for p in passages))
        value=matrix.parse_answer(json.dumps(dict(status='supported',answer='Separate mentions.',evidence_ids=[1,len(passages)])),text,passages)
        self.assertEqual(value['evidence_quotes'],[passages[0]['text'],passages[-1]['text']])
        self.assertTrue(all(q in text for q in value['evidence_quotes']))
        for ids in [[],[999],[True]]:
            with self.assertRaises(ValueError):matrix.parse_answer(json.dumps(dict(status='supported',answer='Answer',evidence_ids=ids)),text,passages)

    def test_missing_literal_names_are_review_hints_not_automatic_rejections(self):
        notes=matrix.interpretation_warnings('Edward Trapper y Lake Abitibi?', 'Edward\nTrapper is listed in Abitibi Preserve.', [{'status':'supported'}])
        self.assertEqual(notes,[dict(code='name_not_literal',term='Lake Abitibi')])
        self.assertEqual(matrix.interpretation_warnings('Lake Abitibi?', 'No mention here.',[{'status':'not_found'}]),[])


if __name__=='__main__':unittest.main()
