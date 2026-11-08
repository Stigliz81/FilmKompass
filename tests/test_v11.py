"""Focused 1.1 card, serial batch and private-data regressions; no network."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image

from thumbnail_view import CARD_SIZES, card_geometry
from genre_art import ArtCache
from fanart_covers import (CoverService, FanartCache, Credentials, RemoteError, CoverError,
    CoverCancelled, CoverRequestGate, missing_covers, external_id)
from manager_core import Catalog
from user_images import UserImages

KEY='synthetic_project_key_123'

def row(n,**values):
    return dict(title='Testfilm '+str(n),year='2005',media_type='Film',
                url='https://www.moviepilot.de/movies/test-'+str(n),rating=8.5,**values)

def image():
    stream=io.BytesIO();Image.new('RGB',(80,120),'blue').save(stream,'JPEG');return stream.getvalue()

def poster():
    return dict(url='https://assets.fanart.tv/fanart/test.jpg',lang='de',id='1',likes=1)

class Version11Tests(unittest.TestCase):
    def test_card_sizes_change_columns_and_whole_image_box_without_overflow(self):
        values=[card_geometry(name,1800,96/72) for name in CARD_SIZES]
        self.assertGreater(values[0][0],values[1][0]);self.assertGreater(values[1][0],values[2][0])
        self.assertLess(values[0][1][0],values[1][1][0]);self.assertLess(values[1][1][0],values[2][1][0])
        for width in (925,1291,1845):
            for scale in (96/72,2.0):
                for name in CARD_SIZES:
                    cols,size,wrap=card_geometry(name,width,scale)
                    self.assertLessEqual(size[0]+24,width//cols)
                    self.assertEqual(size[1],round(size[0]*1.5));self.assertLessEqual(wrap,width//cols-20)

    def test_full_manual_image_is_contained_and_legacy_list_crop_stays_available(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'image.png';im=Image.new('RGB',(300,100),'red')
            for x in range(10):
                for y in range(100):im.putpixel((x,y),(0,255,0))
            im.save(p);manual=Mock();manual.path_for.return_value=p
            art=ArtCache(Path(tmp),manual)
            with patch('genre_art.ImageTk.PhotoImage',side_effect=lambda im:im.copy()):
                result=art.get(row(1),(150,225),contain=True)
                self.assertEqual(result.size,(150,225));self.assertGreater(result.getpixel((2,112))[1],200)
                self.assertEqual(result.getpixel((75,0)),(16,27,37))
                cropped=art.get(row(1),(150,225));self.assertNotEqual(cropped.getpixel((75,0)),(16,27,37))

    def test_batch_mixed_outcomes_and_repeat_uses_existing_and_negative_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows=[row(i) for i in range(6)];rows[1]['imdb_id']='tt0000001';rows[5]['imdb_id']='tt0000005'
            cache=FanartCache(tmp);download=Mock(return_value=image())
            def request(url,headers):
                if 'tt0000005' in url:raise RemoteError(404)
                return dict(name='Test',movieposter=[poster()])
            request=Mock(side_effect=request);resolver=Mock()
            resolver.candidates.side_effect=lambda r: ([] if r['url']==rows[4]['url'] else
                [dict(identity=external_id('wikidata','Q123','Film'),exact_year=True)] if r['url']==rows[2]['url'] else
                [dict(identity=external_id('wikidata',q,'Film'),exact_year=True) for q in ('Q456','Q457')])
            service=CoverService(cache,Credentials(KEY),request=request,resolver=resolver,download=download)
            service.apply(rows[1],external_id('imdb','tt0000001','Film'),poster())
            result=missing_covers(service,rows,{rows[0]['url']})
            self.assertEqual([result[k] for k in ('checked','found','skipped','unclear','not_found','errors')],[6,1,2,1,2,0])
            counts=request.call_count,resolver.candidates.call_count,download.call_count
            result=missing_covers(service,rows,{rows[0]['url']})
            self.assertEqual(result['found'],0);self.assertEqual(result['skipped'],3)
            self.assertEqual(counts,(request.call_count,resolver.candidates.call_count,download.call_count))
            self.assertIn('/bigpreview/',download.call_args.args[0]);self.assertEqual(cache.data['last_batch'],result)

    def test_cancel_during_lookup_prevents_cover_assignment_and_next_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            cancelled=[False]
            def request(url,headers):cancelled[0]=True;return dict(movieposter=[poster()])
            service=CoverService(FanartCache(tmp),Credentials(KEY),request=request,download=Mock(side_effect=AssertionError('no download')))
            rows=[row(n,imdb_id='tt0000001') for n in range(3)]
            result=missing_covers(service,rows,set(),cancelled=lambda:cancelled[0])
            self.assertTrue(result['cancelled']);self.assertEqual(result['checked'],0)
            self.assertFalse(service.cache.data['entries']);self.assertEqual(result['remaining'],3)

    def test_rate_limit_stops_batch_and_respects_cooldown_on_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=FanartCache(tmp,clock=lambda:1000);request=Mock(side_effect=RemoteError(429,120))
            service=CoverService(cache,Credentials(KEY),request=request)
            rows=[row(n,imdb_id='tt0000001') for n in range(3)]
            result=missing_covers(service,rows,set())
            self.assertTrue(result['stopped']);self.assertEqual((result['errors'],result['remaining']),(1,2))
            missing_covers(service,rows,set());self.assertEqual(request.call_count,1)
            self.assertEqual(cache.data['retry_until'],1120)

    def test_no_key_and_offline_failure_do_not_start_unbounded_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            request=Mock(side_effect=CoverError('Offline'));resolver=Mock()
            service=CoverService(FanartCache(tmp),Credentials(''),request=request,resolver=resolver)
            with self.assertRaisesRegex(CoverError,'persönlichen API Key'):missing_covers(service,[row(1)],set())
            request.assert_not_called();resolver.candidates.assert_not_called()
            service.client.credentials=Credentials(KEY)
            result=missing_covers(service,[row(n,imdb_id='tt0000001') for n in range(3)],set())
            self.assertEqual(request.call_count,1);self.assertEqual(result['errors'],1)

    def test_pacing_is_shared_and_wait_is_cancellable(self):
        clock=[10];waits=[];cancelled=[False];request=Mock(return_value={})
        def pause(seconds):waits.append(seconds);clock[0]+=seconds
        gate=CoverRequestGate(lambda:cancelled[0],pause,lambda:clock[0])
        gate.call(request,'a');gate.call(request,'b');self.assertEqual(waits,[1.0])
        def cancel_pause(seconds):cancelled[0]=True
        gate.pause=cancel_pause
        with self.assertRaises(CoverCancelled):gate.call(request,'c')
        self.assertEqual(request.call_count,2)

    def test_manual_cover_and_all_sql_data_are_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=Catalog(root/'manager.sqlite');r=row(1)
            db.con.execute('INSERT INTO titles(url,title,year,rating,media_type,imported_at,modified_at) VALUES (?,?,?,?,?,?,?)',
                (r['url'],r['title'],r['year'],8.5,'Film','before','before'));db.con.commit()
            manual=UserImages(db);path=manual.save(r['url'],image());before=list(db.con.iterdump());content=path.read_bytes()
            service=CoverService(FanartCache(root),Credentials(KEY),request=Mock(side_effect=AssertionError('no API')))
            result=missing_covers(service,[r],{r['url']})
            self.assertEqual(result['skipped'],1);self.assertEqual(list(db.con.iterdump()),before)
            self.assertEqual(path.read_bytes(),content);db.close()
