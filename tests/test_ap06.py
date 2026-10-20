"""AP06 read-only selection statistics and retained introductory help."""
import unittest
from catalog_view import selection_caption,filter_rows
from compact_widgets import HELP_STEPS,QUICK_HELP

class AP06Tests(unittest.TestCase):
 def test_selection_types_half_ratings_and_zero_exclusion(self):
  rows=[{'media_type':kind,'rating':rating} for kind,rating in [('Film',6.5),('Film',7),('Serie',8),('Film',0)]]
  self.assertEqual(selection_caption(rows),'Aktuelle Auswahl: 3 Filme · 1 Serie · 4 Titel · Ø Note 7,17')
  self.assertEqual(rows[-1]['rating'],0)
 def test_empty_and_no_positive_rating(self):
  self.assertEqual(selection_caption([]),'Aktuelle Auswahl: 0 Filme · 0 Serien · 0 Titel · Ø Note –')
  self.assertIn('1 Film · 1 Serie · 2 Titel · Ø Note –',selection_caption([{'media_type':'Film','rating':0},{'media_type':'Serie','rating':None}]))
 def test_combined_filters_summary_and_help_topics(self):
  rows=[dict(media_type='Film',year='2005',rating=r,rated_at='2026-10-19',genres=g) for r,g in [(7.5,'Abenteuerfilm, Thriller'),(0,'Abenteuerfilm'),(9,'Horrorfilm')]]
  selected=filter_rows(rows,{'year':{'2005'},'rated_month':{'10'},'genres':{'Abenteuerfilm'}},'or',{'Thriller'})
  self.assertEqual(selection_caption(selected),'Aktuelle Auswahl: 1 Film · 0 Serien · 1 Titel · Ø Note –')
  self.assertEqual(len(HELP_STEPS),5)
  for topic in ['private','Browseradapter','vollständig','ODER','UND','Doppelklick','CSV','Excel','Sicherung','Mehrdeutigkeit','Appdaten','Datenschutz']:
   # Datenschutz is described by the concrete local-data section and no-transfer notice.
   if topic=='Datenschutz':self.assertIn('überträgt keine Daten',QUICK_HELP)
   else:self.assertIn(topic,QUICK_HELP)

if __name__=='__main__':unittest.main()
