import hashlib,json,tempfile,unittest
from pathlib import Path
import review,triage
class TriageTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.out=self.root/'documents'/'sample';self.out.mkdir(parents=True)
  self.doc=dict(source='sample.pdf',output=str(self.out),page_count=1,pages=[dict(number=1,status='needs_review')]);self.ident=review.key(self.doc)
  (self.root/'progress.json').write_text(json.dumps(dict(documents=[self.doc])))
  (self.out/'page_0001.md').write_text('Synthetic original');(self.out/'page_0001.json').write_text('{"status":"needs_review","flags":["repeated_lines"]}')
 def data(self):return dict(document=self.ident,page=1,decision='correct',reviewer='Tester',original_hash=hashlib.sha256(b'Synthetic original').hexdigest(),review_revision=0,previous_id=None)
 def test_preserve_and_history(self):
  a=triage.save(self.root,self.data());self.assertTrue(a['applicable']);self.assertEqual(a['baseline_flags'],['repeated_lines'])
  d=self.data();d.update(previous_id=a['id'],decision='incorrect');b=triage.save(self.root,d)
  self.assertEqual(b['previous_id'],a['id']);self.assertEqual(len((self.root/'triage_events.jsonl').read_text().splitlines()),2)
  self.assertEqual((self.out/'page_0001.md').read_text(),'Synthetic original');self.assertFalse((self.root/'reviews').exists())
 def test_concurrent_decision(self):
  triage.save(self.root,self.data())
  with self.assertRaises(FileExistsError):triage.save(self.root,self.data())
 def test_changed_review_invalidates_decision(self):
  triage.save(self.root,self.data())
  review.save(self.root,dict(document=self.ident,page=1,text='Synthetic edit',reviewer='Tester',status='draft',original_hash=self.data()['original_hash'],revision=0))
  self.assertFalse(triage.index(self.root)[self.ident+':1']['applicable'])
  with self.assertRaises(FileExistsError):triage.save(self.root,self.data())
 def test_method_required(self):
  d=self.data();d['decision']='different_method'
  with self.assertRaises(ValueError):triage.save(self.root,d)
  d['method']='regions';self.assertEqual(triage.save(self.root,d)['method'],'regions')
 def test_changed_source(self):
  triage.save(self.root,self.data());(self.out/'page_0001.md').write_text('Different original')
  self.assertFalse(triage.index(self.root)[self.ident+':1']['applicable'])
  with self.assertRaises(FileExistsError):triage.save(self.root,self.data())
 def test_invalid_requests(self):
  for data in [[],dict(self.data(),page=True),dict(self.data(),reviewer=''),dict(self.data(),decision='unknown')]:
   with self.assertRaises(ValueError):triage.save(self.root,data)
if __name__=='__main__':unittest.main()
