import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('audit_run',Path(__file__).parent/'audit/run.py');audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
def response(text,finish='stop'):return {'choices':[{'message':{'content':text},'finish_reason':finish}]}
class AuditTests(unittest.TestCase):
 def test_refusal(self):
  t='Unfortunately, it is impossible to accurately transcribe the text in this image.';r=audit.inspect(t,response(t));self.assertEqual(r['classification'],'not_transcribed')
 def test_ordinary_prose(self):
  t='The committee visited the northern lakes and recorded observations along the shoreline during the summer survey.';self.assertEqual(audit.inspect(t,response(t))['findings'],[])
 def test_short_title_is_only_advisory(self):
  t='Index';r=audit.inspect(t,response(t));self.assertEqual(r['classification'],'possibly_incomplete');self.assertEqual(r['findings'][0]['severity'],'low')
 def test_empty_and_truncated(self):
  r=audit.inspect('',response('','length'));self.assertEqual(r['classification'],'not_transcribed');self.assertIn('truncated_output',[x['rule'] for x in r['findings']])
 def test_mismatch(self):self.assertIn('output_mismatch',[x['rule'] for x in audit.inspect('Edited',response('Original'))['findings']])
 def test_repeat(self):
  t=('Repeated sample line for a synthetic test only\n'*30);self.assertIn('repeated_lines',[x['rule'] for x in audit.inspect(t,response(t))['findings']])
if __name__=='__main__':unittest.main()
