"""Explicit Fanart.tv requests and private cache; no catalog/database writes."""
from __future__ import annotations

from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
import hashlib
import json
import os
from pathlib import Path
import re
import time
import threading
from functools import wraps
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from app_info import APP_VERSION
from app_data import _not_link
from manager_core import normalized_title
from user_images import download_image, validate_image

DAY=86400
API='https://webservice.fanart.tv/v3.2/'
WIKIDATA='https://www.wikidata.org/w/api.php'
PROJECT_FILE='fanart.local.json'
USER_AGENT=f'FilmKompass/{APP_VERSION} (private cover lookup; https://github.com/Stigliz81/FilmKompass)'


class CoverError(ValueError):
    pass


class RemoteError(CoverError):
    def __init__(self,status,retry_after=0):
        super().__init__(f'HTTP {status}')
        self.status=status;self.retry_after=retry_after


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):
        raise CoverError('Unerwartete Weiterleitung; Anfrage beendet.')


def request_json(url,headers=None):
    parts=urlsplit(url)
    if parts.scheme!='https' or parts.hostname not in ('webservice.fanart.tv','www.wikidata.org'):
        raise CoverError('Nicht unterstützter API-Server.')
    request=Request(url,headers={'User-Agent':USER_AGENT,'Accept':'application/json',**(headers or {})})
    try:
        with build_opener(NoRedirect()).open(request,timeout=20) as response:
            raw=response.read(4*1024*1024+1)
            if len(raw)>4*1024*1024:raise CoverError('API-Antwort ist zu groß.')
        data=json.loads(raw)
        if not isinstance(data,dict):raise ValueError()
        return data
    except HTTPError as error:
        retry=error.headers.get('Retry-After','0') if error.headers else '0'
        try:retry=max(0,int(retry))
        except ValueError:
            try:retry=max(0,int(parsedate_to_datetime(retry).timestamp()-time.time()))
            except (TypeError,ValueError,OverflowError):retry=60
        error.close()
        raise RemoteError(error.code,retry) from None
    except (URLError,TimeoutError,ConnectionError,OSError):
        raise CoverError('Verbindung fehlgeschlagen. Bitte Internetverbindung prüfen.') from None
    except (ValueError,UnicodeError) as error:
        if isinstance(error,CoverError):raise
        raise CoverError('Die API-Antwort wurde nicht erkannt.') from None


def _key(value):
    value=value.strip() if isinstance(value,str) else ''
    if value and not re.fullmatch(r'[A-Za-z0-9_-]{16,128}',value):
        raise CoverError('API-Schlüssel hat ein ungültiges Format.')
    return value


def project_key(folder,environ=None):
    environ=os.environ if environ is None else environ
    if environ.get('FANART_TV_PROJECT_KEY'):
        return _key(environ['FANART_TV_PROJECT_KEY'])
    path=Path(folder)/PROJECT_FILE
    try:
        _not_link(path)
        if path.stat().st_size>4096:raise CoverError('Lokale API-Konfiguration ist ungültig.')
        return _key(json.loads(path.read_text(encoding='utf-8')).get('project_key',''))
    except FileNotFoundError:return ''
    except (OSError,ValueError,AttributeError):
        raise CoverError('Lokale API-Konfiguration konnte nicht gelesen werden.') from None


@dataclass(frozen=True)
class Credentials:
    project: str=field(repr=False)
    personal: str=field(default='',repr=False)

    def headers(self):
        project=_key(self.project)
        personal=_key(self.personal)
        if not project and not personal:
            raise CoverError('Fanart.tv einrichten: persönlichen API Key eintragen. Ohne Schlüssel bleiben Onlinecover deaktiviert.')
        return {**({'api-key':project} if project else {}),**({'client-key':personal} if personal else {})}


