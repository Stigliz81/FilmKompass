import unittest,tempfile,os,json,sqlite3,zipfile
from pathlib import Path
from unittest.mock import patch
from contextlib import closing
from manager_core import Catalog
from app_data import backup_managed_data,register_data_directory,delete_managed_data,automatic_backup_directory
from moviepilot_lists import ListStore,download_list

class AP16071(unittest.TestCase):
 def test_backup_normalizes_database_path_alias(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as external:
   root=Path(td);(root/'alias').mkdir()
   with patch.dict(os.environ,MOVIEPILOT_MANAGER_DATA_DIR=td):
    c=Catalog(root/'alias'/'..'/'manager.sqlite')
    try:
     register_data_directory(root)
     c.con.execute('PRAGMA journal_mode=WAL')
     c.con.execute('CREATE TABLE path_probe(value)');c.con.execute('INSERT INTO path_probe VALUES (42)');c.con.commit()
     archive=backup_managed_data(c,Path(external))
     with zipfile.ZipFile(archive) as z:
      self.assertEqual(z.read('manager.sqlite'),archive.with_suffix('.sqlite').read_bytes())
     with closing(sqlite3.connect(archive.with_suffix('.sqlite'))) as saved:
      self.assertEqual(saved.execute('SELECT value FROM path_probe').fetchone()[0],42)
    finally:c.close()
 def test_automatic_path_is_windows_documents(self):
  if os.name!='nt':self.skipTest('Windows only')
  path=automatic_backup_directory()
  self.assertTrue(path.is_absolute());self.assertEqual(path.parts[-2:],('FilmKompass','Sicherungen'))
 def test_backup_lists_unique_and_survives_deletion(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as external:
   with patch.dict(os.environ,MOVIEPILOT_MANAGER_DATA_DIR=td):
    root=Path(td);c=Catalog(root/'manager.sqlite');register_data_directory(root);store=ListStore(c.con)
    fixture=json.loads((Path(__file__).parent/'fixtures/ap1602_public_pages.json').read_text(encoding='utf-8'))
    store.save(download_list('https://www.moviepilot.de/liste/demo',fetch=lambda _:fixture['small']))
    (root/'foreign.txt').write_text('keep');target=Path(external)/'Documents/FilmKompass/Sicherungen'
    a=backup_managed_data(c,target);b=backup_managed_data(c,target);self.assertNotEqual(a,b)
    with zipfile.ZipFile(a) as z:self.assertIsNone(z.testzip());self.assertIn('manager.sqlite',z.namelist())
    with closing(sqlite3.connect(a.with_suffix('.sqlite'))) as con:self.assertEqual(con.execute('SELECT COUNT(*) FROM movie_lists').fetchone()[0],1)
    c.close();delete_managed_data(root);self.assertTrue(a.exists());self.assertTrue(b.exists());self.assertEqual((root/'foreign.txt').read_text(),'keep')
 def test_unwritable_target_no_deletion(self):
  with tempfile.TemporaryDirectory() as td,tempfile.TemporaryDirectory() as external:
   with patch.dict(os.environ,MOVIEPILOT_MANAGER_DATA_DIR=td):
    root=Path(td);c=Catalog(root/'manager.sqlite');register_data_directory(root)
    with patch('tempfile.TemporaryFile',side_effect=PermissionError('read-only')):
     with self.assertRaises(PermissionError):backup_managed_data(c,Path(external))
    self.assertTrue(c.db_path.exists());c.close()
