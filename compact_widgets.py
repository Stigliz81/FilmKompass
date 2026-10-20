"""Small Tk widgets; no extra GUI or chart dependencies."""
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from catalog_view import compact_filter_text

FILTER_LABEL_FONT=('Segoe UI',10,'bold')
FILTER_LABEL_GAP=3

HELP_STEPS=(
    ('1. Moviepilot-Profil angeben','Für ein öffentliches Profil genügt dein Benutzername oder Profillink. Der normale öffentliche Abruf benötigt keine Anmeldung.'),
    ('2. Bewertungen herunterladen','Klicke auf „Von Moviepilot aktualisieren“. Filme, Serien und Bewertungen werden geprüft und lokal gespeichert.'),
    ('3. Filme und Serien finden','Durchsuche deine Bibliothek oder filtere nach Erscheinungsjahr, deiner Note, Bewertungsdatum und Genre.'),
    ('4. Filmdatenbank exportieren','Exportiere alle Bewertungen oder nur die aktuell gefilterten Ergebnisse als Excel oder CSV.'),
    ('5. Daten mit KI auswerten','Du kannst die Exportdatei selbst beispielsweise bei ChatGPT hochladen und Filmempfehlungen erhalten. Die App überträgt nichts automatisch an KI-Dienste.'),
)

