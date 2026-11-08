"""Paged, responsive cards sharing the library's filtered/sorted row snapshot."""
import tkinter as tk
from tkinter import ttk
from genre_art import page_slice, media_badge, genre_group, GROUPS
from compact_widgets import scroll_wheel
from manager_core import normalized_url

def source_link(url):
    try:return normalized_url(url) if url.startswith('https://') else ''
    except (ValueError,AttributeError):return ''

CARD_SIZES={'Klein':(185,154),'Mittel':(242,210),'Groß':(306,278)}

def card_geometry(choice,width,scaling):
    minimum,poster=CARD_SIZES.get(choice,CARD_SIZES['Mittel'])
    factor=max(.8,float(scaling)/(96/72))
    columns=max(1,min({'Klein':6,'Mittel':5,'Groß':4}.get(choice,5),int(width)//round(minimum*factor)))
    cell=max(1,min(int(width)//columns,round(minimum*factor*1.15)))
    image_width=max(1,min(round(poster*factor),cell-24))
    return columns,(image_width,round(image_width*1.5)),max(30,cell-30)

class ThumbnailView(ttk.Frame):
    def __init__(self,parent,art,colors,open_title,context,*,navigation=True,outer_scroll=None):
        super().__init__(parent)
        self.art=art;self.colors=colors;self.open_title=open_title;self.context=context
        self.rows=[];self.number=1;self.size=12;self.columns=0;self.job=None;self.photos=[];self.page_rows=[]
        self.selected_url=None;self.cards={}
        self.card_size='Mittel'
        self.outer_scroll=outer_scroll
        self.canvas=tk.Canvas(self,bg=colors['bg'],highlightthickness=0)
        scrollbar=ttk.Scrollbar(self,command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        footer=ttk.Frame(self,padding=(0,6))
        if navigation:footer.pack(side='bottom',anchor='center')
        self.previous=ttk.Button(footer,text='‹ Zurück',command=lambda:self.turn(-1));self.previous.pack(side='left')
        self.page_label=ttk.Label(footer,anchor='center',width=22);self.page_label.pack(side='left',padx=8)
        self.next=ttk.Button(footer,text='Weiter ›',command=lambda:self.turn(1));self.next.pack(side='left')
        scrollbar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.body=ttk.Frame(self.canvas)
        self.item=self.canvas.create_window(0,0,anchor='nw',window=self.body)
        self.canvas.bind('<Configure>',self.schedule_resize)
        self.body.bind('<Configure>',self._layout)
        self.bind('<Map>',lambda e:self.request_draw() if e.widget is self else None)
        self.canvas.bind('<MouseWheel>',self.wheel)

    def wheel(self,event):
        first,last=self.canvas.yview()
        edge=(event.delta>0 and first<=0) or (event.delta<0 and last>=1)
        target=self.outer_scroll if self.outer_scroll is not None and (event.state & 1 or edge) else self.canvas
        return scroll_wheel(target,event.delta)

    def _layout(self,event=None):
        height=max(1,self.body.winfo_reqheight())
        top=min(max(0,self.canvas.canvasy(0)),max(0,height-self.canvas.winfo_height()))
        self.canvas.configure(scrollregion=(0,0,self.canvas.winfo_width(),height))
        self.canvas.yview_moveto(top/height)

    def request_draw(self):
        if self.job:self.after_cancel(self.job)
        self.job=self.after(80,self.draw)

    def schedule_resize(self,event):
        self.canvas.itemconfigure(self.item,width=max(1,event.width))
        self.request_draw()

    def set_rows(self,rows,reset=True):
        self.rows=rows
        if reset:
            self.number=1;self.canvas.yview_moveto(0)
        self.request_draw()

    def turn(self,delta):
        self.number+=delta;self.request_draw();self.canvas.yview_moveto(0)

    def draw(self):
        if self.job:self.after_cancel(self.job)
        self.job=None
        if not self.winfo_ismapped() or self.canvas.winfo_width()<10:return
        page,self.number,pages=page_slice(self.rows,self.number,self.size)
        self.page_rows=page
        self.previous.configure(state='disabled' if self.number==1 else 'normal')
        self.next.configure(state='disabled' if self.number==pages else 'normal')
        self.page_label.configure(text=f'Seite {self.number} von {pages}')
        old_columns=self.columns
        self.columns,poster_size,wrap=card_geometry(self.card_size,self.canvas.winfo_width(),self.tk.call('tk','scaling'))
        # Prepare optional artwork before removing any visible cards.
        images=[]
        for row in page:
            try:images.append(self.art.get(row,poster_size,contain=True))
            except (OSError,ValueError,tk.TclError):images.append(None)
        for row_index in range(24):self.body.rowconfigure(row_index,weight=0,uniform='')
        for widget in self.body.winfo_children():widget.destroy()
        self.photos=[];self.cards={}
        for col in range(max(old_columns,self.columns)):self.body.columnconfigure(col,weight=0,minsize=0,uniform='')
        self.body.grid_anchor('n')
        for col in range(self.columns):self.body.columnconfigure(col,weight=0,minsize=wrap+30,uniform='cards')
        if not page:
            ttk.Label(self.body,text='Keine passenden Titel.',style='Muted.TLabel').grid(padx=18,pady=30);return
        for i,row in enumerate(page):
            shadow=tk.Frame(self.body,bg='#080e15')
            shadow.grid(row=i//self.columns,column=i%self.columns,sticky='nsew',padx=5,pady=5)
            card=tk.Frame(shadow,bg=self.colors['panel'],highlightbackground=self.colors['accent'] if row['url']==self.selected_url else '#3a5364',highlightcolor=self.colors['accent'],highlightthickness=1,takefocus=True)
            self.cards[row['url']]=card
            card.pack(fill='both',expand=True,padx=(0,2),pady=(0,3))
            self.body.rowconfigure(i//self.columns,weight=1,uniform='cardrows')
            card.bind('<FocusIn>',lambda e,url=row['url']:self.select_card(url))
            card.bind('<Return>',lambda e,url=row['url']:self.open_title(url))
            image=images[i]
            if image:self.photos.append(image)
            picture=tk.Label(card,image=image if image else '',text='' if image else 'Kein Vorschaubild',bg=self.colors['panel'],fg=self.colors['muted'],cursor='hand2')
            if not image:picture.configure(width=18,height=10)
            picture.pack(padx=5,pady=(5,4))
            valid=source_link(row['url'])
            title=tk.Label(card,text=row['title']+(' ↗' if valid else ''),font=('Segoe UI Semibold',10),bg=self.colors['panel'],fg=self.colors['ink'],wraplength=wrap,justify='left',anchor='w',cursor='hand2')
            title.pack(fill='x',padx=8)
            tk.Label(card,text=f"{row['year'] or 'Jahr unbekannt'} · Meine Note {row['rating']:g}".replace('.',','),bg=self.colors['panel'],fg=self.colors['accent'],font=('Segoe UI Semibold',10),wraplength=wrap,justify='left',anchor='w').pack(fill='x',padx=8,pady=3)
            tk.Label(card,text=media_badge(row['media_type'])+' · '+(row.get('genres') or 'Genre unbekannt'),bg=self.colors['panel'],fg=self.colors['muted'],font=('Segoe UI',9),wraplength=wrap,justify='left',anchor='w').pack(fill='x',padx=8,pady=(0,6))
            valid=source_link(row['url'])
            picture.configure(cursor='hand2' if valid else '')
            title.configure(cursor='hand2' if valid else '')
            if valid:
                for widget in (picture,title):widget.bind('<Double-1>',lambda e,url=valid:self.open_title(url))
            def bind_all(widget,url):
                widget.bind('<Button-1>',lambda e,u=url:self.select_card(u,True))
                widget.bind('<Button-3>',lambda e,u=url:self.context(e,u))
                widget.bind('<MouseWheel>',self.wheel)
                for child in widget.winfo_children():bind_all(child,url)
            bind_all(card,row['url'])

    def select_card(self,url,focus=False):
        self.selected_url=url
        for key,card in self.cards.items():
            if card.winfo_exists():card.configure(highlightbackground=self.colors['accent'] if key==url else '#3a5364')
        if focus and url in self.cards and self.cards[url].winfo_exists():self.cards[url].focus_set()

    def destroy(self):
        if self.job:self.after_cancel(self.job)
        super().destroy()
