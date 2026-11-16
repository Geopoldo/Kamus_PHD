import contextlib,io,json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import batch_client as client

class BatchTests(unittest.TestCase):
 def test_multiple_files_and_resume_without_duplicate_submission(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);files=[root/'one.png',root/'two.png']
   for file in files:file.write_bytes(b'test image bytes')
   jobs=[]
   def fake(base,path,data=None):
    if data is not None:
     jid=str(len(jobs)+1);jobs.append(jid);return json.dumps({'job_id':jid}).encode()
    if path.endswith('/result'):return b'{"pages": []}'
    if path.endswith('/markdown'):return b'# Page\nText'
    return b'{"status":"complete"}'
   argv=['batch_client.py',*[str(p) for p in files],'--output-dir',str(root/'out')]
   with patch.dict(os.environ,{'OCR_API_URL':'http://test'},clear=True),patch.object(client,'request',side_effect=fake),patch.object(sys,'argv',argv),contextlib.redirect_stdout(io.StringIO()):
    self.assertEqual(client.main(),0);self.assertEqual(client.main(),0)
   self.assertEqual(len(jobs),2)
   self.assertEqual(len(list((root/'out').glob('*.md'))),2)
   self.assertEqual(len(list((root/'out').glob('*-[12].json'))),2)
 def test_lost_upload_response_is_not_resubmitted(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);file=root/'one.png';file.write_bytes(b'test')
   argv=['batch_client.py',str(file),'--output-dir',str(root/'out')]
   with patch.dict(os.environ,{'OCR_API_URL':'http://test'},clear=True),patch.object(sys,'argv',argv),patch.object(client,'request',side_effect=OSError('lost response')) as req,contextlib.redirect_stdout(io.StringIO()):
    with self.assertRaises(OSError):client.main()
    self.assertEqual(client.main(),1);self.assertEqual(req.call_count,1)

if __name__=='__main__':unittest.main()
