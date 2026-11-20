#!/usr/bin/env python3
"""Five research assistants. Read-only sources; suggestions never change site content."""
import argparse
import csv
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import gzip
import hashlib
from html import escape, unescape
from html.parser import HTMLParser
import importlib.util
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import unicodedata
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urljoin, urlsplit, unquote
from urllib.request import Request, urlopen
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parents[1]
TASKS=('publications','links','packages','digest','notes')

def norm(s):
    return re.sub(r'[^a-z0-9]+',' ',unicodedata.normalize('NFKD',s).encode('ascii','ignore').decode().lower()).strip()
def now():return datetime.now(timezone.utc)
def stamp():return now().isoformat(timespec='seconds')
def date(s):
    try:return datetime.fromisoformat(s.replace('Z','+00:00')).astimezone(timezone.utc)
    except (ValueError,TypeError,AttributeError):return None
def read_json(p,default=None):return json.loads(p.read_text(encoding='utf-8')) if p.exists() else ({} if default is None else default)
def csv_rows(p):
    with p.open(encoding='utf-8',newline='') as f:return list(csv.DictReader(f))
def write_json(p,x):
    p.parent.mkdir(parents=True,exist_ok=True);temp=p.with_suffix('.tmp');temp.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');temp.replace(p)
def doi(s):
    s=unquote(s).strip().lower();s=re.sub(r'^https?://(?:dx\.)?doi.org/','',s)
    return s.rstrip(' .') if re.match(r'^10\.\d{4,9}/\S+$',s) else ''
def safe_url(url):
    u=urlsplit(url)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password:return False
    if u.hostname.lower() in ('localhost','localhost.localdomain') or u.hostname.lower().endswith('.local'):return False
    try:
        if not ipaddress.ip_address(u.hostname).is_global:return False
    except ValueError:pass
    return True

class Fetcher:
    def __init__(self,network=False,timeout=12):self.network=network;self.timeout=timeout;self.cache={}
    def get(self,url,accept='application/json',method='GET',limit=12*1024*1024):
        key=(url,accept,method)
        if key in self.cache:return self.cache[key]
        if not self.network:return {'ok':False,'status':'not-checked','reason':'Network checks disabled'}
        if not safe_url(url):return {'ok':False,'status':'invalid-url','reason':'Unsupported or non-public URL'}
        headers={'User-Agent':'MauroBernardiResearchMaintenance/1.0 (+https://maurobernardi.github.io/)','Accept':accept}
        if urlsplit(url).hostname=='api.github.com' and os.getenv('GITHUB_TOKEN'):headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
        try:
            with urlopen(Request(url,headers=headers,method=method),timeout=self.timeout) as response:
                raw=response.read(limit+1) if method!='HEAD' else b''
                if len(raw)>limit:raise ValueError('Response exceeds size limit')
                result={'ok':True,'status':response.status,'url':response.url,'body':raw}
        except HTTPError as e:
            result={'ok':False,'status':e.code,'reason':'HTTP '+str(e.code)}
        except (URLError,TimeoutError,OSError,ValueError) as e:
            result={'ok':False,'status':'unavailable','reason':type(e).__name__}
        self.cache[key]=result;return result
    def json(self,url):
        r=self.get(url)
        if not r['ok']:return None,r
        try:return json.loads(r['body']),r
        except (ValueError,UnicodeDecodeError):return None,{'ok':False,'status':'invalid-json','reason':'Invalid JSON response'}

def author_match(authors,cfg):
    exact=False;initial=False
    for a in authors:
        if norm(a.get('family',''))!=norm(cfg['author']['family']):continue
        given=norm(a.get('given',''))
        if given==norm(cfg['author']['given']) or given.startswith(norm(cfg['author']['given'])+' '):exact=True
        elif given in ('m','mauro'):initial=True
    return 'full-name match; verify identity' if exact else ('initial-only match; identity uncertain' if initial else '')