def external_id(source,value,media_type):
    value=str(value).strip()
    if media_type not in ('Film','Serie'):raise CoverError('Film-/Serientyp fehlt.')
    valid=(source=='imdb' and re.fullmatch(r'tt\d{7,10}',value)
        or source=='wikidata' and re.fullmatch(r'Q[1-9]\d*',value)
        or source in ('tmdb','tvdb') and re.fullmatch(r'[1-9]\d*',value))
    if not valid or media_type=='Film' and source=='tvdb':
        raise CoverError('Bitte eine gültige IMDb-, Wikidata-, TMDB- oder passende TVDB-ID eingeben.')
    return dict(source=source,value=value,media_type=media_type)


def existing_id(row):
    for key,source in (('imdb_id','imdb'),('tvdb_id','tvdb'),('tmdb_id','tmdb'),('wikidata_id','wikidata')):
        if row.get(key):
            try:return external_id(source,row[key],row['media_type'])
            except CoverError:continue
    return None


def poster_url(value):
    parts=urlsplit(value)
    if (parts.scheme!='https' or parts.hostname!='assets.fanart.tv' or parts.username or parts.password
            or parts.port not in (None,443) or parts.query or parts.fragment
            or not re.fullmatch(r'/fanart/[A-Za-z0-9_./%-]+\.(?:jpg|jpeg|png|webp)',parts.path,re.I)
            or '..' in parts.path.split('/')):
        raise CoverError('Ungültige Fanart.tv-Bildadresse.')
    return value


def _integer(value):
    try:return max(0,int(value))
    except (ValueError,TypeError,OverflowError):return 0


def ranked_posters(values):
    result=[];seen=set()
    for item in values[:300] if isinstance(values,list) else []:
        if not isinstance(item,dict):continue
        try:url=poster_url(str(item.get('url','')))
        except (ValueError,TypeError):continue
        if url in seen:continue
        seen.add(url)
        result.append(dict(url=url,id=str(item.get('id','')),lang=str(item.get('lang') or ''),
            likes=_integer(item.get('likes')),width=_integer(item.get('width')),height=_integer(item.get('height')),
            copyright=str(item.get('copyright') or 'Unknown')))
    return sorted(result,key=lambda p:({'de':0,'en':1,'00':2,'':2}.get(p['lang'],3),-p['likes'],-p['width']*p['height']))


class FanartClient:
    def __init__(self,credentials,request=request_json):
        self.credentials=credentials;self.request=request

    def posters(self,identity):
        identity=external_id(identity['source'],identity['value'],identity['media_type'])
        kind='movies' if identity['media_type']=='Film' else 'tv'
        # Numeric TV identifiers are always accompanied by an explicit source.
        url=API+kind+'/'+identity['value']+'?'+urlencode({'source':identity['source']})
        try:data=self.request(url,self.credentials.headers())
        except RemoteError as error:
            if error.status==401:raise CoverError('Fanart.tv: API-Schlüssel fehlt oder ist ungültig (HTTP 401).') from None
            if error.status==404:return '',[]
            if error.status==429:raise
            raise CoverError(f'Fanart.tv konnte nicht geladen werden (HTTP {error.status}).') from None
        field='movieposter' if kind=='movies' else 'tvposter'
        if field in data and not isinstance(data[field],list):raise CoverError('Posterformat wurde nicht erkannt.')
        return str(data.get('name') or ''),ranked_posters(data.get(field,[]))


def _claims(entity,prop):
    values=[]
    for claim in entity.get('claims',{}).get(prop,[]):
        if claim.get('rank')=='deprecated':continue
        value=claim.get('mainsnak',{}).get('datavalue',{}).get('value')
        if value is not None:values.append(value)
    return values


