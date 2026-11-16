import importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('model_auditor',Path(__file__).parent/'audit/model_run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class ModelAuditTests(unittest.TestCase):
 def test_candidate(self):self.assertEqual(m.parse('{"code":"candidate","evidence_quote":""}','Synthetic prose')['code'],'candidate')
 def test_quote_must_be_in_input(self):
  with self.assertRaises(ValueError):m.parse('{"code":"refusal","evidence_quote":"invented"}','Synthetic prose')
 def test_invalid_code(self):
  with self.assertRaises(ValueError):m.parse('{"code":"accurate","evidence_quote":""}','Synthetic prose')
 def test_supported_quote(self):self.assertEqual(m.parse('{"code":"refusal","evidence_quote":"cannot transcribe"}','I cannot transcribe this image')['code'],'refusal')
 def test_complete_page_is_not_split_or_cut(self):
  text='Synthetic document text. '*1500;parts=m.chunks(text);self.assertEqual(parts,[(0,text)])
if __name__=='__main__':unittest.main()
