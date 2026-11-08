"""Public Moviepilot lists: validated page snapshots, isolated tables, no ratings."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from xml.sax.saxutils import escape
import zipfile

from app_info import APP_VERSION
from moviepilot_exporter import ExportError
from manager_core import normalized_title, normalized_url

BASE = 'https://www.moviepilot.de'
PAGE_SIZE = 25
MAX_ENTRIES = 10000
HEADERS = ('Position', 'Typ', 'Titel', 'Erscheinungsjahr', 'Moviepilot-ID',
           'Moviepilot-URL', 'Listenname', 'Listen-URL', 'Moviepilot Ø',
           'Bibliotheksstatus', 'Eigene Bewertung', 'Eigene minus Moviepilot Ø')
CATALOG_LIMIT = 200


def validate_list_url(value: str) -> str:
    """Accept exactly one public list; discard pasted pagination/tracking."""
    try:
        url = urlsplit(value.strip())
        if (url.scheme != 'https' or url.hostname not in ('www.moviepilot.de', 'moviepilot.de')
                or url.username or url.password or url.port not in (None, 443)
                or not re.fullmatch(r'(?:/liste/[A-Za-z0-9_-]+|/filme/beste(?:/[A-Za-z0-9_-]+)*)/?', url.path)):
            raise ValueError()
    except ValueError as exc:
        raise ExportError('Bitte eine öffentliche HTTPS-Adresse von moviepilot.de/liste/… oder /filme/beste/… eingeben.') from exc
    return BASE + url.path.rstrip('/')


class _ListRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_list_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_list_page(url: str) -> dict:
    """Same urllib/Next-data approach as ratings; stop immediately on restrictions."""
    validate_list_url(url)
    opener = build_opener(_ListRedirects())
    for attempt in range(3):
        try:
            request = Request(url, headers={
                'User-Agent': f'FilmKompass/{APP_VERSION} (private public-list backup)',
                'Accept-Language': 'de-DE',
            })
            with opener.open(request, timeout=35) as response:
                if validate_list_url(response.url) != validate_list_url(url):
                    raise ExportError('Moviepilot hat auf eine andere Liste umgeleitet; kein Import.')
                raw = response.read(8 * 1024 * 1024 + 1)
                if len(raw) > 8 * 1024 * 1024:
                    raise ExportError('Die Listenseite überschreitet die zulässige Seitengröße.')
                html = raw.decode('utf-8')
            match = re.search(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S)
            if not match:
                raise ExportError('Keine öffentlichen Listendaten gefunden; Zugriff gesperrt oder Seitenformat geändert.')
            props = json.loads(match.group(1))['props']['initialProps']['pageProps']
            if not isinstance(props, dict):
                raise ValueError('Listendaten fehlen')
            return props
        except HTTPError as exc:
            if exc.code in (401, 403, 404, 429):
                raise ExportError(f'Moviepilot antwortet mit HTTP {exc.code}. Kein weiterer Abruf; Liste privat, nicht verfügbar oder Zugriff begrenzt.') from exc
            if exc.code < 500 or attempt == 2:
                raise ExportError(f'Moviepilot antwortet mit HTTP {exc.code}.') from exc
        except (URLError, TimeoutError, ConnectionError) as exc:
            if attempt == 2:
                raise ExportError(f'Moviepilot konnte nicht geladen werden: {exc}') from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise ExportError('Moviepilot-Listenformat wurde nicht erkannt.') from exc
        time.sleep(2 * (attempt + 1))
    raise ExportError('Moviepilot konnte nicht geladen werden.')


@dataclass(frozen=True)
class PublicList:
    source_url: str
    source_id: int
    name: str
    source_count: int
    entries: tuple[dict, ...]
    skipped_count: int
    warnings: tuple[str, ...]


def rating_number(value):
    return float(value) if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 10 else None


def community_rating(data):
    """Observed public Next-data scale is 0..100; never use critics/owner ratings."""
    value = data.get('averageCommunityRating')
    count = data.get('communityRatingsCount')
    if (data.get('hideRatings') is True or type(count) is not int or count <= 0
            or type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 100):
        return None
    return value / 10


def validate_catalog_filters(source_url, returned):
    requested=urlsplit(source_url).path.split('/')[3:]
    if (not isinstance(returned,list) or any(not isinstance(v,str) or not v for v in returned)
            or len(set(returned))!=len(returned) or len(set(requested))!=len(requested)
            or set(returned)!=set(requested)):
        raise ExportError('Moviepilot bestätigt die angeforderten Katalogfilter nicht eindeutig. Kein Import abweichender Ergebnisse.')


def download_catalog(source_url, notify, progress, fetch, pause, cancelled):
    entries, seen = [], set()
    identity = None
    for page in range(1, CATALOG_LIMIT // PAGE_SIZE + 1):
        if cancelled():
            raise ExportError('Listenimport abgebrochen; lokale Kopie unverändert.')
        props = fetch(f'{source_url}?page={page}')
        total, name = props.get('total'), props.get('title')
        if (type(total) is not int or total < 0 or props.get('page') != page
                or props.get('type') != 'filme' or props.get('order') != 'beste'
                or not isinstance(name, str) or not name.strip()):
            raise ExportError('Filmkatalog oder Seitennavigation nicht eindeutig erkannt.')
        validate_catalog_filters(source_url,props.get('filters'))
        current = (total, name, json.dumps(props.get('filters'), sort_keys=True))
        if identity is None:
            identity = current
        elif current != identity:
            raise ExportError('Filmkatalog während des Abrufs geändert; bitte erneut laden.')
        items = props.get('results')
        if not isinstance(items, list) or len(items) != min(PAGE_SIZE, max(0, total-(page-1)*PAGE_SIZE)):
            raise ExportError('Unvollständige Katalogseite; lokale Kopie unverändert.')
        for data in items:
            if not isinstance(data, dict):
                raise ExportError('Filmdaten im Katalog fehlen.')
            path, title, movie_id = data.get('path'), data.get('title'), str(data.get('id', ''))
            if (data.get('type') != 'Movie' or not isinstance(title, str) or not title.strip()
                    or not isinstance(path, str) or not re.fullmatch(r'/movies/[A-Za-z0-9_-]+', path)
                    or not re.fullmatch(r'[1-9]\d*', movie_id) or movie_id in seen):
                raise ExportError('Ungültige oder wiederholte Filmreferenz im Katalog.')
            seen.add(movie_id)
            years = re.findall(r'itemprop=["\']copyrightYear["\'][^>]*>\s*((?:18|19|20|21)\d{2})\s*<', data.get('metaShort') or '')
            entries.append(dict(position=len(entries)+1, media_type='Film', title=title,
                year=years[0] if len(years)==1 else '', moviepilot_id=movie_id,
                url=BASE+path, source_item_id=int(movie_id), community_rating=community_rating(data)))
        pages = max(1, (min(total, CATALOG_LIMIT)+PAGE_SIZE-1)//PAGE_SIZE)
        notify(f'Filmliste: Seite {page}/{pages} · {len(entries)}/{min(total,CATALOG_LIMIT)} Titel (Quelle: {total})')
        if progress:
            progress(dict(kind='Filmliste',page=page,pages=pages,loaded=len(entries),expected=min(total,CATALOG_LIMIT)))
        if page >= pages:
            break
        pause(1.0)
    if cancelled():
        raise ExportError('Listenimport abgebrochen; lokale Kopie unverändert.')
    warnings = (f'Begrenzter Katalogausschnitt: erste {len(entries)} von {total} Titeln; keine vollständige Gesamtliste.',) if total > CATALOG_LIMIT else ()
    return PublicList(source_url, 0, name, total, tuple(entries), 0, warnings)


def download_list(url: str, notify=lambda msg: None, progress=None, *, fetch=None, pause=time.sleep, cancelled=lambda: False) -> PublicList:
    fetch = fetch or fetch_list_page
    source_url = validate_list_url(url)
    if urlsplit(source_url).path.startswith('/filme/beste'):
        return download_catalog(source_url, notify, progress, fetch, pause, cancelled)
    entries, seen = [], set()
    expected = identity = None
    skipped = 0
    warnings = []
    page, pages = 1, 1
    while page <= pages:
        if cancelled():
            raise ExportError('Listenimport abgebrochen; lokale Kopie unverändert.')
        props = fetch(f'{source_url}?page={page}&itemsPerPage={PAGE_SIZE}')
        if props.get('public') is not True:
            raise ExportError('Die Liste ist nicht öffentlich zugänglich.')
        total = props.get('totalListItemCount')
        name, source_id = props.get('title'), props.get('id')
        if (type(total) is not int or not 0 <= total <= MAX_ENTRIES
                or type(source_id) is not int or source_id <= 0
                or not isinstance(name, str) or not name.strip()
                or props.get('page') != page or props.get('itemsPerPage') != PAGE_SIZE):
            raise ExportError('Listenname, ID, Gesamtzahl oder Seitennavigation fehlen bzw. sind ungültig.')
        current_identity = (source_id, name, props.get('editedAt'), props.get('permalink'))
        if expected is None:
            expected, identity = total, current_identity
            pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        elif total != expected or current_identity != identity:
            raise ExportError('Die Liste wurde während des Abrufs geändert. Bitte erneut importieren.')
        items = props.get('listItems')
        required = min(PAGE_SIZE, max(0, expected - (page - 1) * PAGE_SIZE))
        if not isinstance(items, list) or len(items) != required:
            raise ExportError(f'Unvollständige Listenseite {page}: erwartet {required} Einträge.')
        for offset, item in enumerate(items, 1):
            position = (page - 1) * PAGE_SIZE + offset
            if not isinstance(item, dict) or type(item.get('itemId')) is not int:
                raise ExportError(f'Listeneintrag {position} hat keine eindeutige Eintrags-ID.')
            if item['itemId'] in seen:
                raise ExportError('Wiederholte Seite oder doppelte Listeneintrags-ID; kein Import.')
            seen.add(item['itemId'])
            kind = item.get('itemType')
            if kind not in ('Movie', 'Series'):
                skipped += 1
                continue
            data = item.get('itemData')
            if not isinstance(data, dict):
                raise ExportError(f'Film-/Seriendaten an Listenposition {position} fehlen.')
            title, path = data.get('title'), data.get('path')
            prefix = 'movies' if kind == 'Movie' else 'serie'
            if (not isinstance(title, str) or not title.strip()
                    or not isinstance(path, str) or not re.fullmatch(r'/' + prefix + r'/[A-Za-z0-9_-]+', path)
                    or data.get('type') != kind):
                raise ExportError(f'Titel, Typ oder Moviepilot-Referenz an Position {position} ist ungültig.')
            year = str(data.get('productionYear') or '')
            if year and not re.fullmatch(r'(18|19|20|21)\d{2}', year):
                warnings.append(f'Position {position}: Erscheinungsjahr nicht eindeutig; leer gespeichert.')
                year = ''
            elif not year:
                warnings.append(f'Position {position}: Erscheinungsjahr fehlt.')
            movie_id = data.get('id')
            if movie_id is not None and (type(movie_id) is not int or movie_id <= 0):
                raise ExportError(f'Ungültige Moviepilot-ID an Position {position}.')
            entries.append(dict(position=position, media_type='Film' if kind == 'Movie' else 'Serie',
                                title=title, year=year, moviepilot_id=str(movie_id or ''),
                                url=BASE + path, source_item_id=item['itemId'],
                                community_rating=community_rating(data)))
        notify(f'Filmliste: Seite {page}/{pages} · {len(seen)}/{expected} Listeneinträge geprüft')
        if progress:
            progress(dict(kind='Filmliste', page=page, pages=pages, loaded=len(seen), expected=expected))
        page += 1
        if page <= pages:
            pause(1.0)
    if len(seen) != expected:
        raise ExportError('Die Liste ist unvollständig; kein Import.')
    if cancelled():
        raise ExportError('Listenimport abgebrochen; lokale Kopie unverändert.')
    if skipped:
        warnings.append(f'Andere Einträge ausgelassen: {skipped}. Originalpositionen bleiben erhalten.')
    return PublicList(source_url, identity[0], identity[1], expected, tuple(entries), skipped, tuple(warnings))


class ListStore:
    """Only these two additive tables are written; no links to personal titles."""
    def __init__(self, connection: sqlite3.Connection):
        self.con = connection
        self.con.executescript('''
            CREATE TABLE IF NOT EXISTS movie_lists (
                source_url TEXT PRIMARY KEY, source_id INTEGER NOT NULL,
                name TEXT NOT NULL, source_count INTEGER NOT NULL,
                skipped_count INTEGER NOT NULL, imported_at TEXT NOT NULL,
                warnings TEXT NOT NULL DEFAULT '[]'
            );
            CREATE TABLE IF NOT EXISTS movie_list_entries (
                list_url TEXT NOT NULL REFERENCES movie_lists(source_url) ON DELETE CASCADE,
                position INTEGER NOT NULL, media_type TEXT NOT NULL,
                title TEXT NOT NULL, year TEXT NOT NULL, moviepilot_id TEXT NOT NULL,
                url TEXT NOT NULL, source_item_id INTEGER NOT NULL,
                PRIMARY KEY(list_url, position), UNIQUE(list_url, source_item_id)
            );
        ''')

    def save(self, snapshot: PublicList):
        with self.con:
            self.con.execute('''INSERT INTO movie_lists VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(source_url) DO UPDATE SET source_id=excluded.source_id,
                name=excluded.name, source_count=excluded.source_count,
                skipped_count=excluded.skipped_count, imported_at=excluded.imported_at,
                warnings=excluded.warnings''',
                (snapshot.source_url, snapshot.source_id, snapshot.name, snapshot.source_count,
                 snapshot.skipped_count, datetime.now().astimezone().isoformat(timespec='seconds'),
                 json.dumps(dict(version=2, warnings=snapshot.warnings,
                     community={str(r['position']): r.get('community_rating') for r in snapshot.entries}), ensure_ascii=False)))
            self.con.execute('DELETE FROM movie_list_entries WHERE list_url=?', (snapshot.source_url,))
            self.con.executemany('INSERT INTO movie_list_entries VALUES (?,?,?,?,?,?,?,?)',
                [(snapshot.source_url, r['position'], r['media_type'], r['title'], r['year'],
                  r['moviepilot_id'], r['url'], r['source_item_id']) for r in snapshot.entries])

    def lists(self):
        rows = [dict(r) for r in self.con.execute('''SELECT l.*, COUNT(e.position) AS entry_count
            FROM movie_lists l LEFT JOIN movie_list_entries e ON e.list_url=l.source_url
            GROUP BY l.source_url ORDER BY l.name COLLATE NOCASE, l.source_url''')]
        for row in rows:
            data = json.loads(row['warnings'])
            if isinstance(data, dict):
                row['warnings'] = json.dumps(data.get('warnings', []), ensure_ascii=False)
        return rows

    def entries(self, url):
        meta = self.con.execute('SELECT warnings FROM movie_lists WHERE source_url=?', (url,)).fetchone()
        data = json.loads(meta[0]) if meta else []
        community = data.get('community', {}) if isinstance(data, dict) else {}
        rows = [dict(r) for r in self.con.execute('SELECT * FROM movie_list_entries WHERE list_url=? ORDER BY position', (url,))]
        for row in rows:
            row['community_rating'] = rating_number(community.get(str(row['position'])))
        return rows

    def delete(self, url):
        with self.con:
            self.con.execute('DELETE FROM movie_list_entries WHERE list_url=?', (url,))
            self.con.execute('DELETE FROM movie_lists WHERE source_url=?', (url,))


def import_public_list(url: str, db_path: Path, notify=lambda msg: None, progress=None, *, cancelled=lambda: False):
    snapshot = download_list(url, notify, progress, cancelled=cancelled)
    if cancelled():
        raise ExportError('Listenimport abgebrochen; lokale Kopie unverändert.')
    connection = sqlite3.connect(db_path, timeout=20)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        ListStore(connection).save(snapshot)
    finally:
        connection.close()
    return {'movie_list': snapshot}


def compare_list(entries, library):
    """Read-only, deterministic identity matching; never infer whether seen."""
    by_url, by_exact, by_normal = {}, {}, {}
    def add(index, key, row):
        index.setdefault(key, []).append(row)
    def canonical(value):
        try:
            return normalized_url(value)
        except ValueError:
            return ''
    for row in library:
        url = canonical(row.get('url', ''))
        if url:
            add(by_url, url, row)
        key = (row['title'].strip().casefold(), row['media_type'], str(row.get('year') or ''))
        add(by_exact, key, row)
        add(by_normal, (normalized_title(row['title']), *key[1:]), row)
    result = []
    for entry in entries:
        row = dict(entry)
        year = str(row.get('year') or '')
        matches = by_url.get(canonical(row['url']), [])
        if not matches and year:
            matches = by_exact.get((row['title'].strip().casefold(), row['media_type'], year), [])
        if not matches and year:
            matches = by_normal.get((normalized_title(row['title']), row['media_type'], year), [])
        own = rating_number(matches[0].get('rating')) if len(matches)==1 else None
        row['library_status'] = ('Zuordnung unklar' if len(matches)>1 else
            'Bereits bewertet' if own is not None else
            'Vorhanden ohne verlässliche Bewertung' if matches else 'Nicht in Bibliothek')
        row['own_rating'] = own
        community = rating_number(row.get('community_rating'))
        row['rating_difference'] = own-community if own is not None and community is not None else None
        result.append(row)
    return result


def list_summary(rows):
    own = [r['own_rating'] for r in rows if rating_number(r.get('own_rating')) is not None]
    community = [r['community_rating'] for r in rows if rating_number(r.get('community_rating')) is not None]
    paired = [r['own_rating']-r['community_rating'] for r in rows
              if rating_number(r.get('own_rating')) is not None and rating_number(r.get('community_rating')) is not None]
    average = lambda values: sum(values)/len(values) if values else None
    return dict(total=len(rows), rated=sum(r['library_status']=='Bereits bewertet' for r in rows),
        unrated=sum(r['library_status']=='Vorhanden ohne verlässliche Bewertung' for r in rows),
        missing=sum(r['library_status']=='Nicht in Bibliothek' for r in rows),
        unclear=sum(r['library_status']=='Zuordnung unklar' for r in rows),
        own_average=average(own), community_average=average(community),
        difference_average=average(paired), absolute_difference_average=average([abs(x) for x in paired]),
        own_count=len(own), community_count=len(community), paired_count=len(paired))


def export_list(path: Path, metadata: dict, entries: list[dict], *, overwrite=False):
    """Reuse the application's dependency-free OOXML conventions, ordered rows."""
    records = [(r['position'], r['media_type'], r['title'], r['year'], r['moviepilot_id'],
                r['url'], metadata['name'], metadata['source_url'], rating_number(r.get('community_rating')),
                r.get('library_status', ''), rating_number(r.get('own_rating')), r.get('rating_difference')) for r in entries]
    if path.suffix.lower() == '.csv':
        with path.open('w' if overwrite else 'x', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream, delimiter=';')
            writer.writerow(HEADERS)
            for row in records:
                # Excel's CSV parser has no cell types; protect text from formulas.
                writer.writerow([str(round(v, 4)).replace('.', ',') if type(v) is float else
                    ("'" + v) if isinstance(v, str) and v.startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else v for v in row])
    elif path.suffix.lower() == '.xlsx':
        _write_list_xlsx(path, records, overwrite=overwrite)
    else:
        raise ValueError('Bitte .xlsx oder .csv wählen.')


