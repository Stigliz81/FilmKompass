import unittest
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
import app_info
from moviepilot_manager import PUBLIC_PROFILE_HINT,PUBLIC_PROFILE_WARNING,FEEDBACK_MAILTO
from manager_core import APP_NAME

class AP11Tests(unittest.TestCase):
    def test_central_product_metadata_and_legacy_data_identity(self):
        self.assertEqual(app_info.PUBLIC_NAME,'FilmKompass')
        self.assertEqual(app_info.SHORT_NAME,'FilmKompass')
        self.assertEqual(app_info.BUILD_NUMBER,2)
        self.assertEqual(app_info.FILE_VERSION,'1.0.0.2')
        self.assertEqual(APP_NAME,'MoviepilotManager')
        self.assertIn("'FilmKompass.exe'",app_info.windows_version_info())
        self.assertEqual(app_info.PACKAGE_STEM,'FilmKompass-1.0')
    def test_profile_notice_and_feedback_have_no_data_attachment(self):
        self.assertIn('Meine Bewertungen öffentlich zeigen',PUBLIC_PROFILE_HINT)
        self.assertIn('wieder auf privat',PUBLIC_PROFILE_HINT)
        self.assertIn('auch andere',PUBLIC_PROFILE_WARNING)
        link=urlsplit(FEEDBACK_MAILTO)
        self.assertEqual(link.path,'stigliz1981@gmail.com')
        self.assertEqual(parse_qs(link.query),{'subject':['FilmKompass 1.0 – Feedback']})
