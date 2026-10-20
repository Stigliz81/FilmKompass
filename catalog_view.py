"""Compact view filters and the public six-column exchange format."""
from __future__ import annotations
import csv
import zipfile
from datetime import date, datetime
from pathlib import Path
from xml.sax.saxutils import escape
from manager_core import rating_date, display_date

PUBLIC_HEADERS = ('Typ', 'Titel', 'Jahr', 'Note', 'Bewertet am', 'Genre')
FILTER_LABELS = {'year':'Erscheinungsjahr', 'rating':'Meine Note', 'rated_year':'Bewertet im Jahr', 'rated_month':'Bewertet im Monat', 'genres':'Moviepilot Genre'}

def selection_caption(rows):
    """Read-only summary of the complete filtered snapshot, never a gallery page."""
    positive=[row['rating'] for row in rows if row['rating'] is not None and row['rating']>0]
    average=f'{sum(positive)/len(positive):.2f}'.replace('.',',') if positive else '–'
    films=sum(row['media_type']=='Film' for row in rows)
    series=sum(row['media_type']=='Serie' for row in rows)
    film_label='Film' if films==1 else 'Filme'
    series_label='Serie' if series==1 else 'Serien'
    return f'Aktuelle Auswahl: {films} {film_label} · {series} {series_label} · {len(rows)} Titel · Ø Note {average}'

def genres(value):
    return {v.strip() for v in str(value or '').split(',') if v.strip()}

def filter_values(rows):
    result={key:set() for key in FILTER_LABELS}
    for r in rows:
        if r['year']: result['year'].add(str(r['year']))
        if r['rating'] is not None: result['rating'].add(float(r['rating']))
        result['genres'].update(genres(r.get('genres')))
        dt=rating_date(r.get('rated_at'))
        if dt:
            result['rated_year'].add(dt[:4])
            result['rated_month'].add(dt[5:7])
    return {k:sorted(v, key=(lambda x: x.casefold()) if k=='genres' else None) for k,v in result.items()}

def filter_rows(rows, selections, genre_mode='or', excluded_genres=()):
    def matches(r):
        dt=rating_date(r.get('rated_at'))
        values={'year':str(r['year']), 'rating':r['rating'], 'rated_year':dt[:4], 'rated_month':dt[5:7], 'genres':genres(r.get('genres'))}
        wanted=selections.get('genres',set())
        available=values['genres']
        genre_match=not wanted or (wanted <= available if genre_mode=='and' else bool(wanted & available))
        return genre_match and not (set(excluded_genres) & available) and all(not chosen or values[k] in chosen for k,chosen in selections.items() if k!='genres')
    return [r for r in rows if matches(r)]

def public_records(rows):
    return [(r['media_type'],r['title'],r['year'],r['rating'],display_date(r['rated_at']),r.get('genres','')) for r in rows]

def suggest_export_path(folder, scope, extension, now=None):
    """Offer an unused name based on the chosen scope, never on row counts."""
    if scope not in ('all','filtered') or extension not in ('.xlsx','.csv'):
        raise ValueError('Ungültiger Exportumfang oder Dateityp.')
    stem='FilmKompass_Filmdaten_'+('Alle' if scope=='all' else 'Filter')
    target=Path(folder)/(stem+extension)
    if not target.exists():return target
    stem+='_'+(now or datetime.now()).strftime('%Y%m%d_%H%M')
    target=Path(folder)/(stem+extension);counter=2
    while target.exists():
        target=Path(folder)/(stem+f'_{counter}'+extension);counter+=1
    return target

def export_public(path: Path, rows, *, overwrite=True):
    records=public_records(rows)
    if path.suffix.lower()=='.csv':
        with path.open('w' if overwrite else 'x',encoding='utf-8-sig',newline='') as f:
            writer=csv.writer(f,delimiter=';')
            writer.writerow(PUBLIC_HEADERS)
            for row in records:
                row=list(row); row[3]=str(row[3]).replace('.',',')
                writer.writerow(row)
    elif path.suffix.lower()=='.xlsx':
        write_xlsx(path,records,overwrite=overwrite)
    else: raise ValueError('Bitte .csv oder .xlsx wählen.')
    return path

