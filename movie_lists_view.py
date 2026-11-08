"""Small independent lists area using the Manager's existing background queue."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import tkinter as tk
import threading
from tkinter import filedialog, messagebox, ttk

from table_links import TableLinks
from moviepilot_lists import ExportError, ListStore, export_list, import_public_list, validate_list_url, compare_list, list_summary


class MovieListsView(ttk.Frame):
    def __init__(self, parent, manager):
        super().__init__(parent, padding=16)
        self.manager = manager
        self.cancel_event = threading.Event()
        self.store = ListStore(manager.db.con)
        self.url = tk.StringVar()
        self.selection = tk.StringVar()
        self.info = tk.StringVar(value='Eine öffentliche Moviepilot-Liste eingeben und importieren.')
        self.filter_hidden=bool(manager.settings.get('list_filters_hidden',False))
        self.filter_toggle=ttk.Button(self,style='ActiveFilter.TButton',command=self.toggle_filters)
        self.filter_toggle.pack(anchor='w',pady=(0,6))
        self.scroll=manager.tab_scroll_class(self);self.scroll.pack(fill='both',expand=True)
        controls=ttk.Frame(self.scroll.body);controls.pack(fill='x')
        self.split=ttk.Panedwindow(self.scroll.body,orient='vertical');self.split.pack(fill='both',expand=True)
        info=ttk.Frame(self.split);self.split.add(info,weight=0)
        ttk.Label(info,text='Geladene Liste · Bibliotheksvergleich',style='Accent.TLabel').pack(anchor='w',pady=4)
        self.controls=controls
        body=controls
        self.scroll.attach_result(self.split)
        result=ttk.Frame(self.split);self.split.add(result,weight=1)
        ttk.Label(body, text='Filmlisten', style='Section.TLabel').pack(anchor='w')
        ttk.Label(body, text='Einzelne öffentliche Listen und Kataloge privat speichern (Katalog: maximal 200 Titel).',
                  style='Muted.TLabel').pack(anchor='w', pady=(4, 12))
        url_row = ttk.Frame(body)
        url_row.pack(fill='x')
        url_row.columnconfigure(0, weight=1)
        self.url_entry = ttk.Entry(url_row, textvariable=self.url)
        self.url_entry.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        self.import_button = ttk.Button(url_row, text='Liste importieren', command=self.import_url, style='Accent.TButton')
        self.paste_button=ttk.Button(url_row,text='Einfügen',command=self.paste_url)
        self.paste_button.grid(row=0,column=1,padx=(0,8))
        self.import_button.grid(row=0, column=2)
        self.cancel_button=ttk.Button(url_row,text='Abbrechen',command=self.cancel_event.set,state='disabled')
        self.cancel_button.grid(row=0,column=3,padx=(8,0))
        ttk.Label(body, text='moviepilot.de/liste/… oder moviepilot.de/filme/beste/…', style='Muted.TLabel').pack(anchor='w', pady=(4, 12))
        local_row = ttk.Frame(body)
        local_row.pack(fill='x')
        local_row.columnconfigure(0, weight=1)
        self.picker = ttk.Combobox(local_row, textvariable=self.selection, state='readonly')
        self.picker.grid(row=0, column=0, sticky='ew', padx=(0, 8))
        self.picker.bind('<<ComboboxSelected>>', self.show_selected)
        self.export_button = ttk.Button(local_row, text='Excel / CSV …', command=self.export_selected)
        self.export_button.grid(row=0, column=1, padx=(0, 8))
        self.delete_button = ttk.Button(local_row, text='Lokal entfernen', command=self.delete_selected)
        self.delete_button.grid(row=0, column=2)
        details=ttk.Label(body, textvariable=self.info, wraplength=1000, style='Muted.TLabel')
        details.pack(anchor='w', pady=10)
        body.bind('<Configure>',lambda e:details.configure(wraplength=max(250,e.width-15)),add='+')
        self.filter=tk.StringVar(value='Alle')
        filters=ttk.Combobox(body,textvariable=self.filter,state='readonly',values=(
            'Alle','Bereits bewertet','Ohne verlässliche eigene Bewertung','Zuordnung unklar'))
        filters.pack(anchor='w',fill='x',pady=(0,8))
        filters.bind('<<ComboboxSelected>>',self.show_selected)
        self.summary=tk.StringVar()
        summary=ttk.Label(result,textvariable=self.summary,style='Muted.TLabel',wraplength=1000)
        summary.pack(side='bottom',fill='x',pady=4)
        summary.bind('<Configure>',lambda e:summary.configure(wraplength=max(250,e.width)),add='+')
        table = ttk.Frame(result)
        table.pack(fill='both', expand=True)
        table.rowconfigure(0, weight=1)
        table.columnconfigure(0, weight=1)
        columns = ('position', 'media_type', 'title', 'year', 'community_rating', 'library_status', 'own_rating', 'rating_difference', 'moviepilot_id', 'url')
        self.tree = ttk.Treeview(table, columns=columns, show='headings', selectmode='browse')
        for key, label, width in zip(columns, ('Position', 'Typ', 'Titel', 'Jahr', 'Moviepilot Ø', 'Bibliotheksstatus', 'Eigene Bewertung', 'Eigene − MP Ø', 'Moviepilot-ID', 'Moviepilot-URL'),
                                     (72, 75, 280, 75, 110, 265, 135, 120, 115, 320)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=60, stretch=key == 'title')
        self.tree.grid(row=0, column=0, sticky='nsew')
        vertical = ttk.Scrollbar(table, orient='vertical', command=self.tree.yview)
        vertical.grid(row=0, column=1, sticky='ns')
        horizontal = ttk.Scrollbar(table, orient='horizontal', command=self.tree.xview)
        horizontal.grid(row=1, column=0, sticky='ew')
        self.tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.tree.heading('url', text='Moviepilot-URL ↗')
        self.links=TableLinks(self.tree,('url',),lambda iid:self.tree.set(iid,'url'),manager.open_moviepilot)
        self.refresh()
        manager.prepare_split(self.split,30,lambda:30)
        self.apply_filter_visibility()

    def apply_filter_visibility(self):
        active=' · 1 Filter aktiv' if self.filter.get()!='Alle' else ''
        self.filter_toggle.configure(text=('▾ Filter anzeigen' if self.filter_hidden else '▴ Filter ausblenden')+active)
        if self.filter_hidden:self.controls.pack_forget()
        elif not self.controls.winfo_manager():self.controls.pack(fill='x',before=self.split)

    def toggle_filters(self):
        self.filter_hidden=not self.filter_hidden
        self.manager.settings['list_filters_hidden']=self.filter_hidden;self.manager.save_settings()
        self.apply_filter_visibility()
        if self.filter_hidden:self.scroll.reveal_results()
        else:self.scroll.canvas.yview_moveto(0)

    def paste_url(self):
        try:
            value=self.clipboard_get().strip()
            validate_list_url(value)
        except tk.TclError:
            messagebox.showinfo('Einfügen','Die Zwischenablage enthält keinen Text.',parent=self)
            return
        except ExportError:
            messagebox.showinfo('Einfügen','Die Zwischenablage enthält keine gültige öffentliche Moviepilot-Listenadresse.',parent=self)
            return
        if self.url_entry.selection_present():
            self.url_entry.delete('sel.first','sel.last')
        self.url_entry.insert('insert',value)
        self.url_entry.focus_set()

    def refresh(self, source_url=None):
        previous = self.selected()
        target = source_url or (previous['source_url'] if previous else None)
        self.saved_lists = self.store.lists()
        self.picker.configure(values=[f"{r['name']} · {r['entry_count']} Titel · #{r['source_id']}" for r in self.saved_lists])
        if self.saved_lists:
            index = next((i for i, r in enumerate(self.saved_lists) if r['source_url'] == target), 0)
            self.picker.current(index)
        else:
            self.selection.set('')
        self.show_selected()

    def selected(self):
        if not hasattr(self, 'saved_lists'):
            return None
        index = self.picker.current()
        return self.saved_lists[index] if 0 <= index < len(self.saved_lists) else None

    def show_selected(self, event=None):
        self.apply_filter_visibility()
        self.tree.delete(*self.tree.get_children())
        selected = self.selected()
        if selected:
            rows=compare_list(self.store.entries(selected['source_url']),self.manager.db.get_rows(hidden=True))
            stats=list_summary(rows)
            fmt=lambda v: '—' if v is None else f'{v:.2f}'.replace('.',',')
            self.summary.set(f"{stats['total']} Titel · bewertet {stats['rated']} · vorhanden ohne Note {stats['unrated']} · fehlt {stats['missing']} · unklar {stats['unclear']}\n"
                f"MP Ø {fmt(stats['community_average'])} (n={stats['community_count']}) · Eigene Ø {fmt(stats['own_average'])} (n={stats['own_count']}) · Δ eigene − MP {fmt(stats['difference_average'])} (n={stats['paired_count']})")
            for row in rows:
                status=row['library_status']
                if (self.filter.get()=='Bereits bewertet' and status!='Bereits bewertet'
                        or self.filter.get()=='Ohne verlässliche eigene Bewertung' and status not in ('Nicht in Bibliothek','Vorhanden ohne verlässliche Bewertung')
                        or self.filter.get()=='Zuordnung unklar' and status!='Zuordnung unklar'):
                    continue
                self.tree.insert('', 'end', values=tuple('' if row[k] is None else
                    f'{row[k]:.2f}'.replace('.',',') if type(row[k]) is float else row[k] for k in self.tree['columns']))
            warnings = json.loads(selected['warnings'])
            self.info.set(f"{selected['entry_count']} Filme/Serien aus {selected['source_count']} Listeneinträgen · "
                          f"{selected['skipped_count']} andere Einträge ausgelassen · Stand {selected['imported_at']}\n"
                          f"{selected['source_url']}" + (f"\n{len(warnings)} Hinweis(e): " + ' '.join(warnings[:2]) if warnings else ''))
        else:
            self.info.set('Noch keine lokalen Filmlisten vorhanden.')
            self.summary.set('')
        self.set_busy(self.manager._export_running)

    def set_busy(self, busy):
        self.import_button.configure(state='disabled' if busy else 'normal')
        self.url_entry.configure(state='disabled' if busy else 'normal')
        self.paste_button.configure(state='disabled' if busy else 'normal')
        self.cancel_button.configure(state='normal' if busy and getattr(self.manager,'_task_is_list',False) else 'disabled')
        self.picker.configure(state='disabled' if busy else 'readonly')
        state = 'normal' if not busy and self.selected() else 'disabled'
        self.export_button.configure(state=state)
        self.delete_button.configure(state=state)

    def import_url(self):
        if self.manager._busy_guard(allow_covers=True):
            return
        try:
            url = validate_list_url(self.url.get())
        except ExportError as error:
            messagebox.showerror('Filmliste', str(error), parent=self)
            return
        self.url.set(url)
        self.cancel_event.clear()
        if any(row['source_url'] == url for row in self.saved_lists):
            if not messagebox.askyesno('Lokale Liste aktualisieren',
                    'Die lokale Kopie dieser Liste durch den aktuellen vollständigen Abruf ersetzen?', parent=self):
                return
        db_path = self.manager.db.db_path
        self.manager._start_task(lambda notify, progress: import_public_list(url, db_path, notify, progress, cancelled=self.cancel_event.is_set),
                                 'Filmliste wird geladen', list_import=True)

    def delete_selected(self):
        if self.manager._busy_guard(allow_covers=True):
            return
        selected = self.selected()
        if selected and messagebox.askyesno('Lokale Liste entfernen',
                f"Die lokale Liste „{selected['name']}“ entfernen?", parent=self):
            self.store.delete(selected['source_url'])
            self.refresh()

    def export_selected(self):
        if self.manager._busy_guard(allow_covers=True):
            return
        selected = self.selected()
        if not selected:
            return
        filename = filedialog.asksaveasfilename(parent=self, title='Filmliste exportieren',
            initialfile=f"FilmKompass_Filmliste_{selected['source_id']}_{datetime.now():%Y%m%d_%H%M%S}.xlsx",
            defaultextension='.xlsx', confirmoverwrite=False,
            filetypes=[('Excel', '*.xlsx'), ('CSV (UTF-8)', '*.csv')])
        if not filename:
            return
        path = Path(filename)
        overwrite = path.exists()
        if overwrite and not messagebox.askyesno('Datei überschreiben', f'{path.name} überschreiben?', parent=self):
            return
        try:
            export_list(path, selected, compare_list(self.store.entries(selected['source_url']),self.manager.db.get_rows(hidden=True)), overwrite=overwrite)
            self.manager.statusbar.set(f'Filmliste exportiert: {path.name}')
        except (OSError, ValueError) as error:
            messagebox.showerror('Listenexport fehlgeschlagen', str(error), parent=self)
