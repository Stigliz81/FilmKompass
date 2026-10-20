"""Focused AP03 data/image boundaries; no productive data or network requests."""
import io,socket,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from genre_art import genre_group,page_slice,media_badge,GROUPS
from user_images import UserImages,validate_image,public_target,download_image,MAX_BYTES
from manager_core import Catalog
from catalog_view import export_public

def png():
    out=io.BytesIO();Image.new('RGB',(80,120),'teal').save(out,'PNG');return out.getvalue()
def answer(address):return [(socket.AF_INET,socket.SOCK_STREAM,6,'',(address,443))]

class AP03Tests(unittest.TestCase):
    def test_genre_variants_and_priority(self):
        for a,b in [('Science Fiction-Film','Science Fiction-Serie'),('Zombiefilm','Zombieserie'),('Coming of Age-Film','Coming of Age-Serie')]:self.assertEqual(genre_group(a),genre_group(b))
        for value,expected in [('Drama, Thriller','thriller'),('Drama, Science Fiction Film','scifi'),('Anime, Fantasy','animation'),('Detektivfilm','crime'),('Horrorkomödie','horror'),('Melodram','drama'),('??','neutral')]:self.assertEqual(genre_group(value),expected)
        self.assertEqual(len(GROUPS),14);self.assertIn('Serie',media_badge('Serie'));self.assertIn('Film',media_badge('Film'))

    def test_paging_sizes_and_clamping(self):
        rows=list(range(120))
        for size,pages in [(6,20),(12,10),(18,7),(24,5)]:
            page,number,total=page_slice(rows,999,size)
            self.assertEqual(total,pages);self.assertEqual(number,pages);self.assertLessEqual(len(page),size)
            self.assertEqual(page_slice(rows,1,size)[0],rows[:size])
        self.assertEqual(page_slice([],9,24),([],1,1))
        self.assertEqual(page_slice(rows[:2],10,12),([0,1],1,1))

    def test_local_images_identity_promotion_and_reset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=Catalog(root/'manager.sqlite');images=UserImages(db)
            rows=[dict(media_type='Film',title='Gleicher Titel',year='2005',rating=8,rated_at='2026-10-18',genres='Drama'),dict(media_type='Film',title='Gleicher Titel',year='2006',rating=7,rated_at='',genres='Horror')]
            plain=root/'plain.csv';export_public(plain,rows);db.import_files([plain])
            before=db.get_rows();url=before[0]['url'];original=root/'my.png';original.write_bytes(png())
            stored=images.choose_file(url,original);self.assertEqual(original.read_bytes(),png())
            self.assertEqual(images.path_for(url),stored);self.assertIsNone(images.path_for(before[1]['url']))
            # Legacy URL promotion preserves the exact per-title image association.
            from test_ap02 import source,record
            old=root/'old.csv';source(old,[record('same-2005','Gleicher Titel','2005',8),record('same-2006','Gleicher Titel','2006',7)])
            db.import_files([old]);new='https://www.moviepilot.de/movies/same-2005'
            self.assertEqual(images.path_for(new),stored)
            images.remove(new);self.assertIsNone(images.path_for(new));self.assertTrue(stored.exists())
            images.choose_file(new,original);db.reset_library()
            self.assertEqual(db.con.execute('SELECT COUNT(*) FROM user_images').fetchone()[0],0)
            db.close()

    def test_invalid_image_and_limits(self):
        self.assertTrue(validate_image(png()).startswith(b'\xff\xd8'))
        for data in [b'<svg/>',b'MZ'+b'fake',b'not an image',b'x'*(MAX_BYTES+1)]:
            with self.assertRaises(ValueError):validate_image(data)
        gif=io.BytesIO();Image.new('RGB',(10,10)).save(gif,'GIF')
        with self.assertRaises(ValueError):validate_image(gif.getvalue())

    def test_url_validation_and_mixed_dns(self):
        for url in ['http://example.com/a.png','https://user:pass@example.com/a.png','https://example.com:444/a.png']:
            with self.assertRaises(ValueError):public_target(url)
        for address in ['127.0.0.1','10.0.0.1','169.254.169.254','192.168.1.1','::1','fc00::1','::ffff:127.0.0.1']:
            with self.assertRaises(ValueError):public_target('https://image.invalid/a.png',lambda *a,**k:answer(address))
        with self.assertRaises(ValueError):public_target('https://image.invalid/a.png',lambda *a,**k:answer('8.8.8.8')+answer('127.0.0.1'))
        parts,host,addresses=public_target('https://image.invalid/a.png',lambda *a,**k:answer('8.8.8.8'))
        self.assertEqual(addresses,['8.8.8.8']);self.assertEqual(host,'image.invalid')

    def test_redirect_private_rejected_and_download_bytes_validated(self):
        class Response:
            status=302
            def getheader(self,key):return 'https://private.invalid/a.png' if key=='Location' else None
        class Conn:
            def __init__(self,*args):pass
            def request(self,*a,**k):pass
            def getresponse(self):return Response()
            def close(self):pass
        def resolve(host,*a,**k):return answer('127.0.0.1' if host=='private.invalid' else '8.8.8.8')
        with patch('user_images.socket.getaddrinfo',side_effect=resolve),patch('user_images.PinnedHTTPS',Conn):
            with self.assertRaisesRegex(ValueError,'gesperrt'):download_image('https://image.invalid/a.png')
        class ValidResponse:
            status=200
            def __init__(self):self.data=io.BytesIO(png())
            def getheader(self,key):return str(len(png())) if key=='Content-Length' else None
            def read(self,n):return self.data.read(n)
        with patch('user_images.socket.getaddrinfo',return_value=answer('8.8.8.8')),patch.object(Conn,'getresponse',lambda s:ValidResponse()),patch('user_images.PinnedHTTPS',Conn):
            self.assertTrue(download_image('https://image.invalid/a.png').startswith(b'\xff\xd8'))

    def test_user_image_storage_rejects_links(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Catalog(Path(tmp)/'manager.sqlite');store=UserImages(db)
            with patch('app_data._not_link',side_effect=ValueError('link')):
                with self.assertRaises(ValueError):store._path('a'*64+'.jpg')
            db.close()

    def test_full_reset_includes_private_images_and_keeps_foreign_files(self):
        import os
        from app_data import register_data_directory,delete_managed_data
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'MOVIEPILOT_MANAGER_DATA_DIR':tmp}):
            root=Path(tmp);register_data_directory(root)
            (root/'user-images').mkdir();(root/'user-images'/('a'*64+'.jpg')).write_bytes(png())
            (root/'settings.json').write_text('{"view":"Miniaturansicht","page_size":24}',encoding='utf-8')
            foreign=root/'my-file.txt';foreign.write_text('untouched')
            result=delete_managed_data(root)
            self.assertFalse((root/'user-images').exists());self.assertFalse((root/'settings.json').exists())
            self.assertEqual(foreign.read_text(),'untouched');self.assertIn('my-file.txt',result['foreign'])

if __name__=='__main__':unittest.main()
