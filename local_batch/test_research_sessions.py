import sqlite3,tempfile,time,unittest
from pathlib import Path
import research_sessions as S
import reading_matrix as M
import sources
from test_sources import fixture,uploaded,transcribed
class SessionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=fixture(self.tmp.name);self.item=uploaded(self.root);self.docs=transcribed(self.root,'Synthetic family met by the river.')
  self.ref={'document_id':self.item['id'],'document':self.item['source'],'page':1,'version':'original','note':'Useful synthetic note','contexts':[{'kind':'simple_search','query':'family','filters':{'mode':'phrase'}}]}
  self.payload={'title':'Synthetic session','objective':'Study synthetic relationships','researcher':'Tester','curator':'Reviewer','records':[self.ref],'searches':[{'id':'query1','kind':'simple_search','query':'family','created':time.time(),'parameters':{'mode':'phrase'}}]}
 def test_resume_accumulate_isolate_and_revision_conflict(self):
  first=S.save(self.root,self.payload);self.assertEqual(first['readings'],1)
  p=dict(first);p['records']=[self.ref,dict(self.ref,contexts=[{'kind':'cross_analysis','filters':{'priority':['Alta']}}])];second=S.save(self.root,p)
  self.assertEqual(second['readings'],1);self.assertEqual(len(second['records'][0]['contexts']),2)
  self.assertEqual(second['records'][0]['original_text'],second['records'][0]['text'])
  with self.assertRaises(FileExistsError):S.save(self.root,first)
  other=S.save(self.root,dict(self.payload,title='Another objective',records=[],searches=[]))
  self.assertEqual(S.get(self.root,other['id'])['readings'],0);self.assertEqual(S.get(self.root,first['id'])['readings'],1)
  self.assertEqual(len(S.listing(self.root)),2);self.assertTrue((S.path(self.root,first['id']).parent/'revision-1.json').exists())
 def test_snapshots_survive_corrections_and_retirement(self):
  session=S.save(self.root,self.payload);before=session['records'][0]['text'];(Path(self.docs[0]['output'])/'page_0001.md').write_text('Changed later')
  session['records'][0]['note']='Updated note';saved=S.save(self.root,session);self.assertEqual(saved['records'][0]['text'],before)
  sources.archive(self.root,[self.item['id']]);self.assertEqual(S.save(self.root,saved)['records'][0]['text'],before)
 def test_matrix_uses_session_snapshot_and_links_export_answers(self):
  session=S.save(self.root,self.payload);(Path(self.docs[0]['output'])/'page_0001.md').write_text('Changed later')
  job=M.create(self.root,{'session_id':session['id'],'records':[self.ref],'questions':['Who met by the river?']},launch=False)
  self.assertEqual(job['rows'][0]['text'],'Synthetic family met by the river.');self.assertEqual(job['session_id'],session['id'])
  job.update(status='complete',completed=1,cells=[{'row':0,'question':0,'status':'supported','parts':[{'status':'supported','answer':'Synthetic family','evidence_quote':'Synthetic family','evidence_quotes':['Synthetic family','met by the river.']}],'errors':[]}]);sources.write(M.job_path(self.root,job['id']),job)
  other=S.save(self.root,dict(self.payload,title='Separate',records=[],searches=[]));self.assertEqual(len(S.jobs(self.root,session['id'])),1);self.assertEqual(S.jobs(self.root,other['id']),[])
  output=Path(self.tmp.name)/'export.sqlite';output.write_bytes(S.sqlite_bytes(self.root,session['id']));db=sqlite3.connect(output)
  self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(),[])
  self.assertEqual(db.execute('SELECT text,original_text FROM readings WHERE selected=1').fetchone(),('Synthetic family met by the river.',)*2)
  self.assertEqual(db.execute('SELECT text FROM questions').fetchone()[0],'Who met by the river?');self.assertEqual(db.execute('SELECT answer,evidence_quote FROM answers').fetchone(),('Synthetic family','Synthetic family'))
  self.assertEqual(db.execute('SELECT evidence_quote FROM answers ORDER BY id').fetchall(),[('Synthetic family',),('met by the river.',)])
  self.assertIn('phrase',db.execute('SELECT parameters_json FROM search_events').fetchone()[0]);db.close()
 def test_invalid_inputs_and_snapshot_hashes(self):
  for field in ['title','objective','researcher']:
   with self.assertRaises(ValueError):S.save(self.root,dict(self.payload,**{field:''}))
  with self.assertRaises(ValueError):S.get(self.root,'../secret')
  with self.assertRaises(FileExistsError):S.save(self.root,dict(self.payload,records=[dict(self.ref,text_sha256='wrong')]))
  session=S.save(self.root,self.payload)
  with self.assertRaises(ValueError):M.create(self.root,{'session_id':session['id'],'records':[dict(self.ref,version='human')],'questions':['Test question?']},launch=False)
if __name__=='__main__':unittest.main()
