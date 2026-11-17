import unittest
from graphrag_schema import Extraction, convert, split_evidence_text


class TypedGraphTests(unittest.TestCase):
    def test_split_preserves_exact_unicode_words_and_overlapping_evidence(self):
        class Encoder:
            def encode(self,text): return text.split()
        text='\n'.join(f'Nombre{i} Měkwādj{i} río{i} familia{i}' for i in range(40))
        parts=split_evidence_text(text,Encoder(),max_tokens=30,overlap_words=5)
        self.assertGreater(len(parts),1)
        for part in parts:
            self.assertIn(part,text)
            self.assertLessEqual(len(part.split()),30)
        self.assertEqual(set(text.split()),{word for part in parts for word in part.split()})
        for first,second in zip(parts,parts[1:]):
            self.assertEqual(first.split()[-5:],second.split()[:5])

    def test_same_name_different_types_and_literal_quote_gate(self):
        text='Lake lived near Lake. This is a person named Lake and a place named Lake.'
        value=Extraction.model_validate(dict(entities=[
            dict(name='Lake',type='PERSON',description='Person',quote='person named Lake'),
            dict(name='Lake',type='PLACE',description='Place',quote='place named Lake'),
            dict(name='FAMILY',type='FAMILY',description='Placeholder',quote='Lake'),
        ],relationships=[dict(source='Lake',source_type='PERSON',target='Lake',target_type='PLACE',
            relation='lived near',quote='Lake lived near Lake.',assertion='explicit',attribution='unknown',event_time='unknown',document_time='unknown')]))
        tuples,rejected=convert(value,text)
        from graphrag.index.operations.extract_graph.graph_extractor import GraphExtractor
        extractor=GraphExtractor(None,'',0)
        entities,relations=extractor._process_result(tuples,'page1','<|>','##')
        self.assertEqual(set(entities.title),{'PERSON::LAKE','PLACE::LAKE'})
        self.assertEqual(len(relations),1)
        self.assertEqual(relations.iloc[0]['source'],'PERSON::LAKE')
        self.assertEqual(relations.iloc[0]['target'],'PLACE::LAKE')
        self.assertEqual(len(rejected),1)

    def test_ungrounded_endpoint_or_quote_cannot_enter_graph(self):
        value=Extraction.model_validate(dict(entities=[dict(name='Peter',type='PERSON',description='Person',quote='Peter'),dict(name='Pine',type='PLACE',description='Place',quote='Pine')],relationships=[dict(source='Peter',source_type='PERSON',target='Pine',target_type='PLACE',relation='owns',quote='Peter owns Pine',assertion='explicit',attribution='unknown',event_time='unknown',document_time='unknown')]))
        tuples,rejected=convert(value,'Peter visited Pine.')
        self.assertNotIn('"relationship"',tuples)
        self.assertEqual(rejected[0]['reason'],'quote_not_found')


if __name__=='__main__':unittest.main()
