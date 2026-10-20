import unittest
from unittest.mock import patch
from moviepilot_exporter import validate_profile, fetch_ratings, ExportError

def page(items, total=1, pages=1):
    return dict(items=items, itemsCount=total, pagesCount=pages)

def item(slug="demo", rating=85):
    return dict(title="Demo", path="/movies/"+slug, rating=dict(value=rating), metaYearAndCountry="USA - 2024")

class DirectTests(unittest.TestCase):
    def test_links(self):
        for link in ["https://www.moviepilot.de/users/demo", "https://moviepilot.de/users/demo/rated/movies?page=2", "www.moviepilot.de/users/demo/rated/series/"]:
            self.assertEqual(validate_profile(link),"demo")
        for link in ["https://evil.de/users/demo", "https://moviepilot.de@evil.de/users/demo", "https://www.moviepilot.de/movies/demo"]:
            with self.assertRaises(ValueError): validate_profile(link)
    def test_pages_and_scores(self):
        with patch("moviepilot_exporter.time.sleep"):
            values=iter([page([item("a",85)],2,2),page([item("b",0)],2,2)])
            rows=fetch_ratings("demo","Film",lambda m:None,lambda u:next(values))
        self.assertEqual([r["Meine Bewertung"] for r in rows],[8.5,0])
    def test_reject_incomplete_duplicate_missing_private(self):
        for value in [page([],1),page([item(),item()],2),page([item(rating=None)]),dict(isPrivate=True),dict(items=[])]:
            with self.subTest(value=value), self.assertRaises(ExportError):
                fetch_ratings("demo","Film",lambda m:None,lambda u:value)
    def test_empty_list(self):
        self.assertEqual(fetch_ratings("demo","Film",lambda m:None,lambda u:page([],0,0)),[])
