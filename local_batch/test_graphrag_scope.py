import copy
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from embeddings import write, read
from graphrag_scope import normalize, restrict_tables
import graphrag_queries as queries
from graphrag_provenance import analyze_answer, index_records


class SourceScopeTests(unittest.TestCase):
    def setUp(self):
        self.inputs=[dict(id='p'+str(i),document_id='d'+str(i),document=f'{folder}/source.pdf',folder=folder,
                          page=1,version='original',review_status='pending',text_sha256='hash') for i,folder in [(1,'A'),(2,'B')]]
        self.review=dict(selection=self.inputs,nodes=[dict(id='PERSON::A',type='PERSON',mentions=[dict(text_unit_id='u'+str(i),page=p,quotes=[dict(quote='allowed' if i==1 else 'EXCLUDED_SECRET')]) for i,p in enumerate(self.inputs,1)]),dict(id='PLACE::B',type='PLACE',mentions=[])],
                         relationships=[dict(source='PERSON::A',target='PLACE::B',page=p,text_unit_id='u'+str(i),description='allowed relation' if i==1 else 'EXCLUDED_SECRET',quotes=[]) for i,p in enumerate(self.inputs,1)])
        self.tables=dict(
            text_units=pd.DataFrame([dict(id='u'+str(i),document_id='p'+str(i),text='allowed' if i==1 else 'EXCLUDED_SECRET',entity_ids=['e1','e2'],relationship_ids=['r'],covariate_ids=[]) for i in (1,2)],index=[3,9]),
            entities=pd.DataFrame([dict(id='e'+str(i),human_readable_id=i,title=title,type=kind,description='EXCLUDED_SECRET',text_unit_ids=['u1','u2'],frequency=2,degree=1) for i,title,kind in [(1,'PERSON::A','PERSON'),(2,'PLACE::B','PLACE')]]),
            relationships=pd.DataFrame([dict(id='r',human_readable_id=4,source='PERSON::A',target='PLACE::B',description='merged EXCLUDED_SECRET',weight=2,combined_degree=2,text_unit_ids=['u1','u2'])]),
            communities=pd.DataFrame([dict(id='c',human_readable_id=0,community=0,level=0,parent=-1,children=[],title='EXCLUDED_SECRET',entity_ids=['e1','e2'],relationship_ids=['r'],text_unit_ids=['u1','u2'],period='',size=2)]),
            community_reports=pd.DataFrame([dict(community=0,full_content='EXCLUDED_SECRET')]))

    def test_filters_are_validated_and_conjoined(self):
        for value in [[],{'documents':['missing']},{'folders':['A'],'documents':['B/source.pdf']},{'documents':'A/source.pdf'}]:
            with self.assertRaises(ValueError):normalize(value,self.inputs)
        self.assertEqual(normalize({'folders':['A','A']},self.inputs),dict(folders=['A'],documents=[]))

    def test_no_merged_description_or_citation_can_leak_excluded_sources(self):
        original=copy.deepcopy(self.review)
        tables,inputs,review=restrict_tables(self.tables,self.inputs,self.review,dict(folders=['A']))
        self.assertEqual(self.review,original)
        self.assertEqual(list(tables['text_units'].index),[3])
        self.assertEqual(len(tables['community_reports']),0)
        for name in ['entities','relationships','text_units','communities']:
            self.assertNotIn('EXCLUDED_SECRET',tables[name].to_json())
        self.assertIn('EXCLUDED_SECRET',self.tables['entities'].to_json())
        job=dict(mode='local',answer='[Data: Relationships (4); Entities (1); Sources (3)]',context=dict(relationships=[dict(id='4',source='PERSON::A',target='PLACE::B')],entities=[dict(id='1',entity='PERSON::A')],sources=[dict(id='3',text='allowed')]))
        result=analyze_answer(job,index_records(tables),inputs,review)
        for ref in result['citations'][0]['records']:
            self.assertEqual(ref['status'],'resolved')
            self.assertTrue(all(p['page']['folder']=='A' for p in ref['pages']))
        self.assertTrue(all(e['page']['folder']=='A' for e in result['graph']['relationships']))

    def test_scope_is_frozen_with_question_and_global_scope_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);pilot=root/'knowledge_graph/pilot_30';run='20261116T120000'
            write(pilot/'latest.json',dict(run_id=run));write(pilot/'runs'/run/'manifest.json',dict(status='complete',input_sha256='frozen',total=2))
            write(pilot/'runs'/run/'inputs.json',dict(records=self.inputs))
            payload=dict(question='Where is A?',source_filters=dict(documents=['A/source.pdf']))
            with self.assertRaises(ValueError):queries.create(root,dict(payload,mode='global'),launch=False)
            with self.assertRaises(ValueError):queries.create(root,dict(payload,pilot_run='20261116T130000'),launch=False)
            job=queries.create(root,payload,launch=False)
            self.assertEqual(job['scope_input_ids'],['p1'])
            self.assertEqual(job['scope_pages'],1)
            self.assertEqual(read(queries.path_for(root,job['id']))['source_filters']['documents'],['A/source.pdf'])


if __name__=='__main__':unittest.main()
