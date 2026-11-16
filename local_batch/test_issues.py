import json,tempfile,unittest,hashlib
from pathlib import Path
import issues
class IssueTests(unittest.TestCase):
 def setUp(self):
  self.t=tempfile.TemporaryDirectory();self.addCleanup(self.t.cleanup);self.root=Path(self.t.name);out=self.root/'documents'/'test';out.mkdir(parents=True);self.source='DEMO/test.pdf';self.ident=hashlib.sha256(self.source.encode()).hexdigest();self.out=out
  (self.root/'progress.json').write_text(json.dumps(dict(documents=[dict(source=self.source,output=str(out),page_count=1)])));(out/'page_0001.md').write_text('Original synthetic text')
 def data(self):return dict(document=self.ident,page=1,reason='not_transcribed',note='Synthetic issue',reporter='Test',status='open')
 def test_persist_and_preserve(self):
  saved=issues.save(self.root,self.data());self.assertEqual(issues.index(self.root)[self.ident+':1'],saved);self.assertEqual((self.out/'page_0001.md').read_text(),'Original synthetic text')
 def test_one_page_multiple_events_and_resolution(self):
  a=issues.save(self.root,self.data());b=issues.save(self.root,self.data());self.assertEqual(a['created'],b['created']);self.assertEqual(len(issues.index(self.root)),1)
  data=self.data();data['status']='resolved';issues.save(self.root,data);self.assertEqual(issues.index(self.root)[self.ident+':1']['status'],'resolved');self.assertEqual(len((self.root/'user_issues.jsonl').read_text().splitlines()),3)
 def test_reject_invalid(self):
  for update in [dict(page=2),dict(reason='invalid'),dict(reporter=''),dict(document='../secret'),dict(page=True)]:
   data=self.data();data.update(update)
   with self.assertRaises(ValueError):issues.save(self.root,data)
if __name__=='__main__':unittest.main()
