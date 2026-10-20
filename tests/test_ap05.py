"""AP05 filename collisions and exclusive CSV/XLSX writes, no user data."""
import tempfile,unittest
from datetime import datetime
from pathlib import Path
from catalog_view import suggest_export_path,export_public

class AP05Tests(unittest.TestCase):
 def test_scope_names_timestamp_and_repeated_collisions(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);now=datetime(2026,10,19,10,18)
   for extension in ('.csv','.xlsx'):
    for scope,label in [('all','Alle'),('filtered','Filter')]:
     path=suggest_export_path(root,scope,extension,now)
     self.assertEqual(path.name,f'FilmKompass_Filmdaten_{label}{extension}');path.touch()
     dated=suggest_export_path(root,scope,extension,now)
     self.assertEqual(dated.name,f'FilmKompass_Filmdaten_{label}_20261019_1018{extension}');dated.touch()
     dated2=suggest_export_path(root,scope,extension,now);self.assertTrue(dated2.name.endswith('_2'+extension));dated2.touch()
     self.assertTrue(suggest_export_path(root,scope,extension,now).name.endswith('_3'+extension))
 def test_both_formats_refuse_unconfirmed_overwrite(self):
  rows=[dict(media_type='Film',title='Erfunden',year='2000',rating=7.5,rated_at='2026-10-19',genres='Abenteuerfilm, Thriller')]
  with tempfile.TemporaryDirectory() as tmp:
   for extension in ('.csv','.xlsx'):
    target=Path(tmp)/('export'+extension);target.write_bytes(b'Keep original bytes')
    with self.assertRaises(FileExistsError):export_public(target,rows,overwrite=False)
    self.assertEqual(target.read_bytes(),b'Keep original bytes')
    export_public(target,rows,overwrite=True);self.assertNotEqual(target.read_bytes(),b'Keep original bytes')

if __name__=='__main__':unittest.main()
