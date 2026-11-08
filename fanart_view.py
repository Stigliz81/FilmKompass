"""Small Fanart settings/selection UI, using the existing Manager task queue."""
from pathlib import Path
import sys
import threading
import queue
import tkinter as tk
from tkinter import ttk, messagebox
import webbrowser
from PIL import Image, ImageTk, ImageOps

from fanart_covers import (CoverError, CoverService, Credentials, FanartCache,
                          external_id, project_key, _key, missing_covers, CoverRequestGate, request_json)
from user_images import download_image
from parallel_covers import NetworkGate, ConcurrentCoverService, parallel_missing_covers


class FanartController:
    SOURCES={'Automatisch':None,'IMDb':'imdb','Wikidata':'wikidata','TheTVDB':'tvdb','TMDB (vorhandene ID)':'tmdb'}

    def __init__(self,manager,resource_root):
        self.manager=manager
        self.project_folder=Path(sys.executable).parent if getattr(sys,'frozen',False) else Path(resource_root)
        self.cache=FanartCache(manager.db.db_path.parent,enabled=self.options().get('enabled') is True)
        self.dialog=None;self.token=0;self.result=None;self.row=None;self.photo=None
        self.batch_cancel=threading.Event();self.batch_running=False
        previous=self.cache.data.get('last_batch',{})
        restored=100*previous.get('checked',0)/max(1,previous.get('total',0)) if isinstance(previous,dict) else 0
        self.progress_value=tk.DoubleVar(master=manager,value=restored)
        self.auto_state=manager.settings.get('cover_auto','pending' if self.cache.enabled else 'ready')
        self._library_signature=None
        self._auto_job=manager.after(1200,self.auto_tick)
        self.events=queue.Queue();self._cover_job=manager.after(100,self.poll_covers)

    def poll_covers(self):
        try:
            while True:
                kind,payload=self.events.get_nowait()
                if kind=='measure':self.update_progress(payload)
                elif kind=='done':self.handle(payload)
        except queue.Empty:pass
        self._cover_job=self.manager.after(100,self.poll_covers)

    def auto_tick(self):
        if not getattr(self,'_closing',False) and not self.batch_running and (not self.manager._export_running or getattr(self.manager,'_task_is_list',False)) and self.cache.enabled:
            rows=self.manager.db.get_rows(hidden=True)
            signature=tuple((r['url'],tuple(self.cache.signature(r))) for r in rows)
            if self._library_signature is not None and signature!=self._library_signature and self.auto_state not in ('paused','cancelled','error'):
                self.set_auto('pending')
            self._library_signature=signature
            if self.auto_state=='completed' and any(self.cache.data.get('batch_done',{}).get(r['url'],{}).get('signature')!=self.cache.signature(r) for r in rows):self.set_auto('pending')
            if self.auto_state in ('pending','running'):self.start_batch(automatic=True)
        self._auto_job=self.manager.after(2000,self.auto_tick)

    def set_auto(self,state):
        self.auto_state=state;self.manager.settings['cover_auto']=state;self.manager.save_settings()

    def update_progress(self,value):
        stats=value.get('stats',{})
        percent=100*value['page']/max(1,value['expected'])
        self.progress_value.set(percent)
        self.manager.cover_main_text.set(f"Cover: {value['page']} / {value['expected']} geprüft · {value['loaded']} neu · {stats.get('skipped',0)} übersprungen")
        self.cover_status.set(f"Läuft · {value['page']}/{value['expected']} · neu {stats.get('found',0)} · übersprungen {stats.get('skipped',0)} · unklar {stats.get('unclear',0)} · ohne Treffer {stats.get('not_found',0)} · Fehler {stats.get('errors',0)}\n{value.get('title','')}")

    def project_signature(self):
        import hashlib
        try:key=project_key(self.project_folder)
        except CoverError:return ''
        personal=_key(self.options().get('personal_key',''))
        value=key+'|'+personal if personal else key
        return hashlib.sha256(value.encode()).hexdigest() if value else ''

    def show_setup(self,visible=True):
        if visible:
            self.setup_frame.pack(fill='x',before=self.credit,pady=(3,5))
        else:self.setup_frame.pack_forget()

    def toggle_setup(self):
        self.show_setup(not bool(self.setup_frame.winfo_manager()))

    def invalidate_connection(self):
        options=dict(self.options());options.pop('verified_project',None)
        self.manager.settings['fanart']=options;self.manager.save_settings()
        self.connection_summary.set('Verbindung fehlt – API Key prüfen');self.show_setup(True)

    def pause_batch(self,resume=False):
        if resume:self._closing=True
        self.set_auto('pending' if resume else 'paused');self.batch_cancel.set()
        self.cover_status.set('Pausiert – laufende Anfrage wird beendet.');self.sync_pause()

    def resume_batch(self):
        self.set_auto('pending');self.start_batch(automatic=True)

    def setup_project(self):
        if self.manager._busy_guard():return
        try:
            value=_key(self.project_input.get())
            if value:
                from app_data import _not_link
                import json,os
                if os.environ.get('FANART_TV_PROJECT_KEY') and project_key(self.project_folder)!=value:
                    raise CoverError('Eine Umgebungsvariable hat Vorrang. Bitte die erweiterte Konfigurationshilfe prüfen.')
                target=self.project_folder/'fanart.local.json';_not_link(target)
                data=json.loads(target.read_text(encoding='utf-8')) if target.exists() else {}
                if not isinstance(data,dict):raise CoverError('Lokale Konfiguration ungültig.')
                data['project_key']=value
                target.write_text(json.dumps(data),encoding='utf-8')
            Credentials(project_key(self.project_folder)).headers()
            self.project_input.set('')
            self.cover_status.set('Verbindung wird geprüft …')
            self._setup_check=True
            self.test_connection()
        except (CoverError,OSError,ValueError) as error:
            self.cover_status.set('API Key einrichten');self.status.set(str(error))

    def setup_personal(self):
        if self.manager._busy_guard():return
        try:
            personal=_key(self.personal.get())
            Credentials(project_key(self.project_folder),personal).headers()
            self.manager.settings['fanart']=dict(self.options(),personal_key=personal)
            self.manager.save_settings()
            self._setup_check=True
            self.cover_status.set('Verbindung wird geprüft …')
            self.test_connection()
        except (CoverError,OSError,ValueError) as error:
            self.status.set(str(error));self.show_setup(True)

    def toggle_advanced(self):
        if self.advanced.winfo_manager():
            self.advanced.pack_forget();self.advanced_toggle.configure(text='▸ Erweiterte Einstellungen')
        else:
            self.advanced.pack(fill='x',pady=(6,0));self.advanced_toggle.configure(text='▾ Erweiterte Einstellungen')

    def sync_pause(self):
        self.cancel_button.configure(text='Pausieren' if self.batch_running else 'Fortsetzen',
            command=self.pause_batch if self.batch_running else self.resume_batch,state='normal')
        if hasattr(self,'progress_row'):
            if self.batch_running or self.auto_state in ('paused','cancelled','error') and self.cache.enabled:
                self.progress_row.pack(fill='none',anchor='w',pady=6,before=self.progress_anchor)
            else:self.progress_row.pack_forget()
        if hasattr(self.manager,'cover_main_frame'):
            if not self.batch_running:self.manager.cover_main_text.set('Cover angehalten – vorhandene Ergebnisse bleiben erhalten. Details unter Einstellungen & Daten.')
            self.manager.cover_main_action.configure(text='Pausieren' if self.batch_running else 'Fortsetzen',command=self.pause_batch if self.batch_running else self.resume_batch)
            self.manager._sync_cover_progress()

    def options(self):
        value=self.manager.settings.get('fanart',{})
        return value if isinstance(value,dict) else {}

    def build_settings(self,parent):
        box=ttk.Frame(parent,padding=(0,8));box.pack(fill='x',pady=(0,12))
        ttk.Label(box,text='Onlinecover',style='Section.TLabel').pack(anchor='w')
        self.enabled=tk.BooleanVar(value=self.cache.enabled)
        ttk.Style(self.manager).configure('Cover.TCheckbutton',font=('Segoe UI Semibold',10))
        ttk.Checkbutton(box,text='Onlinecover automatisch laden',style='Cover.TCheckbutton',variable=self.enabled,command=self.save_settings).pack(anchor='w',pady=(8,4))
        ttk.Label(box,text='Fehlende Cover werden automatisch geladen. Eigene Bilder bleiben erhalten.',style='Muted.TLabel',wraplength=650).pack(anchor='w',pady=4)
        self.personal=tk.StringVar(value=str(self.options().get('personal_key') or ''))
        try:configured=bool(project_key(self.project_folder) or _key(self.personal.get()))
        except CoverError:configured=False
        initial='API Key einrichten' if self.cache.enabled and not configured else {'paused':'Pausiert','cancelled':'Pausiert','completed':'Abgeschlossen','error':'Fehler'}.get(self.auto_state,'Bereit')
        self.cover_status=tk.StringVar(value=initial)
        ttk.Label(box,textvariable=self.cover_status,wraplength=650).pack(fill='x')
        row=ttk.Frame(box);row.pack(fill='x',pady=6)
        self.progress_row=row
        row.pack_configure(fill='none',anchor='w');row.pack_propagate(False)
        def fit(event):
            factor=float(self.manager.tk.call('tk','scaling'))/(96/72)
            row.configure(width=max(100,min(event.width,round(800*factor))),height=max(32,round(32*factor)))
        box.bind('<Configure>',fit,add='+')
        self.cover_progress=ttk.Progressbar(row,variable=self.progress_value,maximum=100);self.cover_progress.pack(side='left',fill='x',expand=True,padx=(0,8))
        self.cancel_button=ttk.Button(row,text='Fortsetzen',command=self.resume_batch);self.cancel_button.pack(side='right')
        self.batch_button=ttk.Button(box,command=self.start_batch)  # Internal compatibility, never displayed.
        self.progress_anchor=ttk.Separator(box);self.progress_anchor.pack(fill='x',pady=8)
        verified=configured and self.options().get('verified_project')==self.project_signature()
        self.connection_summary=tk.StringVar(value='Fanart.tv verbunden' if verified else 'API Key vorhanden – Verbindung prüfen' if configured else 'Fanart.tv einrichten')
        connection=ttk.Frame(box);connection.pack(fill='x')
        ttk.Label(connection,textvariable=self.connection_summary).pack(side='left')
        ttk.Button(connection,text='API Key ändern',command=self.toggle_setup,style='Compact.TButton').pack(side='left',padx=8)
        self.setup_frame=ttk.Frame(box)
        keyrow=ttk.Frame(self.setup_frame);keyrow.pack(fill='x',pady=5)
        ttk.Label(keyrow,text='Persönlicher Fanart.tv API Key').pack(side='left',padx=(0,8))
        self.project_input=tk.StringVar()
        self.project_entry=ttk.Entry(keyrow,textvariable=self.personal,show='*',width=28)
        self.project_entry.pack(side='left',fill='x',expand=True)
        self.save_project_button=ttk.Button(self.setup_frame,text='Speichern und Verbindung prüfen',command=self.setup_personal)
        self.save_project_button.pack(anchor='w',pady=4)
        link=ttk.Label(self.setup_frame,text='Persönlichen API Key beantragen ↗',style='Accent.TLabel',cursor='hand2')
        link.pack(anchor='w');link.bind('<Button-1>',lambda e:webbrowser.open('https://fanart.tv/get-an-api-key/'))
        self.status=tk.StringVar(value='Schlüssel lokal vorhanden – Verbindung prüfen.' if configured else 'Persönlichen Key kostenlos bei fanart.tv erhalten. Keine Entwicklerregistrierung nötig.')
        ttk.Label(self.setup_frame,textvariable=self.status,wraplength=650,style='Muted.TLabel').pack(fill='x',pady=5)
        credit=ttk.Label(box,text='Filmcover werden über fanart.tv bereitgestellt. ↗',style='Accent.TLabel',cursor='hand2')
        credit.pack(anchor='w');credit.bind('<Button-1>',lambda e:webbrowser.open('https://fanart.tv/'))
        self.credit=credit
        self.show_setup(not verified)
        self.advanced_toggle=ttk.Button(box,text='▸ Erweiterte Einstellungen',command=self.toggle_advanced)
        self.advanced_toggle.pack(anchor='w',pady=(8,0))
        self.advanced=ttk.Frame(box,padding=(0,4))
        ttk.Label(self.advanced,text='Entwickler / bestehende Project-Key-Konfiguration').pack(anchor='w')
        ttk.Entry(self.advanced,textvariable=self.project_input,show='*').pack(fill='x',pady=4)
        ttk.Button(self.advanced,text='Projektkonfiguration speichern und prüfen',command=self.setup_project).pack(anchor='w')
        for text,command in (('Persönlichen Key entfernen',self.remove_personal),('Letztes Ergebnis',self.show_batch_result),('Erneut prüfen',self.start_batch),('Technische Konfigurationshilfe',lambda:messagebox.showinfo('Fanart.tv','Project API Key: lokale fanart.local.json neben FilmKompass.exe oder FANART_TV_PROJECT_KEY. Eine Umgebungsvariable hat Vorrang. Persönlicher Key ist separat optional. Die direkte Einrichtung speichert ausschließlich lokal.',parent=self.manager))):
            ttk.Button(self.advanced,text=text,command=command).pack(anchor='w',pady=2)
        self.manager.after_idle(self.sync_pause)

    def save_settings(self):
        was_enabled=self.cache.enabled
        try:personal=_key(self.personal.get())
        except CoverError as error:
            messagebox.showerror('Fanart.tv',str(error),parent=self.manager);return
        options=dict(self.options(),enabled=self.enabled.get(),personal_key=personal)
        self.manager.settings['fanart']=options;self.manager.save_settings()
        self.cache.enabled=options['enabled'];self.manager.art.clear()
        if options['enabled'] and not was_enabled:self.set_auto('pending');self.manager.after_idle(lambda:self.start_batch(automatic=True))
        if self.batch_running and not self.cache.enabled:self.cancel_batch()
        self.manager.refresh_list(reset_page=False)
        self.status.set('Einstellungen gespeichert.')

    def remove_personal(self):
        self.personal.set('');self.save_settings()

    def run(self,operation,work,message):
        if self.manager._busy_guard():return
        token=self.token
        options=dict(self.options());folder=self.project_folder;root=self.manager.db.db_path.parent
        def task(notify,progress):
            notify(message)
            try:
                credentials=Credentials(project_key(folder),_key(options.get('personal_key','')))
                service=CoverService(FanartCache(root),credentials)
                value=work(service)
                result=dict(operation=operation,token=token,value=value)
            except (CoverError,OSError) as error:
                result=dict(operation=operation,token=token,error=str(error))
            except Exception as error:
                # Never expose raw request objects, headers, or configuration values.
                result=dict(operation=operation,token=token,error=f'Coveranfrage fehlgeschlagen ({type(error).__name__}).')
            return {'fanart_result':result}
        self.manager._start_task(task,message)

    def test_connection(self):
        self.run('connection',lambda service:service.posters(external_id('imdb','tt0137523','Film'),force=True),
                 'Fanart.tv-Verbindung wird geprüft …')

    def start_batch(self,automatic=False):
        if self.batch_running:return
        if self.manager._export_running and not getattr(self.manager,'_task_is_list',False):return
        if not self.cache.enabled:
            self.status.set('Bitte zuerst Onlinecover aktivieren.');return
        options=dict(self.options())
        try:
            credentials=Credentials(project_key(self.project_folder),_key(options.get('personal_key','')))
            credentials.headers()
        except CoverError as error:self.status.set(str(error));self.cover_status.set('API Key einrichten');return
        self.set_auto('running')
        rows=[dict(r) for r in self.manager.db.get_rows(hidden=True)]
        manual_urls={r['url'] for r in rows if self.manager.images.path_for(r['url'])}
        root=self.manager.db.db_path.parent
        self.batch_cancel.clear();self.batch_running=True;self.sync_pause()
        self.batch_button.configure(state='disabled');self.cancel_button.configure(state='normal')
        def work(notify,progress):
            cache=FanartCache(root)
            gate=NetworkGate(cache,self.batch_cancel.is_set)
            service=ConcurrentCoverService(cache,credentials,
                request=lambda *args:gate.call(request_json,*args),
                download=lambda url:gate.call(download_image,url))
            try:
                value=parallel_missing_covers(service,rows,manual_urls,gate=gate,cancelled=self.batch_cancel.is_set,progress=progress,resume=automatic)
                return {'fanart_result':dict(operation='batch',token=0,value=value)}
            except Exception as error:
                text=str(error) if isinstance(error,(CoverError,OSError)) else f'Coverabgleich fehlgeschlagen ({type(error).__name__}).'
                return {'fanart_result':dict(operation='batch',token=0,error=text)}
        def run_batch():
            try:
                result=work(lambda text:None,lambda value:self.events.put(('measure',value)))['fanart_result']
            except Exception as error:
                result=dict(operation='batch',token=0,error=f'Coverabgleich fehlgeschlagen ({type(error).__name__}).')
            self.events.put(('done',result))
        self.manager.cover_main_text.set('Coverabgleich läuft …');self.manager._sync_cover_progress()
        self.thread=threading.Thread(target=run_batch,daemon=True,name='filmkompass-cover-coordinator');self.thread.start()

    def cancel_batch(self):
        self.set_auto('cancelled')
        self.batch_cancel.set();self.cancel_button.configure(state='disabled')
        self.status.set('Abbruch angefordert. Eine laufende HTTPS-Anfrage darf noch bis zum Timeout benötigen.')

    def show_batch_result(self,value=None):
        value=value or self.cache.data.get('last_batch')
        if not value:
            self.status.set('Noch kein Coverabgleich ausgeführt.');return
        label='Abgebrochen' if value.get('cancelled') else 'Gestoppt' if value.get('stopped') else 'Abgeschlossen'
        summary=(f"{label} · geprüft {value['checked']}/{value['total']} · neu {value['found']} · "
                 f"übersprungen {value['skipped']} · unklar {value['unclear']} · ohne Treffer {value['not_found']} · Fehler {value['errors']}")
        self.status.set(summary);self.manager.statusbar.set(summary)
        window=tk.Toplevel(self.manager);window.title('Coverabgleich – Ergebnis');window.transient(self.manager)
        window.geometry('700x420');window.minsize(420,280)
        body=ttk.Frame(window,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text=summary,wraplength=640,style='Accent.TLabel').pack(fill='x',pady=(0,10))
        from tkinter.scrolledtext import ScrolledText
        text=ScrolledText(body,wrap='word',bg='#16212b',fg='#edf6f6',font=('Segoe UI',10),height=10)
        text.pack(fill='both',expand=True)
        text.insert('end',f"Noch nicht geprüft: {value.get('remaining',0)}. Bereits gespeicherte Cover bleiben erhalten.\n\n")
        for item in value.get('issues',[]):text.insert('end',item['title']+' – '+item['reason']+'\n')
        if len(value.get('issues',[]))>=200:text.insert('end','\nProblemliste auf 200 Titel begrenzt; Zähler umfassen alle Titel.')
        text.configure(state='disabled')
        ttk.Button(body,text='Schließen',command=window.destroy).pack(anchor='e',pady=(10,0))

    def open(self,url):
        if self.manager._busy_guard():return
        row=self.manager.db.get_row(url)
        if not row:return
        if not self.cache.enabled:
            messagebox.showinfo('Fanart.tv','Bitte zuerst unter „Einstellungen & Daten“ die Onlinecover aktivieren.',parent=self.manager)
            return
        if self.dialog and self.dialog.winfo_exists():self.dialog.destroy()
        self.token+=1;self.row=dict(row);self.result=None;self.photo=None
        window=tk.Toplevel(self.manager);self.dialog=window
        window.title('Fanart.tv – Cover suchen');window.transient(self.manager)
        width=min(800,window.winfo_screenwidth()-60);height=min(590,window.winfo_screenheight()-100)
        window.geometry(f'{width}x{height}');window.minsize(min(620,width),min(420,height))
        body=ttk.Frame(window,padding=14);body.pack(fill='both',expand=True)
        ttk.Label(body,text=f"{row['title']} · {row['year'] or 'Jahr unbekannt'} · {row['media_type']}",style='Section.TLabel',wraplength=720).pack(anchor='w')
        ttk.Label(body,text='Titel/Jahr prüfen. Manuell zugeordnete Bilder bleiben unverändert und haben Vorrang.',style='Muted.TLabel',wraplength=720).pack(anchor='w',pady=(5,10))
        entry=ttk.Frame(body);entry.pack(fill='x')
        self.source=tk.StringVar(value='Automatisch');self.identifier=tk.StringVar()
        ttk.Combobox(entry,textvariable=self.source,values=list(self.SOURCES),state='readonly',width=23).pack(side='left',padx=(0,6))
        ttk.Entry(entry,textvariable=self.identifier).pack(side='left',fill='x',expand=True,padx=(0,6))
        ttk.Button(entry,text='Cover suchen',command=self.lookup).pack(side='left')
        self.detail=tk.StringVar(value='Automatische Suche über Wikidata oder eine vorhandene ID eingeben.')
        ttk.Label(body,textvariable=self.detail,style='Muted.TLabel',wraplength=720).pack(anchor='w',pady=10)
        center=ttk.Frame(body);center.pack(fill='both',expand=True)
        center.rowconfigure(0,weight=1);center.columnconfigure(0,weight=1)
        self.choices=tk.Listbox(center,exportselection=False,bg='#1e303b',fg='#edf6f6',selectbackground='#24564f',selectforeground='#ffffff',font=('Segoe UI',10),height=9)
        self.choices.grid(row=0,column=0,sticky='nsew')
        bar=ttk.Scrollbar(center,command=self.choices.yview);bar.grid(row=0,column=1,sticky='ns');self.choices.configure(yscrollcommand=bar.set)
        self.preview_label=ttk.Label(center,text='Vorschau',anchor='center',width=24)
        self.preview_label.grid(row=0,column=2,sticky='ns',padx=(12,0))
        actions=ttk.Frame(body);actions.pack(fill='x',pady=(12,0))
        self.preview_button=ttk.Button(actions,text='Vorschau laden',command=self.preview,state='disabled');self.preview_button.pack(side='left')
        self.use_button=ttk.Button(actions,text='Auswahl verwenden',command=self.use,state='disabled');self.use_button.pack(side='left',padx=8)
        ttk.Button(actions,text='Schließen',command=window.destroy).pack(side='right')
        selected=self.cache.identity(self.row)
        if selected:
            label=next((k for k,v in self.SOURCES.items() if v==selected['source']),'Automatisch')
            self.source.set(label);self.identifier.set(selected['value'])

    def lookup(self,identity=None):
        row=dict(self.row)
        if identity is None and self.SOURCES[self.source.get()]:
            try:identity=external_id(self.SOURCES[self.source.get()],self.identifier.get(),row['media_type'])
            except CoverError as error:self.detail.set(str(error));return
        self.run('lookup',lambda service:service.lookup(row,identity),'Fanart.tv: Zuordnung und Poster werden gesucht …')

    def selected(self):
        if not self.result or not self.choices.curselection():return None
        key='candidates' if self.result['stage']=='candidates' else 'posters'
        index=self.choices.curselection()[0]
        values=self.result.get(key,[])
        return values[index] if index<len(values) else None

    def preview(self):
        poster=self.selected()
        if poster and self.result['stage']=='posters':
            self.run('preview',lambda service:service.preview(poster),'Fanart.tv: Vorschau wird geladen …')

    def use(self):
        selected=self.selected()
        if not selected:return
        if self.result['stage']=='candidates':self.lookup(selected['identity']);return
        row=dict(self.row);identity=dict(self.result['identity'])
        self.run('apply',lambda service:service.apply(row,identity,selected),'Fanart.tv: Onlinecover wird gespeichert …')

    def handle(self,payload):
        self.cache.reload();self.cache.enabled=self.options().get('enabled') is True
        if payload['operation']=='batch':
            self.batch_running=False;self.batch_button.configure(state='normal');self.sync_pause()
            if payload.get('error'):self.set_auto('error');self.cover_status.set('Fehler: '+payload['error']);self.sync_pause()
            self.manager.art.clear();self.manager.refresh_list(reset_page=False)
            if not payload.get('error'):
                value=payload['value']
                if not value.get('cancelled'):self.set_auto('error' if value.get('stopped') else 'completed')
                if value.get('stopped') and any('401' in item.get('reason','') for item in value.get('issues',[])):self.invalidate_connection()
                label={'completed':'Abgeschlossen','error':'Fehler','pending':'Bereit','paused':'Pausiert','cancelled':'Pausiert'}.get(self.auto_state,'Bereit')
                self.cover_status.set(f"{label} · geprüft {value['checked']}/{value['total']} · neu {value['found']} · übersprungen {value['skipped']} · unklar {value['unclear']} · ohne Treffer {value['not_found']} · Fehler {value['errors']}")
                self.sync_pause()
                return
        if payload.get('error'):
            if payload['operation']=='connection' and getattr(self,'_setup_check',False):
                self._setup_check=False;self.set_auto('error');self.cover_status.set('API Key prüfen – Verbindung fehlgeschlagen')
                self.invalidate_connection()
            self.status.set(payload['error']);self.manager.statusbar.set(payload['error'])
            if self.dialog and self.dialog.winfo_exists() and payload['token']==self.token:self.detail.set(payload['error'])
            return
        operation=payload['operation'];value=payload['value']
        if operation=='connection':
            self.manager.settings['fanart']=dict(self.options(),verified_project=self.project_signature())
            self.manager.save_settings();self.connection_summary.set('Fanart.tv verbunden');self.show_setup(False)
            if getattr(self,'_setup_check',False):
                self._setup_check=False
                if not self.cache.enabled and messagebox.askyesno('Fanart.tv verbunden','Fehlende Filmcover jetzt laden und zukünftig automatisch herunterladen?',parent=self.manager,default='no'):
                    self.enabled.set(True);self.save_settings()
                elif self.cache.enabled and self.auto_state not in ('paused','cancelled'):
                    self.set_auto('pending');self.manager.after_idle(lambda:self.start_batch(automatic=True))
            self.status.set(f"Verbindung erfolgreich · {value['name']} · {len(value['posters'])} Poster")
            self.manager.statusbar.set(self.status.get());return
        if operation=='apply':
            self.manager.art.clear();self.manager.refresh_list(reset_page=False)
            manual=bool(self.row and self.manager.images.path_for(self.row['url']))
            self.manager.statusbar.set('Onlinecover gespeichert. Manuelles Bild hat weiterhin Vorrang.' if manual else 'Onlinecover gespeichert.')
        if not self.dialog or not self.dialog.winfo_exists() or payload['token']!=self.token:return
        if operation=='lookup':
            self.result=value;self.choices.delete(0,'end');self.preview_label.configure(image='',text='Vorschau');self.photo=None
            candidates=value['stage']=='candidates'
            values=value.get('candidates' if candidates else 'posters',[])
            for item in values:
                label=(f"{item['title']} · {item['year'] or 'Jahr unbekannt'} · {item['identity']['value']}" if candidates else
                    f"{item['lang'] or 'neutral'} · {item['likes']} Likes · {item['width']}×{item['height']} · #{item['id']}")
                self.choices.insert('end',label)
            if values:self.choices.selection_set(0)
            self.use_button.configure(state='normal' if values else 'disabled',text='Treffer laden' if candidates else 'Als Onlinecover verwenden')
            self.preview_button.configure(state='normal' if values and not candidates else 'disabled')
            text=('Zuordnung nicht eindeutig: bitte Titel und Jahr prüfen und einen Treffer wählen.' if candidates and values else
                'Kein sicherer Wikidata-Treffer. Bitte eine manuelle ID eingeben.' if candidates else
                f"Fanart.tv: {value['name']} · {len(values)} Poster. Bitte Film/Serie und Cover prüfen.")
            if value.get('stale'):text+=' Offline: ältere Cacheantwort verwendet.'
            elif value.get('cached'):text+=' Aus dem lokalen Cache.'
            self.detail.set(text)
        elif operation=='preview':
            try:
                with Image.open(self.cache.path(value)) as image:
                    self.photo=ImageTk.PhotoImage(ImageOps.contain(image.convert('RGB'),(150,220)))
                self.preview_label.configure(image=self.photo,text='')
                self.detail.set('Vorschau geladen. Rechte am Bild verbleiben beim angegebenen Rechteinhaber.')
            except (OSError,ValueError):self.detail.set('Vorschau konnte nicht angezeigt werden.')
        elif operation=='apply':self.detail.set(self.manager.statusbar.get())
