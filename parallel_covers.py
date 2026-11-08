"""Bounded cover-only concurrency; no SQLite or Tk calls in pool threads."""
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
import threading
import time
from urllib.parse import urlsplit
from fanart_covers import (CoverService, CoverError, CoverCancelled, RemoteError,
    WikidataResolver, external_id, existing_id, DAY)


class NetworkGate:
    """At most two cover requests total; Wikidata remains serial, other sources <=2."""
    def __init__(self,cache,cancelled):
        self.cache=cache;self.cancelled=cancelled;self.stopped=threading.Event()
        self.total=threading.BoundedSemaphore(2)
        self.sources={host:threading.BoundedSemaphore(n) for host,n in
                      [('www.wikidata.org',1),('webservice.fanart.tv',2),('assets.fanart.tv',2)]}

    def check(self):
        if self.cancelled() or self.stopped.is_set():raise CoverCancelled()
        with self.cache._lock:
            if self.cache.data.get('retry_until',0)>self.cache.clock():
                raise CoverError('API-Wartezeit aktiv. Bitte später fortsetzen.')

    def acquire(self,semaphore):
        while not semaphore.acquire(timeout=.05):self.check()

    def call(self,request,url,*args):
        self.check();source=self.sources.get(urlsplit(url).hostname)
        if source is None:raise CoverError('Nicht unterstützte Coverquelle.')
        self.acquire(source)
        try:
            self.check();self.acquire(self.total)
            try:
                self.check()
                try:
                    result=request(url,*args)
                    if isinstance(result,dict) and result.get('error'):
                        self.stopped.set();raise CoverError('Quelle meldet eine API-Sperre oder Serverlast. Bitte später prüfen.')
                    return result
                except RemoteError as error:
                    if error.status!=404:self.stopped.set()
                    if error.status==429:
                        with self.cache._lock:
                            self.cache.data['retry_until']=self.cache.clock()+max(1,error.retry_after or 60)
                            self.cache.save()
                    raise
            finally:self.total.release()
        finally:source.release()


class BatchResolver(WikidataResolver):
    def __init__(self,request):
        super().__init__(request);self.lock=threading.RLock();self.results={}

    def candidates(self,row):
        key=tuple(str(row.get(k) or '') for k in ('title','original_title','year','media_type'))
        with self.lock:
            if key not in self.results:
                if len(self.results)>=512:self.results.clear()
                self.results[key]=super().candidates(row)
            return self.results[key]


class ConcurrentCoverService(CoverService):
    def __init__(self,cache,credentials,*,request,download):
        super().__init__(cache,credentials,request=request,resolver=BatchResolver(request),download=download)
        self.lock=threading.Lock();self.locks={}

    def keyed(self,key):
        with self.lock:return self.locks.setdefault(key,threading.RLock())

    def posters(self,identity,*,force=False):
        identity=external_id(identity['source'],identity['value'],identity['media_type'])
        key=tuple(identity[k] for k in ('media_type','source','value'))
        with self.keyed(('id',key)):return super().posters(identity,force=force)

    def apply(self,row,identity,poster):
        with self.keyed(('image',poster['url'])):return super().apply(row,identity,poster)


def parallel_missing_covers(service,rows,manual_urls,*,gate,cancelled=lambda:False,
                            progress=lambda value:None,resume=False):
    """Two outstanding titles, one coordinator owns counters/checkpoints."""
    service.client.credentials.headers()
    unique={row['url']:row for row in rows};rows=list(unique.values());cache=service.cache
    result=dict(total=len(rows),checked=0,found=0,skipped=0,unclear=0,not_found=0,errors=0,
                cancelled=False,stopped=False,issues=[])
    with cache._lock:
        previous=cache._defer_saves;cache._defer_saves=True
        cache.data.setdefault('lookups',{});cache.data.setdefault('batch_done',{})

    def process(row):
        try:
            if cancelled() or gate.stopped.is_set():raise CoverCancelled()
            with cache._lock:
                stamp=cache.data['batch_done'].get(row['url'],{})
                if row['url'] in manual_urls or cache.path_for(row['url']) or (resume and stamp.get('signature')==cache.signature(row) and 0<=cache.clock()-stamp.get('at',0)<DAY):
                    return 'skipped',''
                old=cache.data['lookups'].get(row['url'],{})
                known=cache.identity(row) or existing_id(row)
                if (not known and old.get('signature')==cache.signature(row) and old.get('outcome') in ('unclear','not_found') and 0<=cache.clock()-old.get('checked_at',0)<DAY):
                    return old['outcome'],'Kurzzeitig gespeicherter Zuordnungstreffer'
            value=service.lookup(row)
            if cancelled() or gate.stopped.is_set():raise CoverCancelled()
            if value['stage']=='candidates':
                outcome='unclear' if value['candidates'] else 'not_found'
                with cache._lock:
                    cache.data['lookups'][row['url']]=dict(signature=cache.signature(row),outcome=outcome,checked_at=cache.clock())
                return outcome,'Keine eindeutige Titel-/Jahr-Zuordnung'
            if not value['posters']:return 'not_found','Keine Poster bei Fanart.tv'
            if value.get('stale'):raise CoverError('Onlineabgleich nicht erreichbar; ältere Cacheantwort erhalten.')
            service.apply(row,value['identity'],value['posters'][0]);return 'found',''
        except CoverCancelled:return None,''
        except (CoverError,OSError) as error:
            gate.stopped.set();return 'errors',str(error)
        except Exception as error:
            gate.stopped.set();return 'errors',f'Coverabgleich fehlgeschlagen ({type(error).__name__}).'

    pending={};index=0;last_emit=0;last_save=time.monotonic()
    def emit(force=False):
        nonlocal last_emit
        now=time.monotonic()
        if force or now-last_emit>=.2:
            last_emit=now
            progress(dict(kind='Cover',page=result['checked'],pages=max(1,result['total']),loaded=result['found'],
                          expected=result['total'],title=' · '.join(r['title'] for r in pending.values()),stats=dict(result)))
    try:
        with ThreadPoolExecutor(max_workers=2,thread_name_prefix='fanart-cover') as pool:
            while pending or index<len(rows):
                while len(pending)<2 and index<len(rows) and not cancelled() and not gate.stopped.is_set():
                    row=rows[index];index+=1;pending[pool.submit(process,row)]=row
                emit()
                if not pending:break
                completed,_=wait(pending,timeout=.05,return_when=FIRST_COMPLETED)
                for future in completed:
                    row=pending.pop(future);outcome,reason=future.result()
                    if outcome is None:continue
                    result['checked']+=1;result[outcome]+=1
                    if outcome=='errors':result['stopped']=True
                    if reason and len(result['issues'])<200:result['issues'].append(dict(title=row['title'],reason=reason))
                    with cache._lock:
                        if outcome!='errors':cache.data['batch_done'][row['url']]=dict(signature=cache.signature(row),at=cache.clock())
                        cache.data['last_batch']=dict(result,remaining=result['total']-result['checked'])
                        if outcome=='errors' or result['checked']%25==0 or time.monotonic()-last_save>=1:
                            cache.save(force=True);last_save=time.monotonic()
            result['cancelled']=bool(cancelled())
        result['remaining']=result['total']-result['checked']
        with cache._lock:cache.data['last_batch']=result
        emit(True);return result
    finally:
        with cache._lock:
            cache._defer_saves=previous;cache.save(force=True)
