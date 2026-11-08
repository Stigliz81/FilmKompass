"""Focused tests with public factual fixtures captured 2026-11-07."""
import copy
import csv
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET
import zipfile
import moviepilot_lists as lists

FIXTURES=json.loads((Path(__file__).parent/'fixtures/ap1602_public_pages.json').read_text(encoding='utf-8'))

class AP1602Tests(unittest.TestCase):
    def test_real_pages_order_and_rating_scale(self):
        pages=iter([FIXTURES['best'],FIXTURES['best2']])
        with patch.object(lists,'CATALOG_LIMIT',50):
            snap=lists.download_list(lists.BASE+'/filme/beste',fetch=lambda _:next(pages),pause=lambda _:None)
        self.assertEqual(len(snap.entries),50)
        self.assertEqual((snap.entries[0]['title'],snap.entries[25]['title']),('Pulp Fiction','Matrix'))
        self.assertEqual(snap.entries[25]['position'],26)
        self.assertEqual(snap.entries[0]['year'],'1994')
        self.assertAlmostEqual(snap.entries[0]['community_rating'],8.44636)
        self.assertNotEqual(snap.entries[0]['community_rating'],FIXTURES['best']['results'][0]['averageCriticsRating']/10)
        self.assertIn('keine vollständige',snap.warnings[0])
        small=lists.download_list(lists.BASE+'/liste/demo',fetch=lambda _:FIXTURES['small'])
        self.assertEqual(small.entries[0]['title'],'Easy Rider')
        self.assertAlmostEqual(small.entries[0]['community_rating'],7.0301)

    def test_missing_invalid_hidden_values_and_cancel(self):
        for value in (None,'78',True,-1,101,float('nan'),float('inf')):
            self.assertIsNone(lists.community_rating(dict(averageCommunityRating=value,communityRatingsCount=3)))
        for extra in (dict(communityRatingsCount=0),dict(communityRatingsCount=3,hideRatings=True)):
            self.assertIsNone(lists.community_rating(dict(averageCommunityRating=78,**extra)))
        self.assertEqual(lists.community_rating(dict(averageCommunityRating=0,communityRatingsCount=3)),0)
        p=copy.deepcopy(FIXTURES['small']);p['listItems'][0]['itemData']['averageCommunityRating']=None
        self.assertIsNone(lists.download_list(lists.BASE+'/liste/demo',fetch=lambda _:p).entries[0]['community_rating'])
        with self.assertRaises(lists.ExportError):
            lists.download_list(lists.BASE+'/filme/beste',fetch=lambda _:self.fail('must not fetch'),cancelled=lambda:True)
        pages=iter([FIXTURES['best'],FIXTURES['best']])
        with self.assertRaises(lists.ExportError):
            lists.download_list(lists.BASE+'/filme/beste',fetch=lambda _:next(pages),pause=lambda _:None)

    def test_urls_and_synthetic_filtered_transport(self):
        for path in ('/filme/beste','/filme/beste/online-netflix','/filme/beste/genre-drama/jahr-2024'):
            self.assertEqual(lists.validate_list_url(lists.BASE+path+'?page=9'),lists.BASE+path)
        for path in ('/filme/neu','/filme/beste/../api','/filme/beste/%2fapi'):
            with self.assertRaises(lists.ExportError):lists.validate_list_url(lists.BASE+path)
        p=copy.deepcopy(FIXTURES['best']);p['total']=25;p['filters']=['online-netflix']
        snap=lists.download_list(lists.BASE+'/filme/beste/online-netflix',fetch=lambda _:p)
        self.assertEqual(len(snap.entries),25) # Not a live Netflix success.

    def test_matching_averages_zero_ambiguity_and_no_mutation(self):
        entries=[dict(position=i,media_type='Film',title=t,year='2024',url=lists.BASE+'/movies/'+str(i),community_rating=c)
                 for i,t,c in [(1,'Eindeutig',8),(2,'Normal: Titel',6),(3,'Doppelt',9),(4,'Fehlt',None),(5,'Ohne Note',7)]]
        library=[dict(title=t,media_type='Film',year='2024',url=u,rating=r) for t,u,r in [
            ('Anderer Name',entries[0]['url'],0),('Normal Titel','local:2',8),('Doppelt','local:3',7),
            ('Doppelt','local:4',9),('Ohne Note','local:5',None)]]
        before=copy.deepcopy(library);rows=lists.compare_list(entries,library);s=lists.list_summary(rows)
        self.assertEqual([r['library_status'] for r in rows],['Bereits bewertet','Bereits bewertet','Zuordnung unklar','Nicht in Bibliothek','Vorhanden ohne verlässliche Bewertung'])
        self.assertEqual(rows[0]['own_rating'],0)
        self.assertEqual((s['own_average'],s['community_average'],s['difference_average'],s['paired_count']),(4,7.5,-3,2))
        self.assertEqual(library,before)

    def test_storage_no_migration_and_numeric_exports(self):
        snap=lists.download_list(lists.BASE+'/liste/demo',fetch=lambda _:FIXTURES['small'])
        con=sqlite3.connect(':memory:');con.row_factory=sqlite3.Row;store=lists.ListStore(con)
        schema=[tuple(r) for r in con.execute('SELECT sql FROM sqlite_master ORDER BY name')]
        store.save(snap);rows=store.entries(snap.source_url)
        self.assertAlmostEqual(rows[0]['community_rating'],7.0301)
        self.assertEqual(schema,[tuple(r) for r in con.execute('SELECT sql FROM sqlite_master ORDER BY name')])
        con.execute("UPDATE movie_lists SET warnings='[]'")
        self.assertIsNone(store.entries(snap.source_url)[0]['community_rating'])
        rows[0].update(community_rating=5.5,own_rating=8.5,rating_difference=3.0,library_status='Bereits bewertet')
        with tempfile.TemporaryDirectory() as tmp:
            meta=dict(name=snap.name,source_url=snap.source_url)
            for ext in ('csv','xlsx'):lists.export_list(Path(tmp)/('test.'+ext),meta,rows)
            with (Path(tmp)/'test.csv').open(encoding='utf-8-sig',newline='') as f:data=list(csv.reader(f,delimiter=';'))
            self.assertEqual((data[1][8],data[1][10]),('5,5','8,5'))
            with zipfile.ZipFile(Path(tmp)/'test.xlsx') as z:sheet=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
            ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            for cell,value in (('I2','5.5'),('K2','8.5'),('L2','3.0')):
                c=sheet.find(f'.//m:c[@r="{cell}"]',ns);self.assertIsNone(c.get('t'));self.assertEqual(c.find('m:v',ns).text,value)
        con.close()