QUICK_HELP='''Deine Bewertungen in wenigen Schritten

1. Profil vorbereiten
Für öffentliche Moviepilot-Bewertungen genügt der Profillink oder Benutzername. Der normale Download arbeitet per HTTPS ohne Anmeldung und ohne Browsercookies. Deine Anmeldung im normalen Browser wird dabei nicht verwendet.

Private oder eingeschränkte Profile können nicht auf diesem Weg geladen werden. Importiere dann einen vorhandenen CSV-/Excel-Export. Es werden keine Zugriffsbeschränkungen umgangen. Der optionale Browseradapter verwendet ausschließlich ein eigenes lokales Profil; eine dort fehlende oder abgelaufene Anmeldung kann eine erneute manuelle Anmeldung verlangen. Dieser Adapter ist nicht in der portablen Version enthalten und sein aktuelles Seitenlayout ist nicht bestätigt.

2. Bewertungen herunterladen
„Von Moviepilot aktualisieren“ öffnen und deinen Profillink einfügen. Film- und Serienlisten werden vollständig geprüft, gespeichert und mit der vorhandenen Bibliothek abgeglichen. Eine Sicherung vorhandener Daten wird zuvor angelegt.

3. Finden und öffnen
Titel suchen, Film/Serie wählen und die kleinen Filter öffnen. Erscheinungsjahr meint das Filmjahr beziehungsweise gespeicherte Startjahr der Serie. Meine Note ist deine Moviepilot-Note einschließlich 0 und Halbnoten. Bewertet im Jahr und Bewertet im Monat beziehen sich auf das echte Bewertungsdatum; ohne Jahr gilt der Monat in allen Jahren. Innerhalb dieser Filter gilt ODER, zwischen Filtern UND. Moviepilot Genre verwendet unveränderte Originalnamen: mindestens eines (ODER, Standard) oder alle gewünschten Genres (UND); jedes ausgeschlossene Genre entfernt den Titel. Eine neue widersprüchliche Auswahl entfernt dasselbe Genre aus der Gegenseite. „Zurücksetzen“ im Auswahlfenster löscht diesen Filter; „Alles zurücksetzen“ löscht auch Suche und Typauswahl.

Spaltenüberschriften sortieren; Spaltengrenzen lassen sich ziehen. Ein Doppelklick auf den Titel öffnet den vorhandenen Moviepilot-Link. Ohne gespeicherten Link wird nichts erraten.

4. Exportieren und sichern
„Filmdatenbank exportieren“ bietet CSV oder Excel, standardmäßig die gesamte Bibliothek. Eine gefilterte Auswahl ist ausdrücklich wählbar; die Anzahl wird angezeigt. Beide Formate enthalten genau sechs Spalten. Für eine vollständige Sicherung einschließlich vorhandener Links und alter persönlicher Angaben verwende zusätzlich „Sicherung“.

Beim Reimport ohne URLs erfolgt die Zuordnung über Typ, exakten Titel und Jahr. Bei Mehrdeutigkeit wird abgebrochen. Unbekannte Titel bleiben lokal ohne Weblink. Gleichnamige Werke im selben Jahr lassen sich ohne URL nicht zuverlässig unterscheiden; nutze dafür einen alten Export mit URLs.

5. Freiwillige KI-Auswertung
Du kannst die vollständige Exportdatei selbst bei ChatGPT oder einem anderen KI-Dienst hochladen, um deinen Geschmack und Lieblingsgenres zu analysieren und Film-/Serienempfehlungen anhand deiner Noten zu erhalten. Die App überträgt keine Daten an KI-Dienste.

Bei häufiger Nutzung kannst du die Datei selbst in einem privaten Cloudordner, etwa Google Drive, ablegen und später durch eine aktuelle vollständige Version ersetzen. Keine automatische Synchronisation: Zugriff hängt von tatsächlich verbundenen Diensten und Berechtigungen ab. Persönliche Listen brauchen keine öffentlichen Freigabelinks.

6. Bilder und Miniaturansicht
Listenansicht und Miniaturansicht verwenden dieselben Filter und dieselbe Sortierung. In der Miniaturansicht wählst du 6, 12, 18 oder 24 Titel pro Seite; Ansicht und Seitengröße bleiben gespeichert. Eigene Genreillustrationen sind keine echten Filmplakate. Film/Serie erkennt man am kleinen Badge; Doppelklick öffnet den gespeicherten Moviepilot-Link.

Mit Rechtsklick kannst du einem Titel ein eigenes JPG, PNG oder WebP zuweisen oder eine selbst eingegebene direkte HTTPS-Bildadresse verwenden. Nutze nur Bilder mit passenden Nutzungsrechten. Die App sucht keine Poster und liest keine fremden Anmeldungen aus. Beim URL-Abruf erhält der eingegebene Bildserver deine Anfrage. Entfernen der eigenen Zuordnung zeigt wieder das Genremotiv. Die Quelldatei bleibt erhalten; lokale Benutzerbilder werden niemals mit dem Programm veröffentlicht.

Neue Installationen starten leer. Lokale Daten und Bilder bleiben im eigenen Appdatenordner. Unter Einstellungen & Daten kannst du vier vorhandene Kinomotive für den Kopfbereich wählen. Standard ist Ohne Hintergrundbild; fehlende Motive fallen sicher auf die dunkle Fläche zurück. Tabellen bleiben einfarbig.

7. Lokale Daten und Filterstatistik
Die vier oberen Kennzahlen beschreiben immer die gesamte Bibliothek. Bei aktiver Suche oder Filtern zeigt die Zeile darunter die komplette aktuelle Treffermenge, unabhängig von der Miniaturseite. Noten 0 bleiben gespeichert und werden wie global aus dem Durchschnitt ausgeschlossen; ohne positive Noten erscheint ein Gedankenstrich.

Lokale Daten liegen standardmäßig unter %LOCALAPPDATA%/MoviepilotManager; Python und EXE nutzen denselben Ordner. Vorhandene Sicherungen werden nicht automatisch gelöscht. Vor Bibliotheksreset oder Appdatenreset Umfang und Bestätigungen sorgfältig prüfen. Für einen Gerätewechsel den Appdatenordner einschließlich eigener Bilder separat sichern; SQLite-Sicherungen enthalten Bildzuordnungen, aber keine Bilddateien.

Genrefenster: Alle markieren schließt alle bekannten Genres außer der gewünschten Auswahl aus, unabhängig von der Suche. Alle Ausschlüsse entfernen erhält die gewünschte Auswahl. Nur ausgewählte Genres ist ohne gewünschtes Genre deaktiviert. Klick/Strg schaltet einzelne Werte um, Shift ergänzt einen sichtbaren Bereich; ausgeblendete Auswahlen bleiben erhalten.

Exportdateien heißen je nach gewähltem Umfang FilmKompass_Filmdaten_Alle oder FilmKompass_Filmdaten_Filter. Kollisionen erhalten Datum/Uhrzeit und bei Bedarf eine Nummer. Eine vorhandene Datei wird nur nach ausdrücklicher Bestätigung überschrieben.'''