class WikidataResolver:
    """Two indexed title searches, batched entities, bounded subclass verification."""
    def __init__(self,request=request_json):self.request=request;self._class_parents={}

    def get(self,**params):
        try:
            result=self.request(WIKIDATA+'?'+urlencode({'format':'json','maxlag':5,**params}))
        except RemoteError as error:
            raise CoverError(f'Wikidata nicht erreichbar (HTTP {error.status}); manuelle ID möglich.') from None
        if 'error' in result:raise CoverError('Wikidata-Suche fehlgeschlagen; manuelle ID möglich.')
        return result

    def entities(self,ids):
        if not ids:return {}
        return self.get(action='wbgetentities',ids='|'.join(sorted(ids)),props='labels|aliases|claims',languages='de|en').get('entities',{})

    def candidates(self,row):
        if row.get('media_type') not in ('Film','Serie'):raise CoverError('Film-/Serientyp fehlt.')
        searches=[(row['title'],'de'),(row.get('original_title') or row['title'],'en')]
        ids=set()
        for title,language in searches:
            result=self.get(action='wbsearchentities',search=str(title)[:200],language=language,limit=5,type='item')
            ids.update(r['id'] for r in result.get('search',[]) if re.fullmatch(r'Q[1-9]\d*',r.get('id','')))
        entities=self.entities(ids)
        if len(self._class_parents)>512:self._class_parents.clear()
        parents=self._class_parents;roots={'Film':'Q11424','Serie':'Q5398426'}
        pending={v['id'] for e in entities.values() for v in _claims(e,'P31') if isinstance(v,dict) and 'id' in v}
        for _ in range(3):
            pending-=set(parents)|set(roots.values())
            if not pending or len(pending)>30:break
            classes=self.entities(pending)
            for q in pending:
                parents[q]={v['id'] for v in _claims(classes.get(q,{}),'P279') if isinstance(v,dict) and 'id' in v}
            pending={p for q in pending for p in parents.get(q,())}
        def is_type(entity,root):
            pending=[v['id'] for v in _claims(entity,'P31') if isinstance(v,dict) and 'id' in v];seen=set()
            while pending:
                q=pending.pop()
                if q==root:return True
                if q not in seen:seen.add(q);pending.extend(parents.get(q,()))
            return False
        wanted={normalized_title(str(row.get(k) or '')) for k in ('title','original_title')}- {''}
        candidates=[]
        for q,e in entities.items():
            labels=[v.get('value','') for v in e.get('labels',{}).values()]
            aliases=[v.get('value','') for values in e.get('aliases',{}).values() for v in values]
            titles=[v.get('text','') for v in _claims(e,'P1476') if isinstance(v,dict)]
            if not wanted & {normalized_title(t) for t in labels+aliases+titles}:continue
            if not is_type(e,roots[row['media_type']]):continue
            if is_type(e,roots['Serie' if row['media_type']=='Film' else 'Film']):continue
            years=[]
            for prop in ('P577','P580'):
                for value in _claims(e,prop):
                    if isinstance(value,dict) and _integer(value.get('precision'))>=9:
                        match=re.match(r'\+(\d{4})-',value.get('time',''))
                        if match:years.append(match[1])
            year=min(years) if years else ''
            candidates.append(dict(identity=external_id('wikidata',q,row['media_type']),
                title=e.get('labels',{}).get('de',e.get('labels',{}).get('en',{})).get('value',row['title']),
                year=year,exact_year=bool(year and str(row.get('year') or '')==year)))
        return candidates


def cache_locked(method):
    @wraps(method)
    def locked(self,*args,**kwargs):
        with self._lock:return method(self,*args,**kwargs)
    return locked