def crossref_candidate(item,known,cfg):
    match=author_match(item.get('author',[]),cfg)
    if not match:return None
    title=unescape(' '.join(item.get('title',[])));d=doi(item.get('DOI',''))
    if not title:return None
    for row in known:
        if d and d==doi(row.get('paper_url','')):return None
        similarity=SequenceMatcher(None,norm(title),norm(row['title'])).ratio()
        if similarity>=.9:
            if row.get('kind')=='preprint' and d:
                return {'title':title,'doi':d,'url':'https://doi.org/'+d,'action':'Possible journal version of listed preprint','listed_id':row['id'],'identity':match,'source':'Crossref'}
            return None
    return {'title':title,'doi':d,'url':('https://doi.org/'+d) if d else item.get('URL',''),'action':'Possible publication missing from selected list','identity':match,'source':'Crossref','venue':'; '.join(item.get('container-title',[]))}

def publications(cfg,fetch):
    known=csv_rows(ROOT/'data/publications.csv');candidates=[];sources=[]
    start=now().year-cfg['publication_search_years']
    url='https://api.crossref.org/works?'+urlencode({'query.author':cfg['author']['name'],'filter':f'from-pub-date:{start}-01-01','rows':cfg['crossref_rows'],'sort':'published','order':'desc'})
    data,result=fetch.json(url);sources.append({'source':'Crossref','url':url,'status':result['status']})
    for item in (data or {}).get('message',{}).get('items',[]):
        c=crossref_candidate(item,known,cfg)
        if c:candidates.append(c)
    orcid=cfg['author']['orcid'];person,r=fetch.json('https://pub.orcid.org/v3.0/'+orcid+'/person');identity_ok=False
    if person:
        name=person.get('name') or {};given=(name.get('given-names') or {}).get('value','');family=(name.get('family-name') or {}).get('value','')
        identity_ok=norm(given+' '+family)==norm(cfg['author']['name'])
    sources.append({'source':'ORCID identity','url':'https://orcid.org/'+orcid,'status':r['status'],'identity_verified':identity_ok})
    if identity_ok:
        works,r=fetch.json('https://pub.orcid.org/v3.0/'+orcid+'/works');sources.append({'source':'ORCID works','status':r['status']})
        existing={doi(x.get('paper_url','')) for x in known}
        for group in (works or {}).get('group',[]):
            for w in group.get('work-summary',[])[:1]:
                title=((w.get('title') or {}).get('title') or {}).get('value','')
                ds=[doi(x.get('external-id-value','')) for x in (w.get('external-ids') or {}).get('external-id',[]) if x.get('external-id-type')=='doi']
                d=next((x for x in ds if x),'')
                if d and d not in existing and not any(SequenceMatcher(None,norm(title),norm(x['title'])).ratio()>.9 for x in known):
                    candidates.append({'title':title,'doi':d,'url':'https://doi.org/'+d,'action':'Possible publication missing from selected list','identity':'ORCID record name verified; review work','source':'ORCID'})
    # Search public arXiv author metadata, then verify the full author name.
    u='https://export.arxiv.org/api/query?'+urlencode({'search_query':'au:"Mauro_Bernardi"','start':0,'max_results':50,'sortBy':'submittedDate','sortOrder':'descending'})
    response=fetch.get(u,'application/atom+xml');sources.append({'source':'arXiv','status':response['status']})
    if response['ok']:
        sys.path.insert(0,str(ROOT/'reading-list'))
        from library import parse_atom
        try:
            records,_=parse_atom(response['body'],now())
            for w in records:
                if not re.search(r'\bmauro bernardi\b',norm(w['authors'])):continue
                if any(w['id'] in x.get('paper_url','') or SequenceMatcher(None,norm(w['title']),norm(x['title'])).ratio()>.9 for x in known):continue
                candidates.append({'title':w['title'],'url':w['url'],'doi':'','action':'Possible preprint missing from selected list','identity':'Full author-name match; verify identity','source':'arXiv'})
        except ValueError:sources.append({'source':'arXiv parsing','status':'invalid-response'})
    # De-duplicate candidates, preserving the provenance of each source.
    merged={}
    for c in candidates:
        key=c['doi'] or norm(c['title'])
        if key in merged:merged[key]['source']+='; '+c['source']
        else:merged[key]=c
    return {'title':'Publication update proposals','sources':sources,'candidates':list(merged.values()),'notice':'Suggestions only. No publication data were changed. A selected list need not include every detected work; name matches require human identity review.'}

