"""Original genre art selection; source genres are never changed."""
import re
import unicodedata
from collections import OrderedDict
from PIL import Image, ImageOps, ImageTk

GROUPS = {
    'action':'Action', 'scifi':'Science Fiction', 'fantasy':'Fantasy', 'drama':'Drama',
    'thriller':'Thriller', 'crime':'Krimi', 'horror':'Horror', 'comedy':'Komödie',
    'romance':'Romanze', 'adventure':'Abenteuer', 'animation':'Animation',
    'documentary':'Dokumentation', 'western':'Western', 'history':'Historie & Krieg',
}
# The first matching group wins. Specific visual genres precede general drama.
PRIORITY = ('documentary','animation','horror','scifi','fantasy','western','history',
            'thriller','crime','action','adventure','comedy','romance','drama')
TOKENS = {
 'documentary':('dokument','biopic','reality','unterhaltungssendung','mockumentary'),
 'animation':('animation','anime','zeichentrick'),
 'horror':('horror','zombie','vampir','werwolf','slasher','splatter','spuk','geister','grusel','monster','exorzist','kannibal','torture porn'),
 'scifi':('science fiction','hard sf','cyberpunk','space opera','zeitreise','utopie','dystopie','endzeit'),
 'fantasy':('fantasy','marchen','superheld'),
 'western':('western',),
 'history':('historien','historisch','krieg','militar','ritter','sandalen','monumental','samurai'),
 'thriller':('thriller','serienkiller'),
 'crime':('krimi','kriminal','detektiv','gangster','mafia','polizei','buddy cop','heist','caper','noir','whodunit'),
 'action':('action','agenten','kampfsport','martial arts','girls with guns','motorrad','rennsport'),
 'adventure':('abenteuer','piraten','schatzsucher','bergfilm','katastroph','road movie'),
 'comedy':('komodie','sitcom','satire','parodie','klamauk','groteske','buddy film'),
 'romance':('liebes','romanze','erotik','sex film','sex serie','sexploitation'),
 'drama':('drama','melodram','coming of age','coming out','familiensaga','seifenoper','anwalt','gericht','sport','baseball','box film','musical','musikfilm','tanzfilm'),
}

def folded(value):
    return re.sub(r'\s+',' ',''.join(c for c in unicodedata.normalize('NFKD',str(value).casefold().replace('ß','ss')) if not unicodedata.combining(c)).replace('-',' ')).strip()

def genre_group(value):
    text=folded(value)
    for group in PRIORITY:
        if any(token in text for token in TOKENS[group]):return group
    return 'neutral'

def page_slice(rows,number,size):
    size=size if size in (6,12,18,24) else 12
    pages=max(1,(len(rows)+size-1)//size)
    number=max(1,min(number,pages))
    return rows[(number-1)*size:number*size],number,pages

def media_badge(media_type):
    return '▤ Serie' if media_type=='Serie' else '▶ Film'

class ArtCache:
    """At most 48 ready Tk photos; no scroll-time decoding or resizing."""
    def __init__(self,folder,user_store):
        self.folder=folder;self.user_store=user_store;self.photos=OrderedDict()

    def get(self,row,size):
        user=self.user_store.path_for(row['url'])
        filename=user or self.folder/(genre_group(row.get('genres',''))+'.jpg')
        if not filename.is_file():filename=self.folder/'neutral.jpg'
        key=(str(filename),tuple(size))
        if key in self.photos:self.photos.move_to_end(key);return self.photos[key]
        try:
            with Image.open(filename) as im:im=ImageOps.fit(im.convert('RGB'),size,Image.Resampling.LANCZOS)
        except (OSError,ValueError):
            with Image.open(self.folder/'neutral.jpg') as fallback:im=ImageOps.fit(fallback.convert('RGB'),size,Image.Resampling.LANCZOS)
        photo=ImageTk.PhotoImage(im)
        self.photos[key]=photo
        while len(self.photos)>48:self.photos.popitem(last=False)
        return photo

    def clear(self):self.photos.clear()
