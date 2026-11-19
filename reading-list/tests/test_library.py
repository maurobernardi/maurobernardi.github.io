import importlib.util
from pathlib import Path
import sys
import json
import unittest
from copy import deepcopy
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import library as lib
import reader
CFG=json.loads((ROOT/'preferences.json').read_text())
ATOM=b'''<feed xmlns="http://www.w3.org/2005/Atom" xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"><opensearch:totalResults>201</opensearch:totalResults><entry><id>http://arxiv.org/abs/stat/0612345v2</id><title>Quantile regression and variable selection</title><summary>Adaptive lasso for conditional quantile regression.</summary><published>2006-12-01T00:00:00Z</published><updated>2010-01-01T00:00:00Z</updated><author><name>A Researcher</name></author><category term="stat.ME"/></entry></feed>'''
class LibraryTests(unittest.TestCase):
 def test_atom_and_dates(self):
  papers,total=lib.parse_atom(ATOM,lib.datetime.now(lib.timezone.utc))
  self.assertEqual(total,201);self.assertEqual(papers[0]['id'],'stat/0612345');self.assertEqual(papers[0]['source_date'][:4],'2006')
 def test_api_error_rejected(self):
  with self.assertRaises(ValueError):lib.parse_atom(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors</id></entry></feed>',lib.datetime.now(lib.timezone.utc))
 def test_query_fields(self):
  q=lib.search_query(['quantile regression'],['stat.ME'])
  self.assertIn('ti:"quantile regression"',q);self.assertIn('abs:"quantile regression"',q);self.assertIn('cat:stat.ME',q)
 def test_dedup_and_no_expiry(self):
  cfg=deepcopy(CFG);cfg['library']['queries']={'Quantiles':['quantile regression']}
  p=lib.parse_atom(ATOM,lib.datetime.now(lib.timezone.utc))[0][0];p['first_seen']='2000-01-01T00:00:00+00:00'
  out=lib.update({'papers':[p]},[p],cfg,fetch=lambda *a,**k:ATOM,sleep=lambda _:None)
  self.assertEqual(len(out['papers']),1);self.assertEqual(out['papers'][0]['first_seen'],p['first_seen'])
 def test_page_progress(self):
  cfg=deepcopy(CFG);cfg['library']['queries']={'Quantiles':['quantile regression']}
  out=lib.update({},[],cfg,fetch=lambda *a,**k:ATOM,sleep=lambda _:None)
  self.assertEqual(out['progress']['Quantiles'],1)
  urls=[]
  def fetch(url,**kwargs):urls.append(url);return ATOM
  lib.update(out,[],cfg,fetch=fetch,sleep=lambda _:None)
  self.assertIn('start=1',urls[0])
 def test_failure_preserves_records(self):
  p=lib.parse_atom(ATOM,lib.datetime.now(lib.timezone.utc))[0][0]
  def fail(*a,**k):raise OSError('offline')
  out=lib.update({'papers':[p]},[],CFG,fetch=fail,sleep=lambda _:None)
  self.assertEqual(len(out['papers']),1);self.assertTrue(out['warnings']);self.assertFalse(out['initial_search_attempted'])
 def test_recent_relevant_has_no_twenty_limit(self):
  import tempfile
  p=lib.parse_atom(ATOM,lib.datetime.now(lib.timezone.utc))[0][0]
  rows=[]
  for i in range(25):
   q=dict(p,id='2611.'+str(10000+i));q['ranking']=reader.rule_score(q,CFG);rows.append(q)
  with tempfile.TemporaryDirectory() as d:
   target=Path(d)/'page.html';reader.render(rows,CFG,{},target,{'papers':[p]});html=target.read_text()
  self.assertIn('All relevant recent papers (25)',html);self.assertIn('Browse relevant historical papers (1)',html)
  self.assertIn('Submitted 2006-12-01',html)
if __name__=='__main__':unittest.main()