class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.ids=set();self.rows=[];self.row=None;self.cell=None
    def handle_starttag(self,t,a):
        a=dict(a)
        if a.get('id'):self.ids.add(a['id'])
        if t in ('a','link','script','img'):
            value=a.get('href') if t in ('a','link') else a.get('src')
            if value:self.links.append(value)
        if t=='tr':self.row=[]
        if t in ('td','th'):self.cell=[]
    def handle_data(self,d):
        if self.cell is not None:self.cell.append(d)
    def handle_endtag(self,t):
        if t in ('td','th') and self.cell is not None:
            if self.row is not None:self.row.append(' '.join(' '.join(self.cell).split()))
            self.cell=None
        if t=='tr' and self.row is not None:self.rows.append(self.row);self.row=None

def check_remote(url,fetch):
    r=fetch.get(url,'*/*',method='HEAD')
    if r['status'] in (405,501):r=fetch.get(url,'*/*',limit=2*1024*1024)
    state='ok' if r['ok'] else ('broken' if r['status'] in (404,410) else ('restricted-or-rate-limited' if r['status'] in (401,403,429) else 'unverified'))
    return {'url':url,'state':state,'status':r['status']}

def links(cfg,fetch):
    root=ROOT/'docs';pages={};problems=[];external=set();local_count=0
    for p in root.rglob('*.html'):
        parser=Links();parser.feed(p.read_text(encoding='utf-8'));pages[p.resolve()]=parser
    for p,parser in pages.items():
        for href in parser.links:
            u=urlsplit(href)
            if u.scheme in ('mailto','tel','data'):continue
            if u.scheme in ('http','https') or href.startswith('//'):
                external.add(('https:'+href) if href.startswith('//') else href.split('#')[0]);continue
            if u.scheme:problems.append({'page':str(p.relative_to(root.resolve())),'link':href,'problem':'Unsupported URL scheme'});continue
            target=(p.parent/unquote(u.path)).resolve() if u.path else p;local_count+=1
            issue=''
            if not target.is_relative_to(root.resolve()):issue='Link escapes the public site'
            elif not target.exists():issue='Missing local target'
            elif u.fragment and target in pages and unquote(u.fragment) not in pages[target].ids:issue='Missing anchor'
            if issue:problems.append({'page':str(p.relative_to(root.resolve())),'link':href,'problem':issue})
    if not (root/'index.html').exists():problems.append({'page':'index.html','problem':'Homepage missing'})
    chosen=sorted(external)[:cfg['maximum_external_links']]
    with ThreadPoolExecutor(max_workers=4) as pool:remote=list(pool.map(lambda u:check_remote(u,fetch),chosen))
    large=[{'file':str(p.relative_to(root)),'MiB':round(p.stat().st_size/1024**2,2)} for p in root.rglob('*') if p.is_file() and p.stat().st_size>25*1024**2]
    return {'title':'Website and thesis link audit','local_targets_checked':local_count,'local_problems':problems,'external':remote,'external_not_checked':max(0,len(external)-len(chosen)),'browser_upload_over_25_MiB':large,'notice':'403/429, timeouts and access restrictions are not classified as broken links. External checks are bounded and may be blocked by publishers.'}

def cran_packages(raw):
    data={}
    for block in gzip.decompress(raw).decode('utf-8').split('\n\n'):
        vals=dict(re.findall(r'^([^ :]+): (.*)$',block,re.M))
        if vals.get('Package'):data[vals['Package']]=vals
    return data

