"""Optionaler Moviepilot-Browserexport über Playwright; keine Konto-API, kein Login-Automatismus.

WICHTIG: Die Live-DOM-Struktur von Moviepilot ist nicht Bestandteil einer öffentlichen
API. Bei unbekannten Elementen und unvollständigen Seiten wird abgebrochen, nicht geraten.
"""
from __future__ import annotations

import csv
import json
import re
import time
import zipfile
from html.parser import HTMLParser
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse
from xml.sax.saxutils import escape

from app_info import APP_VERSION
from manager_core import HEADERS, normalize_row, normalized_url, validate_rating, rating_date

PROFILE_RE = re.compile(r"^[a-zA-Z0-9_.-]{2,70}$")
BASE_URL = "https://www.moviepilot.de"

# Executes only in the normal user's browser session. It collects *table rows*,
# using the column explicitly labelled 'Meine Bewertung' (never the public average).
DOM_SNAPSHOT_JS = r"""() => {
  const plain = (el) => (el?.innerText || el?.textContent || '').trim();
  const norm = (s) => (s || '').replace(/\s+/g, ' ').trim();
  const isMedia = (href, kind) => {
    try { const u = new URL(href, location.href); return u.hostname === 'www.moviepilot.de' && u.pathname.startsWith(kind === 'Film' ? '/movies/' : '/serie/'); }
    catch { return false; }
  };
  const kind = location.pathname.endsWith('/series') ? 'Serie' : 'Film';
  const markers = [...document.querySelectorAll('h1,h2,h3')].map(plain).join(' ') || plain(document.body).slice(0,500);
  let expected = null;
  const rx = kind === 'Film' ? /(\d[\d.,]*)\s+Filme\b/i : /(\d[\d.,]*)\s+Serien\b/i;
  const mt = markers.match(rx);
  if(mt) expected = Number(mt[1].replace(/[.,]/g,''));

  function scoreCandidates(cell) {
    if (!cell) return [];
    const list = [];
    for (const el of [cell, ...cell.querySelectorAll('*')]) {
      for (const attr of ['data-my-rating','data-user-rating','data-rating','data-score','data-value','aria-valuenow','aria-label','title','data-original-title']) {
        const v = el.getAttribute?.(attr);
        if (v) list.push(v);
      }
    }
    list.push(plain(cell));
    return list;
  }
  const rows = [];
  const seen = new Set();
  const tables = [...document.querySelectorAll('table')];
  for (const table of tables) {
    const thead = [...table.querySelectorAll('thead th')].map(x => norm(plain(x)).toLowerCase());
    const header = thead.length ? thead : [...(table.querySelector('tr')?.querySelectorAll('th') || [])].map(x => norm(plain(x)).toLowerCase());
    const myIdx = header.findIndex(x => /meine\s+bewertung/.test(x));
    if (myIdx < 0) continue; // Never confuse general 'Bewertung' with the user's own rating.
    const dateIdx = header.findIndex(x => /datum|bewertet\s+am/.test(x));
    for (const tr of table.querySelectorAll('tr')) {
      const cols = [...tr.querySelectorAll(':scope > td')];
      if (cols.length <= myIdx) continue;
      const anchor = [...tr.querySelectorAll('a[href]')].find(a => isMedia(a.href,kind));
      if (!anchor) continue;
      const url = new URL(anchor.href, location.href).href;
      if (seen.has(url)) continue;
      seen.add(url);
      const textTitle = norm(plain(anchor)) || norm(anchor.getAttribute('title')) || norm(anchor.querySelector('img')?.getAttribute('alt'));
      const first = plain(cols[0]);
      const yearMatch = first.match(/\b(?:18|19|20)\d{2}\b/);
      const dateMatch = dateIdx >= 0 ? plain(cols[dateIdx]).match(/\b\d{1,2}\.\d{1,2}\.\d{4}\b/) : null;
      const id = tr.getAttribute('data-id') || anchor.getAttribute('data-id') || '';
      rows.push({url, title:textTitle, year:yearMatch?.[0] || '', date:dateMatch?.[0] || '', id, ratings:scoreCandidates(cols[myIdx])});
    }
  }
  // Some layouts display table semantics via ARIA instead of native <table> tags.
  if (!rows.length) {
    for (const wrap of document.querySelectorAll('[role="table"],[role="grid"]')) {
      const headers = [...wrap.querySelectorAll('[role="columnheader"]')].map(x => norm(plain(x)).toLowerCase());
      const myIdx = headers.findIndex(x => /meine\s+bewertung/.test(x));
      if (myIdx < 0) continue;
      const dateIdx = headers.findIndex(x => /datum|bewertet\s+am/.test(x));
      for (const node of wrap.querySelectorAll('[role="row"]')) {
        const cells = [...node.querySelectorAll(':scope > [role="cell"],:scope > [role="gridcell"]')];
        if (cells.length <= myIdx) continue;
        const anchor = [...node.querySelectorAll('a[href]')].find(a => isMedia(a.href,kind));
        if (!anchor) continue;
        const url = new URL(anchor.href, location.href).href;
        if (seen.has(url)) continue;
        seen.add(url);
        const first = plain(cells[0]);
        const yearMatch = first.match(/\b(?:18|19|20)\d{2}\b/);
        const dateMatch = dateIdx>=0 ? plain(cells[dateIdx]).match(/\b\d{1,2}\.\d{1,2}\.\d{4}\b/) : null;
        rows.push({url,title:norm(plain(anchor))||norm(anchor.getAttribute('title'))||norm(anchor.querySelector('img')?.alt),year:yearMatch?.[0]||'',date:dateMatch?.[0]||'',id:node.getAttribute('data-id')||'',ratings:scoreCandidates(cells[myIdx])});
      }
    }
  }
  const nextAnchor = [...document.querySelectorAll('a[href]')].find(a =>
    (a.rel?.includes('next') || /^(weiter|nächste|next|›|»|→)$/i.test(norm(plain(a)))) &&
    !a.closest('[aria-disabled="true"],.disabled') &&
    new URL(a.href,location.href).pathname === location.pathname);
  const nextButton = [...document.querySelectorAll('button,[role="button"]')].find(b =>
    /^(weiter|nächste|next|›|»|→)$/i.test(norm(plain(b))) && !b.disabled && b.getAttribute('aria-disabled') !== 'true');
  return {kind, expected, rows, nextHref: nextAnchor?.href || '', nextButtonText:nextButton ? norm(plain(nextButton)) : '',
    pageTitle:document.title, browserUrl:location.href,
    headerDetected:tables.some(t=>[...t.querySelectorAll('th')].some(e=>/meine\s+bewertung/i.test(plain(e))))};
}"""


