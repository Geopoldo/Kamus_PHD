import hashlib,json,tempfile,unittest,zipfile,io
from pathlib import Path
import review
class ReviewTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.out=self.root/'documents'/'sample';self.out.mkdir(parents=True)
  self.doc=dict(source='sample.pdf',output=str(self.out),page_count=1,pages=[dict(number=1,status='complete')]);self.ident=review.key(self.doc)
  (self.root/'progress.json').write_text(json.dumps(dict(documents=[self.doc])));(self.root/'config.json').write_text('{}')
  (self.out/'page_0001.md').write_text('Synthetic original');(self.out/'page_0001.json').write_text('{"status":"complete"}')
 def data(self):return dict(document=self.ident,page=1,text='Synthetic correction',reviewer='Test reviewer',status='validated',original_hash=hashlib.sha256(b'Synthetic original').hexdigest(),revision=0)
 def test_preserve_and_conflict(self):
  review.save(self.root,self.data());self.assertEqual((self.out/'page_0001.md').read_text(),'Synthetic original')
  with self.assertRaises(FileExistsError):review.save(self.root,self.data())
  self.assertEqual(len(list((self.root/'reviews'/self.ident/'1.history').glob('*.json'))),1)
 def test_annotations_unicode_and_ranges(self):
  data=self.data();data['status']='deferred';data['text']='A😀 date';data['annotations']=[dict(start=1,end=3,quote='😀',note='Synthetic doubt')]
  saved=review.save(self.root,data);self.assertEqual(saved['annotations'],data['annotations'])
  self.assertEqual(review.load(self.root,self.ident,1)['review']['annotations'],data['annotations'])
 def test_invalid_annotations(self):
  for marks in [[dict(start=0,end=999,quote='bad')],[dict(start=0,end=3,quote='wrong')]]:
   data=self.data();data['annotations']=marks
   with self.assertRaises(ValueError):review.save(self.root,data)
 def test_open_doubts_cannot_be_validated(self):
  data=self.data();data['annotations']=[dict(start=0,end=9,quote='Synthetic',note='Check')]
  with self.assertRaises(ValueError):review.save(self.root,data)
  data['status']='deferred';saved=review.save(self.root,data);self.assertEqual(saved['status'],'deferred')
  data['annotations']=[];data['status']='validated';data['revision']=saved['revision']
  self.assertEqual(review.save(self.root,data)['status'],'validated')
 def test_reading_choice_is_saved_separately(self):
  data=self.data();data['basis']='27b_pilot_01';data['status']='draft'
  saved=review.save(self.root,data);self.assertEqual(saved['basis'],'27b_pilot_01')
  self.assertEqual((self.out/'page_0001.md').read_text(),'Synthetic original')
 def test_original_changed(self):
  (self.out/'page_0001.md').write_text('Changed')
  with self.assertRaises(FileExistsError):review.save(self.root,self.data())
 def test_reject_unknown_and_traversal(self):
  for ident in ['../../etc/passwd','unknown']:
   with self.assertRaises(ValueError):review.locate(self.root,ident,1)
  with self.assertRaises(ValueError):review.locate(self.root,self.ident,2)
 def test_validation_and_bundle(self):
  bad=self.data();bad['reviewer']=' '
  with self.assertRaises(ValueError):review.save(self.root,bad)
  data=self.data();data['status']='draft';data['note']='Synthetic unresolved date';saved=review.save(self.root,data);self.assertEqual(saved['note'],'Synthetic unresolved date');archive=zipfile.ZipFile(io.BytesIO(review.bundle(self.root,self.ident)))
  self.assertIn('model/page_0001.md',archive.namelist());self.assertIn('human/1.json',archive.namelist())
if __name__=='__main__':unittest.main()
