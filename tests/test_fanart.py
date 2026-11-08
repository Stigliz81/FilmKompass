"""Focused Fanart boundaries; synthetic responses, no network or real keys."""
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from PIL import Image

from fanart_covers import (CoverError, CoverService, Credentials, FanartCache, FanartClient,
    RemoteError, WikidataResolver, DAY, external_id, project_key, ranked_posters)
from genre_art import ArtCache
from manager_core import Catalog
from package_release import check_public_path
from user_images import UserImages

KEY='synthetic_project_key_123'
PERSONAL='synthetic_personal_key_123'
FILM=dict(title='Testfilm',original_title='Original',year='2005',media_type='Film',url='https://www.moviepilot.de/movies/testfilm')
ID=external_id('imdb','tt0137523','Film')


def poster(lang='en',name='test',likes=1):
    return dict(id=name,url=f'https://assets.fanart.tv/fanart/{name}.jpg',lang=lang,likes=str(likes),width='1000',height='1500')


def image_bytes(color):
    stream=io.BytesIO();Image.new('RGB',(20,30),color).save(stream,'JPEG');return stream.getvalue()


def claim(value):return dict(mainsnak=dict(datavalue=dict(value=value)))


def entity(title='Testfilm',year='2005',kind='Q11424',aliases=()):
    return dict(labels=dict(de=dict(value=title)),aliases=dict(en=[dict(value=v) for v in aliases]),claims={
        'P31':[claim(dict(id=kind))],
        'P577':[claim(dict(time='+'+year+'-01-01T00:00:00Z',precision=9))]})


