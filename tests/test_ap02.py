"""Targeted AP02 regressions, fictitious temporary data only."""
import csv
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from manager_core import Catalog, HEADERS, read_export, sort_rows
from catalog_view import export_public, filter_rows, filter_values, PUBLIC_HEADERS

def source(path, rows):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=HEADERS,delimiter=';');wr.writeheader();wr.writerows(rows)

def record(slug='a', title='Erfundener Film', year='2005', score=7.5, typ='Film', dt='18.10.2026', genre='Thriller, Drama'):
    return {'Titel':title,'Erscheinungsjahr':year,'Meine Bewertung':score,'Typ':typ,'Moviepilot-URL':'https://www.moviepilot.de/'+('movies/' if typ=='Film' else 'serie/')+slug,'Bewertungsdatum':dt,'Genre':genre}

class AP02Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.db=Catalog(self.root/'manager.sqlite');self.src=self.root/'legacy.csv'
        self.records=[record(),record('b','Erfundene Serie','2006',0,'Serie'),record('c','Anderer Film','1999',10,dt='01.01.2025',genre='Science Fiction')]
        source(self.src,self.records);self.db.import_files([self.src])
    def tearDown(self): self.db.close();self.temp.cleanup()

    def test_compound_filters_actual_values_and_sort(self):
        rows=self.db.get_rows(); values=filter_values(rows)
        self.assertEqual(values['rating'],[0,7.5,10]);self.assertEqual(values['rated_month'],['01','10'])
        chosen={'year':{'2005','2006'},'rating':{0,7.5},'rated_year':{'2026'},'rated_month':{'10'},'genres':{'Thriller','Science Fiction'}}
        self.assertEqual(len(filter_rows(rows,chosen)),2)
        chosen['rating']={0};self.assertEqual(filter_rows(rows,chosen)[0]['media_type'],'Serie')
        chosen['rating']=set();self.assertEqual(len(filter_rows(rows,chosen)),2)
        self.assertEqual(len(filter_rows(rows,{k:set() for k in chosen})),3)
        self.assertEqual([r['rating'] for r in sort_rows(filter_rows(rows,chosen),'rating',True)],[7.5,0])
        self.assertEqual(len(self.db.get_rows(query='Anderer',media_type='Film')),1)

    def test_public_csv_xlsx_types_roundtrip_and_partial(self):
        url=self.db.get_rows()[0]['url'];self.db.save_personal(url,'Pausiert','S2','Geheime Testnotiz',True,True)
        self.db.save_season(url,2,8,True,'Staffelnotiz')
        for ext in ('.csv','.xlsx'):
            path=self.root/('public'+ext);export_public(path,self.db.get_rows(sort_by='rating'))
            data=read_export(path);self.assertEqual(len(data),3)
            result=self.db.import_files([path]);self.assertEqual(result['unchanged'],3);self.assertEqual(result['added'],0)
            self.assertEqual(self.db.get_row(url)['note'],'Geheime Testnotiz');self.assertEqual(len(self.db.seasons(url)),1)
            if ext=='.csv':
                with path.open(encoding='utf-8-sig') as f:self.assertEqual(tuple(next(csv.reader(f,delimiter=';'))),PUBLIC_HEADERS)
                self.assertNotIn('Geheime',path.read_text(encoding='utf-8-sig'))
            else:
                with zipfile.ZipFile(path) as z:
                    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    self.assertEqual(len(ET.fromstring(z.read('xl/workbook.xml')).find('m:sheets',ns)),1)
                    cells=ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
                    self.assertEqual(cells.find('.//m:c[@r="D2"]/m:v',ns).text,'0.0')
                    self.assertEqual(cells.find('.//m:c[@r="E2"]',ns).attrib['s'],'2')
        path=self.root/'subset.csv';export_public(path,self.db.get_rows()[:1]);self.db.import_files([path]);self.assertEqual(self.db.count(),3)

    def test_local_first_import_and_url_promotion(self):
        path=self.root/'plain.csv';rows=self.db.get_rows();export_public(path,rows)
        other=Catalog(self.root/'other.sqlite')
        try:
            self.assertEqual(other.import_files([path])['added'],3)
            self.assertEqual(other.import_files([path])['unchanged'],3)
            url=other.get_rows()[0]['url'];other.save_personal(url,'Gesehen','','Notiz',False,True)
            self.assertEqual(other.import_files([self.src])['added'],0)
            self.assertEqual(other.count(),3);self.assertTrue(all(r['url'].startswith('https:') for r in other.get_rows()))
            self.assertEqual(sum(r['note']=='Notiz' for r in other.get_rows()),1)
        finally:other.close()

    def test_ambiguous_titles_rollback_and_distinct_years(self):
        self.records.append(record('same','Erfundener Film','2005',8))
        source(self.src,self.records);self.db.import_files([self.src])
        path=self.root/'ambiguous.csv';export_public(path,[r for r in self.db.get_rows() if r['title']=='Erfundener Film'][:1])
        with self.assertRaisesRegex(ValueError,'uneindeutig'):self.db.import_files([path])
        self.assertEqual(self.db.count(),4)
        export_public(path,self.db.get_rows())
        with self.assertRaisesRegex(ValueError,'Mehrdeutiger'):read_export(path)
        self.records[-1]['Erscheinungsjahr']='2006';source(self.src,self.records);self.db.import_files([self.src])
        export_public(path,self.db.get_rows());self.assertEqual(self.db.import_files([path])['unchanged'],4)

    def test_followup_counts_missing_rating_and_preserved_data(self):
        self.assertEqual(self.db.import_files([self.src])['unchanged'],3)
        self.records[0]['Meine Bewertung']=8
        self.records.pop();self.records.append(record('new','Neuer erfundener Film','2020',6.5))
        source(self.src,self.records);r=self.db.import_files([self.src])
        self.assertEqual((r['added'],r['changed'],r['unchanged'],r['unavailable']),(1,1,1,1))
        self.assertEqual(self.db.count(),3)
        self.assertEqual(len(self.db.get_rows(hidden=True)),4)
        self.assertEqual(self.db.import_files([self.src])['unchanged'],3)

    def test_summary_boundaries_reset(self):
        summary=self.db.summary();self.assertEqual(sum(summary['rating_hist'].values()),3)
        self.assertEqual(summary['zeros'],1);self.assertEqual(summary['average'],8.75)
        self.assertEqual(summary['decades']['2000er'],2)
        self.db.reset_library();self.assertEqual(self.db.count(),0)

    def test_mixed_formats_cannot_bypass_completeness_guard(self):
        path=self.root/'public.csv';export_public(path,self.db.get_rows()[:1])
        with self.assertRaisesRegex(ValueError,'getrennt importieren'):self.db.import_files([path,self.src])
        self.assertEqual(self.db.count(),3)

if __name__=='__main__':unittest.main()
