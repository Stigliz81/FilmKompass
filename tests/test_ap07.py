import unittest
from catalog_view import rating_year_counts, PUBLIC_HEADERS

class RatingYears(unittest.TestCase):
    def test_exact_dates_only(self):
        rows=[{'rated_at':d,'year':'2040'} for d in ['1998-01-02','2026-10-19','01.02.1998','2026-02-30','',None,'2025','2027-01-01']]
        self.assertEqual(rating_year_counts(rows),([('1998',2),('2026',1),('2027',1)],4))
        self.assertEqual(PUBLIC_HEADERS[0],'Typ')
    def test_empty(self):
        self.assertEqual(rating_year_counts([]),([],0))
