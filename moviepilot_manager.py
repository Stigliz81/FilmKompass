"""FilmKompass – Bewertungsarchiv für Windows (Tkinter)."""
from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk
from pathlib import Path
from datetime import datetime
import sys
import webbrowser
from urllib.parse import quote
import json
import queue
import threading
import subprocess
from tkinter import simpledialog
from app_info import APP_VERSION, APP_TITLE, PUBLIC_NAME, DISPLAY_VERSION, ICON_PNG, ICON_ICO, SUBTITLE, INDEPENDENCE_NOTICE

FEEDBACK_EMAIL="stigliz1981@gmail.com"
FEEDBACK_MAILTO="mailto:"+FEEDBACK_EMAIL+"?subject="+quote(f"{PUBLIC_NAME} {APP_VERSION} – Feedback")
from donation_assets import DONATIONS, PAYPAL_URL, qr_preview, copy_address
from PIL import ImageTk, Image, ImageOps
from catalog_view import FILTER_LABELS, filter_values, filter_rows, export_public, suggest_export_path, selection_caption, rating_year_counts, filter_display_values
from compact_widgets import MultiSelect, GenreSelect, BarChart, QUICK_HELP, HELP_STEPS, HeadingTip, FilterControl, FILTER_LABEL_FONT, FILTER_LABEL_GAP
from header_backdrop import HeaderBackdrop, BACKGROUNDS, background_choice
from genre_art import ArtCache
from user_images import UserImages, download_image
from thumbnail_view import ThumbnailView

from manager_core import Catalog, normalized_url, data_directory, compare_recommendations, display_date, rating_date
from app_data import register_data_directory, managed_data_preview, delete_managed_data

BASE = Path(__file__).resolve().parent
COLORS = dict(bg="#0e141b", panel="#16212b", side="#1b2b36", field="#1e303b",
              ink="#edf6f6", muted="#93aeb6", accent="#49d6bd",
              accent2="#78bfcf", border="#29424d", danger="#efa3a3")
FONT = ("Segoe UI", 10)


def set_geometry(window, w=1360, h=810):
    width = min(w, window.winfo_screenwidth() - 80)
    height = min(h, window.winfo_screenheight() - 100)
    window.geometry(f"{width}x{height}+30+30")
    window.minsize(min(980, width), min(580, height))


def monitor_work_area(window):
    """Usable monitor rectangle, excluding the Windows taskbar."""
    if sys.platform == 'win32':
        import ctypes
        from ctypes import wintypes
        class MonitorInfo(ctypes.Structure):
            _fields_ = [('size', wintypes.DWORD), ('monitor', wintypes.RECT),
                        ('work', wintypes.RECT), ('flags', wintypes.DWORD)]
        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
        user32.MonitorFromWindow.restype = wintypes.HANDLE
        user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(MonitorInfo)]
        info = MonitorInfo(); info.size = ctypes.sizeof(info)
        monitor = user32.MonitorFromWindow(window.winfo_id(), 2)
        if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
            r = info.work
            return r.left, r.top, r.right, r.bottom
    return 0, 0, window.winfo_screenwidth(), window.winfo_screenheight()


class ScrollPanel(ttk.Frame):
    """Keep the existing forms reachable when Windows scaling reduces space."""
    def __init__(self, parent, padding=(15, 14)):
        super().__init__(parent, style="Panel.TFrame")
        self.canvas = tk.Canvas(self, bg=COLORS["panel"], highlightthickness=0, width=320)
        scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.body = ttk.Frame(self.canvas, style="Panel.TFrame", padding=padding)
        self.item = self.canvas.create_window(0, 0, anchor="nw", window=self.body)
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.item, width=e.width))
        self.body.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.after_idle(self._bind_wheel)

    def _bind_wheel(self):
        def bind(widget):
            if not getattr(widget,'_moviepilot_wheel_bound',False):
                def wheel(event):
                    self.canvas.yview_scroll(-int(event.delta / 120),'units')
                    return 'break'
                widget.bind("<MouseWheel>",wheel,add="+")
                widget._moviepilot_wheel_bound=True
            for child in widget.winfo_children():
                bind(child)
        bind(self)


PUBLIC_PROFILE_HINT="Für den Download müssen deine Bewertungen auf Moviepilot öffentlich sichtbar sein. Aktiviere dazu bei Bedarf in deinen Profileinstellungen ‚Meine Bewertungen öffentlich zeigen‘. Nach dem Download kannst du deine Bewertungen wieder auf privat stellen."
PUBLIC_PROFILE_WARNING="Während der öffentlichen Freigabe können auch andere deine Bewertungen sehen."
PUBLIC_PROFILE_ERROR="Die Bewertungen konnten nicht abgerufen werden. Möglicherweise sind sie nicht öffentlich sichtbar. Bitte prüfe deine Moviepilot Profileinstellungen."


class ProfileDialog(simpledialog.Dialog):
    def __init__(self,parent,initialvalue=''):
        self.initialvalue=initialvalue
        super().__init__(parent,title='Moviepilot-Profil')
    def body(self,master):
        self.configure(bg=COLORS['bg']);master.configure(bg=COLORS['bg'])
        ttk.Label(master,text='Moviepilot-Profillink oder Benutzername:').pack(anchor='w',pady=(5,5))
        self.entry=ttk.Entry(master,width=56);self.entry.insert(0,self.initialvalue);self.entry.pack(fill='x',pady=(0,9))
        ttk.Label(master,text=PUBLIC_PROFILE_HINT,wraplength=520,justify='left').pack(anchor='w',pady=(0,7))
        ttk.Label(master,text=PUBLIC_PROFILE_WARNING,style='Accent.TLabel',wraplength=520,justify='left').pack(anchor='w')
        return self.entry
    def buttonbox(self):
        box=ttk.Frame(self,padding=8);box.pack(fill='x')
        ttk.Button(box,text='Abbrechen',command=self.cancel).pack(side='right',padx=4)
        ttk.Button(box,text='Download starten',command=self.ok,style='Accent.TButton').pack(side='right',padx=4)
        self.bind('<Return>',self.ok);self.bind('<Escape>',self.cancel)
    def apply(self):self.result=self.entry.get()


