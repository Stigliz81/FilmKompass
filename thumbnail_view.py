"""Paged, responsive cards sharing the library's filtered/sorted row snapshot."""
import tkinter as tk
from tkinter import ttk
from genre_art import page_slice, media_badge, genre_group, GROUPS

class ThumbnailView(ttk.Frame):
    def __init__(self,parent,art,colors,open_title,context):
        super().__init__(parent)
        self.art=art;self.colors=colors;self.open_title=open_title;self.context=context
        self.rows=[];self.number=1;self.size=12;self.columns=0;self.job=None;self.photos=[];self.page_rows=[]
        self.selected_url=None;self.cards={}
        self.canvas=tk.Canvas(self,bg=colors['bg'],highlightthickness=0)
        scrollbar=ttk.Scrollbar(self,command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        footer=ttk.Frame(self,padding=(0,8));footer.pack(side='bottom',fill='x')
        self.previous=ttk.Button(footer,text='‹ Zurück',command=lambda:self.turn(-1));self.previous.pack(side='left')
        self.page_label=ttk.Label(footer,anchor='center');self.page_label.pack(side='left',fill='x',expand=True)
        self.next=ttk.Button(footer,text='Weiter ›',command=lambda:self.turn(1));self.next.pack(side='right')
        scrollbar.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True)
        self.body=ttk.Frame(self.canvas)
        self.item=self.canvas.create_window(0,0,anchor='nw',window=self.body)
        self.canvas.bind('<Configure>',self.schedule_resize)
        self.body.bind('<Configure>',lambda e:self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self.canvas.bind('<MouseWheel>',self.wheel)

    def wheel(self,event):self.canvas.yview_scroll(-int(event.delta/120),'units')

    def schedule_resize(self,event):
        self.canvas.itemconfigure(self.item,width=max(1,event.width))
        columns=max(1,event.width//210)
        if columns!=self.columns:
            if self.job:self.after_cancel(self.job)
            self.job=self.after(100,self.draw)

    def set_rows(self,rows,reset=True):
        self.rows=rows
        if reset:
            self.number=1;self.canvas.yview_moveto(0)
        self.draw()

    def turn(self,delta):
        self.number+=delta;self.draw();self.canvas.yview_moveto(0)

    def draw(self):
        if self.job:self.after_cancel(self.job)
        self.job=None
        page,self.number,pages=page_slice(self.rows,self.number,self.size)
        self.page_rows=page
        self.previous.configure(state='disabled' if self.number==1 else 'normal')
        self.next.configure(state='disabled' if self.number==pages else 'normal')
        self.page_label.configure(text=f'Seite {self.number} von {pages}')
        for row_index in range(24):self.body.rowconfigure(row_index,weight=0,uniform='')
        for widget in self.body.winfo_children():widget.destroy()
        self.photos=[];self.cards={}
        old_columns=self.columns;self.columns=max(1,self.canvas.winfo_width()//210)
        for col in range(max(old_columns,self.columns)):self.body.columnconfigure(col,weight=0,minsize=0)
        for col in range(self.columns):self.body.columnconfigure(col,weight=1,uniform='cards')
        if not page:
            ttk.Label(self.body,text='Keine passenden Titel.',style='Muted.TLabel').grid(padx=18,pady=30);return
        for i,row in enumerate(page):
            card=tk.Frame(self.body,bg=self.colors['panel'],highlightbackground=self.colors['accent'] if row['url']==self.selected_url else self.colors['border'],highlightcolor=self.colors['accent'],highlightthickness=2,takefocus=True)
            self.cards[row['url']]=card
            card.grid(row=i//self.columns,column=i%self.columns,sticky='nsew',padx=6,pady=6)
            self.body.rowconfigure(i//self.columns,weight=1,uniform='cardrows')
            card.bind('<FocusIn>',lambda e,url=row['url']:self.select_card(url))
            card.bind('<Return>',lambda e,url=row['url']:self.open_title(url))
            image=self.art.get(row,(156,234));self.photos.append(image)
            picture=tk.Label(card,image=image,bg=self.colors['panel'],cursor='hand2')
            picture.pack(padx=12,pady=(12,8))
            badge=tk.Label(picture,text=media_badge(row['media_type']),font=('Segoe UI Semibold',9),bg='#24564f' if row['media_type']=='Film' else '#294958',fg='#edf6f6',padx=7,pady=4)
            badge.place(relx=1,x=-5,y=5,anchor='ne')
            title=tk.Label(card,text=row['title'],font=('Segoe UI Semibold',10),bg=self.colors['panel'],fg=self.colors['ink'],wraplength=175,justify='left',anchor='w',cursor='hand2')
            title.pack(fill='x',padx=12)
            tk.Label(card,text=f"{row['year'] or 'Jahr unbekannt'}   ·   Meine Note {row['rating']:g}".replace('.',','),bg=self.colors['panel'],fg=self.colors['accent'],font=('Segoe UI Semibold',10),anchor='w').pack(fill='x',padx=12,pady=6)
            tk.Label(card,text=row.get('genres') or 'Genre unbekannt',bg=self.colors['panel'],fg=self.colors['muted'],font=('Segoe UI',9),wraplength=175,justify='left',anchor='w').pack(fill='x',padx=12,pady=(0,10))
            for widget in (picture,title,badge):widget.bind('<Double-1>',lambda e,url=row['url']:self.open_title(url))
            def bind_all(widget,url):
                widget.bind('<Button-1>',lambda e,u=url:self.select_card(u,True))
                widget.bind('<Button-3>',lambda e,u=url:self.context(e,u))
                widget.bind('<MouseWheel>',self.wheel)
                for child in widget.winfo_children():bind_all(child,url)
            bind_all(card,row['url'])

    def select_card(self,url,focus=False):
        self.selected_url=url
        for key,card in self.cards.items():
            card.configure(highlightbackground=self.colors['accent'] if key==url else self.colors['border'])
        if focus and url in self.cards:self.cards[url].focus_set()

    def destroy(self):
        if self.job:self.after_cancel(self.job)
        super().destroy()
