"""Browserlose Tests des Exportadapters mit künstlichen Moviepilot-ähnlichen Daten."""
import tempfile
from pathlib import Path
import unittest

from manager_core import read_export
from moviepilot_exporter import (
    ExportError, extract_rating, record_from_dom, write_moviepilot_csv, write_combined_xlsx,
    validate_profile, _scrape_type
)


def item(title,url,rating,year="2024"):
    return {"title":title,"url":url,"ratings":[rating],"year":year,"date":"18.10.2026","id":""}


class FakePage:
    def __init__(self, infos):self.infos=infos;self.position=0
    def goto(self,url,**kw): self.position = self.position if "page=2" not in url else 1
    def wait_for_timeout(self,ms):pass
    def evaluate(self,script):return self.infos[self.position]
    def content(self):return "<html></html>"
    def screenshot(self,**kw):pass


class ExporterTests(unittest.TestCase):
    def test_browser_empty_category(self):
        page=FakePage([{"expected":0,"rows":[],"nextHref":""}])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(_scrape_type(page,"demo-123","Serie",lambda m:None,Path(tmp)),[])

    def test_rating_value(self):
        self.assertEqual(extract_rating(["Meine Bewertung: 8,5 von 10"]),8.5)
        self.assertEqual(extract_rating(["Lieblingsfilm"]),10)
        self.assertEqual(extract_rating(["Totenkopf"]),0)
        with self.assertRaises(ExportError):extract_rating(["Bewertung unbekannt"])
        with self.assertRaises(ExportError):extract_rating(["Bewertung: 9 oder 10"])

    def test_profile_validation(self):
        self.assertEqual(validate_profile("demo-123"),"demo-123")
        for bad in ("", "../someone", "user/another", "a space", "http://example.com"):
            with self.assertRaises(ValueError):validate_profile(bad)

    def test_page_counts_and_navigation(self):
        u="https://www.moviepilot.de/movies/"
        page=FakePage([
            {"expected":3,"rows":[item("Beispiel A",u+"beispiel-a","9,5")],"nextHref":"https://www.moviepilot.de/users/demo-123/rated/movies?page=2"},
            {"expected":3,"rows":[item("Beispiel B",u+"beispiel-b","7"),item("Beispiel C",u+"beispiel-c","0")],"nextHref":""}
        ])
        with tempfile.TemporaryDirectory() as tmp:
            records=_scrape_type(page,"demo-123","Film",lambda msg:None,Path(tmp))
        self.assertEqual(len(records),3)
        self.assertEqual(records[-1]["Meine Bewertung"],0)

    def test_incomplete_export_aborts(self):
        u="https://www.moviepilot.de/movies/beispiel-a"
        page=FakePage([{"expected":5,"rows":[item("Beispiel A",u,"9,5")],"nextHref":""}])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ExportError,"nur 1 von 5"):
                _scrape_type(page,"demo-123","Film",lambda msg:None,Path(tmp))

    def test_xlsx_csv_numeric_roundtrip(self):
        a=record_from_dom(item("Fiktiver Film","https://www.moviepilot.de/movies/fiktiver-film","8,5"),"Film")
        b=record_from_dom(item("Fiktive Serie","https://www.moviepilot.de/serie/fiktive-serie","0"),"Serie")
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            write_moviepilot_csv(folder/"movie.csv",[a])
            write_combined_xlsx(folder/"movie.xlsx",[a],[b])
            parsed=read_export(folder/"movie.xlsx")
            self.assertEqual(len(parsed),2)
            self.assertEqual([x["rating"] for x in parsed],[8.5,0.0])
            self.assertEqual(read_export(folder/"movie.csv")[0]["rating"],8.5)


if __name__=="__main__":unittest.main()
