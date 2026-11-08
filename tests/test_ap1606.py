"""Small reproducible cache/pacing regressions, isolated data and simulated APIs."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit
from fanart_covers import (CoverService, Credentials, FanartCache, CoverRequestGate,
    CoverCancelled, RemoteError, WikidataResolver, missing_covers)
from tests.test_fanart import entity, claim, image_bytes, poster

KEY='synthetic_project_key_123'

def rows(n):
    return [dict(url='local:'+str(i),title='QA '+str(i),year='2005',media_type='Film',imdb_id='tt0000001') for i in range(n)]

class AP1606Tests(unittest.TestCase):
    def test_checkpoints_and_progress_are_bounded_and_resume_ledger_is_saved(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp);request=Mock(side_effect=AssertionError('no API'))
            service=CoverService(cache,Credentials(KEY),request=request);data=rows(150);updates=[]
            value=missing_covers(service,data,{r['url'] for r in data},progress=updates.append)
            self.assertEqual(value['skipped'],150);self.assertLess(len(updates),10)
            loaded=FanartCache(tmp);self.assertEqual(len(loaded.data['batch_done']),150)
            value=missing_covers(CoverService(loaded,Credentials(KEY),request=request),data,set(),resume=True)
            self.assertEqual(value['skipped'],150);request.assert_not_called()

    def test_serial_gate_has_no_fixed_sleep_and_keeps_retry_after(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp,clock=lambda:1000);pause=Mock();request=Mock(side_effect=RemoteError(429,90))
            gate=CoverRequestGate(lambda:False,pause,interval=0,cache=cache)
            with self.assertRaises(RemoteError):gate.call(request,'url')
            self.assertEqual(cache.data['retry_until'],1090)
            with self.assertRaises(ValueError):gate.call(request,'url')
            self.assertEqual(request.call_count,1);pause.assert_not_called()

    def test_same_poster_across_titles_is_downloaded_only_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            request=Mock(return_value=dict(name='QA',movieposter=[poster()]))
            download=Mock(return_value=image_bytes('blue'));cache=FanartCache(tmp)
            result=missing_covers(CoverService(cache,Credentials(KEY),request=request,download=download),rows(3),set())
            self.assertEqual(result['found'],3);self.assertEqual(request.call_count,1);self.assertEqual(download.call_count,1)
            self.assertEqual(len(FanartCache(tmp).data['entries']),3)

    def test_cancel_flushes_without_losing_existing_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp);cancelled=[False]
            def request(*args):cancelled[0]=True;return dict(movieposter=[poster()])
            value=missing_covers(CoverService(cache,Credentials(KEY),request=request),rows(3),set(),cancelled=lambda:cancelled[0])
            self.assertTrue(value['cancelled']);self.assertFalse(cache._defer_saves)
            loaded=FanartCache(tmp);self.assertTrue(loaded.data['last_batch']['cancelled']);self.assertTrue(loaded.data['responses'])

    def test_wikidata_class_queries_are_reused_and_maxlag_is_sent(self):
        queries=[]
        def request(url,*args):
            q=parse_qs(urlsplit(url).query);queries.append(q)
            if q['action']==['wbsearchentities']:return {'search':[{'id':'Q1'}]}
            if q['ids']==['Q1']:return {'entities':{'Q1':entity(title='QA 0',kind='Q999')}}
            return {'entities':{'Q999':{'claims':{'P279':[claim({'id':'Q11424'})]}}}}
        resolver=WikidataResolver(request);r=rows(1)[0]
        self.assertEqual(len(resolver.candidates(r)),1);self.assertEqual(len(resolver.candidates(r)),1)
        self.assertEqual(sum(q.get('ids')==['Q999'] for q in queries),1)
        self.assertTrue(all(q['maxlag']==['5'] for q in queries))
