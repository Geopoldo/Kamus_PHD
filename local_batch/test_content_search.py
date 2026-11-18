import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from content_search import search, parse_query, match_text
from content_search import normalize
from content_search_query import parse_boolean, evaluate_boolean


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
    def logical(self, text, query, approximate=False):
        mode='boolean_approximate' if approximate else 'boolean'
        criteria,expression=parse_boolean(query,normalize)
        found=match_text(text,criteria,mode,{})
        return evaluate_boolean(expression,{c['criterion'] for c in found})

    def test_boolean_precedence_parentheses_and_implicit_and(self):
        for text,query,expected in [
            ('alpha','alpha OR beta AND gamma',True),
            ('beta','alpha OR beta AND gamma',False),
            ('beta gamma','alpha OR beta AND gamma',True),
            ('alpha','(alpha OR beta) AND gamma',False),
            ('alpha gamma','(alpha OR beta) gamma',True),
            ('alpha beta','alpha NOT beta',False),
            ('alpha','alpha AND NOT (beta OR gamma)',True),
            ('alpha gamma','alpha AND NOT (beta OR gamma)',False),
            ('alpha','NOT NOT alpha',True),
            ('gamma','NOT (alpha OR beta)',True),
            ('and alpha','"AND" alpha',True),
            ('alpha','"AND" alpha',False),
            ('alpha','alpha OR NOT beta',True),
            ('alpha beta','alpha OR NOT beta',True),
        ]:
            with self.subTest(text=text,query=query):self.assertEqual(self.logical(text,query),expected)
        # Opt-in only: legacy searches still treat upper-case operators as words.
        self.assertEqual([c['terms'] for c in parse_query('alpha AND beta','words')],[['alpha'],['and'],['beta']])

    def test_boolean_errors_and_negation_approximation(self):
        for query in ['alpha AND','OR alpha','alpha OR OR beta','(alpha','alpha)','()','NOT','alpha AND ()','""','"alpha\nbeta"',' '.join('t'+str(i) for i in range(21))]:
            with self.subTest(query=query):
                with self.assertRaises(ValueError):parse_query(query,'boolean')
        self.assertTrue(self.logical('Rene and Brunett','"Rene Brunet"',True))
        self.assertFalse(self.logical('Rene and Brunett','"Rene Brunet"'))
        self.assertTrue(self.logical('Brunett','NOT Brunet'))
        self.assertFalse(self.logical('Brunett','NOT Brunet',True))

    def test_literal_variants_keep_exact_and_approximate_occurrences(self):
        text='😀 René Brunet met Rene Brunett. BRUNET returned.'
        found=match_text(text,parse_query('rene brunet','flexible'),'flexible',{})
        rene,brunet=found
        self.assertEqual([v['text'] for v in rene['variants']],['René','Rene'])
        self.assertTrue(rene['exact']);self.assertFalse(rene['approximate'])
        self.assertTrue(brunet['exact']);self.assertTrue(brunet['approximate'])
        self.assertEqual([(v['text'],v['approximate']) for v in brunet['variants']],[('Brunet',False),('Brunett',True),('BRUNET',False)])
        self.assertEqual([text[a:b] for a,b in brunet['offsets']],['Brunet','Brunett','BRUNET'])
        repeated=match_text('Brunett Brunett',parse_query('Brunet','flexible'),'flexible',{})[0]
        self.assertEqual(repeated['variants'][0]['count'],2)
        phrase=match_text('Rene and Brunett',parse_query('"Rene Brunet"','flexible'),'flexible',{})[0]
        self.assertEqual(phrase['variants'][0]['text'],'Rene and Brunett')
        self.assertEqual(phrase['variants'][0]['words'],['Rene','Brunett'])

    def test_boolean_uses_one_reading_and_keeps_absence_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'documents'/'file';out.mkdir(parents=True)
            source='file.pdf';ident=hashlib.sha256(source.encode()).hexdigest()
            (out/'page_0001.md').write_text('alpha beta')
            (out/'page_0002.md').write_text('gamma')
            (root/'progress.json').write_text(json.dumps({'documents':[dict(source=source,folder='folder',output=str(out),page_count=2)]}))
            review=root/'reviews'/ident;review.mkdir(parents=True)
            (review/'1.json').write_text(json.dumps({'text':'gamma'}))
            self.assertEqual(search(root,'alpha AND gamma','boolean')['total_pages'],0)
            result=search(root,'NOT beta','boolean')
            self.assertEqual(result['total_pages'],2)
            self.assertEqual([m['version'] for m in result['hits'][0]['matches']],['human'])
            match=result['hits'][0]['matches'][0]
            self.assertEqual(match['criteria'],[]);self.assertEqual(match['missing_criteria'],[0]);self.assertTrue(match['query_matches'])
            snapshot=search(root,'NOT beta','boolean',document_id=ident,page_number=1,include_text=True)
            self.assertEqual([(m['version'],m['query_matches']) for m in snapshot['hits'][0]['matches']],[('human',True),('original',False)])

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
