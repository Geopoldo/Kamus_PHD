import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import graphrag_queries as queries
from embeddings import write,read


class GraphQueryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        pilot=self.root/'knowledge_graph/pilot_30';write(pilot/'latest.json',dict(run_id='20261116T120000'))
        write(pilot/'runs/20261116T120000/manifest.json',dict(status='graph',input_sha256='saved'))

    def test_question_waits_for_exact_pilot_and_rejects_duplicate_worker(self):
        job=queries.create(self.root,dict(question='Where did the families live?',mode='local',author='Researcher'),launch=False)
        self.assertEqual(job['pilot_run'],'20261116T120000')
        self.assertEqual(job['input_sha256'],'saved')
        self.assertEqual(job['status'],'queued')
        with self.assertRaises(ValueError):queries.create(self.root,dict(question='Another question'),launch=False)
        self.assertEqual(queries.get(self.root,job['id'])['author'],'Researcher')
        with self.assertRaises(ValueError):queries.get(self.root,'../../outside')

    def test_input_validation(self):
        for payload in [dict(question='x'),dict(question=['private']),dict(question='Valid question',mode='remote'),dict(question='Valid question',author={})]:
            with self.assertRaises(ValueError):queries.create(self.root,payload,launch=False)

    def test_graph_only_contains_retrieved_pairs(self):
        review=dict(nodes=[dict(id='PERSON::A',graph_entity_id='a'),dict(id='PLACE::B',graph_entity_id='b'),dict(id='FAMILY::C',graph_entity_id='c')],relationships=[dict(source='PERSON::A',target='PLACE::B'),dict(source='FAMILY::C',target='PLACE::B')])
        local=queries.context_graph({'relationships':[dict(source='PLACE::B',target='PERSON::A')],'entities':[]},review,[],[],'local','The model invents C is related to B')
        self.assertEqual(local['relationships'],review['relationships'][:1])
        global_graph=queries.context_graph({},review,[dict(human_readable_id=7,community=1)],[dict(community=1,entity_ids=['a','b'])],'global','Supported [Data: Reports (7)]')
        self.assertEqual(global_graph['relationships'],review['relationships'][:1])
        missing=queries.context_graph({},review,[dict(human_readable_id=7,community=1)],[],'global','[Data: Reports (999)]')
        self.assertEqual(missing['relationships'],[])


    def test_index_changes_and_outside_paths_are_rejected(self):
        import hashlib
        directory=self.root/'index';directory.mkdir();path=directory/'entities.parquet';path.write_bytes(b'fixed snapshot')
        manifest=dict(files={'entities.parquet':hashlib.sha256(path.read_bytes()).hexdigest()})
        queries.verify_index(directory,manifest)
        path.write_bytes(b'changed')
        with self.assertRaises(ValueError):queries.verify_index(directory,manifest)
        with self.assertRaises(ValueError):queries.verify_index(directory,dict(files={'../outside':'unknown'}))
        with self.assertRaises(ValueError):queries.verify_index(directory,dict(files={}))

    def test_csv_preserves_question_author_and_escapes_formulas(self):
        job=queries.create(self.root,dict(question='=FORMULA()',author='Analyst'),launch=False)
        edge=dict(source='@name',target='Place',fields=dict(relation='lived at',event_time='unknown',document_time='1933'),page=dict(folder='Folder',document='File.pdf',page=1,version='original'),quote_status='found',human_validation='unreviewed')
        job.update(status='complete',graph=dict(relationships=[edge]));write(queries.path_for(self.root,job['id']),job)
        rows=list(csv.DictReader(io.StringIO(queries.csv_bytes(self.root,job['id']).decode('utf-8-sig'))))
        self.assertEqual(rows[0]['question'],"'=FORMULA()")
        self.assertEqual(rows[0]['source'],"'@name")
        self.assertEqual(rows[0]['author'],'Analyst')


if __name__=='__main__':unittest.main()
