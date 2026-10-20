"""Focused AP01 regressions. All data are fictitious and temporary."""
import csv
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from manager_core import Catalog, HEADERS, rating_date, display_date, sort_rows, read_export
from moviepilot_exporter import source_metadata, fetch_ratings, run_export, ExportError
from app_data import register_data_directory, managed_data_preview, delete_managed_data
from update_worker import update_library


def fake_item(slug="example", kind="Film", date="03.02.2024"):
    return dict(title="Erfundener Titel",path=("/movies/" if kind=="Film" else "/serie/")+slug,
                rating=dict(value=85,createdAt=date),dateOfRating=date,
                metaYearAndCountry="USA - 2020",metaInformation=['<span itemprop="genre">Drama</span>, <span itemprop="genre">Science-Fiction</span>'])


def fake_page(kind="Film"):
    return dict(itemsCount=1,pagesCount=1,items=[fake_item(kind=kind)])


def write_source(path, date="03.02.2024", genres="Drama, Science-Fiction"):
    record={"Titel":"Erfundene Serie","Erscheinungsjahr":"2020","Meine Bewertung":0,"Typ":"Serie",
            "Moviepilot-URL":"https://www.moviepilot.de/serie/erfundene-serie","Bewertungsdatum":date,"Genre":genres}
    with path.open("w",newline="",encoding="utf-8-sig") as handle:
        writer=csv.DictWriter(handle,fieldnames=HEADERS,delimiter=";");writer.writeheader();writer.writerow(record)