class FanartCache:
    def __init__(self,data_root,*,enabled=True,clock=time.time):
        self._lock=threading.RLock()
        self._defer_saves=False
        self.folder=Path(data_root)/'fanart-cache';self.enabled=enabled;self.clock=clock;self.reload()

    def path(self,name):
        if name not in ('index.json','index.tmp') and not re.fullmatch(r'[0-9a-f]{64}\.jpg',name):
            raise CoverError('Ungültiger Cachepfad.')
        path=self.folder/name
        for part in (path,self.folder,*self.folder.parents):_not_link(part)
        return path

    @cache_locked
    def reload(self):
        self.data=dict(version=1,entries={},responses={},identities={},retry_until=0)
        try:
            path=self.path('index.json')
            if path.stat().st_size>64*1024*1024:return
            data=json.loads(path.read_text(encoding='utf-8'))
            if data.get('version')==1 and isinstance(data.get('entries'),dict) and isinstance(data.get('responses'),dict):
                self.data=data
                if not isinstance(self.data.get('identities'),dict):self.data['identities']={}
        except (OSError,ValueError,AttributeError):pass

    @cache_locked
    def save(self,*,force=False):
        if self._defer_saves and not force:return
        temp=self.path('index.tmp');target=self.path('index.json');self.folder.mkdir(parents=True,exist_ok=True)
        temp.write_text(json.dumps(self.data,ensure_ascii=False),encoding='utf-8');temp.replace(target)

    @staticmethod
    def signature(row):return [str(row.get(k) or '') for k in ('title','year','media_type')]

    @cache_locked
    def entry(self,row):
        item=self.data['entries'].get(row['url'],{})
        return item if isinstance(item,dict) and item.get('signature')==self.signature(row) else {}

    @cache_locked
    def identity(self,row):
        saved=self.data['identities'].get(row['url'],{})
        if isinstance(saved,dict) and saved.get('signature')==self.signature(row):return saved.get('identity')
        return self.entry(row).get('identity')

    @cache_locked
    def remember_identity(self,row,identity):
        self.data['identities'][row['url']]=dict(signature=self.signature(row),identity=identity)
        self.save()

    @cache_locked
    def path_for(self,url):
        if not self.enabled:return None
        item=self.data['entries'].get(url,{})
        if not isinstance(item,dict):return None
        try:
            path=self.path(item.get('filename',''))
            return path if path.is_file() else None
        except (OSError,ValueError):return None

    def download(self,poster,download=download_image,*,large=False):
        url=poster_url(poster['url']).replace('/fanart/','/bigpreview/' if large else '/preview/',1)
        filename=hashlib.sha256(url.encode()).hexdigest()+'.jpg';path=self.path(filename)
        if path.is_file():
            try:
                if path.stat().st_size>10*1024*1024:raise ValueError()
                validate_image(path.read_bytes())
            except (OSError,ValueError):
                # Only an invalid, owned cache file is replaced; never a manual image.
                path.unlink(missing_ok=True)
        if not path.is_file():
            content=download(url)
            self.folder.mkdir(parents=True,exist_ok=True)
            with path.open('xb') as stream:stream.write(validate_image(content))
        return filename

    @cache_locked
    def assign(self,row,identity,poster,filename):
        external_id(identity['source'],identity['value'],row['media_type'])
        if not self.path(filename).is_file():raise CoverError('Cover ist nicht mehr im Cache.')
        self.data['entries'][row['url']]=dict(signature=self.signature(row),identity=identity,
            poster=poster,filename=filename,selected_at=self.clock())
        self.data['identities'][row['url']]=dict(signature=self.signature(row),identity=identity)
        self.save();self.cleanup()

    @cache_locked
    def cleanup(self):
        if self._defer_saves:return  # Do not collect an image another batch job may be assigning.
        if self.clock()-self.data.get('last_cleanup',0)<7*DAY:return
        referenced={r.get('filename') for r in self.data['entries'].values() if isinstance(r,dict)}
        removed=0
        for item in self.folder.glob('*.jpg'):
            if removed>=100:break
            if item.name in referenced:continue
            try:
                path=self.path(item.name)
                if self.clock()-path.stat().st_mtime>180*DAY:path.unlink();removed+=1
            except (OSError,ValueError):continue
        self.data['last_cleanup']=self.clock();self.save()