def packages(cfg,fetch):
    rows=csv_rows(ROOT/'data/software.csv');index=fetch.get('https://cran.r-project.org/src/contrib/PACKAGES.gz','application/gzip');cran={}
    if index['ok']:
        try:cran=cran_packages(index['body'])
        except (ValueError,OSError,EOFError):index={'status':'invalid-index'}
    result=[]
    for row in rows:
        item={'name':row['name'],'guide':check_remote(row['guide_url'],fetch) if row.get('guide_url') else None}
        if row.get('cran_url'):
            item['cran_index_status']=index['status'];item['cran_version']=cran.get(row['name'],{}).get('Version')
            url='https://cran.r-project.org/web/checks/check_results_'+quote(row['name'])+'.html';r=fetch.get(url,'text/html');item['cran_checks']={'url':url,'status':r['status']}
            if r['ok']:
                parser=Links();parser.feed(r['body'].decode('utf-8',errors='replace'))
                # Only exact status table cells count, never words in surrounding explanations.
                item['cran_checks']['status_cells']={name:sum(cell==name for cells in parser.rows for cell in cells) for name in ('OK','NOTE','WARN','WARNING','ERROR','FAIL')}
        repo_url=row.get('code_url') or row.get('repository_url','');m=re.match(r'https://github.com/([^/]+/[^/#?]+)/*$',repo_url)
        if m:
            repo=m[1];item['repository']=repo
            for endpoint,key in [('releases/latest','latest_release'),('actions/runs?per_page=5','recent_workflows'),('issues?state=open&per_page=20','open_issues')]:
                data,r=fetch.json('https://api.github.com/repos/'+repo+'/'+endpoint)
                entry={'status':r['status']}
                if key=='latest_release' and data:entry.update(tag=data.get('tag_name'),url=data.get('html_url'),published=data.get('published_at'))
                elif key=='recent_workflows' and data:entry['runs']=[{'name':x['name'],'status':x['status'],'conclusion':x.get('conclusion'),'url':x['html_url']} for x in data.get('workflow_runs',[])]
                elif key=='open_issues' and isinstance(data,list):entry['issues']=[{'title':x['title'],'url':x['html_url'],'updated':x['updated_at']} for x in data if 'pull_request' not in x]
                if r['status']==404:entry['notice']='No release/workflow data available, or resource inaccessible; this does not establish a package failure.'
                item[key]=entry
        else:item['repository_notice']='No source repository configured; no repository was guessed from the package name.'
        result.append(item)
    return {'title':'R package and software monitoring','packages':result,'notice':'Only public metadata are inspected. This does not run R CMD check or validate package calculations. Issues and workflow results are bounded recent samples; missing CRAN records do not imply an error for development packages.'}

def recent_papers(cfg):
    config=read_json(ROOT/'reading-list/preferences.json');state=read_json(ROOT/'reading-list/data/papers.json');cut=now()-timedelta(days=7)
    rows=[]
    for p in state.get('papers',[]):
        first=date(p.get('first_seen'));score=p.get('ranking',{}).get('score',0)
        if first and cut<=first<=now() and score>=config.get('minimum_score',4):rows.append(p)
    rows.sort(key=lambda p:(-p['ranking']['score'],p['id']))
    return rows[:cfg['digest_limit']],state.get('status',{})

def abstract_excerpt(text,maximum_words=65):
    # An explicitly labelled extract, never presented as a generated critical summary.
    sentences=re.split(r'(?<=[.!?])\s+',text.strip());chosen=[];count=0
    for sentence in sentences:
        n=len(sentence.split())
        if chosen and count+n>maximum_words:break
        chosen.append(sentence);count+=n
        if len(chosen)==2:break
    if count>maximum_words:return ' '.join(text.split()[:maximum_words])+' …'
    return ' '.join(chosen)

def digest(cfg,fetch):
    papers,status=recent_papers(cfg);groups={}
    for p in papers:
        topics=p.get('ranking',{}).get('topics') or ['Other relevant methods']
        # A paper can appear in several groups; the unique total below does not double-count it.
        for topic in topics:groups.setdefault(topic,[]).append({'title':p['title'],'url':p['url'],'authors':p['authors'],'score':p['ranking']['score'],'abstract':p['abstract'],'basis':'Title/abstract metadata; not a full-text review','abstract_excerpt':abstract_excerpt(p['abstract'])})
    return {'title':'Weekly literature digest','window_days':7,'unique_papers':len(papers),'source_last_success':status.get('last_success'),'groups':groups,'notice':'A thematic, metadata-based digest, not a critical review. Abstracts are explicitly attributed to their authors. Selection is bounded by the configured digest limit.'}

