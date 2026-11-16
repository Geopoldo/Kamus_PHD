import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import priority_catalog as catalog
import priority_search as search
import priority_audit as audit
import test_priority_search as fixture


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.book=self.root/'source.xlsx';self.book.write_bytes(b'original workbook fixture')
        for p in [patch.object(search,'WORKBOOK',self.book),patch.object(search,'workbook_rows',return_value=fixture.rows()),patch.object(search,'start',return_value={'running':True})]:
            p.start();self.addCleanup(p.stop)

    def test_edit_persists_synonyms_priority_history_and_workbook(self):
        before=self.book.read_bytes();value=catalog.get(self.root)
        e=next(e for e in value['entities'] if e['label']=='Namagoos')
        e.update(priority='Media',aliases=['Namagousse'])
        result=catalog.save(self.root,dict(revision=0,changes=[e]))
        self.assertEqual(result['revision'],1)
        loaded=catalog.catalog_for(self.root);entity=next(x for x in loaded['entities'] if x['id']==e['id'])
        self.assertEqual(entity['priority'],'Media')
        hits=search.Matcher(loaded).match('Namagousse')
        self.assertEqual(next(m for m in hits if m['entity']==e['id'])['quality'],'alias')
        self.assertEqual(self.book.read_bytes(),before)
        self.assertTrue((self.root/'priorities'/'catalog_history'/'revision_000001.json').exists())
        log=audit.history(self.root)['events'][0]
        self.assertEqual(log['event'],'catalog_saved')
        self.assertEqual(log['changes'][0]['fields']['priority'],dict(before='Alta',after='Media'))
        with self.assertRaises(FileExistsError):catalog.save(self.root,dict(revision=0,changes=[e]))

    def test_new_person_uses_configured_name_and_lower_score_for_distant_words(self):
        e=dict(id='user:11111111-1111-4111-8111-111111111111',kind='person',label='Jane Example',first_name='Jane',last_name='Example',aliases=['Janet Example'],priority='Alta',enabled=True)
        catalog.save(self.root,dict(revision=0,changes=[e]))
        matcher=search.Matcher(catalog.catalog_for(self.root))
        direct=[m for m in matcher.match('Jane Example') if m['entity']==e['id']]
        distant=[m for m in matcher.match('Jane spoke at length to another Example') if m['entity']==e['id']]
        self.assertEqual(direct[0]['score'],100)
        self.assertEqual(distant[0]['score'],20)
        self.assertEqual(distant[0]['quality'],'cooccurrence')
        self.assertFalse([m for m in matcher.match('Example') if m['entity']==e['id']])

    def test_disable_is_reversible_and_does_not_remove_source_rows(self):
        e=next(e for e in catalog.get(self.root)['entities'] if e['label']=='Namagoos');e['enabled']=False
        catalog.save(self.root,dict(revision=0,changes=[e]));result=catalog.catalog_for(self.root)
        self.assertTrue(next(x for x in result['entities'] if x['id']==e['id'])['sources'])
        self.assertFalse([m for m in search.Matcher(result).match('Namagoos') if m['entity']==e['id']])
        e['enabled']=True;catalog.save(self.root,dict(revision=1,changes=[e]))
        self.assertTrue([m for m in search.Matcher(catalog.catalog_for(self.root)).match('Namagoos') if m['entity']==e['id']])

    def test_family_synonym_propagates_to_full_person_names(self):
        e=next(e for e in catalog.get(self.root)['entities'] if e['label']=='Butterfly' and e['kind']=='surname')
        e['aliases']=['Papillon'];catalog.save(self.root,dict(revision=0,changes=[e]))
        hits=search.Matcher(catalog.catalog_for(self.root)).match('John Papillon')
        self.assertEqual(next(m for m in hits if m['entity']=='person:161')['quality'],'alias')

    def test_invalid_changes_are_not_saved(self):
        e=catalog.get(self.root)['entities'][0];e['priority']='urgent'
        with self.assertRaises(ValueError):catalog.save(self.root,dict(revision=0,changes=[e]))
        self.assertEqual(catalog.settings(self.root)['revision'],0)

    def test_all_types_accept_three_priorities_and_saving_during_search(self):
        value=catalog.get(self.root)
        changes=[]
        for kind,priority in [('person','Baja'),('surname','Media'),('place','Alta')]:
            e=next(e for e in value['entities'] if e['kind']==kind)
            changes.append(dict(e,priority=priority))
        with patch.dict(search._job,running=True):
            result=catalog.save(self.root,dict(revision=0,changes=changes))
        self.assertEqual(result['revision'],1)
        search.start.assert_called_with(self.root,requested_revision=1,reason='catalog_saved')
        self.assertEqual(len(audit.history(self.root)['events'][0]['changes']),3)

    def test_legacy_priorities_are_read_as_current_levels(self):
        e=next(e for e in catalog.get(self.root)['entities'] if e['kind']=='place')
        e['priority']='Segunda'
        folder=self.root/'priorities';folder.mkdir()
        (folder/'catalog-overrides.json').write_text(json.dumps(dict(revision=1,overrides={e['id']:e})))
        self.assertEqual(catalog.settings(self.root)['overrides'][e['id']]['priority'],'Media')


if __name__=='__main__':unittest.main()
