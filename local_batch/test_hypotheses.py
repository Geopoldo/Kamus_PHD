import tempfile,unittest,json
from pathlib import Path
from hypotheses import load,save
class Test(unittest.TestCase):
 def test_versions(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);data={'revision':0,'question':'Synthetic','author':'Tester','branches':[{'label':'Branch','items':[{'text':'Hypothesis','status':'explore','evidence':[]}]}]}
   first=save(root,data)
   with self.assertRaises(ValueError):save(root,data)
   first['branches'][0]['items'][0]['status']='reviewed';second=save(root,first)
   self.assertEqual(load(root)['revision'],2);self.assertEqual(len(second['history']),2)
   self.assertEqual(json.loads((root/'hypotheses/revision-1.json').read_text())['branches'][0]['items'][0]['status'],'explore')
   second['branches'][0]['items'][0]['status']='invalid'
   with self.assertRaises(ValueError):save(root,second)
if __name__=='__main__':unittest.main()