class ExportError(RuntimeError):
    """Export cannot be trusted; no incomplete file is imported."""


@dataclass(frozen=True)
class ExportResult:
    files: tuple[Path, Path, Path]
    movies: int
    series: int
    folder: Path


def validate_profile(value: str) -> str:
    user = value.strip()
    if "://" in user or user.startswith(("www.moviepilot.de/", "moviepilot.de/")):
        parsed = urlparse(user if "://" in user else "https://" + user)
        match = re.fullmatch(r"/users/([^/]+)(?:/rated/(?:movies|series))?/?", parsed.path)
        if parsed.scheme != "https" or parsed.netloc.lower() not in ("www.moviepilot.de", "moviepilot.de") or not match:
            raise ValueError("Bitte einen Moviepilot-Profillink oder Bewertungslisten-Link eingeben.")
        user = match.group(1)
    if not PROFILE_RE.fullmatch(user):
        raise ValueError("Profilname: nur Buchstaben, Zahlen, Punkt, _ und Bindestrich erlaubt (2–70 Zeichen).")
    return user


def extract_rating(candidates: list[str]) -> float:
    """Return user's explicit 0..10 score; never infer from star graphics."""
    for value in candidates:
        s = str(value or "").strip()
        if not s:
            continue
        lower = s.lower()
        if re.search(r"\b(hassfilm|totenkopf)\b", lower):
            return 0.0
        if re.search(r"\b(lieblingsfilm|herzbewertung)\b", lower):
            return 10.0
        one = re.fullmatch(r"\s*(10(?:[.,]0)?|[0-9](?:[.,][05])?)\s*(?:(?:/|von)\s*10)?\s*", s, re.I)
        if one:
            return validate_rating(one.group(1))
        labelled = re.search(r"(?:meine bewertung|deine bewertung|bewertet mit|user.rating|pers[oö]nliche bewertung)\s*:?\s*(10(?:[.,]0)?|[0-9](?:[.,][05])?)(?![\d.,])", lower)
        if labelled:
            return validate_rating(labelled.group(1))
    raise ExportError("Die persönliche Bewertung ist nicht eindeutig auslesbar (DOM geändert?).")


