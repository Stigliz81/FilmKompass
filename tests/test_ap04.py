"""AP04 filter rules and unchanged public exchange, using invented rows only."""
import csv,tempfile,unittest,zipfile
from pathlib import Path
from catalog_view import FILTER_LABELS,filter_rows,export_public,PUBLIC_HEADERS
from header_backdrop import BACKGROUNDS,background_choice

class AP04Tests(unittest.TestCase):
    def setUp(self):
        self.rows=[dict(url=str(i),media_type='Film',title=f'Fiktion {i}',year='2005',rating=rating,rated_at=dt,genres=g) for i,(g,rating,dt) in enumerate([('Abenteuerfilm, Actionfilm',7.5,'2026-10-18'),('Abenteuerfilm, Thriller, Schatzsucherfilm',0,'2025-10-17'),('Thriller, Horrorfilm',8,'2026-09-01'),('',7.5,'')])]
    def test_labels_and_exact_original_genres(self):
        self.assertEqual(list(FILTER_LABELS.values()),['Erscheinungsjahr','Meine Note','Bewertet im Jahr','Bewertet im Monat','Moviepilot Genre'])
        self.assertEqual(filter_rows(self.rows,{'genres':{'Abenteuer'}}),[])
        self.assertEqual(len(filter_rows(self.rows,{'genres':{'Abenteuerfilm'}})),2)
    def test_genre_or_and_exclusions_and_missing(self):
        chosen={'genres':{'Abenteuerfilm','Thriller'}}
        self.assertEqual(len(filter_rows(self.rows,chosen)),3)
        self.assertEqual([r['url'] for r in filter_rows(self.rows,chosen,'and')],['1'])
        self.assertEqual([r['url'] for r in filter_rows(self.rows,chosen,'or',{'Actionfilm','Horrorfilm'})],['1'])
        self.assertEqual([r['url'] for r in filter_rows(self.rows,{},'or',{'Actionfilm'})],['1','2','3'])
        self.assertEqual(filter_rows(self.rows,{},'and'),self.rows)
    def test_combined_dates_zero_and_half_ratings(self):
        chosen={'year':{'2005'},'rating':{0},'rated_month':{'10'},'genres':{'Abenteuerfilm'}}
        self.assertEqual([r['url'] for r in filter_rows(self.rows,chosen)],['1'])
        chosen['rated_year']={'2026'};self.assertEqual(filter_rows(self.rows,chosen),[])
        chosen['rating']={7.5};self.assertEqual([r['url'] for r in filter_rows(self.rows,chosen)],['0'])
    def test_filtered_exports_keep_six_columns_and_complete_genres(self):
        rows=filter_rows(self.rows,{'genres':{'Abenteuerfilm'}},'or',{'Actionfilm'})
        with tempfile.TemporaryDirectory() as tmp:
            csvpath=Path(tmp)/'data.csv';xlsx=Path(tmp)/'data.xlsx'
            export_public(csvpath,rows);export_public(xlsx,rows)
            with csvpath.open(encoding='utf-8-sig') as stream:data=list(csv.reader(stream,delimiter=';'))
            self.assertEqual(data[0],list(PUBLIC_HEADERS));self.assertEqual(data[1][5],self.rows[1]['genres']);self.assertEqual(len(data),2)
            with zipfile.ZipFile(xlsx) as z:
                self.assertEqual(len([n for n in z.namelist() if n.startswith('xl/worksheets/')]),1)
                xml=z.read('xl/worksheets/sheet1.xml').decode();self.assertIn(self.rows[1]['genres'],xml);self.assertIn('r="F2"',xml);self.assertNotIn('r="G2"',xml)
    def test_background_choices_and_old_setting_aliases(self):
        self.assertEqual(len(BACKGROUNDS),5)
        self.assertEqual(background_choice('Einfarbig'),'Ohne Hintergrundbild')
        self.assertEqual(background_choice('Kino · Blau & warmes Licht'),list(BACKGROUNDS)[-1])
        self.assertEqual(background_choice('missing'),'Ohne Hintergrundbild')
        for choice in BACKGROUNDS:self.assertEqual(background_choice(choice),choice)

if __name__=='__main__':unittest.main()
