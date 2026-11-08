"""Moviepilot source links for secondary tables; preserve ttk selection bindings."""
import time
import tkinter as tk
from urllib.parse import urlsplit
from manager_core import normalized_url


def moviepilot_link(value):
    if not isinstance(value, str) or not value or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    try:
        parts = urlsplit(value)
        if parts.scheme != 'https' or parts.netloc.lower() not in ('moviepilot.de', 'www.moviepilot.de'):
            return None
        if '\\' in value or '%' in parts.path:
            return None
        result = normalized_url(value)
        path = urlsplit(result).path
        if len(path.strip('/').split('/')) != 2 or path.rsplit('/', 1)[1] in ('', '.', '..'):
            return None
        return result
    except (ValueError, TypeError):
        return None


class TableLinks:
    def __init__(self, tree, columns, url_for, open_url):
        self.tree = tree
        self.columns = set(columns)
        self.url_for = url_for
        self.open_url = open_url
        self.last = (None, 0)
        self.menu = tk.Menu(tree, tearoff=False)
        tree.bind('<ButtonRelease-1>', self.click, add='+')
        tree.bind('<Double-1>', self.double, add='+')
        tree.bind('<Motion>', self.motion, add='+')
        tree.bind('<Leave>', lambda e: tree.configure(cursor=''), add='+')
        tree.bind('<Button-3>', self.context, add='+')

    def target(self, event, link_column=True):
        t = self.tree
        if t.identify_region(event.x, event.y) != 'cell':
            return None, None
        iid = t.identify_row(event.y)
        displayed = t.cget('displaycolumns')
        displayed = t.cget('columns') if displayed == ('#all',) else displayed
        index = int(t.identify_column(event.x)[1:]) - 1
        if link_column and (index < 0 or index >= len(displayed) or displayed[index] not in self.columns):
            return iid, None
        return iid, moviepilot_link(self.url_for(iid)) if iid else None

    def open(self, url):
        now = time.monotonic()
        if url and (url != self.last[0] or now-self.last[1] > .6):
            self.last = (url, now)
            self.open_url(url)

    def click(self, event):
        self.open(self.target(event)[1])

    def double(self, event):
        self.open(self.target(event, False)[1])
        return 'break'

    def motion(self, event):
        self.tree.configure(cursor='hand2' if self.target(event)[1] else '')

    def context(self, event):
        iid, url = self.target(event, False)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        self.menu.delete(0, 'end')
        self.menu.add_command(label='Bei Moviepilot öffnen ↗', state='normal' if url else 'disabled',
                              command=lambda: self.open(url))
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()
