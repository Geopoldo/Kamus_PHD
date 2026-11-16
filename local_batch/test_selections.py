import csv
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

import selections
import sources
from test_sources import fixture,uploaded,transcribed


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=fixture(self.tmp.name);self.item=uploaded(self.root);self.docs=transcribed(self.root,'Carlos Gomez visited the river. Ruben wrote the report.')
        self.record=dict(document_id=self.item['id'],document=self.item['source'],page=1,version='original',note='Aporta evidencia sobre el río',
                         text_sha256=hashlib.sha256((Path(self.docs[0]['output'])/'page_0001.md').read_bytes()).hexdigest(),
                         contexts=[dict(kind='Búsqueda sencilla',query='Ruben',excerpts=['Ruben wrote the report.'],matches=[dict(label='Ruben',quality='Coincidencia textual')])])
        self.payload=dict(title='Personas y ríos',researcher='Ana',curator='Luis',records=[self.record])

    def test_exact_selection_attribution_metadata_and_csv(self):
        uploaded(self.root,'Another/Unselected.pdf');transcribed(self.root,'Carlos Gomez visited the river. Ruben wrote the report.')
        item=selections.create(self.root,self.payload);value=selections.get(self.root,item['id'])
        self.assertEqual((item['pages'],item['readings']),(1,1));self.assertEqual(value['researcher'],'Ana');self.assertEqual(value['curator'],'Luis')
        rows=list(csv.DictReader(io.StringIO(selections.csv_bytes(value,'http://127.0.0.1:8091').decode('utf-8-sig'))))
        self.assertEqual(len(rows),1);row=rows[0];self.assertEqual(row['Archivo'],'Example.pdf');self.assertEqual(row['Buscado por'],'Ana');self.assertEqual(row['Depurado por'],'Luis');self.assertEqual(row['Página PDF'],'1');self.assertEqual(row['Fragmentos relevantes'],'Ruben wrote the report.');self.assertEqual(row['Motivo de selección'],'Aporta evidencia sobre el río');self.assertIn('saved='+item['id'],row['Abrir página en la app'])
        self.assertEqual(selections.listing(self.root)[0]['id'],item['id']);self.assertIn('selection_export_created',(self.root/'sources/events.jsonl').read_text())

    def test_same_page_different_versions_are_separate_rows(self):
        sources.write(self.root/'reviews'/self.item['id']/'1.json',dict(text='Ruben: human correction.',original_hash=self.record['text_sha256'],status='draft',reviewer='Marta',revision=2))
        self.payload['records']=[self.record,self.record,dict(self.record,version='human',text_sha256=None,contexts=[])]
        item=selections.create(self.root,self.payload);value=selections.get(self.root,item['id']);self.assertEqual((item['pages'],item['readings']),(1,2));self.assertEqual(value['rows'][1]['transcription_reviewer'],'Marta');self.assertEqual(value['rows'][1]['review_revision'],2)

    def test_stale_and_fabricated_evidence_rejected(self):
        self.record['contexts'][0]['excerpts']=['Invented quote']
        with self.assertRaises(FileExistsError):selections.create(self.root,self.payload)
        self.record['contexts']=[];(Path(self.docs[0]['output'])/'page_0001.md').write_text('Changed after selection')
        with self.assertRaises(FileExistsError):selections.create(self.root,self.payload)
        self.assertFalse(selections.listing(self.root))

    def test_export_survives_source_retirement(self):
        image=Path(self.docs[0]['output'])/'page_0001.png';image.write_bytes(b'fixture-image')
        item=selections.create(self.root,self.payload);before=selections.get(self.root,item['id'])
        sources.archive(self.root,[self.item['id']]);self.assertEqual(selections.get(self.root,item['id']),before)
        self.assertEqual(selections.image_path(self.root,item['id'],0).read_bytes(),b'fixture-image')
        with self.assertRaises(ValueError):selections.create(self.root,self.payload)

    def test_names_required_and_formula_neutralized(self):
        for key in ('researcher','curator','title'):
            with self.assertRaises(ValueError):selections.create(self.root,dict(self.payload,**{key:''}))
        self.payload['researcher']='=HYPERLINK("bad")';self.record['note']='   +SUM(1,2)'
        item=selections.create(self.root,self.payload);value=selections.get(self.root,item['id'])
        rows=list(csv.DictReader(io.StringIO(selections.csv_bytes(value,'http://127.0.0.1:8091').decode('utf-8-sig'))))
        self.assertTrue(rows[0]['Buscado por'].startswith("'="));self.assertTrue(rows[0]['Motivo de selección'].startswith("'   +"))
        with self.assertRaises(ValueError):selections.get(self.root,'../private')
        with self.assertRaises(ValueError):selections.image_path(self.root,item['id'],-1)


if __name__=='__main__':unittest.main()
