import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import place_geography as geo

class PlaceGeographyTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.catalog={'entities':[{'id':'place:x','kind':'place','enabled':True,'label':'Lake X'}]}
        self.mock=patch.object(geo.priority_catalog,'get',return_value=self.catalog);self.mock.start();self.addCleanup(self.mock.stop)
    def payload(self,**changes):
        p=dict(revision=0,entity='place:x',status='proposed',feature_name='Lake X',latitude=50,longitude=-80,source_url='https://example.org/location',note='Reference point')
        p.update(changes);return p
    def test_persistence_provenance_and_conflict(self):
        value=geo.save(self.root,self.payload());self.assertEqual(value['revision'],1)
        self.assertEqual(geo.get(self.root)['items']['place:x']['longitude'],-80)
        with self.assertRaises(FileExistsError):geo.save(self.root,self.payload())
        value=geo.save(self.root,self.payload(revision=1,status='confirmed',reviewer='Researcher'))
        self.assertEqual(value['items']['place:x']['status'],'confirmed')
        records=[json.loads(line) for line in (self.root/'geography/events.jsonl').read_text().splitlines()]
        self.assertEqual(records[1]['before']['status'],'proposed')
        self.assertEqual(records[1]['after']['reviewer'],'Researcher')
    def test_invalid_coordinates_reference_and_confirmation(self):
        for changes in [dict(latitude=91),dict(longitude=float('nan')),dict(latitude=True),dict(latitude=None),dict(status='confirmed'),dict(source_url='javascript:alert(1)'),dict(entity='person:x')]:
            with self.subTest(changes=changes),self.assertRaises(ValueError):geo.save(self.root,self.payload(**changes))
        self.assertEqual(geo.read(self.root)['revision'],0)
    def test_unlocated_rename_and_removed_criteria(self):
        geo.save(self.root,self.payload());self.catalog['entities'][0]['label']='Another Lake'
        self.assertTrue(geo.get(self.root)['items']['place:x']['needs_recheck'])
        value=geo.save(self.root,self.payload(revision=1,status='unlocated'))
        self.assertNotIn('latitude',value['items']['place:x'])
        self.catalog['entities'][0]['enabled']=False;self.assertEqual(geo.get(self.root)['items'],{})
        self.assertIn('place:x',geo.read(self.root)['items'])

    def test_unconfirmed_location_requires_explanation_and_can_be_confirmed(self):
        with self.assertRaises(ValueError):
            geo.save(self.root,self.payload(status='unconfirmed',note=' '))
        value=geo.save(self.root,self.payload(status='unconfirmed',note='Two possible lakes; using one reference point.'))
        self.assertEqual(value['items']['place:x']['status'],'unconfirmed')
        self.assertEqual(value['items']['place:x']['latitude'],50)
        with self.assertRaises(ValueError):
            geo.save(self.root,self.payload(revision=1,status='confirmed'))
        value=geo.save(self.root,self.payload(revision=1,status='confirmed',reviewer='Researcher'))
        records=[json.loads(line) for line in (self.root/'geography/events.jsonl').read_text().splitlines()]
        self.assertEqual(records[-1]['before']['status'],'unconfirmed')
        self.assertEqual(value['items']['place:x']['status'],'confirmed')

if __name__=='__main__':unittest.main()