def notes(cfg,fetch,analyze=False):
    if os.getenv('GITHUB_ACTIONS'):return {'title':'Private reading notes','status':'local-only','notice':'Private note generation is never executed or uploaded by the public maintenance workflow.'}
    papers,_=recent_papers(cfg);papers=papers[:cfg['notes_per_run']];out=ROOT/'private-notes/automation/reading-notes';out.mkdir(parents=True,exist_ok=True);results=[]
    jobs_path=out/'jobs.json';jobs=read_json(jobs_path)
    for p in papers:
        slug=re.sub(r'[^a-zA-Z0-9._-]','-',p['id']);target=out/(slug+'.md')
        text='# Reading worksheet: '+p['title']+'\n\nSource: '+p['url']+'\n\nAuthors: '+p['authors']+'\n\n**Preparation only — no full-text analysis has been generated.**\n\n## Author abstract\n\n> '+p['abstract'].replace('\n','\n> ')+'\n\n'
        for section in ['Problem and contribution','Model and assumptions','Theoretical results and proof structure','Algorithms: objective, scaling and convergence','Experiments and reproducibility','Limitations and unanswered questions','Connections to my research','Questions for discussion']:text+='## '+section+'\n\nTo complete after reading the paper; cite PDF pages.\n\n'
        if not target.exists():target.write_text(text,encoding='utf-8')
        item={'title':p['title'],'url':p['url'],'worksheet':str(target.relative_to(ROOT)),'status':'worksheet-prepared'}
        completed=jobs.get(p['id'],{})
        requested_model=os.getenv('CRITICAL_NOTES_MODEL') or os.getenv('READING_LLM_MODEL','')
        reusable=completed.get('status')=='critical-draft-generated' and completed.get('model')==requested_model
        prepared=completed.get('status')=='pdf-prepared-not-analyzed' and not analyze
        if reusable or prepared:
            item['status']=completed['status'];item['notice']='Existing output retained; no repeated model request.'
        elif fetch.network:
            command=[sys.executable,str(ROOT/'critical-notes/critic.py'),'--arxiv',p['id'],'--title',p['title']]
            has_key=bool(os.getenv('CRITICAL_NOTES_API_KEY') or os.getenv('NVIDIA_API_KEY'));has_model=bool(os.getenv('CRITICAL_NOTES_MODEL') or os.getenv('READING_LLM_MODEL'))
            if not (analyze and has_key and has_model):command+=['--prepare']
            run=subprocess.run(command,cwd=ROOT,capture_output=True,text=True,timeout=600)
            item['status']=('critical-draft-generated' if analyze and has_key and has_model else 'pdf-prepared-not-analyzed') if run.returncode==0 else 'preparation-unavailable'
            if run.returncode!=0:item['notice']='PDF preparation did not complete. Check pypdf availability, network access and extraction limits; no discussion was invented.'
        if item['status'] in ('critical-draft-generated','pdf-prepared-not-analyzed'):
            jobs[p['id']]={'status':item['status'],'model':requested_model,'at':stamp()}
        results.append(item)
    write_json(jobs_path,jobs)
    return {'title':'Private reading notes','papers':results,'notice':'Local-only worksheets and optional full-text drafts. --network prepares public arXiv PDFs; --analyze-notes additionally uses a configured model. No private manuscript is transmitted automatically.'}

def report_md(task,data):
    # Explicit structure, not raw JSON as the user-facing report.
    lines=['# '+data['title'],'',data.get('notice',''),'']
    if task=='publications':
        lines+=['## Source availability','']+[f"- {x['source']}: {x['status']}" for x in data['sources']]
        lines+=['','## Proposals for review','']
        for x in data['candidates']:lines += ['### '+x['title'],'',x['action']+'. '+x['identity']+'.','',x['url'],'','Source: '+x['source'],'']
        if not data['candidates']:lines+=['No new candidates were identified from the sources successfully checked. Unavailable sources have not been checked.']
    elif task=='links':
        lines += [f"Local targets checked: {data['local_targets_checked']}",'','## Local problems','']
        lines += ['- '+json.dumps(x,ensure_ascii=False) for x in data['local_problems']] or ['None.']
        lines += ['','## External links requiring attention','']
        lines += [f"- {x['state']} ({x['status']}): {x['url']}" for x in data['external'] if x['state']!='ok']
    elif task=='packages':
        for x in data['packages']:
            lines += ['## '+x['name'],'', 'CRAN version: '+str(x.get('cran_version','not configured or not checked')), '']
            if x.get('guide'):lines += ['Guide: '+str(x['guide']['state'])+' — '+x['guide']['url'],'']
            if x.get('cran_checks'):lines += ['CRAN checks: '+x['cran_checks']['url'],'Status cells: '+json.dumps(x['cran_checks'].get('status_cells',{})),'']
            if x.get('repository_notice'):lines += [x['repository_notice'],'']
            for key in ('latest_release','recent_workflows','open_issues'):
                entry=x.get(key)
                if entry:lines += [key.replace('_',' ').title()+': source status '+str(entry['status']),'']
            if x.get('latest_release',{}).get('tag'):lines += ['Latest release: '+x['latest_release']['tag']+' — '+str(x['latest_release'].get('url','')),'']
            for r in x.get('recent_workflows',{}).get('runs',[]):lines += [f"- Workflow {r['name']}: {r['status']} / {r['conclusion']} — {r['url']}"]
            for issue in x.get('open_issues',{}).get('issues',[]):lines += ['- Issue: '+issue['title']+' — '+issue['url']]
    elif task=='digest':
        lines += [f"Unique relevant papers: {data['unique_papers']}",'','Source last refreshed: '+str(data['source_last_success']),'']
        for group,papers in data['groups'].items():
            lines += ['## '+group,'']
            for p in papers:lines += ['### '+p['title'],'',p['authors'],'',p['url'],'',p['basis'],'','Excerpt from the authors’ abstract (not a generated review):','', '> '+p.get('abstract_excerpt',p['abstract']).replace('\n','\n> '),'']
    else:
        for p in data.get('papers',[]):lines += ['## '+p['title'],'',p['status'],'',p.get('worksheet',''),'']
    return '\n'.join(lines)+'\n'

