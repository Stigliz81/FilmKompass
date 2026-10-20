"""Explicit per-title user images, private storage, bounded HTTPS download."""
from __future__ import annotations
from pathlib import Path
import hashlib,io,ipaddress,socket,ssl,http.client,time,warnings,re
from urllib.parse import urlsplit,urljoin
from PIL import Image,ImageOps

MAX_BYTES=10*1024*1024
MAX_PIXELS=20_000_000

def validate_image(data):
    if len(data)>MAX_BYTES:raise ValueError('Bild ist größer als 10 MiB.')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error',Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                if probe.format not in ('JPEG','PNG','WEBP'):raise ValueError('Nur JPEG, PNG und WebP werden unterstützt.')
                if probe.width*probe.height>MAX_PIXELS:raise ValueError('Bild hat mehr als 20 Millionen Pixel.')
                probe.verify()
            with Image.open(io.BytesIO(data)) as original:
                im=ImageOps.exif_transpose(original).convert('RGB')
                im.thumbnail((900,1350),Image.Resampling.LANCZOS)
                out=io.BytesIO();im.save(out,'JPEG',quality=90,optimize=True)
                return out.getvalue()
    except (OSError,SyntaxError,Image.DecompressionBombError,Image.DecompressionBombWarning) as exc:
        raise ValueError('Die Datei ist kein gültiges unterstütztes Bild.') from exc

def public_target(url,resolver=None):
    parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.port not in (None,443):
        raise ValueError('Nur direkte HTTPS-Bildadressen ohne Anmeldung und ohne Sonderport sind erlaubt.')
    hostname=parts.hostname.encode('idna').decode('ascii')
    if '%' in hostname:raise ValueError('Lokale Adressen sind nicht erlaubt.')
    answers=(resolver or socket.getaddrinfo)(hostname,443,type=socket.SOCK_STREAM)
    addresses=list(dict.fromkeys(entry[4][0] for entry in answers))
    if not addresses:raise ValueError('Bildserver konnte nicht aufgelöst werden.')
    for address in addresses:
        ip=ipaddress.ip_address(address)
        if not ip.is_global or (ip.version==6 and ip.ipv4_mapped and not ip.ipv4_mapped.is_global):
            raise ValueError('Lokale, private und reservierte Netzwerkziele sind gesperrt.')
    return parts,hostname,addresses

class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self,hostname,address):
        super().__init__(hostname,443,timeout=8,context=ssl.create_default_context())
        self.address=address
    def connect(self):
        # Pin the already checked DNS result; TLS still verifies the original hostname.
        sock=socket.create_connection((self.address,443),timeout=self.timeout)
        try:self.sock=self._context.wrap_socket(sock,server_hostname=self.host)
        except Exception:sock.close();raise

def download_image(url):
    deadline=time.monotonic()+25
    for _ in range(4):
        parts,host,addresses=public_target(url)
        conn=PinnedHTTPS(host,addresses[0])
        try:
            conn.request('GET',(parts.path or '/')+('?' + parts.query if parts.query else ''),headers={'Accept':'image/jpeg,image/png,image/webp','User-Agent':'MoviepilotManager/1.0'})
            response=conn.getresponse()
            if response.status in (301,302,303,307,308):
                location=response.getheader('Location')
                if not location:raise ValueError('Bildweiterleitung ohne Ziel.')
                url=urljoin(url,location)
                if time.monotonic()>deadline:raise ValueError('Zeitlimit beim Bilddownload erreicht.')
                continue
            if response.status!=200:raise ValueError(f'Bildserver meldet HTTP {response.status}.')
            length=response.getheader('Content-Length')
            if length and int(length)>MAX_BYTES:raise ValueError('Bild ist größer als 10 MiB.')
            chunks=[];count=0
            while True:
                if time.monotonic()>deadline:raise ValueError('Zeitlimit beim Bilddownload erreicht.')
                chunk=response.read(min(65536,MAX_BYTES+1-count))
                if not chunk:break
                chunks.append(chunk);count+=len(chunk)
                if count>MAX_BYTES:raise ValueError('Bild ist größer als 10 MiB.')
            return validate_image(b''.join(chunks))
        finally:conn.close()
    raise ValueError('Zu viele Bildweiterleitungen.')

class UserImages:
    def __init__(self,catalog):
        self.db=catalog;self.folder=catalog.db_path.parent/'user-images'

    def _path(self,filename):
        if not re.fullmatch(r'[0-9a-f]{64}\.jpg',filename):raise ValueError('Ungültiger lokaler Bildname.')
        # Reuse reset path protection: never traverse junctions or links.
        from app_data import _not_link
        path=self.folder/filename
        for ancestor in (path,self.folder,*self.folder.parents):_not_link(ancestor)
        return path

    def path_for(self,url):
        row=self.db.con.execute('SELECT filename FROM user_images WHERE url=?',(url,)).fetchone()
        if not row:return None
        try:
            p=self._path(row[0]);return p if p.is_file() else None
        except (ValueError,OSError):return None

    def save(self,url,data,validated=False):
        if not self.db.get_row(url):raise ValueError('Titel ist nicht mehr vorhanden.')
        content=data if validated else validate_image(data)
        name=hashlib.sha256(content).hexdigest()+'.jpg'
        path=self._path(name);self.folder.mkdir(exist_ok=True)
        if not path.exists():
            with path.open('xb') as f:f.write(content)
        with self.db.con:self.db.con.execute('INSERT INTO user_images(url,filename) VALUES(?,?) ON CONFLICT(url) DO UPDATE SET filename=excluded.filename',(url,name))
        return path

    def choose_file(self,url,filename):
        path=Path(filename)
        if path.stat().st_size>MAX_BYTES:raise ValueError('Bild ist größer als 10 MiB.')
        return self.save(url,path.read_bytes())

    def remove(self,url):
        # Keep managed image bytes for existing SQLite backups; remove only the assignment.
        with self.db.con:self.db.con.execute('DELETE FROM user_images WHERE url=?',(url,))
