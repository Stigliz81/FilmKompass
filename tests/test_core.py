"""Öffentliche Offline-Tests nur mit frei erfundenen Beispieldaten."""
import csv
import json
from pathlib import Path
import tempfile
import unittest

from manager_core import Catalog, read_export, compare_recommendations


FAKE = [
    {"Titel":"Beispiel: Rückkehr", "Erscheinungsjahr":"2001", "Meine Bewertung":"8,5", "Typ":"Film", "Moviepilot-URL":"https://www.moviepilot.de/movies/beispiel-rueckkehr", "Originaltitel":"", "Bewertungsdatum":"01.02.2024", "Status":"OK", "Moviepilot-ID":"11"},
    {"Titel":"Beispiel: Ablehnung", "Erscheinungsjahr":"2019", "Meine Bewertung":"0", "Typ":"Film", "Moviepilot-URL":"https://www.moviepilot.de/movies/beispiel-ablehnung", "Originaltitel":"", "Bewertungsdatum":"01.03.2024", "Status":"OK", "Moviepilot-ID":"12"},
    {"Titel":"Beispielserie", "Erscheinungsjahr":"2022", "Meine Bewertung":"7,5", "Typ":"Serie", "Moviepilot-URL":"https://www.moviepilot.de/serie/beispielserie", "Originaltitel":"", "Bewertungsdatum":"01.04.2024", "Status":"OK", "Moviepilot-ID":"13"},
]


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)
        self.db=Catalog(self.folder/"data.sqlite")
        self.addCleanup(self.db.close)
        self.path=self.folder/"source.csv"
        self.write_data()

    def write_data(self, items=FAKE):
        from manager_core import HEADERS
        with self.path.open("w",newline="",encoding="utf-8-sig") as f:
            wr=csv.DictWriter(f,fieldnames=HEADERS,delimiter=";")
            wr.writeheader();wr.writerows(items)

    def test_empty_database_initializes_without_seed(self):
        self.assertEqual(self.db.count(),0)
        self.assertEqual(self.db.summary()["total"],0)
        self.assertEqual(dict(self.db.summary()["count_by_type"]),{})

    def test_backups_are_not_automatically_deleted(self):
        folder=self.folder/"backup"
        folder.mkdir()
        old=folder/"MoviepilotManager_20000101_000000_000000.sqlite"
        old.write_bytes(b"existing backup must remain")
        for index in range(21):
            (folder/f"MoviepilotManager_20010101_000000_{index:06d}.sqlite").write_bytes(b"existing")
        self.db.backup()
        self.assertEqual(old.read_bytes(),b"existing backup must remain")
        self.assertEqual(len(list(folder.glob("*.sqlite"))),23)

    def test_import_and_zero_not_assumed_seen(self):
        out=self.db.import_files([self.path]);self.assertEqual(out["added"],3)
        self.assertEqual(self.db.summary()["zeros"],1)
        zero=self.db.get_row(FAKE[1]["Moviepilot-URL"])
        self.assertEqual(zero["watch_status"],"Nicht erfasst")

    def test_preserve_personal_data_on_reimport(self):
        self.db.import_files([self.path])
        url=FAKE[2]["Moviepilot-URL"]
        self.db.save_personal(url,"Pausiert","Staffel 2","Nicht mehr spannend",False,True)
        self.db.save_season(url,1,"9,5",True,"Gute erste Staffel")
        changed=[dict(x) for x in FAKE]
        changed[2]["Meine Bewertung"]="8,0"
        self.write_data(changed)
        result=self.db.import_files([self.path])
        self.assertEqual(result["changed"],1)
        self.assertEqual(self.db.get_row(url)["rating"],8)
        self.assertEqual(self.db.get_row(url)["note"],"Nicht mehr spannend")
        self.assertEqual(self.db.seasons(url)[0]["rating"],9.5)
        self.assertTrue(list((self.folder/"backup").glob("*.sqlite")))

    def test_browser_omitted_metadata_does_not_clear_existing_values(self):
        self.db.import_files([self.path])
        before=self.db.get_row(FAKE[0]["Moviepilot-URL"])
        incoming=[dict(x) for x in FAKE]
        incoming[0]["Moviepilot-ID"]=""
        incoming[0]["Bewertungsdatum"]=""
        incoming[0]["Erscheinungsjahr"]=""
        self.write_data(incoming)
        out=self.db.import_files([self.path])
        after=self.db.get_row(FAKE[0]["Moviepilot-URL"])
        self.assertEqual(out["changed"],0)
        self.assertEqual(before["moviepilot_id"],after["moviepilot_id"])
        self.assertEqual(before["rated_at"],after["rated_at"])
        self.assertEqual(before["year"],after["year"])

    def test_private_seed_only_imported_if_present_and_unset(self):
        self.db.import_files([self.path])
        p=self.folder/"private_seed.json"
        p.write_text(json.dumps([{"url":FAKE[2]["Moviepilot-URL"],"watch_status":"Komplett","progress":"3","note":"Privat"}]),encoding="utf-8")
        self.assertEqual(self.db.seed_private_notes(p),1)
        self.assertEqual(self.db.seed_private_notes(p),0)
        self.assertEqual(self.db.get_row(FAKE[2]["Moviepilot-URL"])["note"],"Privat")

    def test_invalid_rating_rejects_entire_file(self):
        failed=[dict(x) for x in FAKE]
        failed[1]["Meine Bewertung"]="8.5.2024"
        self.write_data(failed)
        with self.assertRaises(ValueError):self.db.import_files([self.path])
        self.assertEqual(self.db.count(),0)

    def test_compare_and_export(self):
        self.db.import_files([self.path])
        x=compare_recommendations("Beispiel: Rückkehr\nUnbekannt",self.db)
        self.assertEqual(x[0]["status"],"Schon bewertet")
        self.assertEqual(x[-1]["status"],"Nicht in der Liste")
        annotated=self.db.export_annotated_csv(self.folder/"annotated.csv")
        self.assertEqual(annotated.stat().st_size>100,True)
        self.assertEqual(len(read_export(self.path)),3)


if __name__=="__main__":unittest.main()