class CoverService:
    def __init__(self,cache,credentials,*,request=request_json,resolver=None,download=download_image):
        self.cache=cache;self.client=FanartClient(credentials,request);self.resolver=resolver or WikidataResolver(request)
        self.download=download

    def posters(self,identity,*,force=False):
        identity=external_id(identity['source'],identity['value'],identity['media_type'])
        key='|'.join(identity[k] for k in ('media_type','source','value'))
        old=self.cache.data['responses'].get(key)
        if (not isinstance(old,dict) or type(old.get('checked_at')) not in (int,float)
                or not isinstance(old.get('posters'),list)):old=None
        ttl=90*DAY if old and old.get('posters') else DAY
        if old and not force and self.cache.clock()-old['checked_at']<ttl:
            return dict(old,cached=True)
        wait=self.cache.data.get('retry_until',0)-self.cache.clock()
        if wait>0:raise CoverError(f'Fanart.tv begrenzt Anfragen. Bitte noch {int(wait)+1} Sekunden warten.')
        try:
            name,posters=self.client.posters(identity)
        except RemoteError as error:
            if error.status==429:
                wait=max(1,error.retry_after or 60)
                with self.cache._lock:self.cache.data['retry_until']=self.cache.clock()+wait;self.cache.save()
                raise CoverError(f'Fanart.tv: HTTP 429. Bitte {wait} Sekunden warten; kein automatischer Neuversuch.') from None
            raise
        except CoverError:
            if old and old.get('posters') and not force:return dict(old,cached=True,stale=True)
            raise
        value=dict(identity=identity,name=name,posters=posters,checked_at=self.cache.clock())
        with self.cache._lock:self.cache.data['responses'][key]=value;self.cache.save()
        return dict(value,cached=False)

    def lookup(self,row,identity=None):
        identity=identity or self.cache.identity(row) or existing_id(row)
        if identity is None:
            self.client.credentials.headers()
            candidates=self.resolver.candidates(row)
            exact=[c for c in candidates if c['exact_year']]
            if len(exact)!=1:return dict(stage='candidates',candidates=candidates)
            identity=exact[0]['identity']
            self.cache.remember_identity(row,identity)
        identity=external_id(identity['source'],identity['value'],row['media_type'])
        return dict(stage='posters',**self.posters(identity))

    def preview(self,poster):return self.cache.download(poster,self.download)

    def apply(self,row,identity,poster):
        filename=self.cache.download(poster,self.download,large=True);self.cache.assign(row,identity,poster,filename)
        return filename


class CoverCancelled(Exception):
    """Worker cancellation, deliberately not an offline/stale-cache fallback."""


class CoverRequestGate:
    """One serial pace for Wikidata, Fanart and CDN, with interruptible waits."""
    def __init__(self,cancelled,pause=time.sleep,clock=time.monotonic,interval=1.0,cache=None):
        self.cancelled=cancelled;self.pause=pause;self.clock=clock;self.interval=interval;self.last=None;self.cache=cache

    def call(self,request,*args):
        if self.cancelled():raise CoverCancelled()
        if self.cache and self.cache.data.get('retry_until',0)>self.cache.clock():
            raise CoverError('API-Wartezeit aktiv. Bitte später erneut starten.')
        if self.last is not None:
            wait=self.interval-(self.clock()-self.last)
            if wait>0:self.pause(wait)
        if self.cancelled():raise CoverCancelled()
        self.last=self.clock()
        try:return request(*args)
        except RemoteError as error:
            if error.status==429 and self.cache:
                self.cache.data['retry_until']=self.cache.clock()+max(1,error.retry_after or 60);self.cache.save()
            raise


def missing_covers(service,rows,manual_urls,*,cancelled=lambda:False,progress=lambda value:None,resume=False):
    """Batch checkpoints preserve state without serializing the index for every cache hit."""
    cache=service.cache;previous=cache._defer_saves;cache._defer_saves=True
    last=[0.0]
    def emit(value):
        now=time.monotonic()
        if value.get('active') or value['page']==value['expected'] or now-last[0]>=.2:
            last[0]=now;progress(value)
    try:
        return _missing_covers(service,rows,manual_urls,cancelled=cancelled,progress=emit,resume=resume)
    finally:
        cache._defer_saves=previous;cache.save(force=True)


