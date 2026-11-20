import importlib.util
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

MODULE=Path(__file__).resolve().parents[1]/'reader.py'
spec=importlib.util.spec_from_file_location('reader',MODULE)
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
NOW=datetime(2026,11,19,12,tzinfo=timezone.utc)
CFG=json.loads((MODULE.parent/'preferences.json').read_text())
RSS=b'''<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#" xmlns="http://purl.org/rss/1.0/" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:arxiv="http://arxiv.org/schemas/atom"><channel rdf:about="x"><title>Statistics</title></channel><item rdf:about="x"><title>Variational inference for mixed models</title><link>https://arxiv.org/abs/2611.01234v2</link><description>&lt;p&gt;arXiv:2611.01234 Announce Type: new Abstract: Bayesian inference with MCMC and variational inference.&lt;/p&gt;</description><dc:creator>David Blei, Andrew Gelman</dc:creator><arxiv:announce_type>new</arxiv:announce_type></item></rdf:RDF>'''

def paper(**updates):
    p=r.parse_feed(RSS,'stat.ME',NOW)[0]
    p.update(updates)
    return p

class ReaderTests(unittest.TestCase):
    def test_rdf(self):
        p=paper();self.assertEqual(p['id'],'2611.01234');self.assertEqual(p['url'],'https://arxiv.org/abs/2611.01234')
        self.assertEqual(p['abstract'],'Bayesian inference with MCMC and variational inference.')
        self.assertEqual(p['authors'],'David Blei, Andrew Gelman')
    def test_rss2(self):
        raw=b'<rss><channel><item><title>A title</title><link>https://arxiv.org/abs/stat/0612345v3</link><description>An abstract</description><author>A Name</author></item></channel></rss>'
        self.assertEqual(r.parse_feed(raw,'stat.AP',NOW)[0]['id'],'stat/0612345')
    def test_bad_xml(self):
        with self.assertRaises(Exception):r.parse_feed(b'<not-closed','stat.ME',NOW)
    def test_not_a_feed(self):
        with self.assertRaises(ValueError):r.parse_feed(b'<html><body>Unavailable</body></html>','stat.ME',NOW)
    def test_id(self):
        self.assertEqual(r.canonical_id('https://arxiv.org/pdf/2611.01234v3.pdf'),'2611.01234')
        self.assertIsNone(r.canonical_id('https://example.com/no-paper'))
    def test_deduplication(self):
        a=paper();b=paper(categories=['stat.CO']);rows=r.merge_papers([], [a,b],CFG,NOW)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['categories'],['stat.CO','stat.ME'])
    def test_first_seen_preserved(self):
        a=paper(first_seen=r.iso(NOW-timedelta(days=2)))
        rows=r.merge_papers([a],[paper()],CFG,NOW)
        self.assertEqual(rows[0]['first_seen'],a['first_seen'])
    def test_retention(self):
        a=paper(first_seen=r.iso(NOW-timedelta(days=8)))
        self.assertEqual(r.merge_papers([a],[],CFG,NOW),[])
    def test_replacements(self):
        self.assertEqual(r.merge_papers([],[paper(announce_type='replace')],CFG,NOW),[])
    def test_accents(self):
        self.assertTrue(r.matches('Emmanuel Candès','Emmanuel Candes'))
        self.assertTrue(r.matches('Peter Bühlmann','Peter Buhlmann'))
    def test_keyword_boundary(self):
        self.assertFalse(r.matches('MCMC','MCMCfoo'));self.assertTrue(r.matches('MCMC','A MCMC-based method'))
    def test_rules(self):
        score=r.rule_score(paper(),CFG)
        self.assertEqual(score['method'],'rules');self.assertTrue(0<=score['score']<=10)
        self.assertIn('Variational inference and Bayesian computation',score['topics']);self.assertIn('Andrew Gelman',score['preferred_authors'])
    def test_missing_key_fallback(self):
        rows,w=r.rank([paper()],CFG,enabled=True)
        self.assertEqual(rows[0]['ranking']['method'],'rules');self.assertTrue(w)
    def test_valid_llm(self):
        raw=json.dumps({'choices':[{'message':{'content':json.dumps({'score':7,'reason':'Methods match.','summary':'Abstract-based summary.'})}}]}).encode()
        with patch.object(r,'request_bytes',return_value=raw):
            score=r.llm_score(paper(),CFG,'dummy','model','https://example.test/v1')
        self.assertEqual(score['method'],'llm');self.assertLessEqual(score['score'],10)
    def test_invalid_llm_score(self):
        for value in (True,-1,12,'9',float('nan')):
            raw=json.dumps({'choices':[{'message':{'content':json.dumps({'score':value,'reason':'r','summary':'s'})}}]}).encode()
            with patch.object(r,'request_bytes',return_value=raw):
                with self.assertRaises(ValueError):r.llm_score(paper(),CFG,'dummy','model','https://example.test/v1')
    def test_https_required(self):
        with self.assertRaises(ValueError):r.llm_score(paper(),CFG,'dummy','model','http://example.test/v1')
    def test_failure_falls_back(self):
        with patch.object(r,'llm_score',side_effect=ValueError('secret provider response')):
            rows,w=r.rank([paper()],CFG,True,'dummy','model','https://example.test/v1')
        self.assertEqual(rows[0]['ranking']['method'],'rules');self.assertNotIn('secret provider response',' '.join(w))
    def test_cache(self):
        p=paper();p['ranking_key']=r.ranking_key(p,CFG,'llm','model');p['ranking']={'method':'llm','score':8}
        with patch.object(r,'llm_score',side_effect=AssertionError('must not call')):
            rows,w=r.rank([p],CFG,True,'dummy','model','https://example.test/v1')
        self.assertEqual(rows[0]['ranking']['score'],8)
    def test_profile_changes_cache(self):
        a=r.ranking_key(paper(),CFG,'llm','model');cfg=dict(CFG,context='another profile')
        self.assertNotEqual(a,r.ranking_key(paper(),cfg,'llm','model'))
    def test_html_escaping(self):
        p=paper(title='<script>alert(1)</script>',abstract='<img onerror=attack>',authors='A & B')
        p['ranking']=r.rule_score(p,CFG)
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'index.html';r.render([p],CFG,{},target);text=target.read_text()
        self.assertNotIn('<script>alert(1)</script>',text);self.assertIn('&lt;script&gt;',text)
        self.assertIn('A &amp; B',text)
    def test_selection_panel_authors_and_collapsed_state(self):
        cfg=dict(CFG,authors=['Example Author <A>'])
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'reading.html';r.render([],cfg,{},target,{});html=target.read_text()
        self.assertIn('<details class="reader-profile"><summary>How papers are selected</summary>',html)
        self.assertIn('<h3>Authors followed</h3>',html)
        self.assertIn('Example Author &lt;A&gt;',html)
        self.assertIn('<h3>From collection to selection</h3>',html)
        self.assertNotIn('Research profile and selection rules',html)
    def test_all_feed_failure_preserves_outputs(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);state=d/'papers.json';output=d/'reading.html';cfg=d/'cfg.json'
            cfg.write_text(json.dumps(CFG));state.write_text('{"papers":[],"status":{}}');output.write_text('previous page')
            args=SimpleNamespace(config=cfg,state=state,output=output,render_only=False)
            with patch.object(r,'request_bytes',side_effect=OSError('offline')),patch.object(r.time,'sleep'):
                with self.assertRaises(RuntimeError):r.run(args)
            self.assertEqual(output.read_text(),'previous page');self.assertEqual(json.loads(state.read_text())['papers'],[])
    def test_partial_feed_warning(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);cfg=d/'cfg.json';cfg.write_text(json.dumps(CFG))
            args=SimpleNamespace(config=cfg,state=d/'papers.json',output=d/'reading.html',render_only=False)
            with patch.object(r,'request_bytes',side_effect=[RSS,OSError('offline'),RSS]),patch.object(r.time,'sleep'):
                r.run(args)
            stored=json.loads(args.state.read_text());self.assertEqual(len(stored['papers']),1)
            self.assertTrue(stored['status']['warnings']);self.assertIn('stat.CO',stored['status']['warnings'][0])
    def test_render_only_no_network_preserves_llm(self):
        with tempfile.TemporaryDirectory() as d:
            d=Path(d);cfg=d/'cfg.json';cfg.write_text(json.dumps(CFG));p=paper()
            p['ranking']=dict(r.rule_score(p,CFG),method='llm',score=8,model='test')
            state=d/'papers.json';state.write_text(json.dumps({'papers':[p],'status':{'last_success':r.iso(NOW)}}))
            args=SimpleNamespace(config=cfg,state=state,output=d/'reading.html',render_only=True)
            class FrozenDateTime(datetime):
                @classmethod
                def now(cls,tz=None):return NOW
            with patch.object(r,'request_bytes',side_effect=AssertionError('network not allowed')),patch.object(r,'datetime',FrozenDateTime):
                r.run(args)
            self.assertIn('LLM-assisted',args.output.read_text())
    def test_config_validation(self):
        with self.assertRaises(ValueError):r.validate_config(dict(CFG,categories=['../../bad']))
        with self.assertRaises(ValueError):r.validate_config(dict(CFG,shortlist_size=0))

if __name__=='__main__':unittest.main()
