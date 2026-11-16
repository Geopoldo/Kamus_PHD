import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from content_search import search, parse_query, match_text


class SearchTests(unittest.TestCase):
    def test_provenance_modes_versions_and_missing_pages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'documents'/'folder'/'file';out.mkdir(parents=True)
            text='René Brunet discussed watershed boundaries.'
            (out/'page_0001.md').write_text(text)
            source='folder/file.pdf';ident=hashlib.sha256(source.encode()).hexdigest()
            (root/'progress.json').write_text(json.dumps({'documents':[dict(source=source,folder='folder',output=str(out),page_count=2)]}))
            result=search(root,'rene brunet')
            self.assertEqual((result['total_pages'],result['pages_without_text']),(1,1))
            self.assertEqual(result['hits'][0]['document_id'],ident)
            self.assertEqual(search(root,'brunet rene','phrase')['total_pages'],0)
            self.assertEqual(search(root,'brunett','words')['total_pages'],0)
            self.assertTrue(search(root,'brunett','approximate')['hits'][0]['matches'][0]['approximate'])
            review=root/'reviews'/ident;review.mkdir(parents=True)
            record=dict(text='A corrected name: Tremblay',status='draft',original_hash=hashlib.sha256(text.encode()).hexdigest())
            (review/'1.json').write_text(json.dumps(record))
            self.assertEqual(search(root,'Tremblay')['hits'][0]['matches'][0]['version'],'human')
            record['original_hash']='stale';(review/'1.json').write_text(json.dumps(record))
            self.assertEqual(search(root,'Tremblay')['hits'][0]['matches'][0]['status'],'stale')
            secondary=root/'second_reading'/'pilot'/'case_01';secondary.mkdir(parents=True)
            (secondary/'metadata.json').write_text(json.dumps(dict(document=source,page=1)))
            (secondary/'transcription.md').write_text('René Brunet alternate reading')
            result=search(root,'Brunet')
            self.assertEqual(result['total_pages'],1)
            self.assertEqual(len(result['hits'][0]['matches']),2)
            for invalid in ('','x','*'):
                with self.assertRaises(ValueError):search(root,invalid)


class QueryTests(unittest.TestCase):
    def test_near_phrases_and_partial_criteria(self):
        criteria=parse_query('"rene brunet" watershed', 'flexible')
        for text in ('Rene Brunet', 'Rene and Brunet', 'Rene one two Brunet'):
            found=match_text(text,criteria,'flexible',{})
            self.assertEqual([x['criterion'] for x in found],[0])
        for text in ('Brunet Rene', 'Rene one two three Brunet'):
            self.assertEqual(match_text(text,criteria,'flexible',{}),[])
        found=match_text('Rene and Brunett discussed watersheds',criteria,'flexible',{})
        self.assertEqual(len(found),2)
        self.assertTrue(all(x['approximate'] for x in found))
        self.assertEqual(match_text('watershed',criteria,'words',{}),[])
        self.assertEqual(match_text('Rene one Brunet',parse_query('rene brunet','phrase'),'phrase',{}),[])
        triple=parse_query('"one two three"','flexible')
        self.assertTrue(match_text('one x two y three',triple,'flexible',{}))
        self.assertFalse(match_text('one x y two z three',triple,'flexible',{}))
        with self.assertRaises(ValueError):parse_query('"unclosed','flexible')

if __name__=='__main__':unittest.main()
