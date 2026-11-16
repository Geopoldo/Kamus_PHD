import sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import run
from parse import parse
from evaluate import validate_assignments,sha,score
class Resources(unittest.TestCase):
 def test_thresholds(self):
  self.assertTrue(run.enough({'ram_available_gib':4,'vram_free_mib':1024},4,1024))
  self.assertFalse(run.enough({'ram_available_gib':3.9,'vram_free_mib':1024},4,1024))
  self.assertFalse(run.enough({'ram_available_gib':4,'vram_free_mib':1023},4,1024))
 def test_no_silent_telemetry(self):
  with patch.dict(run.OLD,{'gpu_free_mib':lambda:(_ for _ in ()).throw(RuntimeError('no telemetry'))}):
   with self.assertRaises(RuntimeError):run.telemetry()
 def test_outside_region(self):self.assertIn('text_outside_regions',parse('extra [REGION R1 body]x[END_REGION]')['errors'])
 def test_duplicate(self):self.assertIn('duplicate_region',parse('[REGION R1 body]x[END_REGION][REGION R1 body]y[END_REGION]')['errors'])
 def test_pending(self):
  with self.assertRaises(ValueError):validate_assignments('x',[dict(hypothesis_sha256=sha('x'),hypothesis_spans=[dict(start=0,end_exclusive=1)],review_status='needs_review')])
 def test_unassigned(self):
  with self.assertRaises(ValueError):validate_assignments('x',[])
 def test_case_cer(self):
  a=score('Word','word');self.assertEqual(a['wer'],0);self.assertGreater(a['cer'],0)
if __name__=='__main__':unittest.main()
