"""Small Tk widgets; no extra GUI or chart dependencies."""
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from catalog_view import compact_filter_text

FILTER_LABEL_FONT=('Segoe UI',10,'bold')
FILTER_LABEL_GAP=3


def scroll_wheel(target, delta):
    """Accumulate high-resolution deltas on the actual scroll target, without timers."""
    remainder=getattr(target,'_wheel_remainder',0.0)
    if remainder*delta<0:remainder=0.0
    total=remainder+delta/120.0
    steps=int(total)
    target._wheel_remainder=total-steps
    if steps:target.yview_scroll(-steps,'units')
    return 'break'

HELP_STEPS=(
    ('1. Bewertungen übernehmen','„Von Moviepilot aktualisieren“ lädt ein öffentliches Profil. „Datei importieren“ übernimmt vorhandene CSV-/Excel-Dateien. Filme und Serien bleiben getrennt erkennbar.'),
    ('2. Bibliothek durchsuchen','Suche, Filter und Sortierung kombinieren. Tabelle: 24, 50, 100 oder Alle. Miniaturen: Klein, Mittel oder Groß mit eigener Seitengröße.'),
    ('3. Listen vergleichen','Unter Filmlisten eine öffentliche Moviepilot-Adresse mit „Liste importieren“ speichern. Empfehlungsabgleich vergleicht eingefügte Titel mit deiner Bibliothek.'),
    ('4. Bilder verwenden','Eigene Bilder per Rechtsklick zuordnen. In Einstellungen & Daten Onlinecover aktivieren, persönlichen API Key speichern und prüfen. Fehlende Cover werden automatisch geladen; Pausieren/Fortsetzen bleiben verfügbar.'),
    ('5. Exportieren und sichern','„Filmdatenbank exportieren“ speichert alle oder gefilterte Bewertungen als Excel/CSV. „Sicherung“ schützt die Datenbank. Für den Gerätewechsel auch Bilder und Appdaten separat sichern.'),
)

