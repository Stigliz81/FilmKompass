"""AP10: central metadata and public exports, fictitious temporary data only."""
import csv
from datetime import date
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile

import app_info
from catalog_view import PUBLIC_HEADERS, export_public, filter_rows, suggest_export_path
from manager_core import read_export, Catalog


class AP10Tests(unittest.TestCase):
    def test_central_build_and_repeatable_windows_resource(self):
        self.assertEqual(app_info.APP_VERSION, '1.0')
        self.assertEqual(app_info.BUILD_NUMBER, 2)
        self.assertEqual(app_info.APP_TITLE, 'FilmKompass 1.0')
        self.assertEqual(app_info.WINDOWS_FILE_VERSION, (1, 0, 0, 2))
        first = app_info.windows_version_info()
        self.assertEqual(first, app_info.windows_version_info())
        self.assertIn("StringStruct('FileVersion', '1.0.0.2')", first)
        self.assertIn("StringStruct('ProductVersion', '1.0')", first)
        self.assertIn('Copyright (c) 2026 Stigliz81', first)
        # Simulate an explicitly changed central build number, without editing it.
        namespace = {'__file__': app_info.__file__, '__name__': 'version_fixture'}
        source = Path(app_info.__file__).read_text(encoding='utf-8')
        exec(compile(source.replace('BUILD_NUMBER = 2', 'BUILD_NUMBER = 3'), 'app_info.py', 'exec'), namespace)
        self.assertEqual(namespace['APP_VERSION'], '1.0')
        self.assertEqual(namespace['FILE_VERSION'], '1.0.0.3')
        self.assertIn("'1.0.0.3'", namespace['windows_version_info']())
        self.assertEqual(app_info.BUILD_NUMBER, 2)

    def test_all_and_filtered_exports_contain_only_six_public_fields(self):
        rows = [
            dict(media_type='Film', title='Erfunden: Übergröße & Spaß; „Ä“', year='2005',
                 rating=7.5, rated_at='2026-10-19', genres='Abenteuerfilm, Thriller'),
            dict(media_type='Serie', title='Erfundene Null-Serie', year='2020',
                 rating=0, rated_at='2025-01-02', genres='Drama'),
            dict(media_type='Film', title='=Erfundener Titel ohne Metadaten', year='',
                 rating=6.5, rated_at='', genres=''),
        ]
        sentinel = 'SYNTHETIC_PRIVATE_FIELD_DO_NOT_EXPORT'
        for row in rows:
            row.update(note=sentinel, favorite=True, seasons=sentinel,
                       url='local:synthetic-internal-id', image_path=sentinel)
        ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subsets = [('all', rows), ('filtered', filter_rows(rows, {'rating': {0}}))]
            for scope, selection in subsets:
                self.assertEqual(len(selection), 3 if scope == 'all' else 1)
                for suffix in ('.csv', '.xlsx'):
                    with self.subTest(scope=scope, suffix=suffix):
                        path = suggest_export_path(root, scope, suffix)
                        self.assertEqual(path.stem, 'FilmKompass_Filmdaten_'+('Alle' if scope == 'all' else 'Filter'))
                        export_public(path, selection, overwrite=False)
                        if suffix == '.csv':
                            raw = path.read_bytes()
                            self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
                            data = list(csv.reader(raw.decode('utf-8-sig').splitlines(), delimiter=';'))
                            self.assertEqual(tuple(data[0]), PUBLIC_HEADERS)
                            self.assertTrue(all(len(row) == 6 for row in data))
                            if scope == 'all':
                                self.assertEqual(data[1][1], rows[0]['title'])
                                self.assertEqual(data[1][3:5], ['7,5', '19.10.2026'])
                        else:
                            with zipfile.ZipFile(path) as z:
                                self.assertIsNone(z.testzip())
                                self.assertEqual(set(z.namelist()), {
                                    '[Content_Types].xml', '_rels/.rels', 'xl/workbook.xml',
                                    'xl/_rels/workbook.xml.rels', 'xl/styles.xml', 'xl/worksheets/sheet1.xml'})
                                xml = b''.join(z.read(n) for n in z.namelist())
                                for forbidden in (sentinel.encode(), b'TargetMode="External"', b'creator', b'lastModifiedBy'):
                                    self.assertNotIn(forbidden, xml)
                                workbook = ET.fromstring(z.read('xl/workbook.xml'))
                                sheets = workbook.findall('m:sheets/m:sheet', ns)
                                self.assertEqual(len(sheets), 1)
                                self.assertNotIn('state', sheets[0].attrib)
                                sheet = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
                                self.assertFalse(sheet.findall('.//m:f', ns))
                                self.assertFalse(sheet.findall('.//*[@hidden="1"]'))
                                self.assertEqual(len(sheet.findall('m:cols/m:col', ns)), 6)
                                self.assertEqual([c.find('m:is/m:t', ns).text for c in sheet.findall('m:sheetData/m:row', ns)[0]], list(PUBLIC_HEADERS))
                                self.assertTrue(all(len(r) == 6 for r in sheet.findall('m:sheetData/m:row', ns)))
                                for i, row in enumerate(selection, 2):
                                    cell = sheet.find(f'.//m:c[@r="D{i}"]', ns)
                                    self.assertNotEqual(cell.get('t'), 'inlineStr')
                                    self.assertEqual(float(cell.find('m:v', ns).text), row['rating'])
                                    if row['year']:
                                        self.assertEqual(sheet.find(f'.//m:c[@r="C{i}"]/m:v', ns).text, row['year'])
                                    if row['rated_at']:
                                        cell = sheet.find(f'.//m:c[@r="E{i}"]', ns)
                                        self.assertEqual(cell.get('s'), '2')
                                        serial = (date.fromisoformat(row['rated_at'])-date(1899,12,30)).days
                                        self.assertEqual(int(cell.find('m:v', ns).text), serial)
                        restored = read_export(path)
                        self.assertEqual([(r['title'], r['rating'], r['rated_at']) for r in restored],
                                         [(r['title'], r['rating'], r['rated_at']) for r in selection])
                        db = Catalog(root / f'{scope}-{suffix[1:]}.sqlite')
                        try:
                            self.assertEqual(db.import_files([path])['added'], len(selection))
                        finally:
                            db.close()
                        if suffix == '.csv':
                            self.assertNotIn(sentinel, path.read_text(encoding='utf-8-sig'))