class HeadingTip:
    """One delayed tooltip for a narrow title heading; no column geometry changes."""
    def __init__(self,tree,colors):
        self.tree=tree;self.colors=colors;self.job=None;self.window=None
        tree.bind('<Motion>',self.motion,add='+')
        for event in ('<Leave>','<ButtonPress>','<MouseWheel>','<Destroy>'):
            tree.bind(event,self.clear,add='+')

    def motion(self,event):
        active=(self.tree.identify_region(event.x,event.y)=='heading' and self.tree.identify_column(event.x)=='#2' and 'Doppelklick' not in self.tree.heading('titel','text'))
        if not active:self.clear();return
        if self.job is None and self.window is None:
            self.job=self.tree.after(500,lambda:self.show(event.x_root,event.y_root))

    def show(self,x,y):
        self.job=None
        self.window=tk.Toplevel(self.tree);self.window.overrideredirect(True)
        self.window.geometry(f'+{x+12}+{y+16}')
        tk.Label(self.window,text='Doppelklick öffnet Moviepilot',bg=self.colors['field'],fg=self.colors['ink'],font=('Segoe UI',9),padx=8,pady=5).pack()

    def clear(self,event=None):
        if self.job:self.tree.after_cancel(self.job);self.job=None
        if self.window:self.window.destroy();self.window=None