class FanartTests(unittest.TestCase):
    def test_local_key_environment_priority_redaction_and_payload_privacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            self.assertEqual(project_key(folder,environ={}), '')
            (folder/'fanart.local.json').write_text(json.dumps(dict(project_key=KEY)))
            self.assertEqual(project_key(folder,environ={}),KEY)
            self.assertEqual(project_key(folder,environ={'FANART_TV_PROJECT_KEY':PERSONAL}),PERSONAL)
            self.assertNotIn(KEY,repr(Credentials(KEY,PERSONAL)))
            self.assertNotIn(PERSONAL,repr(Credentials(KEY,PERSONAL)))
            self.assertEqual(Credentials(KEY,PERSONAL).headers(),{'api-key':KEY,'client-key':PERSONAL})
            with self.assertRaises(CoverError):Credentials('bad\nheader').headers()
        for name in ('fanart.local.json','_internal/fanart.local.json','fanart-cache/index.json','fanart-cache/cover.jpg'):
            with self.assertRaises(ValueError):check_public_path(name)
        check_public_path('fanart.local.example.json')

    def test_api_header_id_source_posters_and_language_order(self):
        calls=[]
        def request(url,headers):
            calls.append((url,headers))
            return dict(name='Test',movieposter=[poster('en','en',99),poster('de','de',1),poster('00','neutral'),dict(url='http://localhost/secret')],tvposter=[poster('de','tv')])
        client=FanartClient(Credentials(KEY,PERSONAL),request)
        name,values=client.posters(ID)
        self.assertEqual([v['id'] for v in values],['de','en','neutral'])
        client.posters(external_id('tmdb','1399','Serie'))
        self.assertEqual(urlsplit(calls[1][0]).path,'/v3.2/tv/1399')
        self.assertEqual(parse_qs(urlsplit(calls[1][0]).query),{'source':['tmdb']})
        self.assertNotIn(KEY,calls[0][0]);self.assertEqual(calls[0][1]['api-key'],KEY)
        with self.assertRaises(CoverError):external_id('tvdb','81189','Film')
        with self.assertRaises(CoverError):external_id('imdb','tt123/../../other','Film')
        self.assertEqual(ranked_posters([poster('en','same'),poster('en','same')])[0]['id'],'same')

    def test_http_401_404_429_and_retry_after_without_automatic_retry(self):
        request=Mock(side_effect=RemoteError(401))
        with self.assertRaisesRegex(CoverError,'401'):FanartClient(Credentials(KEY),request).posters(ID)
        self.assertEqual(request.call_count,1)
        self.assertEqual(FanartClient(Credentials(KEY),Mock(side_effect=RemoteError(404))).posters(ID),('',[]))
        with tempfile.TemporaryDirectory() as tmp:
            clock=[1000];cache=FanartCache(tmp,clock=lambda:clock[0]);request=Mock(side_effect=RemoteError(429,120))
            service=CoverService(cache,Credentials(KEY),request=request)
            with self.assertRaisesRegex(CoverError,'120'):service.posters(ID)
            with self.assertRaisesRegex(CoverError,'warten'):service.posters(ID)
            self.assertEqual(request.call_count,1)
            clock[0]+=121
            with self.assertRaises(CoverError):service.posters(ID)
            self.assertEqual(request.call_count,2)

    def test_positive_negative_cache_expiry_offline_and_optional_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            clock=[1000];cache=FanartCache(tmp,clock=lambda:clock[0])
            request=Mock(return_value=dict(name='Test',movieposter=[poster()]))
            resolver=Mock();service=CoverService(cache,Credentials(KEY),request=request,resolver=resolver,download=lambda _:image_bytes('blue'))
            value=service.lookup(FILM,ID);service.apply(FILM,ID,value['posters'][0])
            self.assertTrue(service.lookup(FILM)['cached']);self.assertEqual(request.call_count,1)
            clock[0]+=91*DAY;request.side_effect=CoverError('offline')
            self.assertTrue(service.lookup(FILM)['stale']);self.assertTrue(cache.path_for(FILM['url']).is_file())
            self.assertNotIn(KEY,json.dumps(cache.data));self.assertNotIn(PERSONAL,json.dumps(cache.data))
            cache.enabled=False;self.assertIsNone(cache.path_for(FILM['url']))
            other=external_id('imdb','tt7654321','Film');request.side_effect=RemoteError(404)
            self.assertEqual(service.posters(other)['posters'],[]);before=request.call_count
            self.assertTrue(service.posters(other)['cached']);self.assertEqual(request.call_count,before)
            clock[0]+=2*DAY;service.posters(other);self.assertEqual(request.call_count,before+1)
            service=CoverService(cache,Credentials(''),request=request,resolver=resolver)
            with self.assertRaises(CoverError):service.lookup(dict(FILM,url='different'))
            resolver.candidates.assert_not_called()

    def test_wikidata_title_original_year_type_and_ambiguous_selection(self):
        records={'Q1':entity(aliases=('Original',)), 'Q2':entity(year='2015'), 'Q3':entity(kind='Q5398426')}
        def request(url,headers=None):
            query=parse_qs(urlsplit(url).query)
            if query['action']==['wbsearchentities']:return {'search':[{'id':q} for q in records]}
            return {'entities':{q:records.get(q,{}) for q in query['ids'][0].split('|')}}
        candidates=WikidataResolver(request).candidates(FILM)
        self.assertEqual(len(candidates),2)
        self.assertEqual([c['identity']['value'] for c in candidates if c['exact_year']],['Q1'])
        with tempfile.TemporaryDirectory() as tmp:
            resolver=Mock();resolver.candidates.return_value=candidates
            service=CoverService(FanartCache(tmp),Credentials(KEY),resolver=resolver,
                request=Mock(return_value=dict(name='Test',movieposter=[poster()])))
            result=service.lookup(FILM);self.assertEqual(result['identity']['value'],'Q1')
            self.assertEqual(service.cache.identity(FILM)['value'],'Q1')
            other=dict(FILM,url='another');resolver.candidates.return_value=[candidates[0],dict(candidates[0],identity=external_id('wikidata','Q4','Film'))]
            self.assertEqual(service.lookup(other)['stage'],'candidates')
            self.assertIsNone(service.cache.identity(other))
        records['Q1']=entity(title='Original',kind='Q999',aliases=())
        records['Q999']={'claims':{'P279':[claim(dict(id='Q11424'))]}}
        self.assertTrue(any(c['identity']['value']=='Q1' for c in WikidataResolver(request).candidates(FILM)))

    def test_manual_images_win_and_catalog_schema_and_values_are_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=Catalog(root/'manager.sqlite')
            db.con.execute('INSERT INTO titles(url,title,year,rating,media_type,imported_at,modified_at) VALUES (?,?,?,?,?,?,?)',
                (FILM['url'],FILM['title'],FILM['year'],8.5,'Film','before','before'));db.con.commit()
            manual=UserImages(db);manual_path=manual.save(FILM['url'],image_bytes('red'))
            before=list(db.con.iterdump());manual_bytes=manual_path.read_bytes()
            cache=FanartCache(root);service=CoverService(cache,Credentials(KEY),download=lambda _:image_bytes('blue'))
            service.apply(FILM,ID,poster())
            art=ArtCache(root,manual,online_store=cache)
            with patch('genre_art.ImageTk.PhotoImage',side_effect=lambda im:im.copy()):
                image=art.get(FILM,(10,15));self.assertGreater(image.getpixel((0,0))[0],200)
            self.assertEqual(list(db.con.iterdump()),before);self.assertEqual(manual_path.read_bytes(),manual_bytes)
            self.assertTrue(cache.path_for(FILM['url']).is_file());db.close()

    def test_cache_links_corruption_and_scoped_orphan_cleanup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);cache=FanartCache(root,clock=lambda:200*DAY)
            cache.folder.mkdir();old=cache.path('a'*64+'.jpg');old.write_bytes(b'old');os.utime(old,(1,1))
            foreign=cache.folder/'unrelated.txt';foreign.write_text('keep')
            manual=root/'user-images';manual.mkdir();protected=manual/'keep.jpg';protected.write_bytes(b'keep')
            cache.cleanup();self.assertFalse(old.exists());self.assertTrue(foreign.exists());self.assertTrue(protected.exists())
            cache.data['entries'][FILM['url']]='broken';cache.save();cache.reload()
            self.assertIsNone(cache.path_for(FILM['url']));self.assertEqual(cache.entry(FILM),{})
            with patch('fanart_covers._not_link',side_effect=ValueError('link')):
                self.assertIsNone(cache.path_for(FILM['url']))
                with self.assertRaises(ValueError):cache.download(poster())
