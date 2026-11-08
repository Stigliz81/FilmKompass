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
        super().__init__(parent,bg=colors['bg'],height=120,highlightthickness=0)
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
        if len(self.parts)!=9:return
        width=max(1,self.winfo_width());pad=22
        compact = getattr(self,'compact',False)
        top_pad=6
        brand,brand_item=self.parts['brand'];support,support_item=self.parts['support']
        top=max(brand.winfo_reqheight(),support.winfo_reqheight())
        brand_x=max(pad,(width-brand.winfo_reqwidth())//2)
        support_x=max(pad,width-pad-support.winfo_reqwidth())
        support_y=top_pad if brand_x+brand.winfo_reqwidth()+12<=support_x else top_pad+brand.winfo_reqheight()+3
        top=max(brand.winfo_reqheight(),support_y-top_pad+support.winfo_reqheight())
        self.coords(brand_item,brand_x,top_pad)
        self.coords(support_item,support_x,support_y)
        actions,actions_item=self.parts['actions'];y=top_pad+top+3
        details,details_item=self.parts['details']
        columns=4 if sum(b.winfo_reqwidth()+6 for b in actions.buttons)+details.winfo_reqwidth()+10<=width-2*pad else 2
        for i,button in enumerate(actions.buttons):button.grid(row=i//columns,column=i%columns)
        actions.update_idletasks()
        self.coords(actions_item,pad,y)
        self.coords(details_item,max(pad,width-pad-details.winfo_reqwidth()),y)
        description,description_item=self.parts['description']
        room=width-2*pad-actions.winfo_reqwidth()-details.winfo_reqwidth()-24
        factor=float(self.tk.call('tk','scaling'))/(96/72)
        if room>=round(300*factor):
            description.configure(wraplength=room)
            self.coords(description_item,pad+actions.winfo_reqwidth()+10,y)
            self.itemconfigure(description_item,state='normal')
            actions.update_idletasks()
            row_height=max(actions.winfo_reqheight(),details.winfo_reqheight(),description.winfo_reqheight())
        else:
            self.itemconfigure(description_item,state='hidden' if compact else 'normal')
            row_height=max(actions.winfo_reqheight(),details.winfo_reqheight())
            if not compact:
                description.configure(wraplength=width-2*pad)
                self.coords(description_item,pad,y+row_height+3)
                actions.update_idletasks();row_height+=description.winfo_reqheight()+3
        y+=row_height+4
        card_width=max(1,min(round(230*factor),(width-2*pad-27)//4))
        card_height=max(self.parts[f'card{i}'][0].winfo_reqheight() for i in range(4))
        for i in range(4):
            _,item=self.parts[f'card{i}'];self.coords(item,pad+i*(card_width+9),y)
            self.itemconfigure(item,width=card_width,height=card_height)
        for i in range(4):
            self.itemconfigure(self.parts[f'card{i}'][1],state='hidden' if compact else 'normal')
        height=(y if compact else y+card_height)+round(10*factor)
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