def record_from_dom(entry: dict, kind: str) -> dict:
    try:
        normalized = {
            "Titel": str(entry.get("title") or "").strip(),
            "Erscheinungsjahr": str(entry.get("year") or "").strip(),
            "Meine Bewertung": extract_rating(entry.get("ratings") or []),
            "Typ": kind,
            "Moviepilot-URL": entry.get("url") or "",
            "Originaltitel": "",
            "Bewertungsdatum": str(entry.get("date") or ""),
            "Status": "OK",
            "Moviepilot-ID": str(entry.get("id") or ""),
        }
        check = normalize_row(normalized)
        return {**normalized, "Moviepilot-URL": check["url"]}
    except (ValueError, ExportError) as exc:
        raise ExportError(f"Fehler beim Titel {entry.get('title') or entry.get('url') or '<unbekannt>'}: {exc}") from exc


def _next_page(page, info: dict) -> bool:
    if info.get("nextHref"):
        address = info["nextHref"]
        if urlparse(address).hostname != "www.moviepilot.de":
            raise ExportError("Unsicheres Ziel in der Seitennavigation")
        page.goto(address, wait_until="domcontentloaded", timeout=45_000)
        return True
    name = info.get("nextButtonText")
    if name:
        button = page.get_by_role("button", name=name, exact=True).first
        button.click(timeout=10_000)
        return True
    return False


def _diagnostics(page, diagnostic_folder: Path, tag: str) -> None:
    diagnostic_folder.mkdir(parents=True, exist_ok=True)
    safe_tag = re.sub(r"[^A-Za-z0-9_-]", "_", tag)[:64]
    try:
        page.screenshot(path=str(diagnostic_folder / f"{safe_tag}.png"), full_page=False)
        (diagnostic_folder / f"{safe_tag}.html").write_text(page.content(), encoding="utf-8")
    except Exception:
        pass


def _scrape_type(page, username: str, kind: str, notify: Callable[[str], None],
                 diagnostic_folder: Path, resume: Callable[[], bool] | None = None) -> list[dict]:
    slug = "movies" if kind == "Film" else "series"
    url = f"{BASE_URL}/users/{username}/rated/{slug}"
    notify(f"{kind}: Profilseite wird geöffnet …")
    page.goto(url, wait_until="domcontentloaded", timeout=45_000)
    expected = None
    seen: dict[str,dict] = {}
    signatures = set()
    for number in range(1, 201):
        info = None
        for attempt in range(8):
            page.wait_for_timeout(600 if attempt else 1200)
            info = page.evaluate(DOM_SNAPSHOT_JS)
            if info.get("rows") or info.get("expected") == 0:
                break
        if info and info.get("expected") == 0 and not info.get("rows"):
            return []
        if number == 1 and not info.get("rows") and resume:
            notify(f"{kind}: keine Bewertungstabelle. Bitte ggf. im Browser anmelden und 'Weiter' drücken.")
            if resume():
                page.goto(url, wait_until="domcontentloaded", timeout=45_000)
                page.wait_for_timeout(1600)
                info = page.evaluate(DOM_SNAPSHOT_JS)
        if not info or not info.get("rows"):
            _diagnostics(page, diagnostic_folder, f"{slug}_seite_{number}_leer")
            raise ExportError(f"{kind}, Seite {number}: Keine auslesbaren Bewertungen. Diagnose im lokalen Ordner 'diagnose'.")
        count = info.get("expected")
        if count is not None:
            if expected is not None and expected != count:
                raise ExportError(f"{kind}: wechselnde Gesamtzahl ({expected} → {count}) während des Exports.")
            expected = count
        signature = tuple(x.get("url") for x in info["rows"])
        if signature in signatures:
            raise ExportError(f"{kind}: Seitennavigation wiederholt dieselben Titel (Seite {number}).")
        signatures.add(signature)
        for entry in info["rows"]:
            item = record_from_dom(entry, kind)
            key = normalized_url(item["Moviepilot-URL"])
            if key in seen:
                raise ExportError(f"{kind}: doppelte URL für {item['Titel']}")
            seen[key] = item
        notify(f"{kind}: Seite {number} • {len(seen)} von {expected if expected is not None else '?'} erfasst")
        if expected is not None and len(seen) > expected:
            raise ExportError(f"{kind}: mehr Titel gefunden als die angezeigte Gesamtzahl ({expected}).")
        if expected is not None and len(seen) == expected:
            break
        if not _next_page(page, info):
            break
        time.sleep(0.8)
    if expected is None:
        raise ExportError(f"{kind}: Gesamtzahl nicht gefunden. Export wird vorsichtshalber nicht übernommen.")
    if len(seen) != expected:
        _diagnostics(page, diagnostic_folder, f"{slug}_unvollstaendig")
        raise ExportError(f"{kind}: nur {len(seen)} von {expected} Titeln erfasst. Nichts wird importiert.")
    return list(seen.values())


