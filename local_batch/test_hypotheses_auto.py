import tempfile,unittest,json,sys,types
from pathlib import Path
from unittest.mock import patch
import hypotheses_auto as h
class Test(unittest.TestCase):
 def test_draft_and_rejected_quote(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);row={'document_id':'fixture','document':'fixture.pdf','folder':'synthetic','page':1,'version':'original','text':'Synthetic family moved to the river.','text_sha256':'test'}
   with patch.object(h,'snapshot',return_value=row),patch.object(h.graphrag_review,'get',return_value={'result':{}}):
    job=h.create(root,{'question':'Synthetic question','author':'Tester','records':[row]},launch=False)
   class Engine:
    def __init__(self,*args):self.token='test'
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def check(self):pass
   class Response:
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self):return json.dumps({'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'items':[{'branch':1,'hypothesis':'A candidate migration','quote':'Synthetic family moved'}]})}}]}).encode()
   with patch.dict(sys.modules,{'graphrag_pilot':types.SimpleNamespace(LocalEngine=Engine)}),patch.object(h.urllib.request,'build_opener',return_value=types.SimpleNamespace(open=lambda *a,**k:Response())):
    h.run(root,job['id'])
   result=h.get(root,job['id']);self.assertEqual(result['status'],'complete');item=result['branches'][1]['items'][0]
   self.assertEqual(item['status'],'explore');self.assertTrue(item['quote_verified']);self.assertEqual(item['evidence'][0]['page'],1)
   self.assertTrue((h.path(root,job['id']).parent/'request-0.json').exists())
   with self.assertRaises(ValueError):h.create(root,{'question':'x','author':'Tester'},launch=False)
if __name__=='__main__':unittest.main()
