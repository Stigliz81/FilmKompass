import unittest
from urllib.parse import urlsplit,parse_qs
from catalog_view import filter_display_values,compact_filter_text
from moviepilot_manager import FEEDBACK_EMAIL,FEEDBACK_MAILTO

class FilterDisplay(unittest.TestCase):
    def test_values_and_month_names(self):
        self.assertEqual(filter_display_values('year',{'1967','1962'}),['1962','1967'])
        self.assertEqual(filter_display_values('year',{'unbekannt','1962'}),['1962','unbekannt'])
        self.assertEqual(filter_display_values('rating',{0,7.5,6}),['0','6','7,5'])
        self.assertEqual(filter_display_values('rated_year',{'2026','2025'}),['2025','2026'])
        self.assertEqual(filter_display_values('rated_month',{'10','01'}),['Januar','Oktober'])
    def test_genre_links_exclusions_and_source_unchanged(self):
        source={'Thriller','Abenteuerfilm'};excluded={'Actionfilm'}
        self.assertEqual(filter_display_values('genres',source,excluded,'and'),['UND: Abenteuerfilm','Thriller','ohne Actionfilm'])
        self.assertEqual(filter_display_values('genres',source,excluded)[0],'ODER: Abenteuerfilm')
        self.assertEqual(source,{'Thriller','Abenteuerfilm'})
        self.assertEqual(excluded,{'Actionfilm'})
        self.assertEqual(filter_display_values('genres',set(),excluded),['ohne Actionfilm'])
    def test_overflow_and_reset(self):
        values=['1962','1967','1970','1980','1990','2000','2010']
        self.assertEqual(compact_filter_text(values,len,35),'1962, 1967, 1970, 1980, +3 weitere')
        self.assertEqual(compact_filter_text(values,len,500),', '.join(values))
        for width in (1,8,20,35):
            text=compact_filter_text(values,len,width)
            self.assertLessEqual(len(text),width)
            self.assertNotIn('\n',text)
            self.assertTrue('weitere' in text or '…' in text)
        self.assertEqual(compact_filter_text([],len,100),'Alle')
    def test_feedback_mailto(self):
        parsed=urlsplit(FEEDBACK_MAILTO)
        self.assertEqual(parsed.scheme,'mailto')
        self.assertEqual(parsed.path,'stigliz1981@gmail.com')
        self.assertEqual(FEEDBACK_EMAIL,parsed.path)
        self.assertEqual(parse_qs(parsed.query),{'subject':['FilmKompass 1.0 – Feedback']})