def write_moviepilot_csv(path: Path, rows: list[dict]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=HEADERS, delimiter=";")
        writer.writeheader()
        for row in rows:
            data = dict(row)
            data["Meine Bewertung"] = str(data["Meine Bewertung"]).replace(".", ",")
            writer.writerow({k: data.get(k, "") for k in HEADERS})


def _excel_col(n: int) -> str:
    value = ""
    while n:
        n, rem = divmod(n - 1, 26)
        value = chr(65 + rem) + value
    return value


def _worksheet_xml(rows: list[list[object]]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
             '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"/></sheetViews><sheetData>']
    for i, row in enumerate(rows, 1):
        parts.append(f'<row r="{i}">')
        for j, value in enumerate(row, 1):
            if value is None or str(value) == "":
                continue
            ref = f"{_excel_col(j)}{i}"
            if i > 1 and (j == 3 or (j == 2 and len(row) > 5)) and isinstance(value, (int, float)):
                parts.append(f'<c r="{ref}" s="1"><v>{value:g}</v></c>')
            else:
                text = escape(str(value), {'"': '&quot;', "'": '&apos;'})
                parts.append(f'<c r="{ref}" t="inlineStr"><is><t>{text}</t></is></c>')
        parts.append('</row>')
    parts.append('</sheetData></worksheet>')
    return "".join(parts)


def write_combined_xlsx(path: Path, films: list[dict], series: list[dict], headers=HEADERS) -> None:
    """Minimal OOXML. Ratings stay *numeric*, never Excel date serials."""
    combined = films + series
    sheets = [
        ("Gesamt", combined), ("Filme", films), ("Serien", series)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        xml_ct = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + ''.join(f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>' for i in range(1,4)) + '</Types>'
        z.writestr('[Content_Types].xml',xml_ct)
        z.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>'+''.join(f'<sheet name="{name}" sheetId="{i}" r:id="rId{i}"/>' for i,(name,_) in enumerate(sheets,1))+'</sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,4))+'<Relationship Id="rId4" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        z.writestr('xl/styles.xml','<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><numFmts count="1"><numFmt numFmtId="164" formatCode="0.0"/></numFmts><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs></styleSheet>')
        for i,(_,items) in enumerate(sheets,1):
            rows = [list(headers)] + [[r.get(k,"") for k in headers] for r in items]
            z.writestr(f'xl/worksheets/sheet{i}.xml',_worksheet_xml(rows))


@contextmanager
def browser_session_lock(folder: Path):
    marker = folder / ".moviepilot-browser-active"
    try:
        with marker.open("x", encoding="utf-8") as handle:
            handle.write("Moviepilot Manager browser export active")
    except FileExistsError as exc:
        raise ExportError("Browserprofil ist bereits als geöffnet markiert. Andere Browserexporte zuerst schließen.") from exc
    try:
        yield
    finally:
        marker.unlink(missing_ok=True)


