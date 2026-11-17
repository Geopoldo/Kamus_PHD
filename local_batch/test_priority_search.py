import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import priority_search as ps


def rows():
    return [
        ('Last_Names_Colin+Camilo', [(1, {'A': 'Trapline', 'B': 'First Name', 'C': 'Last Name', 'D': 'FHID'}),
         (2, {'A': 'PE199', 'B': 'John', 'C': 'Butterfly', 'D': '161'}),
         (3, {'A': 'PE201', 'B': 'Johnny', 'C': 'Butterfly', 'D': '161'}),
         (4, {'A': 'PE200', 'B': 'David', 'C': 'Black', 'D': '162'}),
         (5, {'C': 'Namagoos'})]),
        ('Place highest priority', [(1, {'A': 'shared title area'}), (2, {'A': 'Lawagamau/Katawagami'}),
         (3, {'A': 'Turgeon and Harricanaw/Harricana river'})]),
        ('Second Priority', [(1, {'A': 'shared rights area'}), (2, {'A': 'Lake Abitibinorthwesterly drainage'})]),
        ('Lastnames', [(1, {'A': 'Lastname'}), (2, {'A': 'Archibald (Arohibald; Arohihald)'}),
         (3, {'A': 'Namagoos'}), (4, {'A': 'Cotten?'})]),
    ]


class PriorityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.book = self.root/'catalog.xlsx'
        self.book.write_bytes(b'fixture-only')
        self.patch = patch.object(ps, 'workbook_rows', return_value=rows())
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.catalog = ps.build_catalog(self.book)
        self.matcher = ps.Matcher(self.catalog)

    def matches(self, text, entity):
        return [m for m in self.matcher.match(text) if m['entity'] == entity]

    def test_sources_aliases_grouping_and_no_id_search(self):
        person = next(e for e in self.catalog['entities'] if e['id'] == 'person:161')
        self.assertEqual(len(person['sources']), 2)
        self.assertEqual(person['traplines'], ['PE199', 'PE201'])
        self.assertEqual(self.matches('Johnny Butterfly', person['id'])[0]['quality'], 'alias')
        self.assertEqual(self.matcher.match('FHID 161 PE199 162 PE200'), [])
        self.assertEqual(self.matches('Arohibald', 'surname:archibald')[0]['quality'], 'alias')
        self.assertEqual(self.matches('Butterfly', 'person:161'), [])
        self.assertTrue(self.matches('Butterfly', 'surname:butterfly'))
        self.assertEqual(person['priority'], 'Alta')
        by_label = {e['label']: e for e in self.catalog['entities']}
        self.assertEqual(by_label['Namagoos']['priority'], 'Alta')  # overlap with Lastnames
        self.assertEqual(by_label['Archibald']['priority'], 'Baja')
        self.assertEqual(by_label['Lawagamau/Katawagami']['priority'], 'Alta')
        self.assertEqual(by_label['Lake Abitibinorthwesterly drainage']['priority'], 'Media')

    def test_near_full_names_only(self):
        for text in ['John Butterfly', 'John one Butterfly', 'John one two Butterfly']:
            match = self.matches(text, 'person:161')[0]
            self.assertIn(match['quality'], ('literal', 'near'))
        self.assertEqual(self.matches('John one two three Butterfly', 'person:161'), [])
        self.assertEqual(self.matches('John was here. Many unrelated words. Butterfly appeared elsewhere.', 'person:161'), [])
        self.assertEqual(self.matches('Butterfly, John', 'person:161'), [])
        self.assertEqual(self.matches('J. Butterfly', 'person:161'), [])

    def test_full_name_never_accepts_three_or_ten_intervening_words(self):
        person=dict(id='person:carlos',kind='person',sources=[],name_forms=[dict(first_name='Carlos',last_name='Gomez')],
                    patterns=[dict(label='Carlos Gomez',terms=['carlos','gomez'],origin='canonical',reason='')])
        matcher=ps.Matcher({'entities':[person]})
        for gap in range(11):
            text='Carlos '+'word '*gap+'Gomez'
            matches=matcher.match(text)
            if gap<=2:
                self.assertEqual(matches[0]['quality'],'literal' if gap==0 else 'near')
            else:
                self.assertEqual(matches, [])
        self.assertEqual(ps.MAX_INTERVENING_WORDS,2)

    def test_fuzzy_accents_hyphen_unicode_and_no_occurrence_cap(self):
        self.assertEqual(self.matches('NAMAGOÓS', 'surname:namagoos')[0]['quality'], 'literal')
        m = self.matches('😀 Nama-\ngoose', 'surname:namagoos')[0]
        self.assertEqual(m['quality'], 'candidate')
        self.assertEqual('😀 Nama-\ngoose'[m['offsets'][0][0]:m['offsets'][0][1]], 'Nama-\ngoose')
        self.assertEqual(len(self.matches('Namagoos ' * 120, 'surname:namagoos')), 120)
        self.assertFalse(ps.similar('John', 'Joan'))
        self.assertFalse(ps.similar('Ed', 'Eb'))

    def test_places_separate_aliases_and_context(self):
        place = next(e for e in self.catalog['entities'] if e['label']=='Lawagamau/Katawagami')
        self.assertEqual(self.matches('Katawagami', place['id'])[0]['quality'], 'alias')
        area = next(e for e in self.catalog['entities'] if e['label'].startswith('Turgeon'))
        self.assertEqual(self.matches('Harricana', area['id']), [])

    def test_never_join_paragraphs_but_keep_wrapped_lines(self):
        for separator in ['\n\n', '\r\n \r\n', '\n \t\n', '\u2029', '\f', '\n>\n>']:
            with self.subTest(separator=repr(separator)):
                self.assertEqual(self.matches('John'+separator+'Butterfly', 'person:161'), [])
                self.assertEqual(self.matches('John one'+separator+'two Butterfly', 'person:161'), [])
                self.assertEqual(self.matches('John Butter'+separator+'fly', 'person:161'), [])
        self.assertTrue(self.matches('John\nButterfly', 'person:161'))
        self.assertTrue(self.matches('John Butter-\nfly', 'person:161'))
        text='John\n\nButterfly. Later, John Butterfly arrived.'
        matches=self.matches(text, 'person:161')
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]['offsets'][0][0], text.rindex('John'))

    def test_complete_multiword_places_share_the_name_distance_limit(self):
        entity=dict(id='place:test', kind='place', patterns=[
            dict(label='Black Bear Point', terms=['black','bear','point'], origin='canonical', reason=''),
            dict(label='Bear Point', terms=['bear','point'], origin='alias', reason='Explicit alias'),
            dict(label='Black', terms=['black'], origin='generated', reason='Partial'),
            dict(label='Point', terms=['point'], origin='context', reason='Anchor')])
        matcher=ps.Matcher({'entities':[entity]})
        for text in ['Black Bear Point','Black one Bear two Point','Bear one two Point','Black\nBear Point']:
            with self.subTest(text=text):
                self.assertTrue(matcher.match(text))
        for text in ['Black Bear one two three Point','Black\n\nBear\n\nPoint','Black','Point']:
            with self.subTest(text=text):
                self.assertEqual(matcher.match(text), [])
        strict=ps.Matcher({'entities':[dict(entity,patterns=entity['patterns'][:1])]})
        self.assertEqual(strict.match('Black one two Bear three Point'), [], 'Two intervening words total, not per pair')
        self.assertEqual(strict.match('Black Bea-\nr Point')[0]['quality'],'literal')

    def test_split_and_joined_words_are_reviewable(self):
        self.assertEqual(self.matches('JohnButterfly', 'person:161')[0]['origin'], 'spacing')
        self.assertEqual(self.matches('John Butter fly', 'person:161')[0]['quality'], 'candidate')
        self.assertEqual(self.matches('Archi bald', 'surname:archibald')[0]['origin'], 'spacing')
        self.assertFalse(self.matches('Archi one bald', 'surname:archibald'))

    def test_all_pages_versions_missing_and_stale(self):
        out = self.root/'documents'/'folder'/'a'
        out.mkdir(parents=True)
        original = 'John Butterfly visited Katawagami.'
        (out/'page_0001.md').write_text(original)
        (out/'page_0002.md').write_text('No relevant names.')
        source = 'folder/a.pdf'
        ident = ps.digest(source)
        (self.root/'progress.json').write_text(json.dumps(dict(documents=[dict(source=source, folder='folder', output=str(out), page_count=3)])))
        review = self.root/'reviews'/ident
        review.mkdir(parents=True)
        (review/'1.json').write_text(json.dumps(dict(text='Arohibald was present.', status='validated', original_hash=ps.digest(original))))
        secondary = self.root/'second_reading'/'pilot'/'case_01'
        secondary.mkdir(parents=True)
        (secondary/'metadata.json').write_text(json.dumps(dict(document=source, page=1)))
        (secondary/'transcription.md').write_text('Namagoose.')
        r = ps.run(self.root, self.book)
        self.assertEqual(r['coverage']['inventory_pages'], 3)
        self.assertEqual(r['coverage']['searched_pages'], 2)
        self.assertEqual(r['coverage']['versions'], 4)
        self.assertEqual(len(r['coverage']['missing_pages']), 1)
        self.assertEqual(r['summary']['pages'], 1)
        self.assertGreater(r['summary']['entities_without_hits'], 0)
        self.assertEqual(r['summary']['entities_with_hits']+r['summary']['entities_without_hits'], len(r['catalog']['entities']))
        versions = {v['version']: v for v in r['pages'][0]['versions']}
        self.assertEqual(set(versions), {'original', 'human', 'second_reading:pilot'})
        self.assertEqual(versions['human']['status'], 'validated')
        self.assertFalse(r['changed_during_run'])
        self.assertEqual(r['search_policy'], ps.SEARCH_POLICY)
        self.assertTrue(all(m['gap']<=2 and m['quality'] not in ('clue','cooccurrence') for p in r['pages'] for v in p['versions'] for m in v['matches']))
        self.assertEqual(ps.fingerprint(self.root, self.book), r['fingerprint'])
        (out/'page_0001.md').write_text('Changed original')
        self.assertNotEqual(ps.fingerprint(self.root, self.book), r['fingerprint'])
        r = ps.run(self.root, self.book)
        human = next(v for v in r['pages'][0]['versions'] if v['version']=='human')
        self.assertEqual(human['status'], 'stale')


if __name__ == '__main__':
    unittest.main()
