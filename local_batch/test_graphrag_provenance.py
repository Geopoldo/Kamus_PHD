import unittest
from graphrag_provenance import analyze_answer, parse_citations, STRICT_LOCAL_PROMPT


class ProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.pages=[dict(id='page'+str(i),document_id='doc'+str(i),document='test.pdf',folder='test',page=i,version='original',review_status='pending',text_sha256='fixed') for i in (1,2)]
        self.tables=dict(
            text_units=[dict(id='u1',query_id='0',human_readable_id=99,document_id='page1',text='First source'),dict(id='u2',query_id='7',human_readable_id=0,document_id='page2',text='Second source')],
            entities=[dict(id='e1',human_readable_id=4,title='PERSON::A',text_unit_ids=['u1','u2'])],
            relationships=[dict(id='r1',human_readable_id=8,source='PERSON::A',target='PLACE::B',text_unit_ids=['u1','u2'])],
            community_reports=[dict(human_readable_id=92,community=3)],
            communities=[dict(community=3,entity_ids=['e1'],relationship_ids=['r1'],text_unit_ids=['u1','u2'])])
        self.edge=dict(source='PERSON::A',target='PLACE::B',text_unit_id='u1',quotes=[dict(quote='First source')])
        self.review=dict(nodes=[dict(id='PERSON::A'),dict(id='PLACE::B'),dict(id='TIME::C')],relationships=[self.edge])
        self.context=dict(sources=[dict(id='0',text='First source')],entities=[dict(id='4',entity='PERSON::A'),dict(id='5',entity='TIME::C')],relationships=[dict(id='8',source='PERSON::A',target='PLACE::B')],reports=[dict(id='3',content='A report')])

    def analyze(self,answer,mode='local'):
        return analyze_answer(dict(answer=answer,context=self.context,mode=mode),self.tables,self.pages,self.review)

    def test_sources_use_exact_adapter_index_not_human_readable_id(self):
        data=self.analyze('Evidence [Data: Sources (0, 7, 99)]')['citations'][0]['records']
        self.assertEqual(data[0]['pages'][0]['page']['page'],1)
        self.assertEqual([r['status'] for r in data],['resolved','not_in_context','not_in_context'])
        self.context['sources'][0]['text']='Modified context'
        self.assertEqual(self.analyze('[Data: Sources (0)]')['citations'][0]['records'][0]['status'],'unresolved')

    def test_multi_reference_pages_and_missing_id_never_guessed(self):
        group=self.analyze('😀 **Evidence** [Data: Relationships (8, 999, +more); Entities (4)]')['citations'][0]
        self.assertTrue(group['has_more'])
        self.assertEqual(len(group['records'][0]['pages']),2)
        self.assertEqual(group['records'][1]['status'],'not_in_context')
        self.assertEqual(len(group['records'][2]['pages']),2)

    def test_community_ids_and_scope_not_exact_support(self):
        result=self.analyze('[Data: Reports (3)]','global')
        self.assertEqual(len(result['graph']['relationships']),1)
        self.assertTrue(all(p['basis']=='community_scope' for p in result['citations'][0]['records'][0]['pages']))
        self.assertEqual(self.analyze('[Data: Reports (92)]')['citations'][0]['records'][0]['status'],'not_in_context')
        self.assertEqual(len(self.analyze('No citations','global')['graph']['relationships']),1,'Overview includes all retrieved reports, not only cited reports')

    def test_graph_keeps_isolated_entities_and_excludes_candidates_not_supplied(self):
        self.assertEqual(len(self.analyze('anything')['graph']['nodes']),3)
        self.context['relationships'][0]['in_context']=False
        self.assertEqual(self.analyze('[Data: Relationships (8)]')['graph']['relationships'],[])
        self.assertEqual(self.analyze('[Data: Relationships (8)]')['citations'][0]['records'][0]['status'],'not_in_context')

    def test_prompt_is_context_only_and_formats_without_other_variables(self):
        prompt=STRICT_LOCAL_PROMPT.format(response_type='Concise',context_data='Synthetic record')
        self.assertIn('ONLY the supplied data',prompt)
        self.assertIn('Do not add facts from prior knowledge',prompt)
        self.assertNotIn('incorporating any relevant general knowledge',prompt)

    def test_observed_formats_resolve_the_same_frozen_sources(self):
        for raw in ('[Sources (0); Relationships (8)]', '[Sources: 0; Relationships: 8]',
                    '[Data:\nSources (0); Relationships (8)]', '[Fuentes (0); Relaciones (8)]',
                    '[Données: Sources (0); Relations (8)]'):
            with self.subTest(raw=raw):
                group=self.analyze(raw)['citations'][0]
                self.assertEqual(group['raw'],raw)
                self.assertEqual([r['status'] for r in group['records']],['resolved','resolved'])
        refs=self.analyze('[Data: Entities (4); Relationships (8), (999), (8)]')['citations'][0]['records']
        self.assertEqual([(r['dataset'],r['id'],r['status']) for r in refs],
                         [('entities','4','resolved'),('relationships','8','resolved'),('relationships','999','not_in_context')])

    def test_prose_ranges_unknown_ids_and_links_never_guessed(self):
        refs=self.analyze('[Data: Sources (0-7); Relationships (none direct in 1959, but context implies region)]')['citations'][0]['records']
        self.assertTrue(all(r['status']=='invalid_id' and not r['pages'] for r in refs))
        self.assertEqual(list(parse_citations('Year [1959], [note 8], [Sources (0)](https://example.org)')),[])
        self.assertEqual(self.analyze('[Data: Unknown (0)]')['citations'][0]['records'],[])
        self.assertEqual(self.analyze('[Sources (999)]')['citations'][0]['records'][0]['status'],'not_in_context')

    def test_context_is_available_but_is_not_a_citation(self):
        result=self.analyze('No references supplied')
        self.assertEqual(result['version'],2)
        self.assertEqual(result['citations'],[])
        self.assertEqual(len(result['context_pages']),2)


if __name__=='__main__':unittest.main()
