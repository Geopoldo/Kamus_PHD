import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import embeddings
import process_telemetry as ledger


class ProcessTelemetryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        embeddings.write(self.root/'progress.json',dict(stage='finished',started=100,updated=200,documents=[],summary=dict(processed=0,pdf_pages=0)))
        for key,state,start in [('failed_01','failed',110),('success_02','complete',120)]:
            path=self.root/'model_audits'/key
            embeddings.write(path/'manifest.json',dict(status=state,started=start,finished=start+5,elapsed_seconds=5,processed=2,total_pages=2))
            (path/'telemetry.jsonl').write_text(json.dumps(dict(time=start,gpu_util_percent=50,vram_used_mib=8000))+'\n')

    def test_retains_failed_attempt_and_logical_order(self):
        values=ledger.listing(self.root)['runs']
        self.assertEqual([r['stage'] for r in values],['inventory','rendering','transcription','model_audit','model_audit','human'])
        self.assertEqual([r['status'] for r in values[3:5]],['failed','complete'])
        self.assertIsNone(values[-1]['elapsed_seconds'])
        self.assertEqual(values[-1]['resources'],{})
        self.assertEqual(values[3]['resources']['vram_used_mib']['peak'],8000)

    def test_trace_csv_and_path_validation(self):
        archive=zipfile.ZipFile(io.BytesIO(ledger.bundle(self.root,'model_audit','failed_01')))
        self.assertIn('telemetry.jsonl',archive.namelist());self.assertIn('manifest.json',archive.namelist())
        with self.assertRaises(ValueError):ledger.detail(self.root,'model_audit','../../outside')
        values=list(csv.DictReader(io.StringIO(ledger.csv_bytes(self.root).decode('utf-8-sig'))))
        self.assertEqual(values[-1]['elapsed_seconds'],'')
        self.assertEqual(values[3]['vram_used_mib_peak'],'8000')


    def test_graph_queries_keep_phase_resources_and_history(self):
        directory=self.root/'knowledge_graph/questions'/('a'*32)
        embeddings.write(directory/'question.json',dict(status='complete',started=120,finished=130,elapsed_seconds=10,processed=1,total=1,phases=[dict(name='query',load_seconds=2)],model='local'))
        embeddings.write(directory/'runtime_summary.json',dict(inference_seconds=7))
        phase=directory/'query';phase.mkdir();(phase/'telemetry.jsonl').write_text(json.dumps(dict(time=125,vram_used_mib=6000))+'\n')
        value=ledger.listing(self.root)['runs'][-1]
        self.assertEqual(value['stage'],'graph_query')
        self.assertEqual(value['inference_seconds'],7)
        self.assertEqual(value['load_seconds'],2)
        self.assertEqual(value['resources']['vram_used_mib']['peak'],6000)

    def test_page_audit_becomes_stale_when_original_changes(self):
        output=self.root/'documents/a';output.mkdir(parents=True);(output/'page_0001.md').write_text('Original')
        ident=embeddings.digest('a.pdf')
        embeddings.write(self.root/'progress.json',dict(documents=[dict(source='a.pdf',folder='a',output=str(output),page_count=1)]))
        embeddings.write(self.root/'model_audit_latest.json',dict(run_id='success_02'))
        embeddings.write(self.root/'model_audits/success_02/all_pages.json',[dict(document_id=ident,page=1,input_sha256=embeddings.digest('Original'),classification='candidate',findings=[])])
        self.assertFalse(ledger.page_coverage(self.root)[ident+':1']['model_audit']['stale'])
        (output/'page_0001.md').write_text('Changed')
        self.assertTrue(ledger.page_coverage(self.root)[ident+':1']['model_audit']['stale'])

    def test_legacy_numeric_strings_are_plotted_without_rewriting_logs(self):
        path=self.root/'model_audits/failed_01/telemetry.jsonl'
        original=json.dumps(dict(time=110,power_watts='41.5',temperature_c='60.0'))+'\n'
        path.write_text(original)
        detail=ledger.detail(self.root,'model_audit','failed_01')
        self.assertEqual(detail['summary']['resources']['power_watts']['peak'],41.5)
        self.assertEqual(detail['telemetry'][0]['temperature_c'],60.)
        self.assertEqual(path.read_text(),original)


if __name__=='__main__':unittest.main()
