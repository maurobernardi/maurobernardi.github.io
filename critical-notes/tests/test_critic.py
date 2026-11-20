import importlib.util
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[1]/'critic.py'
spec=importlib.util.spec_from_file_location('critic',MODULE);c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
CFG=c.load_config(MODULE.with_name('preferences.json'))
PAGES=[{'page':1,'text':'The model assumes independent Gaussian errors. The coefficient prior is proper.'},
       {'page':2,'text':'The experiments compare runtime and prediction error on simulated datasets.'}]

def finding(kind='paper_claim'):
    return {'kind':kind,'section':CFG['sections'][0],'text':'The authors assume independent Gaussian observation errors.',
            'evidence':[{'page':1,'quote':'The model assumes independent Gaussian errors.'}]}

def discussion():
    return {'sections':[{'name':name,'paragraphs':[{'kind':'paper_claim','text':'The model uses independent Gaussian observation errors.','finding_ids':['C1F1']}] if i==0 else [],
                         'missing_information':'' if i==0 else 'Not established by this fixture.'} for i,name in enumerate(CFG['sections'])]}

class CriticTests(unittest.TestCase):
    def test_config(self):self.assertEqual(len(CFG['sections']),8)
    def test_arxiv_id(self):
        self.assertEqual(c.validate_arxiv('2412.05905v3'),'2412.05905v3')
        with self.assertRaises(ValueError):c.validate_arxiv('https://evil.example/paper.pdf')
        with self.assertRaises(ValueError):c.validate_arxiv('../../secret')
    def test_public_output_rejected(self):
        with self.assertRaises(ValueError):c.private_output(dict(CFG,output_directory='docs/notes'))
    def test_outside_output_rejected(self):
        with self.assertRaises(ValueError):c.private_output(dict(CFG,output_directory='/tmp/leak'))
    def test_private_output(self):self.assertIn('private-notes',str(c.private_output(CFG)))
    def test_full_chunk_coverage(self):
        pages=[{'page':1,'text':'A'*3000},{'page':2,'text':'B'*2500}]
        chunks=c.make_chunks(pages,dict(CFG,chunk_characters=2000))
        flattened=[p for chunk in chunks for p in chunk]
        for original in pages:self.assertEqual(''.join(x['text'] for x in flattened if x['page']==original['page']),original['text'])
    def test_long_paper_not_truncated(self):
        with self.assertRaises(ValueError):c.make_chunks([{'page':1,'text':'x'*10000}],dict(CFG,chunk_characters=2000,max_chunks=1))
    def test_scanned_pdf_rejected(self):
        with self.assertRaises(ValueError):c.make_chunks([{'page':1,'text':''}],CFG)
    def test_evidence_valid(self):c.validate_evidence(finding()['evidence'],PAGES)
    def test_wrong_page_rejected(self):
        with self.assertRaises(ValueError):c.validate_evidence([{'page':2,'quote':'The model assumes independent Gaussian errors.'}],PAGES)
    def test_invented_quote_rejected(self):
        with self.assertRaises(ValueError):c.validate_evidence([{'page':1,'quote':'The theorem proves global convergence.'}],PAGES)
    def test_too_long_quote(self):
        with self.assertRaises(ValueError):c.validate_evidence([{'page':1,'quote':'word '*36}],PAGES)
    def test_evidence_page_not_boolean(self):
        with self.assertRaises(ValueError):c.validate_evidence([{'page':True,'quote':'The model assumes independent Gaussian errors.'}],PAGES)
    def test_missing_evidence(self):
        with self.assertRaises(ValueError):c.validate_evidence([],PAGES)
    def test_findings(self):c.validate_findings({'findings':[finding()]},PAGES,CFG)
    def test_invalid_kind(self):
        with self.assertRaises(ValueError):c.validate_findings({'findings':[finding('approved-review')]},PAGES,CFG)
    def test_valid_discussion(self):c.validate_discussion(discussion(),[dict(finding(),id='C1F1')],CFG)
    def test_unknown_reference(self):
        d=discussion();d['sections'][0]['paragraphs'][0]['finding_ids']=['unknown']
        with self.assertRaises(ValueError):c.validate_discussion(d,[dict(finding(),id='C1F1')],CFG)
    def test_critique_cannot_become_paper_claim(self):
        with self.assertRaises(ValueError):c.validate_discussion(discussion(),[dict(finding('critique'),id='C1F1')],CFG)
    def test_missing_section(self):
        d=discussion();d['sections'].pop()
        with self.assertRaises(ValueError):c.validate_discussion(d,[dict(finding(),id='C1F1')],CFG)
    def test_unsupported_silence(self):
        d=discussion();del d['sections'][1]['missing_information']
        with self.assertRaises(ValueError):c.validate_discussion(d,[dict(finding(),id='C1F1')],CFG)
    def test_missing_credentials(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(RuntimeError):c.model_call('system',{},CFG)
    def test_local_upload_requires_explicit_flag(self):
        args=SimpleNamespace(config=MODULE.with_name('preferences.json'),limit=1,index_only=False,pdf=Path('/tmp/paper.pdf'),arxiv=None,shortlist=None,prepare=False,allow_local_upload=False,title=None)
        with self.assertRaises(ValueError):c.main(args)
    def test_prepare_does_not_call_model(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp);pdf=temp/'paper.pdf';pdf.write_bytes(b'%PDF-test-only')
            pages=[{'page':1,'text':PAGES[0]['text']*30}]
            with patch.object(c,'extract_pdf',return_value=pages),patch.object(c,'model_call',side_effect=AssertionError('No API in preparation')):
                dest,_,_,m=c.preparation(pdf,CFG,temp/'notes',{'title':'Fixture'})
            self.assertEqual(m['status'],'prepared-not-analyzed');self.assertTrue((dest/'source-pages.json').exists())
            self.assertFalse((dest/'discussion.html').exists())
    def test_pipeline_cache_and_private_render(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);dest=root/'fixture';dest.mkdir()
            manifest={'pdf_sha256':'test','metadata':{'title':'<script>malicious</script>'},'pages':2,'chunks':1,'low_text_pages':[],
                      'extraction_notice':'Fixture only.'}
            with patch.dict(os.environ,{'CRITICAL_NOTES_API_KEY':'dummy','CRITICAL_NOTES_MODEL':'test-model'}),patch.object(c,'private_output',return_value=root):
                with patch.object(c,'model_call',side_effect=[{'findings':[finding()]},discussion()]) as api:
                    result=c.analyze(dest,PAGES,[PAGES],manifest,CFG)
                self.assertEqual(api.call_count,2);self.assertEqual(result['status'],'draft-for-human-review')
                with patch.object(c,'model_call',side_effect=AssertionError('Cached output must not call API')):
                    c.analyze(dest,PAGES,[PAGES],manifest,CFG)
            html=(dest/'discussion.html').read_text()
            self.assertNotIn('<script>malicious</script>',html);self.assertIn('&lt;script&gt;',html)
            self.assertIn('source.pdf#page=1',html);self.assertTrue((root/'index.html').exists())
    def test_changed_text_invalidates_cache(self):
        self.assertNotEqual(c.digest(PAGES),c.digest([{'page':1,'text':'Changed extraction'}]))

if __name__=='__main__':unittest.main()
