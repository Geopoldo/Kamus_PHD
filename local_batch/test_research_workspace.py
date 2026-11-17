"""Synthetic tests for frozen scope, session isolation, diagrams and export."""
import hashlib,json,sqlite3,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
import research_workspace as W
import hypotheses, hypotheses_auto as H, research_sessions as S, reading_matrix as M
from reading_matrix import write
from test_sources import fixture,uploaded,transcribed

class WorkspaceTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=fixture(self.tmp.name)
  item=uploaded(self.root);transcribed(self.root,'Synthetic family moved beside the river.')
  self.ref=dict(document_id=item['id'],document=item['source'],page=1,version='original')
  self.session=S.save(self.root,dict(title='Synthetic investigation',objective='Trace a family',researcher='Tester',records=[self.ref],searches=[]))
  self.row=self.session['records'][0];self.run='20261116T120000';self.id='a'*32
  self.graph=dict(nodes=[dict(id='FAMILY',label='FAMILY',type='FAMILY',mentions=[dict(page=self.ref)])],relationships=[])
  self.job=dict(id=self.id,question='Where did the family move?',session_id=self.session['id'],pilot_run=self.run,created=time.time(),started=time.time(),status='complete',mode='local',answer='Synthetic answer',graph=self.graph)
  write(self.root/'knowledge_graph/questions'/self.id/'question.json',self.job)
  write(self.root/'knowledge_graph/pilot_30/runs'/self.run/'inputs.json',dict(records=[self.row,dict(self.row,page=2,text='Outside this question',text_sha256=hashlib.sha256(b'Outside this question').hexdigest())]))
 def test_scope_does_not_expand_to_pilot_or_client_parameters(self):
  self.assertEqual(len(W.manifest(self.root,self.id,session_id=self.session['id'])['pages']),1)
  with patch.object(H.graphrag_review,'get',return_value={'result':{}}):
   job=H.create(self.root,dict(scope='query',query_id=self.id,session_id=self.session['id'],question='Client supplied different question',author='Tester',records=[dict(self.ref,page=2)]),launch=False)
  saved=H.get(self.root,job['id']);self.assertEqual(saved['question'],self.job['question']);self.assertEqual(saved['query_id'],self.id)
  self.assertEqual([r['page'] for r in saved['rows']],[1]);self.assertEqual(saved['rows'][0]['text'],self.row['text']);self.assertEqual(saved['graph_context'],self.graph)
 def test_session_isolation_ids_pending_and_hash(self):
  with self.assertRaises(ValueError):W.evidence(self.root,self.id)
  with self.assertRaises(ValueError):W.evidence(self.root,'../secret',session_id=self.session['id'])
  with self.assertRaises(ValueError):W.evidence(self.root,self.id,kind='invented',session_id=self.session['id'])
  self.job['status']='queued';write(self.root/'knowledge_graph/questions'/self.id/'question.json',self.job)
  with self.assertRaises(ValueError):W.evidence(self.root,self.id,session_id=self.session['id'])
  self.job['status']='complete';write(self.root/'knowledge_graph/questions'/self.id/'question.json',self.job)
  write(self.root/'knowledge_graph/pilot_30/runs'/self.run/'inputs.json',dict(records=[dict(self.row,text='changed')]))
  with self.assertRaises(ValueError):W.evidence(self.root,self.id,session_id=self.session['id'])
 def test_diagrams_are_separate_and_exported(self):
  base=W.artifact_root(self.root,self.id,session_id=self.session['id'])
  payload=dict(revision=0,query_id=self.id,query_kind='knowledge_graph',session_id=self.session['id'],question=self.job['question'],author='Tester',branches=[dict(label='Mobility',items=[dict(text='Candidate move',status='explore',evidence=[self.row])])])
  W.save_diagram(self.root,payload);
  invalid=dict(payload,revision=1,branches=[dict(label='Wrong scope',items=[dict(text='Invalid source',status='explore',evidence=[dict(self.row,page=2)])])])
  with self.assertRaises(ValueError):W.save_diagram(self.root,invalid)
  for branches in (None, [None], [dict(items=None)], [dict(items=[None])], [dict(items=[dict(evidence=[{}])])]):
   with self.subTest(branches=branches),self.assertRaises(ValueError):W.save_diagram(self.root,dict(payload,revision=1,branches=branches))
  other='b'*32;write(self.root/'knowledge_graph/questions'/other/'question.json',dict(self.job,id=other))
  self.assertEqual(hypotheses.load(W.artifact_root(self.root,other,session_id=self.session['id']))['revision'],0)
  self.assertEqual(hypotheses.load(self.root/'research_sessions'/self.session['id'])['revision'],0)
  p=Path(self.tmp.name)/'export.sqlite';p.write_bytes(S.sqlite_bytes(self.root,self.session['id']));db=sqlite3.connect(p)
  artifact=json.loads(db.execute("SELECT data_json FROM research_artifacts WHERE kind='question_fishbone'").fetchone()[0]);self.assertEqual(artifact['query_id'],self.id)
  self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok');db.close()
 def test_matrix_uses_frozen_selected_readings(self):
  value=M.create(self.root,dict(session_id=self.session['id'],records=[self.ref],questions=['Where did they go?']),launch=False)
  value.update(status='complete',completed=1);write(M.job_path(self.root,value['id']),value)
  _,rows,graph=W.evidence(self.root,value['id'],'matrix',self.session['id']);self.assertEqual(rows[0]['text'],self.row['text']);self.assertEqual(graph['relationships'],[])
  with patch.object(H.graphrag_review,'get',return_value={'result':{}}):
   job=H.create(self.root,dict(scope='query',query_kind='matrix',query_id=value['id'],session_id=self.session['id'],question='Where did they go?',author='Tester'),launch=False)
  self.assertEqual(H.get(self.root,job['id'])['question'],'Where did they go?')
 def test_export_keeps_question_sources_without_marking_them_selected(self):
  self.job['context_pages']=[dict(self.ref,page=2)]
  write(self.root/'knowledge_graph/questions'/self.id/'question.json',self.job)
  p=Path(self.tmp.name)/'sources.sqlite';p.write_bytes(S.sqlite_bytes(self.root,self.session['id']));db=sqlite3.connect(p)
  self.assertEqual(db.execute('SELECT COUNT(*) FROM run_readings WHERE run_id=?',(self.id,)).fetchone()[0],2)
  self.assertEqual(db.execute('SELECT text,selected FROM readings WHERE page=2').fetchone(),('Outside this question',0))
  db.close()
 def enable_auto(self):
  self.job.update(auto_fishbone=True,language='fr',author='Tester')
  write(self.root/'knowledge_graph/questions'/self.id/'question.json',self.job)
 def advance(self):
  with patch.object(H.graphrag_review,'get',return_value={'result':{}}):
   return W.advance_followup(self.root,self.id,session_id=self.session['id'],launch=False)
 def test_auto_is_idempotent_and_recovers_missing_link(self):
  self.enable_auto();first=self.advance();second=self.advance()
  self.assertEqual(first['job_id'],second['job_id'])
  self.assertEqual(H.get(self.root,first['job_id'])['language'],'fr')
  (W.artifact_root(self.root,self.id,session_id=self.session['id'])/'fishbone_followup.json').unlink()
  self.assertEqual(self.advance()['job_id'],first['job_id'])
  self.assertEqual(len(list((self.root/'hypotheses/auto').glob('*/job.json'))),1)
 def test_auto_waits_for_worker_and_does_not_run_old_or_failed_queries(self):
  self.assertIsNone(self.advance())
  self.enable_auto();self.job['status']='failed'
  write(self.root/'knowledge_graph/questions'/self.id/'question.json',self.job)
  self.assertIsNone(self.advance());self.job['status']='complete'
  write(self.root/'knowledge_graph/questions'/self.id/'question.json',self.job)
  with patch.object(H,'create',side_effect=H.BusyError('busy')):
   self.assertEqual(self.advance()['status'],'queued')
  self.assertIn('job_id',self.advance())
 def test_auto_saves_partial_draft_and_preserves_human_revision(self):
  self.enable_auto();state=self.advance();job=H.get(self.root,state['job_id'])
  job.update(status='complete_with_errors',processed=job['total'],errors=[{'task':0,'error':'Synthetic invalid quote'}])
  job['branches'][1]['items']=[dict(text='A candidate move',status='explore',evidence=[self.row])]
  write(H.path(self.root,job['id']),job);self.advance()
  saved=W.diagram_state(self.root,self.id,session_id=self.session['id'])['saved']
  self.assertEqual(saved['revision'],1);self.assertEqual(saved['generation']['status'],'complete_with_errors')
  self.assertEqual(saved['branches'][1]['items'][0]['status'],'explore')
  saved.update(author='Human reviewer');saved['branches'][1]['items'][0]['text']='Human correction'
  W.save_diagram(self.root,saved);self.advance()
  self.assertEqual(W.diagram_state(self.root,self.id,session_id=self.session['id'])['saved']['revision'],2)
 def test_auto_does_not_overwrite_human_draft_created_during_generation(self):
  self.enable_auto();state=self.advance()
  W.save_diagram(self.root,dict(revision=0,query_id=self.id,query_kind='knowledge_graph',session_id=self.session['id'],author='Reviewer',branches=[dict(label='Human branch',items=[])]))
  job=H.get(self.root,state['job_id']);job['status']='complete';write(H.path(self.root,job['id']),job);self.advance()
  saved=W.diagram_state(self.root,self.id,session_id=self.session['id'])['saved']
  self.assertEqual(saved['author'],'Reviewer');self.assertEqual(saved['revision'],1)
 def test_matrix_only_auto_generates_for_one_question(self):
  payload=dict(session_id=self.session['id'],records=[self.ref],auto_fishbone=True,language='en',author='Tester')
  one=M.create(self.root,dict(payload,questions=['Where?']),launch=False)
  self.assertTrue(one['auto_fishbone'])
  one['status']='complete';write(M.job_path(self.root,one['id']),one)
  many=M.create(self.root,dict(payload,questions=['Where?','When?']),launch=False)
  self.assertFalse(many['auto_fishbone'])
if __name__=='__main__':unittest.main()
