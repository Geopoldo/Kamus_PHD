"""Synthetic PDFs only; never loads a model or touches the production corpus."""
import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

import dashboard
import sources
import source_worker
from audit.incremental import select, VERSION


def pdf(text='Synthetic source'):
    stream=f'BT /F1 12 Tf 50 200 Td ({text}) Tj ET'.encode()
    objects=[b'<< /Type /Catalog /Pages 2 0 R >>',b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
             b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
             b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',b'<< /Length '+str(len(stream)).encode()+b' >>\nstream\n'+stream+b'\nendstream']
    value=b'%PDF-1.4\n';offsets=[0]
    for n,obj in enumerate(objects,1):
        offsets.append(len(value));value+=str(n).encode()+b' 0 obj\n'+obj+b'\nendobj\n'
    start=len(value);value+=b'xref\n0 6\n0000000000 65535 f \n'
    value+=b''.join(f'{pos:010} 00000 n \n'.encode() for pos in offsets[1:])
    return value+b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n'+str(start).encode()+b'\n%%EOF\n'


def fixture(directory):
    root=Path(directory)/'results';root.mkdir()
    source=Path(directory)/'inputs';source.mkdir()
    sources.write(root/'sources/config.json',{'source_root':str(source)})
    sources.write(root/'progress.json',sources.summarize(dict(documents=[],started=0,stage='finished',model='fixture')))
    sources.write(root/'config.json',{'prompt':'Synthetic fixture'})
    (root/'telemetry.jsonl').write_text('')
    return root


def uploaded(root,name='Collection/Example.pdf'):
    data=pdf();return sources.upload(root,name,io.BytesIO(data),len(data))


def transcribed(root,text='Synthetic page for tests only.'):
    progress=sources.read(root/'progress.json')
    for doc in progress['documents']:
        output=Path(doc['output']);output.mkdir(parents=True,exist_ok=True)
        for page in doc['pages']:
            page.update(status='complete',flags=[]);prefix=output/f"page_{page['number']:04}"
            prefix.with_suffix('.md').write_text(text)
            sources.write(prefix.with_suffix('.json'),page)
            sources.write(prefix.with_suffix('.response.json'),{'choices':[{'finish_reason':'stop','message':{'content':text}}]})
        doc['status']='complete'
    sources.write(root/'progress.json',sources.summarize(progress))
    return progress['documents']


def inspection(root,documents,run='original'):
    directory=root/'model_audits'/run;sources.write(directory/'manifest.json',{'version':VERSION})
    for doc in documents:
        for page in doc['pages']:
            ident=sources.ident(doc['source']);text=(Path(doc['output'])/f"page_{page['number']:04}.md").read_bytes()
            sources.write(directory/'pages'/ident/str(page['number'])/'classification.json',
                          dict(document=doc['source'],document_id=ident,page=page['number'],folder=doc['folder'],classification='candidate',findings=[],
                               input_sha256=hashlib.sha256(text).hexdigest(),run_id=run,audit_seconds=1,decisions=[],human_validated=False))
    sources.write(root/'model_audit_latest.json',{'run_id':run})


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=fixture(self.tmp.name)

    def test_upload_duplicate_and_conflict(self):
        item=uploaded(self.root);self.assertEqual(item['pages'],1)
        self.assertTrue(uploaded(self.root)['duplicate']);self.assertEqual(len(sources.listing(self.root)['documents']),1)
        changed=pdf('Different contents')
        with self.assertRaises(FileExistsError):sources.upload(self.root,item['source'],io.BytesIO(changed),len(changed))
        self.assertEqual(sources.safe_path(self.root,item['source']).read_bytes(),pdf())

    def test_reject_unsafe_invalid_and_incomplete_uploads(self):
        for name in ('../x.pdf','/x.pdf','a/../x.pdf','.hidden/x.pdf','a\\x.pdf','x.txt','a//x.pdf','bad\n.pdf'):
            with self.subTest(name=name),self.assertRaises(ValueError):sources.upload(self.root,name,io.BytesIO(pdf()),len(pdf()))
        for content,length in [(b'not pdf',7),(pdf(),len(pdf())+20),(pdf(),sources.MAX_UPLOAD+1),(b'%PDF-invalid',12)]:
            with self.assertRaises(ValueError):sources.upload(self.root,'x.pdf',io.BytesIO(content),length)
        self.assertEqual(sources.listing(self.root)['documents'],[])
        self.assertFalse(list((self.root/'sources/incoming').glob('*')))

    def test_archive_restore_preserves_outputs_and_reviews(self):
        item=uploaded(self.root);docs=transcribed(self.root);path=Path(docs[0]['output'])/'page_0001.md';before=path.read_bytes()
        review=self.root/'reviews'/item['id']/'1.json';sources.write(review,dict(status='validated',revision=1,updated=1,original_hash=hashlib.sha256(before).hexdigest()))
        self.assertEqual(sources.listing(self.root)['documents'][0]['pages'][0]['human_status'],'validated')
        retired=sources.archive(self.root,[item['id']]);self.assertFalse(sources.listing(self.root)['documents']);self.assertTrue(review.exists());self.assertEqual(path.read_bytes(),before)
        self.assertFalse(sources.safe_path(self.root,item['source']).exists())
        sources.restore(self.root,retired['trash'][0]);self.assertEqual(len(sources.listing(self.root)['documents']),1);self.assertTrue(sources.safe_path(self.root,item['source']).is_file())
        path.write_text('Changed original');self.assertEqual(sources.listing(self.root)['documents'][0]['pages'][0]['human_status'],'stale')

    def test_restore_does_not_overwrite_new_active_source(self):
        item=uploaded(self.root);retired=sources.archive(self.root,[item['id']]);uploaded(self.root)
        with self.assertRaises(FileExistsError):sources.restore(self.root,retired['trash'][0])
        self.assertEqual(len(sources.listing(self.root)['trash']),1)

    def test_atomic_failure_rolls_back_moves_and_state(self):
        item=uploaded(self.root);before=(self.root/'progress.json').read_bytes();write=sources.write
        def fail(path,value):
            if path==self.root/'inventory.json':raise OSError('Synthetic storage failure')
            return write(path,value)
        with patch.object(sources,'write',side_effect=fail),self.assertRaises(OSError):sources.archive(self.root,[item['id']])
        sources.recover(self.root)
        self.assertTrue(sources.safe_path(self.root,item['source']).exists());self.assertEqual(json.loads(before),sources.read(self.root/'progress.json'));self.assertFalse(sources.metadata(self.root)['trash'])

    def test_busy_and_invalid_selection_are_safe(self):
        item=uploaded(self.root)
        with sources.lock(self.root):
            self.assertTrue(sources.listing(self.root)['busy'])
            with self.assertRaises(FileExistsError):sources.archive(self.root,[item['id']])
            with self.assertRaises(FileExistsError):sources.start(self.root,launch=False)
        with self.assertRaises(ValueError):sources.archive(self.root,[{}])
        with self.assertRaises(ValueError):sources.start(self.root,dashboard_url='https://external.example',launch=False)

    def test_incremental_audit_scope_and_history(self):
        a=uploaded(self.root);b=uploaded(self.root,'New/Other.pdf');docs=transcribed(self.root);inspection(self.root,docs)
        retained,pending=select(self.root,docs,[docs[1]['source']]);self.assertEqual(len(retained),2);self.assertFalse(pending)
        (Path(docs[1]['output'])/'page_0001.md').write_text('Different input')
        retained,pending=select(self.root,docs,[docs[1]['source']]);self.assertEqual(len(retained),1);self.assertEqual(len(pending),1)
        retired=sources.archive(self.root,[a['id']]);active=sources.read(self.root/'progress.json')['documents'];inspection(self.root,active,'after_removal')
        sources.restore(self.root,retired['trash'][0]);active=sources.read(self.root/'progress.json')['documents'];retained,pending=select(self.root,active,[])
        self.assertEqual(len(retained),2);self.assertFalse(pending);self.assertEqual(next(r for r in retained if r['document']==a['source'])['run_id'],'original')

    def test_empty_refresh_invokes_no_gpu_or_model(self):
        job=sources.start(self.root,refresh_only=True,launch=False)
        def runner(command,env):
            if 'model_run.py' in command[1]:
                env=dict(env,PATH='/no-gpu-programs')
            subprocess.run(command,env=env,check=True,capture_output=True)
        source_worker.execute(self.root,job['id'],runner=runner,recalculate=lambda:None)
        manifest=sources.read(self.root/'model_audits'/('sources_'+job['id'])/'manifest.json')
        self.assertEqual(manifest['processed'],0);self.assertIsNone(manifest['gpu_info']);self.assertEqual(sources.job_status(self.root)['status'],'complete')

    def test_worker_order_failure_and_resume(self):
        item=uploaded(self.root);job=sources.start(self.root,launch=False);calls=[]
        def failure(command,env):
            calls.append(command)
            self.assertEqual(json.loads(Path(env['MAPH_SOURCE_SCOPE']).read_text()),[item['source']])
            if command[1].endswith('/run.py') and '/audit/' not in command[1]:transcribed(self.root)
            else:raise RuntimeError('Synthetic stage failure')
        with self.assertRaises(RuntimeError):source_worker.execute(self.root,job['id'],runner=failure,recalculate=lambda:None)
        self.assertEqual(sources.job_status(self.root)['status'],'failed');self.assertTrue(sources.listing(self.root)['documents'][0]['pending'])
        docs=sources.read(self.root/'progress.json')['documents'];inspection(self.root,docs)
        resumed=sources.start(self.root,launch=False)
        def runner(command,env):
            calls.append(command)
            if '/audit/' in command[1]:subprocess.run(command,env=env,check=True,capture_output=True)
        source_worker.execute(self.root,resumed['id'],runner=runner,recalculate=lambda:calls.append(['analysis']))
        self.assertEqual(sources.job_status(self.root)['status'],'complete');self.assertFalse(sources.listing(self.root)['documents'][0]['pending']);self.assertEqual(calls[-1],['analysis'])
        stages=[json.loads(x)['stage'] for x in (self.root/'sources/events.jsonl').read_text().splitlines() if json.loads(x)['event']=='source_pipeline_stage']
        self.assertEqual(stages[-6:],['inventory','transcription','rules_audit','model_audit','cross_analysis','complete'])


class SourceHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=fixture(self.tmp.name)
        self.server=dashboard.ThreadingHTTPServer(('127.0.0.1',0),dashboard.Handler);self.host='127.0.0.1:'+str(self.server.server_port)
        self.patches=[patch.object(dashboard,'ROOT',self.root),patch.object(dashboard,'HOSTS',{self.host}),patch.object(dashboard,'ORIGINS',{'http://'+self.host})]
        for p in self.patches:p.start()
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()

    def tearDown(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
        for p in self.patches:p.stop()
        self.tmp.cleanup()

    def request(self,path,body,headers=None):
        conn=http.client.HTTPConnection(self.host,timeout=5)
        conn.request('POST',path,body,headers or {'Origin':'http://'+self.host,'Content-Type':'application/json'})
        response=conn.getresponse();value=json.loads(response.read());conn.close();return response.status,value

    def test_http_upload_origin_type_size_and_json(self):
        headers={'Origin':'http://'+self.host,'Content-Type':'application/pdf','X-Source-Path':'Collection%2FTest.pdf'}
        status,value=self.request('/sources/upload',pdf(),headers);self.assertEqual(status,200);self.assertEqual(value['pages'],1)
        self.assertEqual(self.request('/sources/upload',pdf(),dict(headers,Origin='http://wrong.example'))[0],403)
        self.assertEqual(self.request('/sources/upload',pdf(),dict(headers,**{'Content-Type':'text/plain'}))[0],400)
        self.assertEqual(self.request('/sources/upload',b'',dict(headers,**{'Content-Length':str(sources.MAX_UPLOAD+1)}))[0],400)
        self.assertEqual(self.request('/sources/archive','[]')[0],400)
        with patch.object(sources,'start',return_value={'status':'queued'}) as start:
            status,result=self.request('/sources/archive',json.dumps({'ids':[value['id']]}));self.assertEqual(status,200);self.assertEqual(result['removed'],1);self.assertTrue(start.call_args.kwargs['refresh_only'])


if __name__=='__main__':unittest.main()
