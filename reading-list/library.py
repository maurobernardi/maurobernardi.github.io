#!/usr/bin/env python3
"""Build a persistent, bounded thematic arXiv library; metadata only."""
import json
from pathlib import Path
from urllib.parse import urlencode
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
import time
import reader

ATOM={'a':'http://www.w3.org/2005/Atom','o':'http://a9.com/-/spec/opensearch/1.1/'}
STORE=Path(__file__).resolve().parent/'data/library.json'

def parse_atom(raw, now):
    root=ET.fromstring(raw)
    if root.tag!='{http://www.w3.org/2005/Atom}feed':
        raise ValueError('Unexpected API response')
    papers=[]
    for e in root.findall('a:entry',ATOM):
        url=e.findtext('a:id','',ATOM);pid=reader.canonical_id(url)
        if not pid:raise ValueError('Invalid API entry or API error')
        text=lambda field:reader.plain(e.findtext('a:'+field,'',ATOM))
        papers.append(dict(id=pid,url='https://arxiv.org/abs/'+pid,title=text('title'),abstract=text('summary'),authors=', '.join(reader.plain(a.findtext('a:name','',ATOM)) for a in e.findall('a:author',ATOM)),categories=sorted({a.get('term','') for a in e.findall('a:category',ATOM)}),source_date=text('published'),updated=text('updated'),first_seen=reader.iso(now),last_seen=reader.iso(now),announce_type='historical'))
    return papers,int(root.findtext('o:totalResults',str(len(papers)),ATOM))

def search_query(terms,categories):
    # Search title and abstract, allowing cross-listings in the chosen categories.
    phrases=['('+ ' OR '.join(field+':"'+term.replace('"','')+'"' for field in ('ti','abs'))+')' for term in terms]
    return '('+' OR '.join('cat:'+c for c in categories)+') AND ('+' OR '.join(phrases)+')'

def update(state,daily,cfg,fetch=reader.request_bytes,sleep=time.sleep):
    now=datetime.now(timezone.utc);options=cfg['library'];queries=options['queries'];names=list(queries)
    old={p['id']:dict(p) for p in state.get('papers',[])}
    # Feed papers are retained in the library even after the daily archive expires.
    for p in daily:
        if p['id'] in old:
            p=dict(p,first_seen=old[p['id']]['first_seen'])
        old[p['id']]=p
    progress=state.get('progress',{});fingerprint=reader.sha256(json.dumps([queries,options['categories']],sort_keys=True).encode()).hexdigest()
    if state.get('query_fingerprint')!=fingerprint:progress={}
    cursor=state.get('cursor',0)%len(names);indices=list(range(len(names))) if not state.get('initial_search_attempted') else [cursor]
    warnings=[];successes=0
    for n,i in enumerate(indices):
        # Also leave a pause after the preceding daily RSS requests.
        sleep(3.2)
        topic=names[i];start=progress.get(topic,0)
        query=search_query(queries[topic],options['categories'])
        url='https://export.arxiv.org/api/query?'+urlencode(dict(search_query=query,start=start,max_results=options['page_size'],sortBy='submittedDate',sortOrder='descending'))
        try:
            records,total=parse_atom(fetch(url,headers={'User-Agent':'MauroBernardiReadingList/1.0 (+https://maurobernardi.github.io/)'}),now)
            for p in records:
                if p['id'] in old:p['first_seen']=old[p['id']]['first_seen']
                old[p['id']]=p
            next_start=start+len(records)
            progress[topic]=0 if not records or next_start>=min(total,options['max_results_per_query']) else next_start
            successes+=1
        except Exception as e:
            warnings.append('Historical search unavailable for '+topic+' ('+type(e).__name__+'). Previously collected records are retained.')
    papers=list(old.values())
    # Deterministic relevance ranking avoids additional model/API charges for backfill.
    for p in papers:p['ranking']=reader.rule_score(p,cfg)
    result=dict(papers=papers,progress=progress,cursor=(indices[-1]+1)%len(names),query_fingerprint=fingerprint,initial_search_attempted=bool(successes) or state.get('initial_search_attempted',False),warnings=warnings)
    if successes:result['last_success']=reader.iso(now)
    elif state.get('last_success'):result['last_success']=state['last_success']
    return result

def main():
    cfg=reader.validate_config(json.loads((reader.HERE/'preferences.json').read_text()))
    daily=json.loads((reader.HERE/'data/papers.json').read_text())
    state=json.loads(STORE.read_text()) if STORE.exists() else {}
    result=update(state,daily.get('papers',[]),cfg)
    reader.atomic_json(STORE,result)
    reader.render(daily['papers'],cfg,daily.get('status',{}),reader.ROOT/'docs/reading-list.html',result)
    print('Persistent library:',len(result['papers']),'records;',len(result['warnings']),'search warnings.')
    for w in result['warnings']:print('WARNING:',w)

if __name__=='__main__':main()
