from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import gzip
import tempfile
import json
from datetime import timedelta
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import maintenance as m
CFG=m.read_json(Path(m.__file__).with_name('config.json'))
class Tests(unittest.TestCase):
 def test_doi_normalisation(self):self.assertEqual(m.doi('https://doi.org/10.1234/ABC'),'10.1234/abc')
 def test_no_author_name_collision(self):
  self.assertFalse(m.author_match([{'given':'Mario','family':'Bernardi'}],CFG));self.assertIn('uncertain',m.author_match([{'given':'M.','family':'Bernardi'}],CFG))
 def test_known_doi(self):
  item={'author':[{'given':'Mauro','family':'Bernardi'}],'title':['A title'],'DOI':'10.1234/AbC'}
  self.assertIsNone(m.crossref_candidate(item,[{'paper_url':'https://doi.org/10.1234/abc','title':'A title'}],CFG))
 def test_journal_transition(self):
  item={'author':[{'given':'Mauro','family':'Bernardi'}],'title':['Sparse estimation'],'DOI':'10.1234/new'}
  known=[{'kind':'preprint','id':'sparse','title':'Sparse estimation','paper_url':'https://arxiv.org/abs/1234.5678'}]
  self.assertIn('journal version',m.crossref_candidate(item,known,CFG)['action'])
 def test_private_urls(self):
  for url in ['http://127.0.0.1/','http://localhost/a','http://10.0.0.2','file:///etc/passwd','https://user:secret@example.org']:
   self.assertFalse(m.safe_url(url))
 def test_offline_never_fetches(self):
  with patch.object(m,'urlopen',side_effect=AssertionError('network')):
   self.assertEqual(m.Fetcher().get('https://example.com')['status'],'not-checked')
 def test_restricted_not_broken(self):
  class F:
   def get(self,*a,**k):return {'ok':False,'status':403}
  self.assertEqual(m.check_remote('https://example.org',F())['state'],'restricted-or-rate-limited')
 def test_404_is_broken(self):
  class F:
   def get(self,*a,**k):return {'ok':False,'status':404}
  self.assertEqual(m.check_remote('https://example.org',F())['state'],'broken')
 def test_cran_index(self):
  rows=m.cran_packages(gzip.compress(b'Package: fastQR\nVersion: 1.2.0\n\nPackage: fdaSP\nVersion: 0.1\n'))
  self.assertEqual(rows['fastQR']['Version'],'1.2.0')
 def test_internal_missing_link_and_traversal(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'docs').mkdir();(root/'docs/index.html').write_text('<a href="missing.pdf">PDF</a><a href="../private.txt">Private</a>')
   with patch.object(m,'ROOT',root):data=m.links(CFG,m.Fetcher())
   self.assertEqual(len(data['local_problems']),2)
 def test_digest_unique_and_grouped(self):
  p={'id':'2611.12345','title':'A paper','authors':'A Name','url':'https://arxiv.org/abs/2611.12345','abstract':'Author abstract','first_seen':m.stamp(),'ranking':{'score':8,'topics':['Sparsity','Optimisation']}}
  with patch.object(m,'recent_papers',return_value=([p],{'last_success':m.stamp()})):
   data=m.digest(CFG,m.Fetcher())
  self.assertEqual(data['unique_papers'],1);self.assertEqual(len(data['groups']),2)
 def test_no_secret_in_request_errors(self):
  with patch.object(m,'urlopen',side_effect=m.URLError('secret contents')):
   result=m.Fetcher(True).get('https://example.com')
  self.assertNotIn('secret',str(result))
 def test_dashboard_escapes_metadata(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);m.dashboard(p,{'notes':{'title':'<script>x</script>','notice':'Draft','papers':[]}});html=(p/'index.html').read_text()
   self.assertNotIn('<script>x</script>',html);self.assertIn('&lt;script&gt;',html)
 def test_public_ci_excludes_private_notes(self):
  with patch.dict(m.os.environ,{'GITHUB_ACTIONS':'true'}):data=m.notes(CFG,m.Fetcher())
  self.assertEqual(data['status'],'local-only')
 def test_notes_do_not_overwrite_edits(self):
  p={'id':'2611.12345','title':'Paper','authors':'A','url':'https://arxiv.org/abs/2611.12345','abstract':'Abstract'}
  with tempfile.TemporaryDirectory() as d:
   with patch.object(m,'ROOT',Path(d)),patch.object(m,'recent_papers',return_value=([p],{})):
    m.notes(CFG,m.Fetcher());file=Path(d)/'private-notes/automation/reading-notes/2611.12345.md';file.write_text('My annotation');m.notes(CFG,m.Fetcher());self.assertEqual(file.read_text(),'My annotation')
if __name__=='__main__':unittest.main()