class MultiSelect(tk.Toplevel):
    def __init__(self,parent,label,values,selected,callback,colors):
        super().__init__(parent)
        self.title(label+' auswählen'); self.transient(parent)
        self.configure(bg=colors['bg']); self.geometry('370x450'); self.minsize(320,330)
        self.selected=set(selected); self.values=values; self.shown=[]
        body=ttk.Frame(self,padding=16); body.pack(fill='both',expand=True)
        ttk.Label(body,text=label+' · Mehrfachauswahl',font=('Segoe UI Semibold',12)).pack(anchor='w',pady=(0,8))
        search=tk.StringVar()
        entry=ttk.Entry(body,textvariable=search); entry.pack(fill='x')
        ttk.Label(body,text='Werte anklicken zum An-/Abwählen',style='Muted.TLabel').pack(anchor='w',pady=5)
        area=ttk.Frame(body); area.pack(fill='both',expand=True)
        self.listbox=tk.Listbox(area,selectmode='multiple',exportselection=False,bg=colors['field'],fg=colors['ink'],selectbackground='#24564f',selectforeground=colors['ink'],disabledforeground=colors['muted'],highlightbackground=colors['border'],highlightcolor=colors['accent'],relief='flat',font=('Segoe UI',11),activestyle='none')
        self.listbox.pack(side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(area,command=self.listbox.yview); scrollbar.pack(side='right',fill='y')
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.bind('<<ListboxSelect>>',lambda e:self.remember())
        def refill(*_):
            self.shown=[v for v in values if search.get().casefold().replace(',','.') in str(v).casefold()]
            self.listbox.delete(0,'end')
            for i,v in enumerate(self.shown):
                self.listbox.insert('end',str(v).replace('.',',') if isinstance(v,float) else str(v))
                if v in self.selected: self.listbox.selection_set(i)
        search.trace_add('write',refill); refill()
        tools=ttk.Frame(body); tools.pack(fill='x',pady=(12,0))
        def reset(): self.selected.clear(); search.set(''); refill()
        def apply(): self.remember(); callback(set(self.selected)); self.destroy()
        ttk.Button(tools,text='Zurücksetzen',command=reset).pack(side='left')
        ttk.Button(tools,text='Übernehmen',command=apply,style='Accent.TButton').pack(side='right')
        self.grab_set(); entry.focus_set()

    def remember(self):
        self.selected.difference_update(self.shown)
        self.selected.update(self.shown[i] for i in self.listbox.curselection())

class GenreSelect(tk.Toplevel):
    """Two searchable selections; the latest explicit choice resolves conflicts."""
    def __init__(self,parent,values,wanted,excluded,mode,callback,colors):
        super().__init__(parent)
        self.title('Moviepilot Genre auswählen');self.transient(parent)
        self.configure(bg=colors['bg']);self.minsize(560,460)
        x=max(0,parent.winfo_rootx()+(parent.winfo_width()-650)//2)
        y=max(0,parent.winfo_rooty()+(parent.winfo_height()-560)//2)
        self.geometry(f'650x560+{x}+{y}')
        self.selected=[set(wanted),set(excluded)-set(wanted)];self.shown=[[],[]];self.boxes=[];self.searches=[];self.anchors=[None,None]
        self.mode=tk.StringVar(value=mode if mode in ('or','and') else 'or')
        body=ttk.Frame(self,padding=16);body.pack(fill='both',expand=True)
        ttk.Label(body,text='Moviepilot Genre · Originalbezeichnungen',font=('Segoe UI Semibold',12)).pack(anchor='w')
        for text,value in [('Mindestens eines der ausgewählten Genres (ODER)','or'),('Alle ausgewählten Genres (UND)','and')]:
            ttk.Radiobutton(body,text=text,variable=self.mode,value=value,command=self.summary).pack(anchor='w',pady=3)
        # Reserve the footer before the growing lists, including at minimum height.
        footer=ttk.Frame(body);footer.pack(side='bottom',fill='x')
        area=ttk.Frame(body);area.pack(fill='both',expand=True,pady=10)
        for side,label in enumerate(('Gewünschte Genres','Ausgeschlossene Genres')):
            area.columnconfigure(side,weight=1,uniform='genres');area.rowconfigure(0,weight=1)
            pane=ttk.Frame(area);pane.grid(row=0,column=side,sticky='nsew',padx=(0,10) if side==0 else (0,0))
            ttk.Label(pane,text=label).pack(anchor='w')
            search=tk.StringVar();self.searches.append(search)
            ttk.Entry(pane,textvariable=search).pack(fill='x',pady=6)
            if side==0:
                self.only_button=ttk.Button(pane,text='Nur ausgewählte Genres',command=self.only_selected)
                self.only_button.pack(fill='x',pady=(0,4))
                ttk.Label(pane,text='Andere bekannte Genres ausschließen',style='Muted.TLabel',font=('Segoe UI',9)).pack(anchor='w')
            else:
                tools=ttk.Frame(pane);tools.pack(fill='x',pady=(0,4))
                ttk.Button(tools,text='Alle markieren',command=self.exclude_all).pack(fill='x')
                ttk.Button(tools,text='Alle Ausschlüsse entfernen',command=self.clear_exclusions).pack(fill='x',pady=(3,0))
                ttk.Label(pane,text='Alle Genres, unabhängig von der Suche',style='Muted.TLabel',font=('Segoe UI',9)).pack(anchor='w')
            frame=ttk.Frame(pane);frame.pack(fill='both',expand=True)
            box=tk.Listbox(frame,selectmode='multiple',exportselection=False,bg=colors['field'],fg=colors['ink'],selectbackground='#24564f',selectforeground=colors['ink'],disabledforeground=colors['muted'],highlightbackground=colors['border'],highlightcolor=colors['accent'],relief='flat',font=('Segoe UI',10),activestyle='none',width=20)
            box.pack(side='left',fill='both',expand=True);self.boxes.append(box)
            scroll=ttk.Scrollbar(frame,command=box.yview);scroll.pack(side='right',fill='y');box.configure(yscrollcommand=scroll.set)
            box.bind('<<ListboxSelect>>',lambda e,s=side:self.remember(s))
            box.bind('<Button-1>',lambda e,s=side:self.click_selection(e,s))
            search.trace_add('write',lambda *_,s=side:self.refill(s))
        self.values=values
        rule_area=ttk.Frame(footer);rule_area.pack(fill='x',pady=(0,6))
        self.rule=tk.Text(rule_area,height=3,wrap='word',bg=colors['field'],fg=colors['accent'],font=('Segoe UI',10),relief='flat',state='disabled')
        self.rule.pack(side='left',fill='x',expand=True)
        scroll=ttk.Scrollbar(rule_area,command=self.rule.yview);scroll.pack(side='right',fill='y');self.rule.configure(yscrollcommand=scroll.set)
        self.count_label=ttk.Label(footer,style='Accent.TLabel');self.count_label.pack(anchor='w')
        ttk.Label(footer,text='Klick/Strg: an/ab · Shift: sichtbaren Bereich wählen. Neue Auswahl löst Konflikte.',wraplength=480,style='Muted.TLabel').pack(anchor='w')
        tools=ttk.Frame(footer);tools.pack(fill='x',pady=(8,0))
        ttk.Button(tools,text='Zurücksetzen',command=self.reset).pack(side='left')
        ttk.Button(tools,text='Übernehmen',style='Accent.TButton',command=lambda:(callback(set(self.selected[0]),set(self.selected[1]),self.mode.get()),self.destroy())).pack(side='right')
        self.refill(0);self.refill(1);self.summary();self.grab_set()

    def refill(self,side):
        self.anchors[side]=None
        self.shown[side]=[v for v in self.values if self.searches[side].get().casefold() in v.casefold()]
        box=self.boxes[side];box.delete(0,'end')
        for i,value in enumerate(self.shown[side]):
            box.insert('end',value)
            if value in self.selected[side]:box.selection_set(i)

    def click_selection(self,event,side):
        box=self.boxes[side]
        if not self.shown[side]:return 'break'
        index=box.nearest(event.y);anchor=self.anchors[side]
        if event.state & 0x0001 and anchor is not None:
            # Add a range in the currently displayed order; hidden choices survive.
            box.selection_set(min(anchor,index),max(anchor,index))
        else:
            if box.selection_includes(index):box.selection_clear(index)
            else:box.selection_set(index)
            self.anchors[side]=index
        box.activate(index);box.selection_anchor(index);box.focus_set();self.remember(side)
        return 'break'

    def exclude_all(self):
        self.selected[1]=set(self.values)-self.selected[0]
        self.refill(1);self.summary()

    def clear_exclusions(self):
        self.selected[1].clear();self.refill(1);self.summary()

    def only_selected(self):
        if self.selected[0]:self.exclude_all()

    def remember(self,side):
        selected={self.shown[side][i] for i in self.boxes[side].curselection()}
        added=selected-self.selected[side]
        self.selected[side].difference_update(self.shown[side]);self.selected[side].update(selected)
        if added & self.selected[1-side]:
            self.selected[1-side].difference_update(added);self.refill(1-side)
        self.summary()

    def summary(self):
        self.only_button.configure(state='normal' if self.selected[0] else 'disabled')
        self.count_label.configure(text=f'{len(self.selected[0])} Genre(s) gewählt, {len(self.selected[1])} ausgeschlossen')
        join=' UND ' if self.mode.get()=='and' else ' ODER '
        text=join.join(sorted(self.selected[0])) or 'Alle Genres'
        if self.selected[1]:text+=', ohne '+', '.join(sorted(self.selected[1]))
        self.rule.configure(state='normal');self.rule.delete('1.0','end');self.rule.insert('1.0',text);self.rule.configure(state='disabled')

    def reset(self):
        self.selected=[set(),set()];self.mode.set('or')
        for search in self.searches:search.set('')
        self.refill(0);self.refill(1);self.summary()

class BarChart(tk.Canvas):
    def __init__(self,parent,title,colors):
        super().__init__(parent,bg=colors['panel'],highlightthickness=0,height=80)
        self.chart_title=title; self.colors=colors; self.data=[]
        self.bind('<Configure>',lambda e:self.draw())

    def set_data(self,data):
        self.data=data; self.configure(height=max(90,52+len(data)*27)); self.draw()

    def draw(self):
        self.delete('all'); ink=self.colors['ink']
        self.create_text(12,18,text=self.chart_title,fill=ink,anchor='w',font=('Segoe UI Semibold',12))
        if not self.data:
            self.create_text(12,58,text='Noch keine Daten',fill=self.colors['muted'],anchor='w'); return
        high=max((v for _,v in self.data),default=0) or 1
        width=max(60,min(750,self.winfo_width())-185)
        for i,(label,count) in enumerate(self.data):
            y=45+i*27
            self.create_text(12,y+8,text=label,fill=self.colors['muted'],anchor='w',font=('Segoe UI',10))
            self.create_rectangle(118,y,118+width*count/high,y+16,fill=self.colors['accent'],outline='')
            self.create_text(127+width*count/high,y+8,text=str(count),fill=ink,anchor='w',font=('Segoe UI',10))


class FilterControl(ttk.Frame):
    """Two compact text lines, existing popup command and keyboard-capable button."""
    def __init__(self,parent,label,command,inline=False):
        super().__init__(parent)
        self.values=[];self.full_text='Alle';self.tip=None;self.tip_job=None
        self.label=ttk.Label(self,text=label+':',font=FILTER_LABEL_FONT,cursor='hand2')
        self.label.pack(side='left' if inline else 'top',anchor='n' if inline else 'w',padx=(0,3),pady=(0,FILTER_LABEL_GAP))
        self.button=ttk.Button(self,text='Alle',command=command,width=4)
        self.button.pack(side='left' if inline else 'bottom',fill='x',expand=inline)
        self.label.bind('<Button-1>',lambda e:(self.clear_tip(),self.button.focus_set(),self.button.invoke()))
        self.button.bind('<Configure>',lambda e:self.fit_text())
        for widget in (self.label,self.button):
            widget.bind('<Enter>',self.queue_tip,add='+')
            for event in ('<Leave>','<ButtonPress>','<Unmap>','<Destroy>','<FocusOut>'):
                widget.bind(event,self.clear_tip,add='+')

    def set_values(self,values):
        self.clear_tip();self.values=list(values);self.full_text=', '.join(values) or 'Alle';self.fit_text()

    def fit_text(self):
        font=tkfont.Font(self,font=ttk.Style(self).lookup('TButton','font'))
        width=max(8,self.button.winfo_width()-24)
        self.button.configure(text=compact_filter_text(self.values,font.measure,width))

    def queue_tip(self,event):
        if self.button.cget('text')==self.full_text:return
        self.clear_tip()
        self.tip_job=self.after(500,lambda:self.show_tip(event.x_root,event.y_root))

    def show_tip(self,x,y):
        self.tip_job=None
        if not self.winfo_ismapped():return
        self.tip=tk.Toplevel(self);self.tip.overrideredirect(True)
        label=tk.Label(self.tip,text=self.label.cget('text')+' '+self.full_text,
                       bg='#20313b',fg='#e7eef3',font=('Segoe UI',10),justify='left',wraplength=480,padx=10,pady=7)
        label.pack();self.tip.update_idletasks()
        x=max(0,min(x+12,self.winfo_screenwidth()-self.tip.winfo_reqwidth()-12))
        y=max(0,min(y+16,self.winfo_screenheight()-self.tip.winfo_reqheight()-12))
        self.tip.geometry(f'+{x}+{y}')

    def clear_tip(self,event=None):
        if self.tip_job:self.after_cancel(self.tip_job);self.tip_job=None
        if self.tip:self.tip.destroy();self.tip=None

    def configure(self,cnf=None,**kw):
        if hasattr(self,'button'):
            if 'style' in kw:self.label.configure(foreground='#59cfc2' if kw['style']=='ActiveFilter.TButton' else '')
            self.button.configure(cnf,**kw)
        else:super().configure(cnf,**kw)
