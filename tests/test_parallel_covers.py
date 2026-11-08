"""Bounded concurrency, deduplication, cancellation and atomic private cache tests."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time
import tempfile
import unittest
from pathlib import Path
from fanart_covers import FanartCache, Credentials, RemoteError, CoverCancelled
from parallel_covers import NetworkGate, ConcurrentCoverService, parallel_missing_covers
from tests.test_fanart import image_bytes

KEY='synthetic_project_key_123'

def rows(n,same=False):
    return [dict(url='https://www.moviepilot.de/movies/qa'+str(i),title='QA '+str(i),year='2005',media_type='Film',imdb_id='tt'+str(1000000+(0 if same else i))) for i in range(n)]

class FakeNetwork:
    def __init__(self,delay=.01):
        self.lock=threading.Lock();self.active=0;self.peak=0;self.calls=0;self.images=0;self.delay=delay
    def begin(self):
        with self.lock:self.active+=1;self.peak=max(self.peak,self.active)
        time.sleep(self.delay)
    def end(self):
        with self.lock:self.active-=1
    def request(self,url,*args):
        self.begin()
        try:
            with self.lock:self.calls+=1
            name=url.split('/')[-1].split('?')[0]
            return dict(name='QA',movieposter=[dict(id=name,url='https://assets.fanart.tv/fanart/'+name+'.jpg',lang='de')])
        finally:self.end()
    def image(self,url):
        self.begin()
        try:
            with self.lock:self.images+=1
            return image_bytes('blue')
        finally:self.end()

def service(cache,network,cancelled=lambda:False):
    gate=NetworkGate(cache,cancelled)
    return gate,ConcurrentCoverService(cache,Credentials(KEY),request=lambda *a:gate.call(network.request,*a),download=lambda u:gate.call(network.image,u))

class ParallelCoverTests(unittest.TestCase):
    def test_api_error_body_stops_instead_of_marking_batch_completed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp);gate=NetworkGate(cache,lambda:False);calls=[]
            def error(*args):calls.append(1);return {'error':{'code':'maxlag'}}
            s=ConcurrentCoverService(cache,Credentials(KEY),request=lambda *a:gate.call(error,*a),download=lambda u:None)
            result=parallel_missing_covers(s,rows(8,same=True),set(),gate=gate)
            self.assertTrue(result['stopped']);self.assertGreater(result['errors'],0);self.assertEqual(len(calls),1)

    def test_batch_does_not_collect_unassigned_old_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp,clock=lambda:200*86400);cache.folder.mkdir()
            old=cache.path('a'*64+'.jpg');old.write_bytes(image_bytes('blue'))
            import os
            os.utime(old,(1,1));cache._defer_saves=True;cache.cleanup();self.assertTrue(old.exists())

    def test_two_jobs_and_correct_monotonic_counts_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp);network=FakeNetwork();gate,s=service(cache,network);events=[];data=rows(8)
            value=parallel_missing_covers(s,data,set(),gate=gate,progress=events.append)
            self.assertEqual((value['checked'],value['found'],value['errors']),(8,8,0));self.assertEqual(network.peak,2)
            self.assertEqual([v['page'] for v in events],sorted(v['page'] for v in events))
            self.assertEqual(events[-1]['page'],8);self.assertEqual(len(FanartCache(tmp).data['entries']),8)
            calls=network.calls,network.images;gate,s=service(FanartCache(tmp),network)
            value=parallel_missing_covers(s,data,set(),gate=gate,resume=True)
            self.assertEqual(value['skipped'],8);self.assertEqual(calls,(network.calls,network.images))

    def test_same_id_and_image_are_fetched_once_and_duplicate_rows_not_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            network=FakeNetwork();gate,s=service(FanartCache(tmp),network);data=rows(6,same=True)
            result=parallel_missing_covers(s,data+[data[0]],set(),gate=gate)
            self.assertEqual((result['total'],result['checked'],result['found']),(6,6,6))
            self.assertEqual((network.calls,network.images),(1,1))

    def test_cancel_drains_active_requests_and_can_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            network=FakeNetwork(.04);stop=threading.Event();cache=FanartCache(tmp);gate,s=service(cache,network,stop.is_set)
            timer=threading.Timer(.02,stop.set);timer.start()
            result=parallel_missing_covers(s,rows(8),set(),gate=gate,cancelled=stop.is_set);timer.join()
            self.assertTrue(result['cancelled']);self.assertLessEqual(network.calls,2);self.assertFalse(cache._defer_saves)
            self.assertTrue(FanartCache(tmp).data['last_batch']['cancelled'])
            gate,s=service(FanartCache(tmp),network)
            result=parallel_missing_covers(s,rows(8),set(),gate=gate,resume=True)
            self.assertEqual(result['checked'],8);self.assertEqual(result['remaining'],0)

    def test_retry_after_blocks_restart_without_network_retry(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp,clock=lambda:1000);gate=NetworkGate(cache,lambda:False);calls=[]
            def limited(*args):calls.append(1);raise RemoteError(429,90)
            s=ConcurrentCoverService(cache,Credentials(KEY),request=lambda *a:gate.call(limited,*a),download=lambda u:None)
            result=parallel_missing_covers(s,rows(8,same=True),set(),gate=gate)
            self.assertTrue(result['stopped']);self.assertEqual(len(calls),1);self.assertEqual(cache.data['retry_until'],1090)
            gate=NetworkGate(cache,lambda:False)
            s=ConcurrentCoverService(cache,Credentials(KEY),request=lambda *a:gate.call(limited,*a),download=lambda u:None)
            parallel_missing_covers(s,rows(8),set(),gate=gate)
            self.assertEqual(len(calls),1)

    def test_wikidata_gate_serializes_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            network=FakeNetwork();gate=NetworkGate(FanartCache(tmp),lambda:False)
            with ThreadPoolExecutor(max_workers=3) as pool:
                values=[pool.submit(gate.call,network.request,'https://www.wikidata.org/w/api.php?qa='+str(i)) for i in range(4)]
                for value in values:value.result()
            self.assertEqual(network.peak,1)

    def test_manual_rows_and_prior_metadata_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp);cache.data['custom']='preserve';network=FakeNetwork();gate,s=service(cache,network);data=rows(3)
            result=parallel_missing_covers(s,data,{r['url'] for r in data},gate=gate)
            self.assertEqual(result['skipped'],3);self.assertEqual(network.calls,0)
            self.assertEqual(FanartCache(tmp).data['custom'],'preserve')
