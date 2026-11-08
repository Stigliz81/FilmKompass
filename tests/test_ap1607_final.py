import unittest,tempfile,os,sqlite3,json
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from manager_core import Catalog
from moviepilot_lists import ListStore,download_list
from app_data import register_data_directory,verified_backup,backup_managed_data,delete_managed_data

class FinalTests(unittest.TestCase):
 def test_reset_lists_and_verified_snapshot(self):
  with tempfile.TemporaryDirectory() as td:
   c=Catalog(Path(td)/'manager.sqlite');s=ListStore(c.con)
   fixture=json.loads((Path(__file__).parent/'fixtures/ap1602_public_pages.json').read_text(encoding='utf-8'))
   s.save(download_list('https://www.moviepilot.de/liste/demo',fetch=lambda _:fixture['small']))
   p=verified_backup(c);c.reset_library();self.assertEqual(s.lists(),[])
   with closing(sqlite3.connect(p)) as b:self.assertEqual(b.execute('SELECT COUNT(*) FROM movie_lists').fetchone()[0],1)
   c.close()
 def test_all_data_external_backup_foreign_preserved(self):
  with tempfile.TemporaryDirectory() as td, tempfile.TemporaryDirectory() as external:
   with patch.dict(os.environ,MOVIEPILOT_MANAGER_DATA_DIR=td):
    root=Path(td);c=Catalog(root/'manager.sqlite');ListStore(c.con);register_data_directory(root)
    (root/'settings.json').write_text('{"fanart":{"enabled":true}}');(root/'foreign.txt').write_text('untouched')
    (root/'fanart-cache').mkdir();(root/'fanart-cache/x.jpg').write_bytes(b'cache')
    with self.assertRaises(ValueError):backup_managed_data(c,root/'inside')
    archive=backup_managed_data(c,Path(external));c.close();delete_managed_data(root)
    self.assertTrue(archive.is_file());self.assertEqual((root/'foreign.txt').read_text(),'untouched')
    self.assertFalse((root/'manager.sqlite').exists());self.assertFalse((root/'fanart-cache').exists())
 def test_backup_failure_blocks_reset(self):
  with tempfile.TemporaryDirectory() as td:
   c=Catalog(Path(td)/'manager.sqlite')
   with patch.object(c,'backup',side_effect=OSError('full disk')):
    with self.assertRaises(OSError):verified_backup(c)
   self.assertTrue(c.db_path.exists());c.close()