def _write_list_xlsx(path, records, *, overwrite):
    ns = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    rows = []
    for number, row in enumerate([HEADERS, *records], 1):
        cells = []
        for column, value in enumerate(row):
            address = f'{chr(65 + column)}{number}'
            if value is None:
                cells.append(f'<c r="{address}"/>')
            elif number > 1 and (column == 0 or (column == 3 and str(value).isdigit()) or column in (8,10,11)):
                cells.append(f'<c r="{address}"><v>{float(value) if column in (8,10,11) else int(value)}</v></c>')
            else:
                cells.append(f'<c r="{address}" t="inlineStr"><is><t xml:space="preserve">{escape(str(value))}</t></is></c>')
        rows.append(f'<row r="{number}">' + ''.join(cells) + '</row>')
    sheet = f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0" showGridLines="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols>'
    sheet += ''.join(f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>' for i, width in enumerate((10, 12, 55, 18, 18, 65, 48, 70, 18, 48, 20, 28), 1))
    sheet += '</cols><sheetData>' + ''.join(rows) + f'</sheetData><autoFilter ref="A1:L{len(records)+1}"/></worksheet>'
    parts = {
        '[Content_Types].xml': '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>',
        '_rels/.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml': f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Filmliste" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        'xl/worksheets/sheet1.xml': sheet,
    }
    with zipfile.ZipFile(path, 'w' if overwrite else 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, body in parts.items():
            archive.writestr(name, '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' + body)
