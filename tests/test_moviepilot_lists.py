"""AP16.01: list completeness, transactional isolation, ordered public exports."""
import csv
from pathlib import Path
import tempfile
import sqlite3
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import xml.etree.ElementTree as ET
import zipfile

from manager_core import Catalog
from moviepilot_lists import (BASE, ExportError, ListStore, PublicList, download_list,
                             export_list, fetch_list_page, import_public_list, validate_list_url)


def item(number, kind='Movie'):
    return dict(itemId=1000 + number, itemType=kind, itemData=dict(
        id=number, title=f'Titel {number}', type=kind, productionYear='2024',
        path=f"/{'movies' if kind == 'Movie' else 'serie'}/titel-{number}"))


def page(items, total=None, number=1):
    return dict(public=True, id=123, title='Testliste', totalListItemCount=len(items) if total is None else total,
                page=number, itemsPerPage=25, editedAt='2026-11-07', permalink='demo', listItems=items)


class ListTests(unittest.TestCase):
    def test_urls_are_single_public_https_lists(self):
        self.assertEqual(validate_list_url('https://moviepilot.de/liste/demo/?page=3#x'), BASE + '/liste/demo')
        for url in ('http://www.moviepilot.de/liste/demo', 'https://evil.de/liste/demo',
                    'https://www.moviepilot.de@evil.de/liste/demo', 'https://www.moviepilot.de:444/liste/demo',
                    'https://www.moviepilot.de/lists/demo', 'https://www.moviepilot.de/liste/demo/comments/',
                    'https://www.moviepilot.de/liste/%2e%2e', 'https://www.moviepilot.de/liste/a/b'):
            with self.subTest(url=url), self.assertRaises(ExportError):
                validate_list_url(url)

    def test_multiple_pages_preserve_order_and_types(self):
        pages = iter([page([item(n) for n in range(1, 26)], 27),
                      page([item(26, 'Series'), item(27)], 27, 2)])
        snapshot = download_list(BASE + '/liste/demo', fetch=lambda url: next(pages), pause=lambda seconds: None)
        self.assertEqual([r['position'] for r in snapshot.entries], list(range(1, 28)))
        self.assertEqual(snapshot.entries[25]['media_type'], 'Serie')
        self.assertEqual(snapshot.entries[25]['moviepilot_id'], '26')
        self.assertEqual(snapshot.entries[25]['title'], 'Titel 26')

    def test_non_media_keep_source_positions_and_missing_year(self):
        movie = item(3)
        movie['itemData']['productionYear'] = None
        snapshot = download_list(BASE + '/liste/demo', fetch=lambda url: page([
            item(1), dict(itemId=1002, itemType='Person'), movie]), pause=lambda _: None)
        self.assertEqual([r['position'] for r in snapshot.entries], [1, 3])
        self.assertEqual(snapshot.skipped_count, 1)
        self.assertEqual(snapshot.entries[1]['year'], '')
        self.assertTrue(snapshot.warnings)

    def test_reject_incomplete_private_missing_repeated_changed_pages(self):
        bad_values = [dict(public=False), page([], 1), page([dict(itemId=1, itemType='Movie')]),
                      page([item(1), item(1)]), dict(page([item(1)]), itemsPerPage=50)]
        for props in bad_values:
            with self.subTest(props=props), self.assertRaises(ExportError):
                download_list(BASE + '/liste/demo', fetch=lambda url: props, pause=lambda _: None)
        for second in (page([item(1)], 26, 2), page([item(26)], 27, 2),
                       dict(page([item(26)], 26, 2), editedAt='changed')):
            responses = iter([page([item(n) for n in range(1, 26)], 26), second])
            with self.subTest(second=second), self.assertRaises(ExportError):
                download_list(BASE + '/liste/demo', fetch=lambda url: next(responses), pause=lambda _: None)

    def test_http_restrictions_are_not_retried(self):
        for code in (401, 403, 404, 429):
            with self.subTest(code=code), patch('moviepilot_lists.build_opener') as factory:
                factory.return_value.open.side_effect = HTTPError(BASE, code, 'blocked', {}, None)
                with self.assertRaises(ExportError):
                    fetch_list_page(BASE + '/liste/demo')
                self.assertEqual(factory.return_value.open.call_count, 1)

    def test_list_storage_reimport_rollback_and_rating_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Catalog(Path(tmp) / 'manager.sqlite')
            # Real rating/personal/season tables, including 0, remain byte-for-byte equal as rows.
            db.con.execute("INSERT INTO titles(url,title,rating,media_type,imported_at,modified_at) VALUES ('test','Persönlich',0,'Serie','old','old')")
            db.con.execute("INSERT INTO personal(url,note,modified_at) VALUES ('test','Behalten','old')")
            db.con.execute("INSERT INTO seasons(url,season,rating,note) VALUES ('test',1,8.5,'Behalten')")
            db.con.commit()
            tables = ('titles', 'personal', 'seasons', 'import_runs', 'changes', 'meta', 'user_images')
            before = {t: [tuple(r) for r in db.con.execute(f'SELECT * FROM {t}')] for t in tables}
            store = ListStore(db.con)
            snapshot = download_list(BASE + '/liste/demo', fetch=lambda _: page([item(1), item(2, 'Series')]))
            store.save(snapshot)
            store.save(snapshot)
            self.assertEqual(len(store.lists()), 1)
            self.assertEqual([r['position'] for r in store.entries(snapshot.source_url)], [1, 2])
            invalid = PublicList(snapshot.source_url, 123, 'Changed', 2,
                                 (snapshot.entries[0], snapshot.entries[0]), 0, ())
            with self.assertRaises(sqlite3.IntegrityError):
                store.save(invalid)
            self.assertEqual(store.lists()[0]['name'], 'Testliste')
            self.assertEqual(len(store.entries(snapshot.source_url)), 2)
            with patch('moviepilot_lists.download_list', side_effect=ExportError('network')):
                with self.assertRaises(ExportError):
                    import_public_list(snapshot.source_url, db.db_path)
            self.assertEqual(len(store.entries(snapshot.source_url)), 2)
            store.delete(snapshot.source_url)
            self.assertEqual(store.lists(), [])
            after = {t: [tuple(r) for r in db.con.execute(f'SELECT * FROM {t}')] for t in tables}
            self.assertEqual(before, after)
            db.close()

    def test_csv_xlsx_order_numeric_year_and_formula_text(self):
        snapshot = download_list(BASE + '/liste/demo', fetch=lambda _: page([item(1), item(2, 'Series')]))
        entries = [dict(r) for r in snapshot.entries]
        entries[0]['title'] = '=Ä & <Titel>'
        metadata = dict(name='Liste & Ä', source_url=snapshot.source_url)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for suffix in ('.csv', '.xlsx'):
                path = folder / ('liste' + suffix)
                export_list(path, metadata, entries)
                with self.assertRaises(FileExistsError):
                    export_list(path, metadata, entries)
            with (folder / 'liste.csv').open(encoding='utf-8-sig', newline='') as stream:
                rows = list(csv.reader(stream, delimiter=';'))
            self.assertEqual([r[0] for r in rows[1:]], ['1', '2'])
            self.assertEqual(rows[1][2], "'=Ä & <Titel>")
            ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
            with zipfile.ZipFile(folder / 'liste.xlsx') as archive:
                self.assertIsNone(archive.testzip())
                for name in archive.namelist():
                    ET.fromstring(archive.read(name))
                sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            self.assertEqual(sheet.find('.//m:c[@r="D2"]/m:v', ns).text, '2024')
            self.assertEqual(sheet.find('.//m:c[@r="C2"]', ns).get('t'), 'inlineStr')
            self.assertEqual(sheet.find('.//m:c[@r="C2"]/m:is/m:t', ns).text, '=Ä & <Titel>')
            self.assertIsNone(sheet.find('.//m:f', ns))

    def test_empty_public_list_is_valid(self):
        result = download_list(BASE + '/liste/demo', fetch=lambda _: page([]))
        self.assertEqual(result.source_count, 0)
        self.assertEqual(result.entries, ())


if __name__ == '__main__':
    unittest.main()