def _missing_covers(service,rows,manual_urls,*,cancelled=lambda:False,progress=lambda value:None,resume=False):
    """Explicit batch over a read-only library snapshot; writes only existing cover cache."""
    service.client.credentials.headers()
    cache=service.cache
    result=dict(total=len(rows),checked=0,found=0,skipped=0,unclear=0,not_found=0,errors=0,
                cancelled=False,stopped=False,issues=[])
    misses=cache.data.setdefault('lookups',{})
    done=cache.data.setdefault('batch_done',{})
    checkpoint=time.monotonic()
    for row in rows:
        if cancelled():result['cancelled']=True;break
        outcome=None;reason=''
        try:
            stamp=done.get(row['url'],{})
            if row['url'] in manual_urls or cache.path_for(row['url']) or (resume and stamp.get('signature')==cache.signature(row) and 0<=cache.clock()-stamp.get('at',0)<DAY):
                outcome='skipped'
            else:
                old=misses.get(row['url'],{})
                known=cache.identity(row) or existing_id(row)
                if (not known and isinstance(old,dict) and old.get('signature')==cache.signature(row)
                        and old.get('outcome') in ('unclear','not_found')
                        and type(old.get('checked_at')) in (int,float) and 0<=cache.clock()-old['checked_at']<DAY):
                    outcome=old['outcome'];reason='Kurzzeitig gespeicherter Zuordnungstreffer'
                else:
                    progress(dict(kind='Cover',page=result['checked'],pages=max(1,result['total']),loaded=result['found'],expected=result['total'],title=row['title'],stats=dict(result),active=True))
                    value=service.lookup(row)
                    if cancelled():raise CoverCancelled()
                    if value['stage']=='candidates':
                        outcome='unclear' if value['candidates'] else 'not_found'
                        reason='Keine eindeutige Titel-/Jahr-Zuordnung' if value['candidates'] else 'Keine sichere Zuordnung gefunden'
                        misses[row['url']]=dict(signature=cache.signature(row),outcome=outcome,checked_at=cache.clock())
                        cache.save()
                    elif not value['posters']:
                        outcome='not_found';reason='Keine Poster bei Fanart.tv'
                    elif value.get('stale'):
                        # A failed refresh must not trigger downloads for the remaining library.
                        raise CoverError('Onlineabgleich nicht erreichbar; ältere Cacheantwort bleibt erhalten.')
                    else:
                        service.apply(row,value['identity'],value['posters'][0]);outcome='found'
        except CoverCancelled:
            result['cancelled']=True;break
        except (CoverError,OSError) as error:
            outcome='errors';reason=str(error);result['stopped']=True
        except Exception as error:
            outcome='errors';reason=f'Coverabgleich fehlgeschlagen ({type(error).__name__}).';result['stopped']=True
        result['checked']+=1;result[outcome]+=1
        if outcome!='errors':
            done[row['url']]=dict(signature=cache.signature(row),at=cache.clock())
        if outcome in ('found','errors') or result['checked']%25==0 or time.monotonic()-checkpoint>=1:
            cache.data['last_batch']=dict(result,remaining=result['total']-result['checked'])
            cache.save(force=True);checkpoint=time.monotonic()
        if reason and len(result['issues'])<200:
            result['issues'].append(dict(title=str(row['title']),reason=reason))
        progress(dict(kind='Cover',page=result['checked'],pages=max(1,result['total']),
                      loaded=result['found'],expected=result['total'],title=row['title'],stats=dict(result)))
        if result['stopped']:break
    result['remaining']=result['total']-result['checked']
    cache.data['last_batch']=result;cache.save()
    return result
