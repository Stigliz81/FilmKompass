"""Opt-in official product-version check. No installation, telemetry or shared jobs."""
import json
import re
import threading
import queue
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from tkinter import ttk, StringVar
import webbrowser
from app_info import APP_VERSION, BUILD_NUMBER

WEBSITE = 'https://stigliz81.github.io/FilmKompass/'
VERSION_URL = WEBSITE + 'version.json'
LIMIT = 16384
DAY = 86400
UNAVAILABLE = 'Versionsinformation derzeit nicht verfügbar.'


def version_number(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,5}(?:\.[0-9]{1,5}){1,3}', value):
        raise ValueError('Ungültige Produktversion')
    numbers = tuple(map(int, value.split('.')))
    return numbers + (0,) * (4-len(numbers))


def official_download(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 for c in value) or '\\' in value:
        raise ValueError('Keine offizielle Downloadadresse')
    p = urlsplit(value)
    if p.scheme != 'https' or p.query or p.fragment or '%' in p.path:
        raise ValueError('Keine offizielle HTTPS-Adresse')
    if value == WEBSITE:
        return value
    if p.netloc != 'github.com' or not re.fullmatch(
            r'/Stigliz81/FilmKompass/releases(?:/tag/v[0-9]+(?:\.[0-9]+){1,3}|/download/v[0-9]+(?:\.[0-9]+){1,3}/FilmKompass-[A-Za-z0-9._-]+\.zip)?', p.path):
        raise ValueError('Keine offizielle Downloadadresse')
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unerwartete Weiterleitung der Versionsdatei')


def fetch_version():
    request = Request(VERSION_URL, headers={'User-Agent': 'FilmKompass/'+APP_VERSION, 'Accept': 'application/json'})
    with build_opener(NoRedirect()).open(request, timeout=5) as response:
        if response.geturl() != VERSION_URL or response.status != 200:
            raise ValueError('Versionsdatei nicht verfügbar')
        raw = response.read(LIMIT+1)
        if len(raw) > LIMIT:
            raise ValueError('Versionsdatei zu groß')
    return json.loads(raw.decode('utf-8'))


def check_version(installed=APP_VERSION, fetch=fetch_version):
    try:
        info = fetch()
        if not isinstance(info, dict):
            raise ValueError('Ungültige Versionsdatei')
        current, public = version_number(installed), version_number(info.get('version'))
        url = official_download(info.get('download_url'))
        version = info['version']
        if public > current:
            state, message = 'newer', f'Neue öffentliche Version {version} verfügbar.'
        elif public == current:
            state, message = 'current', f'Installierte Version {installed} entspricht der öffentlichen Version.'
        else:
            state, message = 'ahead', f'Installierte Version {installed} ist neuer als die öffentliche Version {version}.'
        return dict(state=state, message=message, download_url=url, public_version=version)
    except (OSError, ValueError, TypeError, KeyError):
        return dict(state='unavailable', message=UNAVAILABLE, download_url=WEBSITE)


def automatic_due(settings, now):
    last = settings.get('last_attempt', 0)
    return settings.get('automatic') is True and (not isinstance(last, (int, float)) or last <= 0 or now-last >= DAY)


class ProgramUpdates:
    def __init__(self, manager, parent, *, fetch=fetch_version, clock=time.time):
        self.manager, self.fetch, self.clock = manager, fetch, clock
        self.events = queue.Queue()
        self.running = False
        self.closed = False
        self.download_url = WEBSITE
        options = manager.settings.get('program_updates', {})
        self.options = dict(options) if isinstance(options, dict) else {}
        from tkinter import BooleanVar
        self.automatic = BooleanVar(value=self.options.get('automatic') is True)
        self.message = StringVar(value='Noch nicht geprüft.')
        self.box = ttk.LabelFrame(parent, text='Programmupdates', padding=10)
        self.box.pack(fill='x', pady=(0, 16))
        ttk.Label(self.box, text=f'Installierte Produktversion: {APP_VERSION} · Build {BUILD_NUMBER}').pack(anchor='w')
        row = ttk.Frame(self.box); row.pack(fill='x', pady=5)
        self.button = ttk.Button(row, text='Auf Updates prüfen', command=self.start)
        self.button.pack(side='left', padx=(0, 8))
        self.download_button = ttk.Button(row, text='Downloadseite öffnen ↗', command=self.open_download)
        self.download_button.pack(side='left')
        label = ttk.Label(self.box, textvariable=self.message, wraplength=650)
        label.pack(fill='x', pady=(0, 5))
        label.bind('<Configure>', lambda e: label.configure(wraplength=max(200, e.width-5)))
        ttk.Checkbutton(self.box, text='Automatisch prüfen (höchstens einmal in 24 Stunden)',
                        variable=self.automatic, command=self.save_option).pack(anchor='w')
        self.job = manager.after(150, self.poll)
        self.auto_job = manager.after(1500, self.tick)

    def save_option(self):
        self.options['automatic'] = bool(self.automatic.get())
        self.persist()

    def persist(self):
        self.manager.settings['program_updates'] = dict(self.options)
        self.manager.save_settings()

    def tick(self):
        if not self.closed:
            if not self.running and automatic_due(self.options, self.clock()):
                self.start()
            self.auto_job = self.manager.after(60000, self.tick)

    def start(self):
        if self.running or self.closed:
            return
        self.running = True
        # Record attempts, including failures, so automatic offline retries stay <=1/day.
        self.options['last_attempt'] = self.clock()
        self.persist()
        self.button.configure(state='disabled')
        self.message.set('Öffentliche Version wird geprüft …')
        def work():
            try:
                result = check_version(fetch=self.fetch)
            except Exception:
                result = dict(state="unavailable", message=UNAVAILABLE, download_url=WEBSITE)
            self.events.put(result)
        threading.Thread(target=work, name='FilmKompass-updatecheck', daemon=True).start()

    def poll(self):
        if self.closed:
            return
        try:
            while True:
                result = self.events.get_nowait()
                self.running = False
                self.download_url = result['download_url']
                self.message.set(result['message'])
                self.button.configure(state='normal')
        except queue.Empty:
            pass
        self.job = self.manager.after(150, self.poll)

    def open_download(self):
        url = official_download(self.download_url)
        if not webbrowser.open(url):
            self.message.set('Der Standardbrowser konnte nicht geöffnet werden.')

    def close(self):
        self.closed = True
        self.manager.after_cancel(self.job)
        self.manager.after_cancel(self.auto_job)