QUICK_HELP='''FilmKompass im Alltag

1. Start und Bewertungen
Neue Installationen starten leer. Unter „Von Moviepilot aktualisieren“ deinen Benutzernamen oder Profillink eingeben. Für den normalen HTTPS-Abruf müssen die Bewertungen öffentlich sichtbar sein; eine Browser-Anmeldung wird nicht übernommen. Private Profile oder Zugriffssperren werden nicht umgangen. Alternativ eine vorhandene Datei mit „Datei importieren“ laden. Vor der Aktualisierung vorhandener Daten wird eine Sicherung angelegt. Film-/Serienbewertungen, 0 und Halbnoten bleiben erhalten.

2. Finden, filtern und sortieren
„Titel suchen“ und Film/Serie kombinieren. Erscheinungsjahr bezeichnet Filmjahr beziehungsweise Serienstart, Bewertungsjahr/-monat das gespeicherte genaue Bewertungsdatum. Innerhalb eines Filters gilt ODER, zwischen Filtern UND. Genres unterstützen gewünschte Werte (ODER/UND) und Ausschlüsse. „Alles zurücksetzen“ leert Suche und Filter. „Filter ausblenden“ schafft Platz; die Auswahl bleibt erhalten. Spaltenüberschriften und „Sortieren“ ändern nur die Anzeige, keine Bewertung. Strg+F fokussiert die Suche, Strg+A markiert Eingaben. Rechtsklick bietet Bearbeiten beziehungsweise das passende Kontextmenü. Tab wechselt den Fokus, in Textfeldern wird nichts automatisch abgesendet.

3. Tabelle, Miniaturen und Quellen
Listenansicht zeigt 24, 50, 100 oder Alle; Standard 100. Alle ist eine durchgehend scrollbarere Tabelle der gefilterten Ergebnisse. Miniaturansicht hat unabhängig davon 6, 12, 18 oder 24 Titel pro Seite und die Größen Klein, Mittel, Groß. Ansicht und Größen werden gespeichert. Beide Ansichten verwenden dieselben Filter und dieselbe Sortierung. Zurück/Weiter blättern. Film/Serie und persönliche Note stehen an den Karten. Doppelklick auf einen gültigen Titel mit ↗ öffnet dessen HTTPS-Moviepilot-Quelle; fehlende Links werden nicht erraten.

4. Filmlisten und Empfehlungen
Unter Filmlisten eine einzelne öffentliche Moviepilot-URL einfügen und „Liste importieren“ wählen. Benutzerlisten werden vollständig geprüft; Bestenlisten-Kataloge sind auf 200 Titel begrenzt und als Ausschnitt gekennzeichnet. Zugriffssperren wie HTTP 403 werden respektiert. Die Tabelle vergleicht lokale Bewertungen und Moviepilot Ø getrennt. „Excel / CSV …“ exportiert die geladene Liste. „Lokal entfernen“ löscht nur diese lokale Liste. Ein fehlender Bibliothekseintrag bedeutet nicht automatisch ungesehen.
Im Empfehlungsabgleich einen Titel pro Zeile einfügen und „Mit meiner Moviepilot-Liste abgleichen“ wählen. Unklare Ähnlichkeiten müssen selbst geprüft werden. Die App schreibt dadurch keine Bewertungen um.

5. Eigene und automatische Cover
Per Rechtsklick ein eigenes JPG, PNG oder WebP zuordnen. Eine direkte HTTPS-Bildadresse darf bewusst eingegeben werden; nur Bilder mit passenden Nutzungsrechten verwenden. Eigene Bilder haben Vorrang. Danach kommen lokal gespeicherte Fanart-Cover; die 15 freigegebenen Genreillustrationen dienen als Ersatz und sind keine echten Filmposter.
Unter Einstellungen & Daten „Onlinecover automatisch laden“ aktivieren. Persönlichen API Key bei fanart.tv beantragen, im maskierten Feld eintragen und „Speichern und Verbindung prüfen“ wählen. Dafür ist kein Project API Key und keine Entwicklerregistrierung nötig. Vorhandene Entwickler-Projektschlüssel bleiben unter erweiterten Einstellungen unterstützt. Nach erfolgreicher Prüfung wird bei noch deaktivierter Automatik gefragt, ob fehlende Cover jetzt und künftig geladen werden sollen. Nein lässt die Automatik aus. Die Entscheidung wird gespeichert. Danach klappt die Einrichtung ein; „API Key ändern“ öffnet sie wieder. Ohne neue Eingabe kann eine vorhandene Konfiguration erneut geprüft werden. Die App zeigt gespeicherte Schlüssel nicht offen an.
Fehlende Cover werden automatisch zugeordnet, sichere Treffer übernommen, unklare ausgelassen. Höchstens zwei Coveraufträge arbeiten gleichzeitig; Wikidata bleibt seriell. „Pausieren“ beendet laufende Anfragen geordnet, „Fortsetzen“ nimmt offene Titel wieder auf. Deaktivieren von „Onlinecover automatisch laden“ bricht nur den Coverlauf ab; gespeicherte Ergebnisse bleiben erhalten. In den erweiterten Einstellungen stehen letztes Ergebnis und „Erneut prüfen“. Der Coverabgleich und „Liste importieren“ laufen unabhängig und besitzen eigene Status-/Abbruchmöglichkeiten. Für Änderungen an persönlichen Bildern, Bibliotheksimport oder Zurücksetzen einen laufenden Coverabgleich zuerst pausieren. Serverfehler können den Lauf stoppen; vorhandene Bilder bleiben erhalten.

6. Export und Sicherung
„Filmdatenbank exportieren“ speichert alle Bewertungen oder ausdrücklich die gefilterte Auswahl als Excel/CSV mit sechs öffentlichen Spalten. Noten sind Zahlen, keine Datumsangaben. Gleichnamige Dateien werden nur nach Bestätigung überschrieben. Reimporte ohne URLs ordnen über Typ, exakten Titel und Jahr zu; Mehrdeutigkeiten werden nicht geschätzt.
„Sicherung“ erstellt eine SQLite-Sicherung mit Links und persönlichen Angaben. Bildzuordnungen sind enthalten, die Bilddateien selbst nicht. Für einen Gerätewechsel daher zusätzlich den gesamten Appdatenordner samt user-images und fanart-cache separat sichern. Keine zwei Programmversionen gleichzeitig mit demselben Datenordner verwenden.

7. Speicherorte und Offlinebetrieb
Persönliche Daten liegen standardmäßig unter %LOCALAPPDATA%/MoviepilotManager; Python und EXE verwenden denselben Ordner. Unter Einstellungen & Daten steht der tatsächliche Datenbankpfad. Ein gesonderter Testdatenordner ist über die Teststartanleitung möglich. Vorhandene Daten werden nicht als Programmpaket veröffentlicht und nicht automatisch zurückgesetzt. Bibliothek zurücksetzen entfernt auch gespeicherte Filmlisten, erhält Einstellungen, Keys und Bilddateien und erstellt vorher eine geprüfte Datenbanksicherung. Alle lokalen Appdaten löschen entfernt auch Einstellungen und Cache im verwalteten Profil; die automatische externe Sicherung im Windows-Dokumenteordner unter FilmKompass/Sicherungen beachten. Unbekannte Dateien und externe Exporte bleiben erhalten. Im eigenen Bestätigungsfenster ist Abbrechen die sichere Standardaktion; nur „Ja, endgültig löschen“ bestätigt. Kein Bestätigungstext und keine Enter-Bestätigung.
Bibliothek, Filter, Vergleiche und lokal gespeicherte Bilder sind offline nutzbar. Aktualisierungen, öffentliche Listen, neue Onlinecover und Browserlinks benötigen Internet. Keine Registrierung ist für lokale Bibliotheksfunktionen nötig. Die App überträgt nichts automatisch an KI-Dienste oder Cloudspeicher. Eine freiwillige KI-Auswertung einer Exportdatei geschieht ausschließlich außerhalb der App auf eigene Entscheidung.

8. Statistik und Einstellungen
Moviepilot-URLs in Filmlisten öffnen sich per einfachem Klick; im Empfehlungsabgleich ist der zugeordnete Titel anklickbar. Rechtsklick bietet „Bei Moviepilot öffnen“. Nur gültige HTTPS-Film-/Serienlinks werden geöffnet.
„🌐 Webseite“ im Kopfbereich und in Einstellungen & Daten öffnet die offizielle FilmKompass-Seite. Unter „Programmupdates“ manuell „Auf Updates prüfen“ wählen; „Downloadseite öffnen“ führt zur offiziellen Quelle. Automatische Prüfung ist freiwillig, standardmäßig aus und auf einmal in 24 Stunden begrenzt. Es wird nichts automatisch installiert. Bei fehlender Versionsdatei oder Verbindungsfehler erscheint keine Aktualitätsbestätigung.
Statistik zeigt die vorhandenen lokalen Daten; die Kopfkennzahlen beschreiben die ganze Bibliothek, Filter die aktuelle Treffermenge. Noten 0 werden gespeichert, aber aus dem Kopf-Durchschnitt ausgeschlossen. Änderungen zeigt die Importhistorie. Einstellungen & Daten enthält Cover, Hinweise, Kopf-Hintergrund und Datenwerkzeuge. Fehlende optionale Bilder fallen auf die dunkle Darstellung zurück. Genreersatz, eigene Bilder und Cachezuordnungen bleiben beim Ansichtswechsel erhalten.'''

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