class Manager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        set_geometry(self)
        self.configure(bg=COLORS["bg"])
        if sys.platform == "win32":
            self.iconbitmap(str(BASE / ICON_ICO))
            self.iconbitmap(default=str(BASE / ICON_ICO))
        self._setup_styles()
        self.db = Catalog(data_directory() / "manager.sqlite")
        register_data_directory(self.db.db_path.parent)
        self.current_url = None
        self._export_queue = queue.Queue()
        self._export_thread = None
        self._export_resume = None
        self._export_running = False
        self.current_reco_links = {}
        self._sort_field = "rated_at" if any(rating_date(r[0]) for r in self.db.con.execute("SELECT rated_at FROM titles")) else "title"
        self._sort_descending = self._sort_field == "rated_at"
        self._last_clicked_column = None
        self.settings = self.load_settings()
        self.images=UserImages(self.db)
        self.art=ArtCache(BASE / "assets/genres",self.images)
        self._list_photo_refs={}
        self._list_job=None
        self.genre_mode="or";self.excluded_genres=set()
        self.filters = {key:set() for key in FILTER_LABELS}
        self._build_window()
        self.refresh_all()
        self.bind("<Control-f>", lambda e: self.focus_search())
        self.bind("<F5>", lambda e: self.refresh_all())
        self.protocol("WM_DELETE_WINDOW", self.close)

    def _setup_styles(self):
        style=ttk.Style(self)
        style.theme_use("clam")
        style.configure(".", font=FONT, background=COLORS["bg"], foreground=COLORS["ink"])
        style.configure("TFrame", background=COLORS["bg"])
        style.configure("Panel.TFrame", background=COLORS["panel"])
        style.configure("TLabel", background=COLORS["bg"], foreground=COLORS["ink"])
        style.configure("Muted.TLabel", foreground=COLORS["muted"])
        style.configure("Title.TLabel", font=("Segoe UI Semibold", 19), foreground=COLORS["ink"])
        style.configure("Section.TLabel", font=("Segoe UI Semibold", 13))
        style.configure("Danger.TButton", foreground=COLORS["danger"])
        style.configure("Card.TLabel", background=COLORS["panel"], foreground=COLORS["ink"])
        style.configure("Accent.TLabel", foreground=COLORS["accent"])
        style.configure("TButton", padding=(12,8), background=COLORS["field"], foreground=COLORS["ink"], borderwidth=0)
        style.map("TButton", background=[("disabled", "#18232a"), ("active", COLORS["border"])], foreground=[("disabled", "#657b82")])
        style.configure("Accent.TButton", padding=(14,9), background="#266952", foreground="#FFFFFF", borderwidth=0)
        style.map("Accent.TButton", background=[("disabled", "#1b3936"), ("active", "#268c79")], foreground=[("disabled", "#75928c")])
        style.configure("ActiveFilter.TButton", background="#24564f", foreground=COLORS["accent"])
        style.map("ActiveFilter.TButton", background=[("active", "#316d63")])
        style.configure("TEntry", fieldbackground=COLORS["field"], foreground=COLORS["ink"], insertcolor=COLORS["ink"], bordercolor=COLORS["border"], padding=7)
        style.configure("TCombobox", fieldbackground=COLORS["field"], background=COLORS["field"], foreground=COLORS["ink"], arrowcolor=COLORS["ink"], padding=6)
        style.configure("Filter.TCombobox", padding=(6,8))
        style.map("TCombobox", fieldbackground=[("readonly",COLORS["field"])], foreground=[("readonly",COLORS["ink"])])
        # Clam's inherited active/disabled choices are light. Cover all relevant states.
        for choice_style in ('TRadiobutton','TCheckbutton'):
            style.configure(choice_style,background=COLORS['bg'],foreground=COLORS['ink'],
                            indicatorbackground=COLORS['field'],indicatorforeground=COLORS['accent'],focuscolor=COLORS['accent'])
            style.map(choice_style,
                background=[('disabled',COLORS['bg']),('pressed','#24564f'),('active',COLORS['field']),('selected','#183e3a'),('focus',COLORS['field']),('!disabled',COLORS['bg'])],
                foreground=[('disabled',COLORS['muted']),('selected',COLORS['accent']),('!disabled',COLORS['ink'])],
                indicatorbackground=[('disabled','#22313b'),('pressed','#24564f'),('selected','#24564f'),('!disabled',COLORS['field'])],
                indicatorforeground=[('disabled',COLORS['muted']),('!disabled',COLORS['accent'])])
        style.configure('TCheckbutton',padding=(0,6))
        style.map('TButton',background=[('disabled','#18232a'),('pressed','#24564f'),('active',COLORS['border']),('focus',COLORS['border']),('!disabled',COLORS['field'])],foreground=[('disabled',COLORS['muted']),('!disabled',COLORS['ink'])])
        style.map('ActiveFilter.TButton',background=[('disabled','#18232a'),('pressed','#24564f'),('active','#294c47'),('focus','#294c47'),('!disabled','#24564f')],foreground=[('disabled',COLORS['muted']),('active',COLORS['ink']),('!disabled',COLORS['accent'])])
        style.map('Accent.TButton',background=[('disabled','#1b3936'),('pressed','#205e50'),('active','#22705f'),('focus','#22705f'),('!disabled','#266952')],foreground=[('disabled',COLORS['muted']),('!disabled','#ffffff')])
        style.map('TCombobox',
                  background=[('disabled','#18232a'),('pressed','#24564f'),('active',COLORS['border']),('!disabled',COLORS['field'])],
                  fieldbackground=[('disabled','#18232a'),('!disabled',COLORS['field'])],
                  foreground=[('disabled',COLORS['muted']),('!disabled',COLORS['ink'])],
                  arrowcolor=[('disabled',COLORS['muted']),('!disabled',COLORS['ink'])],
                  selectbackground=[('!disabled','#24564f')],selectforeground=[('!disabled',COLORS['ink'])])
        # Combobox drop-downs are native Tk listboxes, not ttk elements.
        for option,color in (('background',COLORS['field']),('foreground',COLORS['ink']),('selectBackground','#24564f'),('selectForeground',COLORS['ink']),('disabledForeground',COLORS['muted'])):
            self.option_add('*TCombobox*Listbox.'+option,color)
        # Scope state maps to the two view selectors; inherited clam active white is overridden.
        style.configure('View.TRadiobutton',background=COLORS['bg'],foreground=COLORS['ink'],padding=(5,4),indicatorbackground=COLORS['field'],indicatorforeground=COLORS['accent'],focuscolor=COLORS['accent'])
        style.map('View.TRadiobutton',
            background=[('disabled',COLORS['bg']),('pressed','#24564f'),('active',COLORS['field']),('selected','#183e3a'),('focus',COLORS['field']),('!selected',COLORS['bg'])],
            foreground=[('disabled',COLORS['muted']),('selected',COLORS['accent']),('!disabled',COLORS['ink'])],
            indicatorbackground=[('disabled',COLORS['panel']),('pressed','#24564f'),('selected','#24564f'),('!selected',COLORS['field'])],
            indicatorforeground=[('disabled',COLORS['muted']),('!disabled',COLORS['accent'])])
        rowheight = max(36, round(float(self.tk.call("tk", "scaling")) * 18))
        style.configure("Treeview", background=COLORS["panel"], fieldbackground=COLORS["panel"], foreground=COLORS["ink"], rowheight=rowheight, borderwidth=0)
        style.map("Treeview",background=[('disabled',COLORS['panel']),('selected','#24564f')],foreground=[('disabled',COLORS['muted']),('selected','#ffffff')])
        style.configure("Treeview.Heading", background=COLORS["field"], foreground=COLORS["muted"], padding=(10,11), relief="flat", font=("Segoe UI Semibold",10))
        style.map("Treeview.Heading", background=[("active",COLORS["border"])])
        style.configure("TNotebook", background=COLORS["bg"], borderwidth=0)
        style.configure("TNotebook", bordercolor=COLORS["border"], lightcolor=COLORS["bg"], darkcolor=COLORS["bg"])
        style.configure("TNotebook.Tab", background=COLORS["bg"], foreground=COLORS["muted"], padding=(14,11), font=("Segoe UI Semibold",10), borderwidth=0)
        style.map("TNotebook.Tab", background=[("selected", "#24564f"), ("active", COLORS["field"])], foreground=[("selected", COLORS["accent"])])
        style.map("TNotebook.Tab", padding=[("selected", (14,11))], lightcolor=[("selected",COLORS['bg']),('!selected',COLORS['bg'])], darkcolor=[("selected",COLORS['bg']),('!selected',COLORS['bg'])], bordercolor=[("selected",COLORS['bg']),('!selected',COLORS['bg'])])
        style.configure("TNotebook.Tab", lightcolor=COLORS["bg"], darkcolor=COLORS["bg"], bordercolor=COLORS["bg"])
        style.configure("TScrollbar", background=COLORS["border"], troughcolor=COLORS["panel"], arrowcolor=COLORS["ink"], borderwidth=0, width=15)
        for orient in ("Vertical", "Horizontal"):
            name=f"{orient}.TScrollbar"
            style.configure(name, background=COLORS["border"], troughcolor=COLORS["bg"], lightcolor=COLORS["border"], darkcolor=COLORS["border"], bordercolor=COLORS["bg"], arrowcolor=COLORS["muted"], arrowsize=13, gripcount=0)
            style.map(name,background=[("active", "#39616b"), ("pressed", "#39616b")])
        style.configure("Horizontal.TProgressbar", background=COLORS["accent"], troughcolor=COLORS["field"], borderwidth=0, thickness=5)

    def _build_window(self):
        tk.Frame(self,bg=COLORS["accent"],height=3).pack(fill="x")
        header=HeaderBackdrop(self,BASE / "assets/backgrounds",COLORS,self.settings.get("background"))
        self.header=header;header.pack(fill="x")
        left=ttk.Frame(header)
        header.attach("brand",left)
        with Image.open(BASE / ICON_PNG) as icon:
            self.header_icon=ImageTk.PhotoImage(icon.resize((42,42),Image.Resampling.LANCZOS))
        ttk.Label(left,image=self.header_icon).pack(side="left",padx=(0,12))
        brand=ttk.Frame(left)
        brand.pack(side="left",fill="x",expand=True)
        self.brand_title=tk.Canvas(brand,bg=COLORS['bg'],highlightthickness=0)
        self.brand_title.pack(anchor='w')
        self.brand_subtitle=ttk.Label(brand,text=SUBTITLE,style='Muted.TLabel',wraplength=700)
        self.brand_subtitle.pack(anchor='w',pady=(1,0))

        support=ttk.Frame(header);header.attach("support",support)
        ttk.Button(support,text="♥ Unterstützen",command=self.show_donations).pack(side="right",padx=4)
        ttk.Button(support,text="Kurzanleitung",command=self.show_help).pack(side="right",padx=4)
        self._brand_support=support
        header.bind('<Configure>',lambda e:self.draw_product_title(e.width),add='+')
        self.after_idle(lambda:self.draw_product_title(header.winfo_width()))
        right=ttk.Frame(header)
        header.attach("actions",right)
        self.export_button=ttk.Button(right,text="Von Moviepilot aktualisieren",command=self.start_browser_export,style="Accent.TButton")
        self.export_button.pack(side="left",padx=4)
        self.import_button=ttk.Button(right,text="Datei importieren",command=self.import_dialog)
        self.import_button.pack(side="left",padx=4)
        self.backup_button=ttk.Button(right,text="Sicherung",command=self.backup)
        self.backup_button.pack(side="left",padx=4)
        self.file_export_button=ttk.Button(right,text="Filmdatenbank exportieren",command=self.export_dialog)
        self.file_export_button.pack(side="left",padx=4)

        self.count_labels=[]
        for i,label in enumerate(("Filme","Serien","Gesamt","Ø Note > 0")):
            pane=tk.Frame(header,bg=COLORS["panel"],highlightbackground=COLORS["border"],highlightthickness=1)
            header.attach(f"card{i}",pane)
            tk.Frame(pane,bg=COLORS["accent"] if i<3 else COLORS["accent2"],width=3).pack(side="left",fill="y")
            number=tk.Label(pane,text="—",bg=COLORS["panel"],fg=COLORS["accent"],font=("Segoe UI Semibold",18))
            number.pack(side="left",padx=(15,10),pady=10)
            tk.Label(pane,text=label,bg=COLORS["panel"],fg=COLORS["muted"],font=("Segoe UI Semibold",10)).pack(side="left",padx=(0,15))
            self.count_labels.append(number)

        compact=ttk.Frame(self,padding=(22,0,22,6))
        compact.pack(fill="x")
        self.more_button=ttk.Button(compact,text="Mehr Statistiken  ▾",command=self.toggle_statistics)
        self.more_button.pack(side="left")
        ttk.Label(compact,text="Gesamte Bibliothek",style="Muted.TLabel").pack(side="right")
        self.short_stats=ttk.Label(self,style="Muted.TLabel",wraplength=880)

        self.statusbar=tk.StringVar(value="Bereit.")
        tk.Label(self,textvariable=self.statusbar,bg=COLORS["bg"],fg=COLORS["muted"],font=("Segoe UI",9),anchor="w").pack(side="bottom",fill="x",padx=24,pady=(3,9))

        self.tabs=ttk.Notebook(self)
        self.tabs.pack(fill="both",expand=True,padx=22,pady=(0,8))
        self.page_library=ttk.Frame(self.tabs)
        self.page_stats=ttk.Frame(self.tabs)
        self.page_reco=ttk.Frame(self.tabs)
        self.page_updates=ttk.Frame(self.tabs)
        self.page_data=ttk.Frame(self.tabs)
        for page,title in ((self.page_library,"Bibliothek"),
                           (self.page_stats,"Statistik"),(self.page_reco,"Empfehlungsabgleich"),
                           (self.page_updates,"Änderungen"),(self.page_data,"Einstellungen & Daten")):
            self.tabs.add(page,text=title)
        self._build_library()
        self._build_stats()
        self._build_reco()
        self._build_changes()
        self._build_data_settings()
        self.progress_frame=ttk.Frame(self,padding=(22,8))
        self.progress_text=tk.StringVar(value="")
        ttk.Label(self.progress_frame,textvariable=self.progress_text,style="Accent.TLabel").pack(anchor="w",pady=(0,6))
        self.progress_bar=ttk.Progressbar(self.progress_frame,mode="indeterminate")
        self.progress_bar.pack(fill="x")
        self._poll_job=self.after(250,self._poll_export)

    def draw_product_title(self,width):
        available=max(250,width-44-66-self._brand_support.winfo_reqwidth())
        parts=[(PUBLIC_NAME,False)]
        for size in range(23,11,-1):
            normal=tkfont.Font(family='Segoe UI',size=size)
            bold=tkfont.Font(family='Segoe UI',size=size,weight='bold')
            small=tkfont.Font(family='Segoe UI',size=max(10,size-7))
            total=sum((bold if strong else normal).measure(text) for text,strong in parts)+small.measure('  '+DISPLAY_VERSION)
            if total<=available:break
        self._brand_fonts=(normal,bold,small)
        baseline=max(normal.metrics('ascent'),bold.metrics('ascent'))+2
        height=baseline+max(normal.metrics('descent'),bold.metrics('descent'))+3
        self.brand_title.configure(width=total,height=height)
        self.brand_title.delete('all');x=0
        for text,strong in parts+[("  "+DISPLAY_VERSION,None)]:
            font=small if strong is None else bold if strong else normal
            self.brand_title.create_text(x,baseline-font.metrics('ascent'),text=text,font=font,fill=COLORS['ink'],anchor='nw')
            x+=font.measure(text)
        self.brand_subtitle.configure(wraplength=max(250,available))

    def _build_library(self):
        page=self.page_library
        self.filter_bar=ttk.Frame(page,padding=(0,8,0,4))
        self.filter_bar.pack(fill='x')
        self.filter_lines=[ttk.Frame(self.filter_bar),ttk.Frame(self.filter_bar)]
        self.filter_lines[0].pack(fill='x')
        type_box=ttk.Frame(self.filter_bar)
        ttk.Label(type_box,text='Film/Serie:',font=FILTER_LABEL_FONT).pack(anchor='w',pady=(0,FILTER_LABEL_GAP))
        self.type_filter=tk.StringVar(value='Alle')
        self.type_combo=ttk.Combobox(type_box,textvariable=self.type_filter,values=['Alle','Film','Serie'],state='readonly',width=7,style='Filter.TCombobox')
        self.type_combo.pack(side='bottom',fill='x')
        title_box=ttk.Frame(self.filter_bar)
        ttk.Label(title_box,text='Titel suchen',font=('Segoe UI',9,'bold')).pack(anchor='w')
        self.search_text=tk.StringVar()
        self.search_entry=ttk.Entry(title_box,textvariable=self.search_text,width=12)
        self.search_entry.pack(fill='x',expand=True)
        self.search_text.trace_add('write',lambda *_:self._schedule_filter())
        self.type_filter.trace_add('write',lambda *_:self.refresh_list())
        self.filter_buttons={}
        for key in ('year','rating','genres'):
            self.filter_buttons[key]=FilterControl(self.filter_bar,FILTER_LABELS[key],lambda k=key:self.choose_filter(k))
        for key,label in (('rated_year','Bewertungsjahr'),('rated_month','Bewertungsmonat')):
            self.filter_buttons[key]=FilterControl(self.filter_bar,label,lambda k=key:self.choose_filter(k))
        reset=ttk.Button(self.filter_bar,text='Alles zurücksetzen',command=self.clear_filters)
        self.filter_groups=[type_box,title_box,self.filter_buttons['year'],self.filter_buttons['rating'],self.filter_buttons['rated_year'],self.filter_buttons['rated_month'],self.filter_buttons['genres'],reset]
        self.filter_columns=[type_box]+[self.filter_buttons[key] for key in ('year','rating','rated_year','rated_month','genres')]
        self._filter_layout=None
        self.filter_bar.bind('<Configure>',lambda e:self.layout_filters(e.width))
        self.after_idle(lambda:self.layout_filters(self.filter_bar.winfo_width()))
        self.rows_label=ttk.Label(page,foreground=COLORS["accent"],font=("Segoe UI Semibold",12))
        self.rows_label.pack(fill="x",pady=(5,6))
        self.rows_label.bind("<Configure>",lambda e:self.rows_label.configure(wraplength=max(250,e.width)))
        self.empty_hint=ttk.Frame(page,style="Panel.TFrame",padding=12)
        ttk.Label(self.empty_hint,text="Noch keine Titel. Mit einem öffentlichen Moviepilot-Profillink starten oder CSV / XLSX importieren.",style="Card.TLabel",wraplength=800).pack(anchor="w")
        ttk.Button(self.empty_hint,text="Moviepilot-Profillink eingeben",command=self.start_browser_export).pack(anchor="w",pady=(6,0))
        views=ttk.Frame(page,padding=(0,2,0,6));views.pack(fill="x")
        self.view_choice=tk.StringVar(value=self.settings.get('view','Listenansicht') if self.settings.get('view') in ('Listenansicht','Miniaturansicht') else 'Listenansicht')
        self.view_buttons=[]
        for label in ('Listenansicht','Miniaturansicht'):
            button=ttk.Radiobutton(views,text=label,variable=self.view_choice,value=label,command=self.change_view,style='View.TRadiobutton')
            button.pack(side='left',padx=(0,10));self.view_buttons.append(button)
        ttk.Label(views,text='Pro Seite').pack(side='left',padx=(5,4))
        saved_size=self.settings.get('page_size',12)
        self.page_size=tk.StringVar(value=str(saved_size if saved_size in (6,12,18,24) else 12))
        size=ttk.Combobox(views,textvariable=self.page_size,values=(6,12,18,24),state='readonly',width=3)
        size.pack(side='left');size.bind('<<ComboboxSelected>>',lambda e:self.change_page_size())
        ttk.Label(views,text='Sortieren').pack(side='left',padx=(15,4))
        self.sort_choice=tk.StringVar()
        sorting=ttk.Combobox(views,textvariable=self.sort_choice,values=['Film/Serie','Titel','Jahr','Note','Bewertet am','Genre'],state='readonly',width=12)
        sorting.pack(side='left');sorting.bind('<<ComboboxSelected>>',lambda e:self.choose_sort())
        self.sort_direction=ttk.Button(views,text='↓',width=2,command=self.reverse_sort);self.sort_direction.pack(side='left',padx=4)
        self.library_area=ttk.Frame(page)
        self.library_area.pack(fill="both",expand=True)
        self.listing=ttk.Frame(self.library_area)
        self.listing.pack(fill="both",expand=True)
        listing=self.listing
        columns=("typ","titel","jahr","note","rated_at","genres")
        self.tree=ttk.Treeview(listing,columns=columns,show="tree headings",selectmode="browse")
        colspec=(("typ","Film/Serie",100),("titel","Titel ↗",410),("jahr","Jahr",70),("note","Note",65),("rated_at","Bewertet am",125),("genres","Genre",215))
        self.column_fields={"typ":"media_type","titel":"title","jahr":"year","note":"rating","rated_at":"rated_at","genres":"genres"}
        self.column_titles={key:title for key,title,_ in colspec}
        self.tree.column("#0",width=34,minwidth=34,stretch=False)
        self.tree.heading("#0",text="")
        widths=self.settings.get('columns',{})
        for key,title,width in colspec:
            anchor="center" if key in ("typ","jahr","note","rated_at") else "w"
            self.tree.heading(key,text=title,anchor=anchor,command=lambda column=key:self.sort_column(column))
            saved=widths.get(key,width) if isinstance(widths,dict) else width
            width=max(55,min(2400,saved)) if isinstance(saved,int) else width
            self.tree.column(key,width=width,minwidth=55,stretch=(key=="genres"),anchor=anchor)
        sb=ttk.Scrollbar(listing,orient="vertical",command=self.tree.yview)
        horizontal=ttk.Scrollbar(listing,orient="horizontal",command=self.tree.xview)
        def scrolled(first,last):
            sb.set(first,last);self.schedule_list_images()
        def horizontally_scrolled(first,last):
            horizontal.set(first,last)
            if float(first)<=0 and float(last)>=1:horizontal.grid_remove()
            else:horizontal.grid(row=1,column=0,sticky='ew')
        self.tree.configure(yscrollcommand=scrolled,xscrollcommand=horizontally_scrolled)
        self.tree.bind('<Configure>',lambda e:(self.schedule_list_images(),self.update_title_heading()))
        listing.rowconfigure(0,weight=1); listing.columnconfigure(0,weight=1)
        self.tree.grid(row=0,column=0,sticky="nsew")
        sb.grid(row=0,column=1,sticky="ns")
        horizontal.grid(row=1,column=0,sticky="ew")
        self.tree.tag_configure("alternate",background="#192832")
        self.tree.tag_configure("zero",foreground=COLORS["muted"])
        self.tree.bind("<<TreeviewSelect>>",self._select_row)
        self.tree.bind("<Double-1>",self.open_title)
        self.tree.bind("<Motion>",lambda e:self.tree.configure(cursor="hand2" if self.tree.identify_column(e.x)=="#2" and self.tree.identify_row(e.y) else ""))
        self.tree.bind("<ButtonRelease-1>",lambda e:self.save_columns())
        self.tree.bind('<Button-3>',self.list_context)
        self.title_hint=HeadingTip(self.tree,COLORS)
        self.gallery=ThumbnailView(self.library_area,self.art,COLORS,self.open_moviepilot,self.image_context)
        self.gallery.size=int(self.page_size.get())
        self.apply_view()





    def sort_column(self, column):
        self._sort_descending = not self._sort_descending if self._last_clicked_column == column else False
        self._sort_field = self.column_fields[column]
        self._last_clicked_column = column
        self.refresh_list(select_url=self.current_url)





    def layout_filters(self,width):
        # Flat, equal-status columns; never compress or wrap the heading text.
        search,filters=self.filter_lines
        labels=[self.filter_columns[0].winfo_children()[0]]+[self.filter_buttons[key].label for key in ('year','rating','rated_year','rated_month','genres')]
        minimum=[label.winfo_reqwidth()+12 for label in labels]
        columns=6 if width>=sum(minimum)+36 else 3
        if self._filter_layout==columns:return
        self._filter_layout=columns
        filters.pack(fill='x',pady=(4,0))
        search.columnconfigure(0,weight=1)
        self.filter_groups[1].grid(in_=search,row=0,column=0,sticky='nsew',padx=(0,12))
        self.filter_groups[-1].grid(in_=search,row=0,column=1,sticky='se')
        for group in self.filter_columns:group.grid_forget()
        for column in range(6):filters.columnconfigure(column,weight=0,minsize=0)
        for i,group in enumerate(self.filter_columns):
            row,column=divmod(i,columns)
            size=max(minimum[j] for j in range(column,6,columns))
            filters.columnconfigure(column,weight=1,minsize=size)
            group.grid(in_=filters,row=row,column=column,sticky='nsew',padx=(0,6) if column<columns-1 else 0,pady=(0,4) if columns==3 and row==0 else 0)

    def _build_stats(self):
        panel=ScrollPanel(self.page_stats)
        panel.pack(fill="both",expand=True,pady=10)
        self.stats_summary=ttk.Label(panel.body,style="Card.TLabel",font=("Segoe UI Semibold",13),wraplength=850)
        self.stats_summary.pack(anchor="w",pady=(0,12))
        self.rating_chart=BarChart(panel.body,"Bewertungsverteilung",COLORS)
        self.rating_chart.pack(anchor="w",pady=8)
        self.decade_chart=BarChart(panel.body,"Erscheinungsjahrzehnte",COLORS)
        self.decade_chart.pack(anchor="w",pady=8)
        self.rating_year_chart=BarChart(panel.body,"Bewertungen nach Jahr",COLORS)
        self.rating_year_chart.pack(anchor="w",pady=8)
        panel.body.bind('<Configure>',lambda e:[chart.configure(width=max(240,min(750,e.width))) for chart in (self.rating_chart,self.decade_chart,self.rating_year_chart)],add='+')
        self.rating_year_missing=ttk.Label(panel.body,style="Muted.TLabel")
        self.rating_year_missing.pack(anchor="w")

    def _build_reco(self):
        page=self.page_reco
        bar=ttk.Frame(page,padding=(12,12))
        bar.pack(fill="x")
        ttk.Label(bar,text="Filmtitel / Serientitel einfügen (ein Titel pro Zeile). Bereits bewertete Titel wiederfinden.",style="Muted.TLabel").pack(anchor="w",pady=(0,8))
        self.reco_input=tk.Text(bar,height=6,wrap="word",bg=COLORS["field"],fg=COLORS["ink"],insertbackground=COLORS["ink"],font=FONT,relief="flat",padx=8,pady=8)
        self.reco_input.pack(fill="x",pady=(0,8))
        ttk.Button(bar,text="Mit meiner Moviepilot-Liste abgleichen",style="Accent.TButton",command=self.match_recommendations).pack(anchor="e")
        columns=("input","result","existing","rating")
        self.reco_tree=ttk.Treeview(page,columns=columns,show="headings")
        for col,title,width in (("input","Gesuchter Titel",225),("result","Abgleich",190),("existing","Titel in der Liste",330),("rating","Note",65)):
            self.reco_tree.heading(col,text=title)
            self.reco_tree.column(col,width=width,stretch=col in ("input","existing"))
        self.reco_tree.tag_configure("possible",foreground="#f4d28a")
        self.reco_tree.pack(fill="both",expand=True,padx=12,pady=(0,12))
        self.reco_tree.bind("<Double-1>",self.open_recommendation)

    def _build_changes(self):
        page=self.page_updates
        tools=ttk.Frame(page,padding=(10,10,10,0))
        tools.pack(fill="x")
        ttk.Button(tools,text="Vorhandenen Exporter starten …",command=self.launch_legacy_exporter).pack(side="left",padx=(0,8))
        ttk.Button(tools,text="Danach CSV / XLSX importieren …",command=self.import_dialog).pack(side="left")
        self.last_import_label=ttk.Label(page,text="",style="Muted.TLabel")
        self.last_import_label.pack(anchor="w",padx=10,pady=(15,8))
        columns=("time","change","title","details")
        self.changes_tree=ttk.Treeview(page,columns=columns,show="headings")
        for col,label,width in (("time","Datum",160),("change","Art",130),("title","Titel",275),("details","Details",580)):
            self.changes_tree.heading(col,text=label)
            self.changes_tree.column(col,width=width,stretch=col in ("title","details"))
        self.changes_tree.pack(fill="both",expand=True,padx=10,pady=(0,12))

    def _schedule_filter(self):
        if hasattr(self,"_filter_job") and self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job=self.after(180,self.refresh_list)

    def _build_data_settings(self):
        panel=ScrollPanel(self.page_data,padding=(22,20))
        panel.pack(fill="both",expand=True,pady=12)
        body=panel.body
        ttk.Label(body,text="Einstellungen & Daten",style="Card.TLabel",font=("Segoe UI Semibold",18)).pack(anchor="w",pady=(0,8))
        ttk.Label(body,text=APP_TITLE,style='Card.TLabel').pack(anchor='w',pady=(0,5))
        ttk.Label(body,text=INDEPENDENCE_NOTICE,style='Muted.TLabel',wraplength=750).pack(anchor='w',pady=(0,12))
        self.data_status=tk.StringVar()
        labels=[]
        labels.append(ttk.Label(body,textvariable=self.data_status,style="Card.TLabel",wraplength=750))
        labels[-1].pack(anchor="w",pady=(0,20))
        labels.append(ttk.Label(body,text="Python-Version und portable EXE verwenden standardmäßig denselben lokalen Datenordner. Eine vorhandene Bibliothek wird daraus geladen; es gibt keinen automatischen Beispieldaten- oder Backupimport.",style="Card.TLabel",wraplength=750))
        labels[-1].pack(anchor="w",pady=(0,20))
        ttk.Label(body,text="Feedback & Verbesserungsvorschläge",style="Card.TLabel",font=("Segoe UI Semibold",13)).pack(anchor='w')
        feedback=ttk.Label(body,text="Du hast einen Fehler entdeckt oder eine Idee zur Verbesserung? Ich freue mich über deine Rückmeldung.",style="Card.TLabel",wraplength=750)
        feedback.pack(anchor='w',pady=(7,5));labels.append(feedback)
        self.feedback_address=ttk.Label(body,text=FEEDBACK_EMAIL,style='Accent.TLabel')
        self.feedback_address.pack(anchor='w')
        self.feedback_button=ttk.Button(body,text='E-Mail schreiben',command=self.open_feedback)
        self.feedback_button.pack(anchor='w',pady=(6,16))
        ttk.Label(body,text="Ansicht und Bilder",style="Card.TLabel",font=("Segoe UI Semibold",13)).pack(anchor="w")
        ttk.Label(body,text="Listen-/Miniaturansicht und Seitengröße werden automatisch gespeichert. Genrebilder sind eigene Illustrationen, keine Filmplakate. Rechtsklick auf einen Titel: eigenes Bild auswählen, per HTTPS laden oder Zuordnung entfernen. Nur Bilder mit passenden Nutzungsrechten verwenden. Ein optionales Kinomotiv verbindet Titel, Aktionen und Kennzahlen; die Tabelle bleibt dunkel.",style="Card.TLabel",wraplength=750).pack(anchor="w",pady=(8,12))
        ttk.Label(body,text="Kinomotiv im Kopfbereich",style="Card.TLabel").pack(anchor='w')
        self.background_var=tk.StringVar(value=background_choice(self.settings.get('background')))
        background=ttk.Combobox(body,textvariable=self.background_var,values=list(BACKGROUNDS),state='readonly',width=46)
        background.pack(anchor='w',pady=(6,12));background.bind('<<ComboboxSelected>>',lambda e:self.change_background())
        ttk.Separator(body).pack(fill="x",pady=12)
        ttk.Label(body,text="Bibliothek zurücksetzen",style="Card.TLabel",font=("Segoe UI Semibold",13)).pack(anchor="w")
        labels.append(ttk.Label(body,text="Entfernt Filme, Serien, Bewertungen, Notizen, Favoriten, Sehstatus, Staffeln und Importverlauf. Einstellungen und bestehende Sicherungen bleiben erhalten. Vorher wird eine neue Sicherung erstellt.",style="Card.TLabel",wraplength=750))
        labels[-1].pack(anchor="w",pady=(7,10))
        self.reset_library_button=ttk.Button(body,text="Bibliothek zurücksetzen",command=self.reset_library_dialog,style="Danger.TButton")
        self.reset_library_button.pack(anchor="w",pady=(0,15))
        ttk.Separator(body).pack(fill="x",pady=12)
        ttk.Label(body,text="Alle lokalen Appdaten löschen",style="Card.TLabel",font=("Segoe UI Semibold",13)).pack(anchor="w")
        labels.append(ttk.Label(body,text="Entfernt zusätzlich Einstellungen, Sicherungen, App-Exporte, Diagnosen und gespeicherte Browsersitzungen im eigenen Appdatenordner. Außerhalb dieses Ordners liegende Exporte und unbekannte Dateien bleiben erhalten. Die Anwendung wird danach beendet.",style="Card.TLabel",wraplength=750))
        labels[-1].pack(anchor="w",pady=(7,10))
        self.delete_data_button=ttk.Button(body,text="Alle lokalen Appdaten löschen",command=self.delete_data_dialog,style="Danger.TButton")
        self.delete_data_button.pack(anchor="w",pady=(0,20))
        body.bind("<Configure>",lambda e:[label.configure(wraplength=max(250,e.width-45)) for label in labels],add='+')

    def open_feedback(self):
        if not webbrowser.open(FEEDBACK_MAILTO):
            messagebox.showinfo('Feedback',f'Bitte schreibe an {FEEDBACK_EMAIL}. Es konnte kein E-Mail-Programm geöffnet werden.',parent=self)

    def change_background(self):
        self.settings["background"]=background_choice(self.background_var.get())
        self.header.set_choice(self.settings["background"]);self.save_settings()

    def load_settings(self):
        try:
            value=json.loads((data_directory()/'settings.json').read_text(encoding='utf-8'))
            return value if isinstance(value,dict) else {}
        except (OSError,ValueError): return {}

    def save_settings(self):
        path=data_directory()/'settings.json'
        try:
            temp=path.with_suffix('.tmp')
            temp.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding='utf-8'); temp.replace(path)
        except OSError as exc: self.statusbar.set('Einstellungen konnten nicht gespeichert werden: '+str(exc))

    def update_title_heading(self):
        text='Titel ↗'
        suffix=('  ↓' if self._sort_descending else '  ↑') if self._sort_field=='title' else ''
        self.tree.heading('titel',text=text+suffix)

    def save_columns(self):
        self.update_title_heading()
        self.settings['columns']={key:self.tree.column(key,'width') for key in self.column_fields}
        self.save_settings()

    def choose_filter(self,key):
        values=filter_values(self.db.get_rows())[key]
        def apply(selected):
            self.filters[key]=selected; self.refresh_list()
        if key=='genres':
            def apply_genres(wanted,excluded,mode):
                self.filters['genres']=wanted;self.excluded_genres=excluded-wanted;self.genre_mode=mode;self.refresh_list()
            return GenreSelect(self,values,self.filters[key],self.excluded_genres,self.genre_mode,apply_genres,COLORS)
        return MultiSelect(self,FILTER_LABELS[key],values,self.filters[key],apply,COLORS)

    def clear_filters(self):
        self.genre_mode="or";self.excluded_genres=set()
        self.filters={key:set() for key in FILTER_LABELS}
        self.search_text.set(''); self.type_filter.set('Alle'); self.refresh_list()

    def toggle_statistics(self):
        if self.short_stats.winfo_manager():
            self.short_stats.pack_forget(); self.more_button.configure(text='Mehr Statistiken  ▾')
        else:
            self.short_stats.pack(fill='x',padx=24,pady=(0,8),before=self.tabs)
            self.more_button.configure(text='Weniger Statistiken  ▴')



    def show_help(self):
        dialog=tk.Toplevel(self);dialog.title('Kurzanleitung');set_geometry(dialog,680,650)
        dialog.minsize(520,380);dialog.transient(self)
        panel=ScrollPanel(dialog);panel.pack(fill='both',expand=True)
        body=panel.body;labels=[]
        title=ttk.Label(body,text=PUBLIC_NAME+' in fünf Schritten',style='Card.TLabel',font=('Segoe UI Semibold',15),wraplength=620)
        title.pack(anchor='w',pady=(0,14));labels.append(title)
        for heading,description in HELP_STEPS:
            label=ttk.Label(body,text=heading,style='Card.TLabel',font=('Segoe UI Semibold',11));label.pack(anchor='w');labels.append(label)
            label=ttk.Label(body,text=description,style='Card.TLabel',justify='left',wraplength=620)
            label.pack(fill='x',pady=(3,12));labels.append(label)
        dialog.details_open=False
        detailed=ttk.Label(body,text=QUICK_HELP,style='Card.TLabel',wraplength=620,justify='left');labels.append(detailed)
        def toggle():
            dialog.details_open=not dialog.details_open
            if dialog.details_open:detailed.pack(fill='x',pady=12,before=close_button)
            else:detailed.pack_forget();panel.canvas.yview_moveto(0)
            toggle_button.configure(text='Ausführliche Anleitung schließen' if dialog.details_open else 'Ausführliche Anleitung anzeigen')
        toggle_button=ttk.Button(body,text='Ausführliche Anleitung anzeigen',command=toggle);toggle_button.pack(anchor='w',pady=6)
        close_button=ttk.Button(body,text='Schließen',command=dialog.destroy);close_button.pack(anchor='e',pady=12)
        body.bind('<Configure>',lambda e:[label.configure(wraplength=max(250,e.width-35)) for label in labels],add='+')
        dialog.panel=panel;dialog.toggle_button=toggle_button;dialog.detail_label=detailed
        return dialog

    def _busy_guard(self):
        if self._export_running:
            messagebox.showinfo("Aktualisierung läuft","Bitte den laufenden Abruf oder Import abwarten. Suche, Sortierung und Navigation bleiben verfügbar.",parent=self)
            return True
        return False

    def reset_library_dialog(self):
        if self._busy_guard(): return
        if not messagebox.askyesno("Bibliothek zurücksetzen", "Alle Filme, Serien, Bewertungen, Notizen, Favoriten, Sehstatus, Staffeln und Importverlauf dieser Bibliothek zurücksetzen?\n\nEinstellungen und Sicherungen bleiben erhalten. Vorher wird eine Sicherung angelegt. Es erfolgt keine automatische Wiederherstellung.",parent=self):
            return
        try:
            self.db.backup()
            self.db.reset_library()
        except Exception as exc:
            messagebox.showerror("Zurücksetzen nicht abgeschlossen",str(exc),parent=self)
            return
        self.current_url=None
        self.refresh_all()
        self.tabs.select(self.page_library)
        self.statusbar.set("Bibliothek zurückgesetzt. Einstellungen und Sicherungen sind erhalten.")

    def delete_data_dialog(self):
        if self._busy_guard(): return
        root=self.db.db_path.parent
        try:
            preview=managed_data_preview(root)
        except Exception as exc:
            messagebox.showerror("Löschung nicht möglich",str(exc),parent=self)
            return
        scope=(f"Appdatenordner:\n{root}\n\n{preview['files']} verwaltete Dateien, {preview['bytes']/1048576:.1f} MiB.\n"
               "Bibliothek, Einstellungen, Sicherungen, App-Exporte, Diagnosen und lokale Browser-Anmeldungen werden gelöscht.\n"
               f"{len(preview['foreign'])} unbekannte Dateien/Ordner bleiben erhalten. Exporte außerhalb dieses Ordners bleiben erhalten.\n\n"
               "Externe Moviepilot-Browser und andere App-Instanzen vorher schließen. Fortfahren?")
        if not messagebox.askyesno("Alle lokalen Appdaten löschen",scope,parent=self): return
        confirm=simpledialog.askstring("Endgültig löschen","Zum endgültigen Löschen ALLES LÖSCHEN eingeben:",parent=self)
        if confirm != "ALLES LÖSCHEN": return
        self.db.close()
        try:
            result=delete_managed_data(root)
        except Exception as exc:
            messagebox.showerror("Löschung unvollständig",str(exc)+"\n\nDie Anwendung wird beendet. Verbliebene Dateien wurden nicht als gelöscht bestätigt.",parent=self)
        else:
            messagebox.showinfo("Appdaten gelöscht",f"Verwaltete Appdaten gelöscht. {len(result['foreign'])} unbekannte Dateien/Ordner wurden nicht bearbeitet.\nDie Anwendung wird beendet.",parent=self)
        self.destroy()

    def focus_search(self):
        self.tabs.select(self.page_library)
        self.search_entry.focus_set()
        self.search_entry.select_range(0,"end")

    def refresh_all(self):
        stats=self.db.summary()
        for lbl,val in zip(self.count_labels,[stats["count_by_type"].get("Film",0),stats["count_by_type"].get("Serie",0),stats["total"],f"{stats['average']:.2f}".replace(".",",")]):
            lbl.configure(text=f"{val:,}".replace(",",".") if isinstance(val,int) else val)
        if stats["total"] == 0:
            self.empty_hint.pack(fill="x",pady=(0,10),before=self.library_area)
        else:
            self.empty_hint.pack_forget()
        self.refresh_list()
        self.refresh_statistics()
        self.refresh_changes()
        self.data_status.set(f"{stats['total']} aktive Titel · Datenbank: {self.db.db_path}")

    def refresh_list(self, select_url=None, reset_page=True):
        if not hasattr(self,"tree"):
            return
        old_url=select_url or self.current_url
        self.tree.delete(*self.tree.get_children())
        rows=self.db.get_rows(query=self.search_text.get(),media_type=self.type_filter.get(),sort_by=self._sort_field,descending=self._sort_descending)
        self.visible_rows=filter_rows(rows,self.filters,self.genre_mode,self.excluded_genres)
        rows=self.visible_rows
        for key,button in self.filter_buttons.items():
            values=self.filters[key]
            active=bool(values) or (key=='genres' and bool(self.excluded_genres))
            button.set_values(filter_display_values(key,values,self.excluded_genres if key=='genres' else (),self.genre_mode))
            button.configure(style='ActiveFilter.TButton' if active else 'TButton')
        for column,title in self.column_titles.items():
            suffix = ("  ↓" if self._sort_descending else "  ↑") if self.column_fields[column] == self._sort_field else ""
            self.tree.heading(column,text=title+suffix)
        self.update_title_heading()
        shown=None
        self._list_photo_refs={}
        for i,x in enumerate(rows):
            rating=f"{x['rating']:g}".replace(".",",")
            tags=["alternate"] if i%2 else []
            if x["rating"]==0: tags.append("zero")
            iid=f"item{i}"
            self.tree.insert("","end",iid=iid,values=(x["media_type"],x["title"],x["year"],rating,display_date(x["rated_at"]),x["genres"]),tags=tags)
            self.tree.set(iid,"titel",x["title"])
            if x["url"]==old_url:
                shown=iid
            # Item mapping is based on immutable Moviepilot URL, not ambiguous names.
        self._tree_url={f"item{i}":x["url"] for i,x in enumerate(rows)}
        active=bool(self.search_text.get().strip()) or self.type_filter.get()!='Alle' or any(self.filters.values()) or bool(self.excluded_genres)
        self.rows_label.configure(text=selection_caption(rows) if active else 'Gesamte Bibliothek')
        if shown:
            self.tree.selection_set(shown)
            self.tree.see(shown)
        elif self.current_url and self.current_url not in self._tree_url.values():
            self.current_url=None
        label={'media_type':'Film/Serie','title':'Titel','year':'Jahr','rating':'Note','rated_at':'Bewertet am','genres':'Genre'}[self._sort_field]
        self.sort_choice.set(label);self.sort_direction.configure(text='↓' if self._sort_descending else '↑')
        if self.view_choice.get()=='Miniaturansicht':self.gallery.set_rows(self.visible_rows,reset=reset_page)
        else:
            self.gallery.rows=self.visible_rows
            if reset_page:self.gallery.number=1
        self.schedule_list_images()

    def apply_view(self):
        self.listing.pack_forget()
        if hasattr(self,'gallery'):self.gallery.pack_forget()
        if self.view_choice.get()=='Miniaturansicht':
            for iid in self._list_photo_refs:
                if self.tree.exists(iid):self.tree.item(iid,image='')
            self._list_photo_refs={}
            self.gallery.pack(fill='both',expand=True)
            self.gallery.set_rows(getattr(self,'visible_rows',[]),reset=False)
        else:
            self.listing.pack(fill='both',expand=True);self.schedule_list_images()

    def change_view(self):
        self.apply_view();self.settings['view']=self.view_choice.get();self.save_settings()

    def change_page_size(self):
        self.gallery.size=int(self.page_size.get());self.gallery.number=1
        if self.view_choice.get()=='Miniaturansicht':self.gallery.set_rows(self.visible_rows)
        self.settings['page_size']=self.gallery.size;self.save_settings()

    def choose_sort(self):
        fields={'Film/Serie':'media_type','Titel':'title','Jahr':'year','Note':'rating','Bewertet am':'rated_at','Genre':'genres'}
        self._sort_field=fields[self.sort_choice.get()];self._last_clicked_column=None;self.refresh_list()

    def reverse_sort(self):
        self._sort_descending=not self._sort_descending;self.refresh_list()

    def schedule_list_images(self):
        if self._list_job:self.after_cancel(self._list_job)
        self._list_job=self.after(70,self.load_list_images)

    def load_list_images(self):
        self._list_job=None
        if not hasattr(self,'visible_rows') or self.view_choice.get()!='Listenansicht' or not self.tree.winfo_ismapped():return
        count=len(self.visible_rows)
        if not count:self._list_photo_refs={};return
        first,last=self.tree.yview()
        start=max(0,int(first*count)-1)
        end=min(count,int(last*count)+2,start+max(6,self.tree.winfo_height()//36+5))
        old=self._list_photo_refs;refs={}
        for i in range(start,end):
            iid=f'item{i}'
            if self.tree.exists(iid):
                photo=self.art.get(self.visible_rows[i],(20,30));refs[iid]=photo
                self.tree.item(iid,image=photo)
        for iid in old.keys()-refs.keys():
            if self.tree.exists(iid):self.tree.item(iid,image='')
        self._list_photo_refs=refs

    def list_context(self,event):
        iid=self.tree.identify_row(event.y)
        if iid:
            self.tree.selection_set(iid);self.image_context(event,self._tree_url[iid])

    def image_context(self,event,url):
        menu=tk.Menu(self,tearoff=False,bg=COLORS['panel'],fg=COLORS['ink'])
        menu.add_command(label='Bei Moviepilot öffnen',command=lambda:self.open_moviepilot(url))
        menu.add_separator()
        menu.add_command(label='Eigenes Bild auswählen …',command=lambda:self.choose_user_image(url))
        menu.add_command(label='Bild über HTTPS-URL hinzufügen …',command=lambda:self.url_user_image(url))
        menu.add_command(label='Eigenes Bild entfernen',command=lambda:self.remove_user_image(url))
        try:menu.tk_popup(event.x_root,event.y_root)
        finally:menu.grab_release()

    def choose_user_image(self,url):
        if self._busy_guard():return
        filename=filedialog.askopenfilename(parent=self,title='Eigenes Bild · nur mit passenden Nutzungsrechten',filetypes=[('Bilder','*.jpg *.jpeg *.png *.webp')])
        if not filename:return
        try:
            self.images.choose_file(url,filename);self.art.clear();self.refresh_list(reset_page=False)
            self.statusbar.set('Eigenes Bild lokal gespeichert; Quelldatei bleibt unverändert.')
        except Exception as exc:messagebox.showerror('Bild nicht übernommen',str(exc),parent=self)

    def url_user_image(self,url):
        if self._busy_guard():return
        address=simpledialog.askstring('Eigenes Bild per HTTPS','Direkte HTTPS-Bildadresse eingeben. Nur Bilder mit passenden Nutzungsrechten verwenden. Der Bildserver erhält die Anfrage; keine Anmeldung oder Cookies.',parent=self)
        if not address:return
        def work(notify,measure):
            notify('Eigenes Bild wird geprüft und geladen')
            return dict(image_url=url,image_data=download_image(address.strip()))
        self._start_task(work,'Eigenes Bild wird geladen')

    def remove_user_image(self,url):
        if self._busy_guard():return
        self.images.remove(url);self.art.clear();self.refresh_list(reset_page=False)
        self.statusbar.set('Eigene Bildzuordnung entfernt; Genreillustration wieder aktiv.')

    def _select_row(self,_event=None):
        selected=self.tree.selection()
        self.current_url=self._tree_url.get(selected[0]) if selected else None

    def open_title(self,event):
        if self.tree.identify_region(event.x,event.y)!="cell" or self.tree.identify_column(event.x)!="#2": return
        item=self.tree.identify_row(event.y)
        self.open_moviepilot(self._tree_url.get(item,''))

    def open_moviepilot(self,url):
        try:
            verified=normalized_url(url)
        except ValueError:
            messagebox.showinfo("Kein Moviepilot-Link","Für diesen lokal importierten Titel liegt kein gültiger Moviepilot-Link vor. Ein Download oder alter URL-Export kann ihn ergänzen.",parent=self)
            return
        if not webbrowser.open(verified):
            messagebox.showerror("Browser","Der Standardbrowser konnte nicht geöffnet werden.",parent=self)

    def refresh_statistics(self):
        s=self.db.summary()
        self.stats_summary.configure(text=f"Gesamte Bibliothek: {s['total']} Titel   ·   Ø {s['average']:.2f} / 10 (ohne 0)   ·   {s['zeros']} Nullwertungen")
        self.rating_chart.set_data(list(s['rating_hist'].items()))
        self.decade_chart.set_data(sorted(s['decades'].items()))
        years,missing=rating_year_counts(self.db.get_rows())
        self.rating_year_chart.set_data(years)
        self.rating_year_missing.configure(text=f"Ohne gültiges Bewertungsdatum: {missing}" if missing else "")
        def mode(values):
            high=max(values.values(),default=0)
            return ', '.join(str(k) for k,v in values.items() if v==high and high) or '—'
        self.short_stats.configure(text=f"Nullwertungen: {s['zeros']}  ·  Häufigste Bewertungsgruppe: {mode(s['rating_hist'])}  ·  Häufigstes Jahrzehnt: {mode(s['decades'])}")

    def match_recommendations(self):
        self.reco_tree.delete(*self.reco_tree.get_children())
        self.current_reco_links={}
        raw=self.reco_input.get("1.0","end-1c")
        results=compare_recommendations(raw,self.db)
        for i,item in enumerate(results):
            iid=f"rec{i}"
            tags=("possible",) if item["status"]=="Möglicher Treffer – prüfen" else ()
            rating="" if item["rating"] is None else f"{item['rating']:g}".replace(".",",")
            self.reco_tree.insert("","end",iid=iid,values=(item["query"],item["status"],item["title"],rating),tags=tags)
            self.current_reco_links[iid]=item["url"]
        exact=sum(x["status"]=="Schon bewertet" for x in results)
        potential=sum(x["status"]=="Möglicher Treffer – prüfen" for x in results)
        self.statusbar.set(f"Abgleich: {exact} exakte Treffer, {potential} mögliche Treffer, {len(results)-exact-potential} nicht enthalten.")

    def open_recommendation(self,_event=None):
        selected=self.reco_tree.selection()
        if selected:
            url=self.current_reco_links.get(selected[0])
            if url:
                self.open_moviepilot(url)

    def refresh_changes(self):
        self.changes_tree.delete(*self.changes_tree.get_children())
        last=self.db.last_import()
        if last:
            self.last_import_label.configure(text=(f"Letzter Import: {last['created_at'][:19].replace('T',' ')}   •   "
               f"{last['added']} neu  ·  {last['changed']} geändert  ·  {last['unchanged']} unverändert  ·  "
               f"{last['unavailable']} nicht mehr im Export"))
        else:
            self.last_import_label.configure(text="Noch kein Import durchgeführt.")
        for i,item in enumerate(self.db.recent_changes()):
            self.changes_tree.insert("","end",iid=f"chg{i}",values=(item["created_at"][:19].replace("T"," "),item["change_type"],item["title"],item["details"][:350]))

    def import_dialog(self):
        if self._busy_guard(): return
        filenames=filedialog.askopenfilenames(title="Vollständige Moviepilot-Exporte wählen (CSV oder XLSX)",
                            filetypes=[("Moviepilot Exporte","*.csv *.xlsx"),("CSV", "*.csv"),("Excel","*.xlsx")])
        if not filenames: return
        if not messagebox.askyesno("Moviepilot importieren","Vollständige Exporte verwenden, keine Teillisten. Neue Bewertungen werden ergänzt, bestehende aktualisiert. Persönliche Angaben bleiben erhalten; vorher wird eine Sicherung erstellt. Fortfahren?",parent=self): return
        path=self.db.db_path
        def work(notify, measure):
            database=Catalog(path)
            try:
                result=database.import_files(list(filenames),notify=notify)
            finally:
                database.close()
            return dict(imported=result,warnings=[])
        self._start_task(work,"Dateiimport wird vorbereitet")

    def show_donations(self):
        window=tk.Toplevel(self);self.donation_dialog=window
        window.title(PUBLIC_NAME+' unterstützen');window.configure(bg=COLORS['bg']);window.transient(self)
        left,top,right,bottom=monitor_work_area(self)
        width=max(320,min(560,self.winfo_screenwidth()-70));height=max(1,min(814,bottom-top-80))
        x=max(left,min(left+60,right-width-16));y=top+32
        window.geometry(f'{width}x{height}{x:+d}{y:+d}');window.minsize(min(340,width),min(350,height))
        if sys.platform=='win32':window.iconbitmap(str(BASE/ICON_ICO))
        panel=ScrollPanel(window,padding=(16,14));panel.pack(fill='both',expand=True,padx=10,pady=10)
        body=panel.body
        ttk.Label(body,text='Danke für deine Unterstützung',style='Card.TLabel',font=('Segoe UI Semibold',14)).pack(anchor='w')
        friendly=ttk.Label(body,text='Wenn dir FilmKompass gefällt und du meine Arbeit unterstützen möchtest, freue ich mich über eine kleine Spende. ❤️\n\nVielen Dank für deine Unterstützung und viel Spaß mit dem Programm!',wraplength=460,justify='left',style='Card.TLabel')
        friendly.pack(fill='x',pady=(8,12))
        selected=tk.StringVar(value='PayPal');window.selected=selected
        picker=ttk.Combobox(body,textvariable=selected,values=list(DONATIONS),state='readonly')
        picker.pack(fill='x',pady=(0,12))
        canvas=tk.Canvas(body,bg='white',highlightthickness=0,width=260,height=260)
        canvas.pack(pady=(0,10));window.qr_canvas=canvas
        network=ttk.Label(body,style='Card.TLabel',foreground=COLORS['accent'],font=('Segoe UI Semibold',11),wraplength=460)
        network.pack(fill='x',pady=(0,6));window.network_label=network
        addresses=ttk.Frame(body,style='Panel.TFrame');addresses.pack(fill='x')
        feedback=tk.StringVar(value='');window.copy_feedback=feedback
        ttk.Label(body,textvariable=feedback,style='Card.TLabel').pack(anchor='w',pady=3)
        warning=ttk.Label(body,style='Card.TLabel',wraplength=460,justify='left')
        warning.pack(fill='x',pady=(4,8))
        paypal=ttk.Button(body,text='Mit PayPal unterstützen ↗',style='Accent.TButton',command=lambda:webbrowser.open(PAYPAL_URL))
        last_size=[None];pending=[None]
        def resize():
            pending[0]=None
            available=max(120,body.winfo_width()-34)
            size=max(120,min(300,available,round(height*.40)))
            for label in (friendly,network,warning):label.configure(wraplength=max(180,body.winfo_width()-5))
            font=tkfont.Font(window,font=FONT)
            for entry in getattr(window,'address_widgets',[]):
                available_width=max(60,entry.winfo_width()-18)
                pixels=font.measure(entry.get('1.0','end-1c'))
                entry.configure(height=max(2,(pixels+available_width-1)//available_width+1))
            if last_size[0]==(selected.get(),size):return
            last_size[0]=(selected.get(),size)
            image=ImageTk.PhotoImage(qr_preview(BASE/'assets/donations/originals',selected.get(),size))
            canvas.image=image;canvas.configure(width=size,height=size);canvas.delete('all');canvas.create_image(size//2,size//2,image=image)
        def schedule(event=None):
            if pending[0]:window.after_cancel(pending[0])
            pending[0]=window.after(90,resize)
        def update(*_):
            config=DONATIONS[selected.get()];network.configure(text=config['network']);feedback.set('')
            for child in addresses.winfo_children():child.destroy()
            window.address_widgets=[];window.copy_buttons=[]
            for label,address in config['addresses']:
                ttk.Label(addresses,text=label,style='Card.TLabel').pack(anchor='w',pady=(0,4))
                entry=tk.Text(addresses,height=3 if '://' in address else 2,width=20,wrap='char',font=FONT,bg=COLORS['field'],fg=COLORS['ink'],selectbackground='#24564f',relief='flat',padx=7,pady=6)
                entry.insert('1.0',address);entry.configure(state='disabled');entry.pack(fill='x')
                button=ttk.Button(addresses,text='Adresse kopieren',command=lambda target=address:copy_address(window,target,feedback))
                button.pack(anchor='e',pady=(5,7));window.address_widgets.append(entry);window.copy_buttons.append(button)
            warning.configure(text='Bitte ausschließlich das angegebene Netzwerk verwenden.' if config['crypto'] else '')
            paypal.pack_forget()
            if selected.get()=='PayPal':paypal.pack(fill='x',pady=5)
            schedule();panel.canvas.yview_moveto(0)
            panel._bind_wheel()
        def close():
            if pending[0]:window.after_cancel(pending[0])
            window.destroy()
        picker.bind('<<ComboboxSelected>>',update);selected.trace_add('write',update)
        body.bind('<Configure>',schedule,add='+');window.protocol('WM_DELETE_WINDOW',close)
        update();window.panel=panel;return window

    def launch_legacy_exporter(self):
        """Compatibility bridge for the user's already working exporter (source unknown)."""
        path=filedialog.askopenfilename(title="Vorhandenen Moviepilot-Exporter auswählen",
                        filetypes=[("Exporter-Startdatei","*.bat *.cmd *.exe *.py"),("Alle Dateien","*.*")])
        if not path:
            return
        file=Path(path)
        if file.suffix.lower() not in (".bat",".cmd",".exe",".py"):
            messagebox.showerror("Unbekannter Dateityp", "Bitte eine .bat, .cmd, .exe oder .py auswählen.")
            return
        if not messagebox.askyesno("Exporter starten",
                                  f"Diese von dir ausgewählte Datei wird jetzt ausgeführt:\n\n{file}\n\n"
                                  "Nur starten, wenn du dieser Datei vertraust. Anschließend das Exporter-Ergebnis importieren."):
            return
        try:
            if file.suffix.lower()==".py":
                own_env=file.parent/".venv"/"Scripts"/"python.exe"
                python_bin=own_env if own_env.is_file() else sys.executable
                if getattr(sys, "frozen", False) and not own_env.is_file():
                    import shutil
                    python_bin = shutil.which("python") or shutil.which("py")
                    if not python_bin:
                        raise OSError("Externe Python-Exporter benötigen Python oder ihre eigene .venv. Der integrierte Abruf benötigt das nicht.")
                subprocess.Popen([str(python_bin),str(file)],cwd=str(file.parent))
            else:
                if sys.platform!="win32":
                    raise OSError("Dieser Startdateityp wird nur unter Windows unterstützt.")
                import os
                os.startfile(str(file))
            self.statusbar.set("Vorhandener Exporter gestartet. Danach die erzeugten CSV/XLSX-Dateien importieren.")
        except Exception as exc:
            messagebox.showerror("Exporter konnte nicht gestartet werden",str(exc))

    def start_browser_export(self):
        if self._export_running: return
        cfg_file=data_directory()/"settings.json"
        config={}
        if cfg_file.is_file():
            try:
                loaded=json.loads(cfg_file.read_text(encoding="utf-8"))
                config=loaded if isinstance(loaded,dict) else {}
            except (OSError,ValueError): pass
        username=ProfileDialog(self,config.get("username","")).result
        if username is None: return
        try:
            from moviepilot_exporter import validate_profile
            username=validate_profile(username)
            cfg_file.parent.mkdir(parents=True,exist_ok=True)
            temp=cfg_file.with_suffix(".tmp")
            self.settings["username"]=username
            temp.write_text(json.dumps(self.settings,ensure_ascii=False,indent=2),encoding="utf-8")
            temp.replace(cfg_file)
        except (ValueError,OSError) as exc:
            messagebox.showerror("Moviepilot-Profil",str(exc),parent=self)
            return
        root=self.db.db_path.parent
        def work(notify, measure):
            from update_worker import update_library
            return update_library(username,root,notify,measure)
        self._start_task(work,"Verbindung zu Moviepilot wird hergestellt",profile_download=True)

    def _start_task(self, work, message, profile_download=False):
        if self._export_running: return
        self._export_running=True
        for button in (self.export_button,self.import_button,self.backup_button,self.file_export_button,self.reset_library_button,self.delete_data_button):
            button.configure(state="disabled")
        self.progress_text.set(message)
        self.statusbar.set(message)
        self.progress_frame.pack(fill="x",before=self.tabs)
        self._indeterminate_progress()
        def run():
            try:
                result=work(lambda msg:self._export_queue.put(("progress",msg)),lambda value:self._export_queue.put(("measure",value)))
                self._export_queue.put(("done",result))
            except Exception as exc:
                detail=str(exc)
                if profile_download and any(marker in detail for marker in ('Keine strukturierten Bewertungsdaten','Keine auslesbaren Bewertungen','Seitenformat wurde nicht erkannt')):
                    detail=PUBLIC_PROFILE_ERROR+'\n\nDetails: '+detail
                self._export_queue.put(("error",detail))
        self._export_thread=threading.Thread(target=run,daemon=True,name="moviepilot-update")
        self._export_thread.start()

    def _indeterminate_progress(self):
        self.progress_bar.stop()
        self.progress_bar.configure(mode="indeterminate",value=0)
        self.progress_bar.start(12)

    def _poll_export(self):
        try:
            while True:
                event,payload=self._export_queue.get_nowait()
                if event=="progress":
                    self.statusbar.set(payload)
                    self.progress_text.set(payload)
                    if "Seite " not in payload:
                        self._indeterminate_progress()
                elif event=="measure":
                    self.progress_bar.stop()
                    self.progress_bar.configure(mode="determinate",maximum=payload["pages"],value=payload["page"])
                    noun="Filme" if payload["kind"]=="Film" else "Serien"
                    self.progress_text.set(f"{noun} werden geladen: Seite {payload['page']} von {payload['pages']} · {payload['loaded']} von {payload['expected']} Bewertungen")
                elif event=="done":
                    self._finish_export()
                    if 'image_data' in payload:
                        try:
                            self.images.save(payload['image_url'],payload['image_data'],validated=True)
                            self.art.clear();self.refresh_list(reset_page=False)
                            self.statusbar.set('Eigenes Bild gespeichert.')
                        except Exception as exc:messagebox.showerror('Bild nicht gespeichert',str(exc),parent=self)
                        continue
                    if self._last_clicked_column is None and any(rating_date(r[0]) for r in self.db.con.execute("SELECT rated_at FROM titles")):
                        self._sort_field="rated_at"
                        self._sort_descending=True
                    self.refresh_all()
                    counts=self.db.summary()["count_by_type"]
                    result=payload["imported"]
                    export=payload.get("export")
                    movies,series=(export.movies,export.series) if export else (counts.get("Film",0),counts.get("Serie",0))
                    summary=f"{movies} Filme · {series} Serien\n{result['added']} neu · {result['changed']} geändert · {result['unchanged']} unverändert · {result['unavailable']} nicht mehr im Abruf"
                    warnings=payload.get("warnings",[])
                    if result.get('identity_note'): warnings=[*warnings,result['identity_note']]
                    self.statusbar.set("Aktualisierung abgeschlossen · "+summary.replace("\n"," · "))
                    messagebox.showinfo("Aktualisierung abgeschlossen",summary+("\n\n"+"\n".join(warnings) if warnings else ""),parent=self)
                elif event=="error":
                    self._finish_export()
                    self.statusbar.set("Aktualisierung fehlgeschlagen; bestehende Bibliothek bleibt erhalten.")
                    messagebox.showerror("Aktualisierung fehlgeschlagen",payload+"\n\nBestehende Bewertungen und persönliche Angaben bleiben erhalten.",parent=self)
        except queue.Empty:
            pass
        if self.winfo_exists(): self._poll_job=self.after(100,self._poll_export)

    def _finish_export(self):
        self._export_running=False
        self.progress_bar.stop()
        self.progress_frame.pack_forget()
        for button in (self.export_button,self.import_button,self.backup_button,self.file_export_button,self.reset_library_button,self.delete_data_button):
            button.configure(state="normal")

    def backup(self):
        if self._busy_guard(): return
        try:
            path=self.db.backup()
            messagebox.showinfo("Sicherung erstellt",f"Sicherung gespeichert unter:\n{path}")
        except Exception as e:
            messagebox.showerror("Sicherung",str(e))

    def export_dialog(self):
        if self._busy_guard(): return
        dialog=tk.Toplevel(self); dialog.title("Filmdatenbank exportieren")
        dialog.transient(self); dialog.configure(bg=COLORS['bg']); dialog.resizable(False,False)
        body=ttk.Frame(dialog,padding=22); body.pack(fill="both")
        scope=tk.StringVar(value='all'); fmt=tk.StringVar(value='.xlsx')
        dialog.scope=scope;dialog.format=fmt
        all_rows=self.db.get_rows(sort_by=self._sort_field,descending=self._sort_descending)
        selected=list(self.visible_rows)
        ttk.Label(body,text="Was möchtest du exportieren?",style="Section.TLabel").pack(anchor="w",pady=(0,12))
        ttk.Radiobutton(body,text=f"Gesamte Filmdatenbank ({len(all_rows)} Titel)",variable=scope,value='all').pack(anchor="w",pady=5)
        ttk.Radiobutton(body,text=f"Aktuell gefilterte Ergebnisse ({len(selected)} Titel)",variable=scope,value='filtered',state='normal' if selected else 'disabled').pack(anchor="w",pady=5)
        ttk.Label(body,text="Format").pack(anchor="w",pady=(14,4))
        ttk.Combobox(body,textvariable=fmt,values=['.xlsx','.csv'],state='readonly',width=16).pack(anchor="w")
        ttk.Label(body,text="Typ · Titel · Jahr · Note · Bewertet am · Genre\nAktuelle Sortierung wird übernommen.",style="Muted.TLabel").pack(anchor="w",pady=16)
        def save():
            rows=all_rows if scope.get()=='all' else selected
            if not rows:
                messagebox.showinfo("Leere Auswahl","Keine Titel zum Exportieren.",parent=dialog); return
            folder=getattr(self,'_export_directory',Path.home()/'Documents')
            if not folder.is_dir():folder=Path.home()
            proposal=suggest_export_path(folder,scope.get(),fmt.get())
            while True:
                filename=filedialog.asksaveasfilename(parent=dialog,title=f"{len(rows)} Titel exportieren",defaultextension=fmt.get(),initialdir=str(proposal.parent),initialfile=proposal.name,confirmoverwrite=False,filetypes=[('Excel','*.xlsx')] if fmt.get()=='.xlsx' else [('CSV','*.csv')])
                if not filename:return
                path=Path(filename);self._export_directory=path.parent
                overwrite=False
                if path.exists():
                    answer=messagebox.askyesnocancel('Datei bereits vorhanden',f'{path.name} existiert bereits.\n\nJa: diese Datei ausdrücklich überschreiben.\nNein: neuen, eindeutigen Namen im Speicherdialog anbieten.\nAbbrechen: nicht exportieren.',parent=dialog)
                    if answer is None:return
                    if not answer:
                        proposal=suggest_export_path(path.parent,scope.get(),fmt.get());continue
                    overwrite=True
                try:
                    export_public(path,rows,overwrite=overwrite)
                    dialog.destroy();self.statusbar.set(f"{len(rows)} Titel exportiert: {path.name}")
                    return
                except FileExistsError:
                    # A file appeared after the dialog: return to an unused suggestion.
                    proposal=suggest_export_path(path.parent,scope.get(),fmt.get())
                except Exception as exc:
                    messagebox.showerror("Export fehlgeschlagen",str(exc),parent=dialog);return
        dialog.save_button=ttk.Button(body,text="Speichern …",command=save,style="Accent.TButton")
        dialog.save_button.pack(anchor="e")
        dialog.grab_set()
        return dialog

    def close(self):
        if self._export_running:
            messagebox.showinfo("Aktualisierung läuft","Bitte Abruf und Speicherung abwarten, bevor du die Anwendung schließt.",parent=self)
            return
        self.save_columns()
        self.db.close()
        for name in ('_poll_job','_filter_job','_list_job'):
            job=getattr(self,name,None)
            if job: self.after_cancel(job)
        self.destroy()


if __name__=="__main__":
    try:
        app=Manager()
        app.mainloop()
    except Exception as exc:
        import traceback
        traceback.print_exc()
        try:
            messagebox.showerror(PUBLIC_NAME,f"Programmfehler:\n{exc}")
        except Exception:
            pass
        raise