def run_browser_export(username: str, folder: Path, browser_folder: Path, notify: Callable[[str],None],
               resume: Callable[[], bool] | None = None) -> ExportResult:
    """Export both types. Files are only published after *both* page counts validate."""
    username = validate_profile(username)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ExportError("Playwright fehlt. Einmalig 'exporter_einrichten_windows.bat' ausführen.") from exc
    folder = Path(folder)
    browser_folder = Path(browser_folder)
    browser_folder.mkdir(parents=True, exist_ok=True)
    diagnostics = folder / "diagnose"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    staging = folder / f"_unvollstaendig_{stamp}"
    staging.mkdir(parents=True, exist_ok=True)
    try:
        with browser_session_lock(browser_folder), sync_playwright() as playwright:
            notify("Chromium startet. Falls nötig, melde dich bei Moviepilot im Browser an.")
            try:
                context = playwright.chromium.launch_persistent_context(
                    user_data_dir=str(browser_folder), headless=False, viewport={"width":1450,"height":920},
                    locale="de-DE", slow_mo=50)
            except Exception as exc:
                raise ExportError("Chromium konnte nicht gestartet werden. Bitte den Exporter installieren und ein evtl. offenes Profil-Fenster schließen.") from exc
            try:
                page = context.pages[0] if context.pages else context.new_page()
                films = _scrape_type(page, username, "Film", notify, diagnostics, resume)
                series = _scrape_type(page, username, "Serie", notify, diagnostics, resume)
            finally:
                context.close()
        filename_f = staging / "Moviepilot_Filme.csv"
        filename_s = staging / "Moviepilot_Serien.csv"
        filename_x = staging / "Moviepilot_Bewertungen.xlsx"
        write_moviepilot_csv(filename_f, films)
        write_moviepilot_csv(filename_s, series)
        write_combined_xlsx(filename_x, films, series)
        # Parse our own output using the exact same validator as the manager.
        from manager_core import read_export
        parsed = read_export(filename_x)
        if len(parsed) != len(films) + len(series):
            raise ExportError("Excel-Datei stimmt nach Prüfung nicht mit den CSV-Daten überein.")
        completed = folder / f"Moviepilot_Export_{stamp}"
        staging.rename(completed)
        notify(f"Export abgeschlossen: {len(films)} Filme und {len(series)} Serien")
        return ExportResult((completed / filename_f.name, completed / filename_s.name, completed / filename_x.name),len(films),len(series),completed)
    except Exception:
        # Keep partial files/diagnostics locally for investigation, never import.
        raise


