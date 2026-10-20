"""Lokale, von Moviepilot unabhängige Datenhaltung. Keine Fremdpakete."""
from __future__ import annotations

import csv
import difflib
import io
import re
import sqlite3
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime, timedelta
import hashlib
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

APP_NAME = "MoviepilotManager"
MEDIA_TYPES = ("Film", "Serie")
STATUSES = (
    "Nicht erfasst", "Gesehen", "Komplett", "Aktuell dabei",
    "Pausiert", "Abgebrochen", "Merkliste", "Nicht gesehen", "Kein Interesse",
)
REQUIRED = ("Titel", "Meine Bewertung", "Typ", "Moviepilot-URL")
HEADERS = ("Titel", "Erscheinungsjahr", "Meine Bewertung", "Typ", "Moviepilot-URL",
           "Originaltitel", "Bewertungsdatum", "Status", "Moviepilot-ID", "Genre")
PUBLIC_HEADERS = ("Typ", "Titel", "Jahr", "Note", "Bewertet am", "Genre")


def supported_headers(headers):
    return set(REQUIRED).issubset(headers) or set(PUBLIC_HEADERS).issubset(headers)


def identity(row):
    return (row['media_type'], row['title'].casefold().strip(), row['year'])


def rating_date(value: object) -> str:
    """Only exact source dates; unknown/relative dates stay empty."""
    raw = str(value or "").strip()
    for pattern in ("%d.%m.%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, pattern).date().isoformat()
        except ValueError:
            pass
    return ""


def display_date(value: object) -> str:
    exact = rating_date(value)
    return datetime.strptime(exact, "%Y-%m-%d").strftime("%d.%m.%Y") if exact else ""


def sort_rows(rows: list[dict], field: str, descending: bool = False) -> list[dict]:
    """Sort a filtered snapshot; missing/invalid values stay last in either direction."""
    if field not in {"media_type", "title", "year", "rating", "rated_at", "genres"}:
        raise ValueError("Unbekannte Sortierspalte")
    def key(row):
        value = row.get(field)
        if field == "rated_at":
            return rating_date(value) or None
        if field in {"year", "rating"}:
            try:
                return float(value) if value is not None and str(value).strip() else None
            except (TypeError, ValueError):
                return None
        return str(value).casefold() if value else None
    valid = [row for row in rows if key(row) is not None]
    missing = [row for row in rows if key(row) is None]
    return sorted(valid, key=key, reverse=descending) + missing


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def data_directory() -> Path:
    import os
    import sys
    override = os.environ.get("MOVIEPILOT_MANAGER_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        home = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    else:
        home = Path.home() / ".local" / "share"
    return home / APP_NAME


def normalized_url(url: str) -> str:
    raw = (url or "").strip()
    parts = urlsplit(raw)
    if parts.scheme not in ("https", "http") or parts.netloc.lower() not in ("moviepilot.de", "www.moviepilot.de"):
        raise ValueError("Ungültige Moviepilot-URL: " + raw[:120])
    path = re.sub(r"/+", "/", parts.path).rstrip("/")
    if not (path.startswith("/movies/") or path.startswith("/serie/")):
        raise ValueError("Kein Film-/Serienlink: " + raw[:120])
    return urlunsplit(("https", "www.moviepilot.de", path, "", ""))


def validate_rating(raw: object) -> float:
    s = str(raw).strip().replace(",", ".")
    if not s:
        raise ValueError("Fehlende Bewertung")
    try:
        val = float(s)
    except ValueError as err:
        raise ValueError(f"Bewertung nicht numerisch: {s!r}") from err
    if not (0 <= val <= 10) or abs(val * 2 - round(val * 2)) > 1e-7:
        raise ValueError(f"Bewertung außerhalb der Moviepilot-Halbpunkte: {s!r}")
    return val


def normalize_row(raw: dict) -> dict:
    if set(PUBLIC_HEADERS).issubset(raw) and not raw.get('Moviepilot-URL'):
        mapped = dict(Titel=raw['Titel'], Erscheinungsjahr=raw['Jahr'], Typ=raw['Typ'],
                      **{'Meine Bewertung':raw['Note'], 'Bewertungsdatum':raw['Bewertet am'], 'Genre':raw['Genre'],
                         'Moviepilot-URL':'https://www.moviepilot.de/movies/local-placeholder'})
        result = normalize_row(mapped)
        key = '\0'.join(identity(result))
        result['url'] = 'local:' + hashlib.sha256(key.encode('utf-8')).hexdigest()
        result['_public'] = True
        return result
    missing = [k for k in REQUIRED if k not in raw]
    if missing:
        raise ValueError("Fehlende Spalten: " + ", ".join(missing))
    url = normalized_url(str(raw["Moviepilot-URL"]))
    typ = str(raw["Typ"]).strip()
    if typ not in MEDIA_TYPES:
        raise ValueError("Unbekannter Typ: " + typ)
    title = str(raw["Titel"]).strip()
    if not title:
        raise ValueError("Titel fehlt")
    year = str(raw.get("Erscheinungsjahr") or "").strip()
    if year and not re.fullmatch(r"\d{4}", year):
        try:
            year = str(int(float(year)))
        except (ValueError, TypeError) as err:
            raise ValueError(f"Ungültiges Erscheinungsjahr: {year}") from err
    return dict(url=url, moviepilot_id=str(raw.get("Moviepilot-ID") or "").strip(),
                title=title, year=year, rating=validate_rating(raw["Meine Bewertung"]),
                media_type=typ, original_title=str(raw.get("Originaltitel") or "").strip(),
                rated_at=rating_date(raw.get("Bewertungsdatum")),
                genres=str(raw.get("Genre") or "").strip(),
                source_status=str(raw.get("Status") or "").strip())


def _csv_contents(path: Path) -> list[dict]:
    raw = path.read_bytes()
    decoded = None
    for enc in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            decoded = raw.decode(enc)
            break
        except UnicodeDecodeError:
            pass
    if decoded is None:
        raise ValueError("Unlesbare Textkodierung")
    sample = decoded[:4096]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    reader = csv.DictReader(io.StringIO(decoded, newline=""), delimiter=delimiter)
    if not reader.fieldnames or not supported_headers(set(reader.fieldnames)):
        raise ValueError("CSV hat keine vollständigen Moviepilot-Spalten")
    return [x for x in reader if any(str(v or "").strip() for v in x.values())]


def _xml_path(root: str, target: str) -> str:
    # Relationships are internal to the XLSX ZIP, never filesystem paths.
    from posixpath import normpath, join
    if target.startswith("/"):
        res = target.lstrip("/")
    else:
        res = normpath(join(root, target))
    if res.startswith("../") or res == "..":
        raise ValueError("Ungültiger XLSX-Pfad")
    return res


def _xlsx_contents(path: Path) -> list[dict]:
    """Lieste die üblichen Excel-Zelltypen per Standardbibliothek (read-only)."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    pkg_rel_ns = "{http://schemas.openxmlformats.org/package/2006/relationships}"
    records = []
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
        if "xl/workbook.xml" not in names:
            raise ValueError("Keine gültige XLSX-Arbeitsmappe")
        shared = []
        if "xl/sharedStrings.xml" in names:
            ss = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in ss.findall(f"{ns}si"):
                shared.append("".join(n.text or "" for n in si.iter(f"{ns}t")))
        rels = {}
        if "xl/_rels/workbook.xml.rels" in names:
            root = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
            rels = {r.attrib.get("Id"): r.attrib.get("Target") for r in root.findall(f"{pkg_rel_ns}Relationship")}
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        sheets = workbook.find(f"{ns}sheets")
        if sheets is None:
            raise ValueError("XLSX enthält keine Blätter")
        for sheet in sheets:
            if not sheet.tag.endswith("sheet"):
                continue
            relationship = sheet.attrib.get(f"{rel_ns}id")
            target = rels.get(relationship, "")
            if not target:
                continue
            sname = _xml_path("xl", target)
            if sname not in names:
                continue
            root = ET.fromstring(z.read(sname))
            data = root.find(f"{ns}sheetData")
            if data is None:
                continue
            matrix = []
            for row in data.findall(f"{ns}row"):
                values = {}
                for cell in row.findall(f"{ns}c"):
                    coord = cell.attrib.get("r", "")
                    m = re.match(r"([A-Z]+)", coord)
                    if not m:
                        continue
                    idx = 0
                    for letter in m.group(1):
                        idx = idx * 26 + ord(letter) - ord("A") + 1
                    idx -= 1
                    typ = cell.attrib.get("t")
                    value_node = cell.find(f"{ns}v")
                    if typ == "inlineStr":
                        inline = cell.find(f"{ns}is")
                        value = "".join(t.text or "" for t in inline.iter(f"{ns}t")) if inline is not None else ""
                    elif typ == "s" and value_node is not None:
                        i = int(value_node.text or 0)
                        value = shared[i] if 0 <= i < len(shared) else ""
                    else:
                        value = value_node.text if value_node is not None else ""
                    values[idx] = value or ""
                if values:
                    matrix.append(values)
            header_row = -1
            columns = {}
            for i, values in enumerate(matrix[:30]):
                lookup = {str(v).strip(): k for k, v in values.items()}
                if supported_headers(lookup):
                    header_row = i
                    columns = lookup
                    break
            if header_row < 0:
                continue
            for line in matrix[header_row + 1:]:
                data_row = {name: line.get(pos, "") for name, pos in columns.items()}
                for key in ('Bewertet am', 'Bewertungsdatum'):
                    value = data_row.get(key, '')
                    if str(value).replace('.', '', 1).isdigit() and 1 <= float(value) <= 2958465:
                        data_row[key] = (datetime(1899,12,30)+timedelta(days=float(value))).date().isoformat()
                if data_row.get("Titel") and (data_row.get("Moviepilot-URL") or set(PUBLIC_HEADERS).issubset(columns)):
                    records.append(data_row)
    if not records:
        raise ValueError("Kein Film-/Serien-Tabellenblatt in der XLSX-Datei gefunden")
    return records


def read_export(path: str | Path) -> list[dict]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        raw = _csv_contents(path)
    elif path.suffix.lower() == ".xlsx":
        raw = _xlsx_contents(path)
    else:
        raise ValueError("Nur .csv und .xlsx werden unterstützt")
    found = {}
    for n, row in enumerate(raw, start=2):
        try:
            item = normalize_row(row)
        except ValueError as e:
            raise ValueError(f"{path.name}, Datenzeile {n}: {e}") from e
        if item["url"] in found:
            if item.get('_public'):
                raise ValueError('Mehrdeutiger Sechs-Spalten-Import: Typ, Titel und Jahr mehrfach vorhanden. Bitte URL-Export verwenden.')
            # The combined Excel sheet duplicates entries on its separated tabs.
            if found[item["url"]] != item:
                raise ValueError(f"Unterschiedliche Daten zur selben URL: {item['url']}")
        found[item["url"]] = item
    if not found:
        raise ValueError(f"Keine Daten in {path.name}")
    return list(found.values())


class Catalog:
    def __init__(self, db_path: Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(str(self.db_path), timeout=20)
        self.con.row_factory = sqlite3.Row
        self.con.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def _initialize(self):
        self.con.executescript("""
            CREATE TABLE IF NOT EXISTS titles (
              url TEXT PRIMARY KEY, moviepilot_id TEXT NOT NULL DEFAULT '',
              title TEXT NOT NULL, year TEXT NOT NULL DEFAULT '',
              rating REAL NOT NULL, media_type TEXT NOT NULL,
              original_title TEXT NOT NULL DEFAULT '', rated_at TEXT NOT NULL DEFAULT '',
              source_status TEXT NOT NULL DEFAULT '', present INTEGER NOT NULL DEFAULT 1,
              imported_at TEXT NOT NULL, modified_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_titles_type ON titles(media_type);
            CREATE TABLE IF NOT EXISTS personal (
              url TEXT PRIMARY KEY REFERENCES titles(url) ON DELETE CASCADE,
              watch_status TEXT NOT NULL DEFAULT 'Nicht erfasst',
              progress TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
              review_later INTEGER NOT NULL DEFAULT 0, favorite INTEGER NOT NULL DEFAULT 0,
              modified_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS seasons (
              url TEXT NOT NULL REFERENCES titles(url) ON DELETE CASCADE,
              season INTEGER NOT NULL CHECK(season>=1 AND season<=100),
              rating REAL, watched INTEGER NOT NULL DEFAULT 0, note TEXT NOT NULL DEFAULT '',
              PRIMARY KEY(url, season)
            );
            CREATE TABLE IF NOT EXISTS import_runs (
              id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
              filenames TEXT NOT NULL, added INTEGER NOT NULL, changed INTEGER NOT NULL,
              unchanged INTEGER NOT NULL, unavailable INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS changes (
              id INTEGER PRIMARY KEY AUTOINCREMENT, created_at TEXT NOT NULL,
              url TEXT NOT NULL, title TEXT NOT NULL, change_type TEXT NOT NULL,
              details TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS user_images (
              url TEXT PRIMARY KEY REFERENCES titles(url) ON DELETE CASCADE,
              filename TEXT NOT NULL
            );
        """)
        self.con.commit()

        # Additive migration: old databases and personal tables remain intact.
        columns = {row[1] for row in self.con.execute("PRAGMA table_info(titles)")}
        if "genres" not in columns:
            self.con.execute("ALTER TABLE titles ADD COLUMN genres TEXT NOT NULL DEFAULT ''")
            self.con.commit()

    def close(self):
        self.con.close()

    def backup(self, folder: Path | None = None) -> Path:
        folder = folder or self.db_path.parent / "backup"
        folder.mkdir(parents=True, exist_ok=True)
        name = datetime.now().strftime("MoviepilotManager_%Y%m%d_%H%M%S_%f.sqlite")
        output = folder / name
        con2 = sqlite3.connect(output)
        try:
            self.con.backup(con2)
        finally:
            con2.close()
        # Retain existing user backups; cleanup is always a user decision.
        return output

    def count(self) -> int:
        return self.con.execute("SELECT COUNT(*) FROM titles WHERE present=1").fetchone()[0]

    def import_files(self, filenames: list[str | Path], notify=None) -> dict:
        notify = notify or (lambda message: None)
        notify("Daten werden geprüft")
        # Read and validate everything BEFORE touching the live DB.
        records = {}
        types = set()
        per_file = []
        public_import = False
        formats = set()
        promotions = {}
        stored = [dict(r) for r in self.con.execute('SELECT * FROM titles')]
        for name in filenames:
            name = Path(name)
            data = read_export(name)
            per_file.append((name.name, len(data)))
            for row in data:
                is_public = row.pop('_public', False)
                formats.add(is_public)
                if len(formats)>1:
                    raise ValueError('URL-Exporte und Sechs-Spalten-Dateien bitte getrennt importieren. Keine Daten geändert.')
                public_import = public_import or is_public
                candidates = [r for r in stored if identity(r)==identity(row)]
                if is_public:
                    if len(candidates)>1 or (candidates and not row['year'] and candidates[0]['url'] != row['url']):
                        raise ValueError('Zuordnung ohne URL ist uneindeutig: '+row['title']+'. Bitte alten Export mit Moviepilot-URLs verwenden. Keine Daten geändert.')
                    if len(candidates)==1:
                        row['url']=candidates[0]['url']
                elif not any(r['url']==row['url'] for r in stored):
                    locals_=[r for r in candidates if r['url'].startswith('local:')]
                    if locals_:
                        # Refuse ambiguous promotion rather than creating a second identity.
                        if len(candidates)!=1 or not row['year']:
                            raise ValueError('Lokaler Titel ohne URL kann nicht eindeutig zugeordnet werden: '+row['title'])
                        promotions[row['url']]=locals_[0]['url']
                if row["url"] in records and row != records[row["url"]]:
                    raise ValueError(f"Abweichende doppelte URL in Importdateien: {row['url']}")
                records[row["url"]] = row
                types.add(row["media_type"])
        if not records:
            raise ValueError("Keine Datensätze zum Importieren")
        # A failed scraper might export only the first page. Refuse suspiciously
        # short replacement imports rather than hiding most of the user's library.
        for typ in types:
            existing = self.con.execute(
                "SELECT COUNT(*) FROM titles WHERE media_type=? AND present=1", (typ,)
            ).fetchone()[0]
            incoming = sum(x["media_type"] == typ for x in records.values())
            if not public_import and existing >= 30 and incoming < existing * 0.80:
                raise ValueError(
                    f"Import abgebrochen: für {typ} nur {incoming} von zuvor {existing} "
                    "Titeln gefunden. Das sieht nach einem unvollständigen "
                    "Export aus. Die Datenbank wurde nicht verändert."
                )
        # Never automatically delete movies or personal annotations.
        if self.count():
            notify("Sicherung wird erstellt")
            self.backup()
        added = changed = unchanged = unavailable = 0
        stamp = now()
        sql_fields = ("moviepilot_id", "title", "year", "rating", "media_type",
                      "original_title", "rated_at", "source_status", "genres")
        notify("Änderungen werden abgeglichen und Daten werden gespeichert")
        with self.con:
            self.con.execute('PRAGMA defer_foreign_keys=ON')
            for new, old in promotions.items():
                for table in ('titles','personal','seasons','changes','user_images'):
                    self.con.execute(f'UPDATE {table} SET url=? WHERE url=?',(new,old))
            for row in records.values():
                old = self.con.execute("SELECT * FROM titles WHERE url=?", (row["url"],)).fetchone()
                if old is None:
                    self.con.execute("""INSERT INTO titles
                        (url,moviepilot_id,title,year,rating,media_type,original_title,rated_at,source_status,genres,present,imported_at,modified_at)
                        VALUES(?,?,?,?,?,?,?,?,?,?,1,?,?)""",
                        (row["url"], *(row[k] for k in sql_fields), stamp, stamp))
                    added += 1
                    self.con.execute("INSERT INTO changes(created_at,url,title,change_type,details) VALUES(?,?,?,?,?)",
                                     (stamp, row["url"], row["title"], "Neu", f"Bewertung {row['rating']:g}"))
                else:
                    # Some browser layouts omit optional metadata (date, ID, original title,
                    # year). Preserve existing nonempty metadata rather than emptying it.
                    # The user's explicit score/title/media type are still authoritative.
                    for optional in ("moviepilot_id", "year", "original_title", "rated_at", "source_status", "genres"):
                        if row[optional] == "" and old[optional]:
                            row[optional] = old[optional]
                    if rating_date(row["rated_at"]) == rating_date(old["rated_at"]) and old["rated_at"]:
                        row["rated_at"] = old["rated_at"]
                    diff = [k for k in sql_fields if old[k] != row[k]]
                    if diff or old["present"] == 0:
                        self.con.execute("""UPDATE titles SET moviepilot_id=?,title=?,year=?,rating=?,media_type=?,
                                          original_title=?,rated_at=?,source_status=?,genres=?,present=1,modified_at=? WHERE url=?""",
                                         (*(row[k] for k in sql_fields), stamp, row["url"]))
                        changed += 1
                        details = "; ".join(f"{k}: {old[k]} → {row[k]}" for k in diff)
                        self.con.execute("INSERT INTO changes(created_at,url,title,change_type,details) VALUES(?,?,?,?,?)",
                                         (stamp, row["url"], row["title"], "Geändert", details or "Wieder verfügbar"))
                    else:
                        unchanged += 1
            missing = self.con.execute(
                "SELECT url,title FROM titles WHERE present=1 AND media_type IN (" + ",".join("?" for _ in types) + ")",
                tuple(sorted(types)),
            ).fetchall()
            for item in missing:
                # Six-column exports may deliberately contain only filtered rows.
                if public_import: continue
                if item["url"] in records:
                    continue
                self.con.execute("UPDATE titles SET present=0,modified_at=? WHERE url=?", (stamp,item["url"]))
                self.con.execute("INSERT INTO changes(created_at,url,title,change_type,details) VALUES(?,?,?,?,?)",
                                 (stamp,item["url"],item["title"],"Nicht im Export", "Nicht gelöscht; persönliche Daten bleiben erhalten"))
                unavailable += 1
            self.con.execute("INSERT INTO import_runs(created_at,filenames,added,changed,unchanged,unavailable) VALUES(?,?,?,?,?,?)",
                             (stamp, ", ".join(f"{n} ({c})" for n,c in per_file),added,changed,unchanged,unavailable))
        return dict(added=added, changed=changed, unchanged=unchanged,
                    unavailable=unavailable, count=len(records), filenames=per_file,
                    identity_note=('Ohne URL: Zuordnung über Typ, exakten Titel und Jahr; unbekannte Titel bleiben lokal ohne Weblink. Kein Abgleich fehlender Titel.' if public_import else ''))

    def seed_private_notes(self, path: Path) -> int:
        """Optional private first-installation notes, never shipped in public source."""
        import json
        path = Path(path)
        if not path.is_file():
            return 0
        contents = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(contents, list):
            raise ValueError("Persönliche Startnotizen müssen eine JSON-Liste sein")
        count = 0
        with self.con:
            for obj in contents:
                url = normalized_url(str(obj["url"]))
                status = str(obj.get("watch_status") or "Nicht erfasst")
                if status not in STATUSES:
                    raise ValueError("Unbekannter Sehstatus in Startnotizen")
                if not self.con.execute("SELECT 1 FROM titles WHERE url=?",(url,)).fetchone():
                    continue
                if self.con.execute("SELECT 1 FROM personal WHERE url=?",(url,)).fetchone():
                    continue
                self.con.execute("INSERT INTO personal(url,watch_status,progress,note,modified_at) VALUES(?,?,?,?,?)",
                                 (url,status,str(obj.get("progress") or ""),str(obj.get("note") or ""),now()))
                count += 1
        return count

    def reset_library(self):
        """Caller must explicitly confirm; settings/backups are outside this transaction."""
        with self.con:
            for table in ("seasons", "personal", "changes", "import_runs", "titles", "meta"):
                self.con.execute(f"DELETE FROM {table}")
            self.con.execute("DELETE FROM sqlite_sequence WHERE name IN ('changes','import_runs')")

    def get_rows(self, query="", media_type="Alle", status="Alle", hidden=False,
                 sort_by="title", descending=False) -> list[dict]:
        sql = """SELECT t.*, COALESCE(p.watch_status,'Nicht erfasst') watch_status,
                        COALESCE(p.progress,'') progress, COALESCE(p.note,'') note,
                        COALESCE(p.review_later,0) review_later, COALESCE(p.favorite,0) favorite,
                        COALESCE(p.modified_at,'') personal_modified_at
                        FROM titles t LEFT JOIN personal p ON t.url=p.url WHERE 1=1"""
        args = []
        if not hidden:
            sql += " AND t.present=1"
        if media_type in MEDIA_TYPES:
            sql += " AND t.media_type=?"
            args.append(media_type)
        if status == "Zur Prüfung":
            sql += " AND COALESCE(p.review_later,0)=1"
        elif status == "Favoriten":
            sql += " AND COALESCE(p.favorite,0)=1"
        elif status in STATUSES:
            sql += " AND COALESCE(p.watch_status,'Nicht erfasst')=?"
            args.append(status)
        if query.strip():
            sql += " AND (LOWER(t.title) LIKE ? OR LOWER(t.original_title) LIKE ?)"
            pattern = "%" + query.lower().strip() + "%"
            args.extend([pattern,pattern])
        sql += " ORDER BY t.title COLLATE NOCASE, t.media_type"
        return sort_rows([dict(x) for x in self.con.execute(sql,args).fetchall()], sort_by, descending)

    def get_row(self, url):
        rs = self.con.execute("""SELECT t.*, COALESCE(p.watch_status,'Nicht erfasst') watch_status,
            COALESCE(p.progress,'') progress, COALESCE(p.note,'') note,
            COALESCE(p.review_later,0) review_later, COALESCE(p.favorite,0) favorite,
            COALESCE(p.modified_at,'') personal_modified_at
            FROM titles t LEFT JOIN personal p ON t.url=p.url WHERE t.url=?""",(url,)).fetchone()
        return dict(rs) if rs else None

    def save_personal(self, url, status, progress, note, review_later, favorite):
        if status not in STATUSES:
            raise ValueError("Unbekannter Sehstatus")
        with self.con:
            self.con.execute("""INSERT INTO personal(url,watch_status,progress,note,review_later,favorite,modified_at)
                 VALUES(?,?,?,?,?,?,?) ON CONFLICT(url) DO UPDATE SET
                 watch_status=excluded.watch_status,progress=excluded.progress,note=excluded.note,
                 review_later=excluded.review_later,favorite=excluded.favorite,modified_at=excluded.modified_at""",
                 (url,status,progress.strip(),note.strip(),int(bool(review_later)),int(bool(favorite)),now()))

    def seasons(self,url):
        return [dict(r) for r in self.con.execute("SELECT * FROM seasons WHERE url=? ORDER BY season",(url,)).fetchall()]

    def save_season(self,url,season,rating,watched,note):
        season=int(season)
        if not (1<=season<=100):
            raise ValueError("Staffelnummer muss zwischen 1 und 100 liegen")
        if rating is not None and str(rating).strip():
            rating=validate_rating(rating)
        else:
            rating=None
        with self.con:
            self.con.execute("""INSERT INTO seasons(url,season,rating,watched,note) VALUES(?,?,?,?,?)
                ON CONFLICT(url,season) DO UPDATE SET rating=excluded.rating,watched=excluded.watched,note=excluded.note""",
                (url,season,rating,int(bool(watched)),note.strip()))

    def delete_season(self,url,season):
        with self.con:
            self.con.execute("DELETE FROM seasons WHERE url=? AND season=?",(url,int(season)))

    def summary(self) -> dict:
        data = self.get_rows()
        count_by_type=Counter(x["media_type"] for x in data)
        counts=Counter(x["watch_status"] for x in data)
        decade=Counter(f"{int(x['year'])//10*10}er" for x in data if str(x["year"]).isdigit())
        valid=[x["rating"] for x in data if x["rating"]>0]
        rating_hist = {f"{k} bis <{k+1}":sum(k<=x["rating"]<k+1 for x in data) for k in range(10)}
        rating_hist["10"] = sum(x["rating"]==10 for x in data)
        return dict(total=len(data),count_by_type=count_by_type,statuses=counts,
                    decades=decade,review_later=sum(x["review_later"] for x in data),
                    favorites=sum(x["favorite"] for x in data),zeros=sum(x["rating"]==0 for x in data),
                    average=sum(valid)/len(valid) if valid else 0, rating_hist=rating_hist)

    def recent_changes(self, limit=300):
        return [dict(x) for x in self.con.execute("SELECT * FROM changes ORDER BY id DESC LIMIT ?",(limit,))]

    def last_import(self):
        item=self.con.execute("SELECT * FROM import_runs ORDER BY id DESC LIMIT 1").fetchone()
        return dict(item) if item else None

    def export_annotated_csv(self,path:Path):
        data = self.export_records()
        columns = [*HEADERS, "Lokal importiert am", "Lokal zuletzt aktualisiert", "Sehstatus", "Fortschritt",
                   "Eigene Notiz", "Später prüfen", "Herz-Favorit", "Im letzten Export"]
        with open(path,"w",encoding="utf-8-sig",newline="") as file:
            wr=csv.writer(file,delimiter=";")
            wr.writerow(columns)
            for item in data:
                values = dict(item)
                values["Meine Bewertung"] = str(values["Meine Bewertung"]).replace(".", ",")
                wr.writerow([values.get(column, "") for column in columns])
        return path

    def export_records(self):
        return [{"Titel":r["title"], "Erscheinungsjahr":r["year"], "Meine Bewertung":r["rating"],
                 "Typ":r["media_type"], "Moviepilot-URL":r["url"], "Originaltitel":r["original_title"],
                 "Bewertungsdatum":display_date(r["rated_at"]), "Status":r["source_status"],
                 "Moviepilot-ID":r["moviepilot_id"], "Genre":r["genres"],
                 "Lokal importiert am":r["imported_at"], "Lokal zuletzt aktualisiert":max(r["modified_at"],r["personal_modified_at"]),
                 "Sehstatus":r["watch_status"], "Fortschritt":r["progress"], "Eigene Notiz":r["note"],
                 "Später prüfen":"Ja" if r["review_later"] else "Nein", "Herz-Favorit":"Ja" if r["favorite"] else "Nein",
                 "Im letzten Export":"Ja" if r["present"] else "Nein"} for r in self.get_rows(hidden=True)]

    def export_library_xlsx(self, path: Path):
        from moviepilot_exporter import write_combined_xlsx
        rows = self.export_records()
        headers = tuple(rows[0]) if rows else (*HEADERS, "Lokal importiert am", "Lokal zuletzt aktualisiert", "Sehstatus", "Fortschritt", "Eigene Notiz", "Später prüfen", "Herz-Favorit", "Im letzten Export")
        write_combined_xlsx(path, [r for r in rows if r["Typ"] == "Film"], [r for r in rows if r["Typ"] == "Serie"], headers=headers)
        return path

    def export_seasons_csv(self,path:Path):
        with open(path,"w",encoding="utf-8-sig",newline="") as file:
            wr=csv.writer(file,delimiter=";")
            wr.writerow(["Serie","Moviepilot-URL","Staffel","Gesehen","Staffel-Bewertung","Notiz"])
            for r in self.con.execute("""SELECT t.title,t.url,s.season,s.watched,s.rating,s.note FROM seasons s
                                          JOIN titles t ON t.url=s.url ORDER BY t.title,s.season"""):
                wr.writerow([r[0],r[1],r[2],"Ja" if r[3] else "Nein",("" if r[4] is None else str(r[4]).replace(".",",")),r[5]])
        return path


def normalized_title(s: str) -> str:
    s = unicodedata.normalize("NFKD",s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ß","ss").replace("&"," und ")
    s = re.sub(r"[^a-z0-9]+"," ",s)
    return " ".join(s.split())


def compare_recommendations(text: str, catalog: Catalog) -> list[dict]:
    items = catalog.get_rows(hidden=True)
    by_name = {}
    for item in items:
        for raw in (item["title"],item["original_title"]):
            name=normalized_title(raw)
            if name:
                by_name.setdefault(name,[]).append(item)
    all_names=list(by_name)
    findings=[]
    for ln in text.splitlines():
        raw=re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*","",ln).strip()
        if not raw:
            continue
        requested=raw
        key=normalized_title(re.sub(r"\s*\((?:19|20)\d{2}\)\s*$","",requested))
        matches=by_name.get(key,[])
        exact=bool(matches)
        if not matches:
            similar=difflib.get_close_matches(key,all_names,n=2,cutoff=.86)
            matches=[row for name in similar for row in by_name[name]][:3]
        if matches:
            status = "Schon bewertet" if exact else "Möglicher Treffer – prüfen"
            for x in matches:
                findings.append(dict(query=requested,status=status,title=x["title"],rating=x["rating"],
                                     watch_status=x["watch_status"],url=x["url"]))
        else:
            findings.append(dict(query=requested,status="Nicht in der Liste",title="",rating=None,watch_status="",url=""))
    return findings
