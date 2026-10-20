"""Optional, bounded header artwork using the existing local cinema motifs."""
from collections import OrderedDict
from pathlib import Path
import tkinter as tk
from PIL import Image, ImageOps, ImageEnhance, ImageTk

BACKGROUNDS={'Ohne Hintergrundbild':None,'Filmgalerie':'gallery.jpg','Filmarchiv':'archive.jpg','Kinostudio':'studio.jpg','Helleres Kino in Blau/Petrol/Warmlicht':'cinema.jpg'}

def background_choice(value):
    aliases={'Einfarbig':'Ohne Hintergrundbild','Helleres Kino':'Helleres Kino in Blau/Petrol/Warmlicht','Kino · Blau & warmes Licht':'Helleres Kino in Blau/Petrol/Warmlicht'}
    value=aliases.get(value,value)
    return value if value in BACKGROUNDS else 'Ohne Hintergrundbild'

class HeaderBackdrop(tk.Canvas):
    def __init__(self,parent,folder,colors,choice):
        super().__init__(parent,bg=colors['bg'],height=190,highlightthickness=0)
        self.folder=Path(folder);self.colors=colors;self.choice=background_choice(choice)
        self.source=None;self.photo=None;self.cache=OrderedDict();self.job=None;self.parts={}
        self.image_item=self.create_image(0,0,anchor='nw')
        self.bind('<Configure>',self.schedule)
        self.set_choice(self.choice)

    def attach(self,name,widget):
        self.parts[name]=(widget,self.create_window(0,0,window=widget,anchor='nw'))
        self.schedule()

    def set_choice(self,choice):
        self.choice=background_choice(choice);self.source=None;self.cache.clear()
        filename=BACKGROUNDS[self.choice]
        if filename:
            try:
                with Image.open(self.folder/'banners'/filename) as image:
                    self.source=ImageEnhance.Brightness(image.convert('RGB')).enhance(.43)
            except (OSError,ValueError):pass
        self.schedule()

    def schedule(self,event=None):
        if self.job:self.after_cancel(self.job)
        self.job=self.after(100,self.render)

    def render(self):
        self.job=None
        if len(self.parts)!=7:return
        width=max(1,self.winfo_width());pad=22
        brand,brand_item=self.parts['brand'];support,support_item=self.parts['support']
        top=max(brand.winfo_reqheight(),support.winfo_reqheight())
        self.coords(brand_item,pad,17);self.coords(support_item,max(pad,width-pad-support.winfo_reqwidth()),17)
        actions,actions_item=self.parts['actions'];y=17+top+12
        self.coords(actions_item,pad,y);y+=actions.winfo_reqheight()+16
        card_width=max(1,(width-2*pad-27)//4)
        card_height=max(self.parts[f'card{i}'][0].winfo_reqheight() for i in range(4))
        for i in range(4):
            _,item=self.parts[f'card{i}'];self.coords(item,pad+i*(card_width+9),y)
            self.itemconfigure(item,width=card_width,height=card_height)
        height=y+card_height+10
        if int(self.cget('height'))!=height:self.configure(height=height)
        if self.source is None:
            self.itemconfigure(self.image_item,image='');self.photo=None;return
        key=(width,height)
        if key not in self.cache:
            fitted=ImageOps.fit(self.source,key,Image.Resampling.LANCZOS,centering=(.5,.5))
            tint=Image.new('RGB',key,'#102934')
            self.cache[key]=ImageTk.PhotoImage(Image.blend(fitted,tint,.24))
            while len(self.cache)>3:self.cache.popitem(last=False)
        self.cache.move_to_end(key);self.photo=self.cache[key]
        self.itemconfigure(self.image_item,image=self.photo);self.tag_lower(self.image_item)

    def destroy(self):
        if self.job:self.after_cancel(self.job)
        super().destroy()