class AP01Tests(unittest.TestCase):
    def test_source_dates_genres_and_missing_dates(self):
        self.assertEqual(source_metadata(fake_item()),("2024-02-03","Drama, Science-Fiction"))
        item=fake_item(date="vor zwei Tagen")
        self.assertEqual(source_metadata(item)[0],"")
        item["rating"]["createdAt"]="31.01.2024"
        self.assertEqual(source_metadata(item)[0],"2024-01-31")
        self.assertEqual(rating_date("31.02.2024"),"")
        self.assertEqual(display_date("2024-02-03"),"03.02.2024")

    def test_sort_numeric_date_text_and_missing_last(self):
        rows=[dict(title="Zulu",year="2000",rating=8.5,rated_at="02.01.2024"),
              dict(title="Alpha",year="1999",rating=10,rated_at="2023-12-31"),
              dict(title="Beta",year="",rating=0,rated_at="")]
        self.assertEqual([r["rating"] for r in sort_rows(rows,"rating")],[0,8.5,10])
        self.assertEqual([r["year"] for r in sort_rows(rows,"year",True)],["2000","1999",""])
        self.assertEqual([r["title"] for r in sort_rows(rows,"rated_at")],["Alpha","Zulu","Beta"])
        self.assertEqual([r["title"] for r in sort_rows(rows,"rated_at",True)],["Zulu","Alpha","Beta"])
        self.assertEqual([r["title"] for r in sort_rows(rows,"title")],["Alpha","Beta","Zulu"])

    def test_migration_and_metadata_preservation_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"old.csv";write_source(source)
            db=Catalog(root/"manager.sqlite");db.import_files([source]);url=db.get_rows()[0]["url"]
            db.save_personal(url,"Pausiert","Staffel 2","Erfundene Notiz",False,True)
            db.save_season(url,1,"9,5",True,"Erfundene Staffel")
            db.con.execute("ALTER TABLE titles DROP COLUMN genres");db.con.commit();db.close()
            db=Catalog(root/"manager.sqlite")
            self.assertEqual(db.get_row(url)["note"],"Erfundene Notiz")
            self.assertEqual(db.get_row(url)["genres"],"")
            db.import_files([source])
            before=db.get_row(url)
            write_source(source,date="unbekannt",genres="")
            result=db.import_files([source])
            after=db.get_row(url)
            self.assertEqual(after["rated_at"],"2024-02-03")
            self.assertEqual(after["genres"],"Drama, Science-Fiction")
            self.assertEqual(after["imported_at"],before["imported_at"])
            self.assertEqual(result["changed"],0)
            self.assertEqual(after["rating"],0)
            self.assertEqual(db.seasons(url)[0]["rating"],9.5)
            csv_path=db.export_annotated_csv(root/"out.csv")
            xlsx=db.export_library_xlsx(root/"out.xlsx")
            for path in (csv_path,xlsx):
                value=read_export(path)[0]
                self.assertEqual((value["rated_at"],value["genres"],value["rating"]),("2024-02-03","Drama, Science-Fiction",0))
            self.assertEqual(db.get_rows(query="Erfundene",sort_by="rated_at")[0]["url"],url)
            db.close()

    def test_worker_progress_and_empty_or_failed_download_preserves_database(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);events=[];measure=[]
            with patch("moviepilot_exporter.fetch_page_props",side_effect=[fake_page(),fake_page("Serie")]):
                result=update_library("fictitious-profile",root,events.append,measure.append)
            self.assertEqual(result["imported"]["count"],2)
            self.assertEqual([m["kind"] for m in measure],["Film","Serie"])
            self.assertIn("Daten werden geprüft",events)
            db=Catalog(root/"manager.sqlite");db.close();before=(root/"manager.sqlite").read_bytes()
            with patch("moviepilot_exporter.fetch_page_props",return_value=dict(itemsCount=0,pagesCount=0,items=[])):
                result=update_library("fictitious-profile",root,events.append,measure.append)
            self.assertTrue(result["warnings"])
            self.assertEqual((root/"manager.sqlite").read_bytes(),before)
            with patch("moviepilot_exporter.fetch_page_props",side_effect=ExportError("test network error")):
                with self.assertRaises(ExportError):update_library("fictitious-profile",root,events.append,measure.append)
            self.assertEqual((root/"manager.sqlite").read_bytes(),before)

    def test_library_reset_keeps_settings_and_backups(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/"source.csv";write_source(source)
            db=Catalog(root/"manager.sqlite");db.import_files([source]);url=db.get_rows()[0]["url"]
            db.save_personal(url,"Gesehen","","Erfundene Notiz",True,True);db.save_season(url,1,8,True,"")
            settings=root/"settings.json";settings.write_text("{}")
            backup=db.backup();backup_bytes=backup.read_bytes()
            db.reset_library()
            for table in ("titles","personal","seasons","changes","import_runs"):
                self.assertEqual(db.con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],0)
            db.close();db=Catalog(root/"manager.sqlite");self.assertEqual(db.count(),0);db.close()
            self.assertEqual(settings.read_text(),"{}");self.assertEqual(backup.read_bytes(),backup_bytes)

    def test_full_reset_scoped_and_partial_failure_reported(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"app";root.mkdir();foreign=Path(temp)/"unrelated.txt";foreign.write_text("outside")
            with patch.dict(os.environ,{"MOVIEPILOT_MANAGER_DATA_DIR":str(root)}):
                register_data_directory(root)
                (root/"settings.json").write_text("{}")
                (root/"unknown.txt").write_text("inside foreign")
                (root/"exports").mkdir();(root/"exports/test.csv").write_text("app export")
                (root/"manager.sqlite-wal").write_text("sidecar")
                self.assertEqual(managed_data_preview(root)["files"],4)
                original_unlink=Path.unlink
                def locked(path,*args,**kwargs):
                    if path.name=="settings.json":raise PermissionError("locked fixture")
                    return original_unlink(path,*args,**kwargs)
                with patch.object(Path,"unlink",locked):
                    with self.assertRaises(OSError):delete_managed_data(root)
                self.assertTrue((root/"settings.json").exists())
                if os.name == "nt":
                    with (root/"settings.json").open("r"):
                        with self.assertRaises(OSError):delete_managed_data(root)
                result=delete_managed_data(root)
                self.assertEqual(result["foreign"],["unknown.txt"])
                self.assertEqual((root/"unknown.txt").read_text(),"inside foreign")
                self.assertEqual(foreign.read_text(),"outside")
                with self.assertRaises(ValueError):delete_managed_data(Path(temp))

    def test_full_reset_refuses_link(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"app";root.mkdir()
            with patch.dict(os.environ,{"MOVIEPILOT_MANAGER_DATA_DIR":str(root)}):
                register_data_directory(root)
                with patch.object(Path,"is_symlink",lambda p:p.name=="exports"):
                    (root/"exports").mkdir()
                    with self.assertRaises(ValueError):managed_data_preview(root)