def dashboard(output,results):
    body='<h1>Research maintenance</h1><p>Generated '+escape(stamp())+'. Reports are observations and proposals, not automatic changes to the website.</p>'
    for name,data in results.items():body+='<section><h2>'+escape(data['title'])+'</h2><p>'+escape(data.get('notice',''))+'</p><p><a href="'+name+'.md">Readable report</a> · <a href="'+name+'.json">Structured data</a></p><details><summary>Read report</summary><pre>'+escape(report_md(name,data))+'</pre></details></section>'
    html='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Research maintenance</title><style>body{max-width:80ch;margin:3rem auto;padding:0 1.4rem;background:#f7f3e8;color:#29292e;font:18px/1.7 system-ui}h1,h2{font-family:Georgia,serif}a,summary{color:#a71930}section{border-top:1px solid #ddd6c7;padding:1rem 0}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:inherit;font-size:.9rem}summary{cursor:pointer}</style>'+body+'</html>'
    (output/'index.html').write_text(html,encoding='utf-8')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--tasks',default=','.join(TASKS));parser.add_argument('--network',action='store_true');parser.add_argument('--analyze-notes',action='store_true');parser.add_argument('--output',type=Path,default=ROOT/'private-notes/automation/reports');args=parser.parse_args()
    cfg=read_json(Path(__file__).with_name('config.json'));output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    selected=args.tasks.split(',')
    if any(t not in TASKS for t in selected):parser.error('Unknown task')
    if os.getenv('GITHUB_ACTIONS') and 'notes' in selected:parser.error('Private reading notes must run locally, not in the public workflow')
    if args.analyze_notes and not args.network:parser.error('--analyze-notes requires --network')
    fetch=Fetcher(args.network,cfg['request_timeout_seconds']);results={}
    for task in selected:
        try:data=notes(cfg,fetch,args.analyze_notes) if task=='notes' else globals()[task](cfg,fetch)
        except Exception as e:data={'title':task.title(),'notice':'Task did not complete: '+type(e).__name__+'. No source content was changed.','error':True}
        data['generated_at']=stamp();results[task]=data;write_json(output/(task+'.json'),data);(output/(task+'.md')).write_text(report_md(task,data) if not data.get('error') else data['notice'],encoding='utf-8')
    # A dated weekly snapshot is retained locally, without changing the live website.
    if 'digest' in results:
        week=now().strftime('%G-W%V');write_json(output/'weekly'/('digest-'+week+'.json'),results['digest'])
        (output/'weekly'/('digest-'+week+'.md')).write_text(report_md('digest',results['digest']),encoding='utf-8')
    dashboard(output,{k:v for k,v in results.items() if not v.get('error')})
    print('Reports ready:',output/'index.html')
    if any(x.get('error') for x in results.values()):return 1
    return 0

if __name__=='__main__':sys.exit(main())
