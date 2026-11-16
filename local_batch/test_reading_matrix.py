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
            part=json.loads(payload['messages'][1]['content'])['transcription'];calls.append(part)
            answer=dict(status='supported',answer='1950',evidence_quote='1950') if '1950' in part else dict(status='not_found',answer='',evidence_quote='')
            return dict(choices=[dict(finish_reason='stop',message=dict(content=json.dumps(answer)))])
        large='x '*7000+text
        result=matrix.answer_cell(large,'When?',request)
        self.assertEqual(result['status'],'supported');self.assertGreater(len(calls),1)
        spans=list(matrix.chunks(large));self.assertEqual(spans[0][0],0);self.assertEqual(spans[-1][0]+len(spans[-1][1]),len(large))
        self.assertTrue(any(p['evidence_quote']=='1950' for p in result['parts']))
        def broken(route,payload):raise OSError('model unavailable')
        self.assertEqual(matrix.answer_cell(text,'When?',broken)['status'],'incomplete')


if __name__=='__main__':unittest.main()