def fetch_page_props(url: str) -> dict:
    from urllib.request import Request, urlopen
    from urllib.error import URLError
    error = None
    for attempt in range(3):
        try:
            request = Request(url, headers={"User-Agent": f"MoviepilotManager/{APP_VERSION} (personal ratings backup)", "Accept-Language": "de-DE"})
            with urlopen(request, timeout=35) as response:
                html = response.read().decode("utf-8")
            match = re.search(r"<script[^>]+id=[\"']__NEXT_DATA__[\"'][^>]*>(.*?)</script>", html, re.S)
            if not match:
                raise ExportError("Keine strukturierten Bewertungsdaten gefunden. Profil muss öffentlich sein; alternativ CSV/XLSX importieren.")
            props = json.loads(match.group(1))["props"]["initialProps"]["pageProps"]
            if not isinstance(props, dict):
                raise ValueError("Ungültige Seitendaten")
            return props
        except (URLError, TimeoutError, ConnectionError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(attempt + 1)
        except (ValueError, KeyError, TypeError) as exc:
            raise ExportError("Moviepilot-Seitenformat wurde nicht erkannt.") from exc
    raise ExportError(f"Moviepilot konnte nicht geladen werden: {error}")


class GenreParser(HTMLParser):
    """Read only explicitly marked genre spans, never infer from synopsis text."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.parts = []
        self.genres = []

    def handle_starttag(self, tag, attrs):
        if self.depth:
            self.depth += 1
        elif dict(attrs).get("itemprop") == "genre":
            self.depth = 1
            self.parts = []

    def handle_endtag(self, tag):
        if self.depth:
            self.depth -= 1
            if not self.depth:
                value = " ".join("".join(self.parts).split())
                if value and value not in self.genres:
                    self.genres.append(value)

    def handle_data(self, data):
        if self.depth:
            self.parts.append(data)


def source_metadata(item: dict) -> tuple[str, str]:
    date = rating_date(item.get("dateOfRating")) or rating_date((item.get("rating") or {}).get("createdAt"))
    parser = GenreParser()
    for fragment in item.get("metaInformation") or []:
        if isinstance(fragment, str):
            parser.feed(fragment)
    return date, ", ".join(parser.genres)


def fetch_ratings(username: str, kind: str, notify, fetch=None, progress=None) -> list[dict]:
    fetch = fetch or fetch_page_props
    slug = "movies" if kind == "Film" else "series"
    base = f"{BASE_URL}/users/{validate_profile(username)}/rated/{slug}"
    rows, seen = [], set()
    expected = pages = None
    number = 1
    while True:
        props = fetch(f"{base}?page={number}&itemsPerPage=48&layout=detailed")
        if props.get("isPrivate"):
            raise ExportError("Dieses Profil ist privat. Bitte einen bestehenden CSV/XLSX-Export importieren.")
        total, count = props.get("itemsCount"), props.get("pagesCount")
        if type(total) is not int or type(count) is not int or total < 0 or count < 0 or count > 10000 or (total > 0 and count == 0):
            raise ExportError("Gesamtzahl oder Seitenzahl fehlen bzw. sind ungültig.")
        if expected is None:
            expected, pages = total, max(1, count)
        elif total != expected or max(1, count) != pages:
            raise ExportError("Die Liste hat sich während des Abrufs geändert. Bitte erneut laden.")
        items = props.get("items")
        if not isinstance(items, list):
            raise ExportError("Ungültige Bewertungsliste.")
        for item in items:
            try:
                raw = item["rating"]["value"]
                if isinstance(raw, bool) or raw is None:
                    raise ValueError("Bewertung fehlt")
                score = validate_rating(float(raw) / 10)
                path = item["path"]
                prefix = "/movies/" if kind == "Film" else "/serie/"
                if not path.startswith(prefix):
                    raise ValueError("Falscher Medientyp oder ungültige URL")
                years = re.findall(r"\b(?:18|19|20)\d{2}\b", str(item.get("metaYearAndCountry") or ""))
                date, genres = source_metadata(item)
                row = record_from_dom({"title": item["title"], "url": BASE_URL + path,
                    "ratings": [str(score)], "year": years[-1] if years else "",
                    "date": date, "id": item.get("id") or ""}, kind)
                row["Originaltitel"] = str(item.get("originalTitle") or "")
                row["Genre"] = genres
                if row["Moviepilot-URL"] in seen:
                    raise ValueError("Doppelte URL / wiederholte Seite")
                seen.add(row["Moviepilot-URL"])
                rows.append(row)
            except (KeyError, TypeError, ValueError) as exc:
                raise ExportError(f"Ungültiger Eintrag auf {kind}-Seite {number}: {exc}") from exc
        notify(f"{kind}: Seite {number}/{pages} · {len(rows)}/{expected} Bewertungen")
        if progress:
            progress(dict(kind=kind, page=number, pages=pages, loaded=len(rows), expected=expected))
        if number >= pages:
            break
        number += 1
        time.sleep(0.15)
    if len(rows) != expected:
        raise ExportError(f"{kind}: nur {len(rows)} von {expected} geladen; kein Import.")
    return rows


def run_export(username: str, folder: Path, browser_folder=None, notify=lambda msg: None, resume=None, progress=None) -> ExportResult:
    """Integrated HTTPS download; publish files only after both lists validate."""
    username = validate_profile(username)
    notify("Verbindung zu Moviepilot wird hergestellt")
    films = fetch_ratings(username, "Film", notify, progress=progress)
    notify("Serienseiten werden eingelesen")
    series = fetch_ratings(username, "Serie", notify, progress=progress)
    notify("Daten werden geprüft und Exportdateien werden gespeichert")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    import tempfile
    staging = Path(tempfile.mkdtemp(prefix="_unvollstaendig_", dir=folder))
    film = staging / "Moviepilot_Filme.csv"
    serial = staging / "Moviepilot_Serien.csv"
    xlsx = staging / "Moviepilot_Bewertungen.xlsx"
    write_moviepilot_csv(film, films)
    write_moviepilot_csv(serial, series)
    write_combined_xlsx(xlsx, films, series)
    from manager_core import read_export
    if (films or series) and len(read_export(xlsx)) != len(films) + len(series):
        raise ExportError("Exportprüfung fehlgeschlagen; kein Import.")
    completed = folder / ("Moviepilot_Export_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    staging.rename(completed)
    return ExportResult(tuple(completed / p.name for p in (film, serial, xlsx)), len(films), len(series), completed)