def write_xlsx(path,records,*,overwrite=True):
    ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
    lines=[]
    for number,row in enumerate([PUBLIC_HEADERS,*records],1):
        cells=[]
        for col,val in enumerate(row):
            pos=f'{chr(65+col)}{number}'
            if number>1 and col==3:
                cell=f'<c r="{pos}" s="1"><v>{float(val)}</v></c>'
            elif number>1 and col==4 and rating_date(val):
                serial=(date.fromisoformat(rating_date(val))-date(1899,12,30)).days
                cell=f'<c r="{pos}" s="2"><v>{serial}</v></c>'
            elif number>1 and col==2 and str(val).isdigit():
                cell=f'<c r="{pos}"><v>{int(val)}</v></c>'
            else:
                cell=f'<c r="{pos}" t="inlineStr"><is><t xml:space="preserve">{escape(str(val))}</t></is></c>'
            cells.append(cell)
        lines.append(f'<row r="{number}">'+''.join(cells)+'</row>')
    sheet=f'<worksheet xmlns="{ns}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols>'+''.join(f'<col min="{i}" max="{i}" width="{w}" customWidth="1"/>' for i,w in enumerate((12,48,10,10,18,40),1))+'</cols><sheetData>'+''.join(lines)+f'</sheetData><autoFilter ref="A1:F{len(records)+1}"/></worksheet>'
    parts={
        '[Content_Types].xml':'<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        '_rels/.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        'xl/workbook.xml':f'<workbook xmlns="{ns}" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Filmdaten" sheetId="1" r:id="rId1"/></sheets></workbook>',
        'xl/_rels/workbook.xml.rels':'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        'xl/styles.xml':f'<styleSheet xmlns="{ns}"><fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border/></borders><cellStyleXfs count="1"><xf/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="2" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/><xf numFmtId="14" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        'xl/worksheets/sheet1.xml':sheet}
    with zipfile.ZipFile(path,'w' if overwrite else 'x',zipfile.ZIP_DEFLATED) as z:
        for name,body in parts.items(): z.writestr(name,'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'+body)


def rating_year_counts(rows):
    """Calendar years from exact stored rating dates; never release/import years."""
    counts={};missing=0
    for row in rows:
        exact=rating_date(row['rated_at'])
        if exact:
            year=exact[:4];counts[year]=counts.get(year,0)+1
        else:missing+=1
    return sorted(counts.items()),missing


MONTH_NAMES = ('Januar','Februar','März','April','Mai','Juni','Juli','August','September','Oktober','November','Dezember')


def filter_display_values(key, values, excluded=(), mode='or'):
    """Display-only names; stored filter values and matching stay untouched."""
    if key=='rating':
        return [f'{float(value):g}'.replace('.',',') for value in sorted(values,key=float)]
    if key in ('year','rated_year','rated_month'):
        ordered=sorted(values,key=lambda value:(0,int(value)) if str(value).isdigit() else (1,str(value).casefold()))
        return [MONTH_NAMES[int(value)-1] if key=='rated_month' and str(value).isdigit() and 1<=int(value)<=12 else str(value) for value in ordered]
    desired=sorted(values,key=str.casefold)
    if len(desired)>1:desired[0]=('UND: ' if mode=='and' else 'ODER: ')+desired[0]
    return desired+['ohne '+value for value in sorted(excluded,key=str.casefold)]


def compact_filter_text(values, measure, width):
    """One value line with truthful overflow, independent of filtering."""
    if not values:return 'Alle'
    full=', '.join(values)
    if measure(full)<=width:return full
    for count in range(len(values)-1,0,-1):
        candidate=', '.join(values[:count])+f', +{len(values)-count} weitere'
        if measure(candidate)<=width:return candidate
    suffix=f', +{len(values)-1} weitere' if len(values)>1 else ''
    first=values[0]
    while first and measure(first+'…'+suffix)>width:first=first[:-1]
    return first+'…'+suffix if first else '…'
