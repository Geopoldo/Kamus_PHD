import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from parse import parse
from evaluate import score,counts,words,validate_assignments,sha
class Core(unittest.TestCase):
 def test_multiline(self):
  p=parse('[REGION R1 body]\n[DEL]old\ntext[/DEL] [INS][UNCLEAR]new[/UNCLEAR][/INS]\n[END_REGION]')
  self.assertFalse(p['errors']);self.assertEqual(next(s for s in p['segments'] if 'old' in s['text'])['state'],'deleted')
 def test_unclear(self):
  p=parse('[REGION R1 body][UNCLEAR]word[/UNCLEAR][END_REGION]');self.assertTrue(p['segments'][0]['uncertain']);self.assertEqual(score('word',p['segments'][0]['text'])['wer'],0)
 def test_abbreviations(self):
  self.assertEqual(words('C.J'),words('C.J.'));self.assertNotEqual(words('J.A.'),words('J.A.G.'));self.assertNotEqual(words('1865'),words('1848'))
 def test_empty(self):
  self.assertEqual(score('two words','')['word']['D'],2);self.assertIsNone(score('','extra')['wer'])
 def test_invariants(self):
  c=counts('abc','axbc');self.assertEqual(c['H']+c['S']+c['D'],c['N']);self.assertEqual(c['H']+c['S']+c['I'],c['M'])
 def test_spans(self):
  r=dict(hypothesis_sha256=sha('abc'),hypothesis_spans=[dict(start=0,end_exclusive=3)],review_status='verified')
  validate_assignments('abc',[r])
  with self.assertRaises(ValueError):validate_assignments('abc',[r,r])
  with self.assertRaises(ValueError):validate_assignments('abd',[r])
 def test_invalid(self):self.assertIn('unclosed_tag',parse('[REGION R1 body][DEL]x')['errors'])
 def test_true_character(self):self.assertEqual(score('ab cd','a bcd')['character']['errors'],2)
if __name__=='__main__':unittest.main()
