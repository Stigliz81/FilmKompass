import json
import unittest
from unittest.mock import patch, MagicMock
from urllib.error import HTTPError, URLError
import program_updates as u
from table_links import moviepilot_link


class AP1607Tests(unittest.TestCase):
    def test_moviepilot_https_only(self):
        for value in (None, '', 'http://moviepilot.de/movies/test', 'https://moviepilot.de.evil/movies/a',
                      'https://user@moviepilot.de/movies/a', 'https://moviepilot.de:443/movies/a',
                      'https://moviepilot.de/liste/a', 'https://moviepilot.de/movies/',
                      'https://moviepilot.de/movies/..', 'https://moviepilot.de/movies/a/b',
                      'https://moviepilot.de/movies/a\nb', 'https://moviepilot.de/movies/%2fadmin'):
            self.assertIsNone(moviepilot_link(value), value)
        self.assertEqual(moviepilot_link('https://moviepilot.de/movies/easy-rider?x=1'),
                         'https://www.moviepilot.de/movies/easy-rider')
        self.assertEqual(moviepilot_link('https://www.moviepilot.de/serie/dark'),
                         'https://www.moviepilot.de/serie/dark')

    def test_numeric_product_versions(self):
        self.assertGreater(u.version_number('1.10'), u.version_number('1.9.9'))
        self.assertEqual(u.version_number('1.1'), u.version_number('1.1.0.0'))
        for value in ('1', None, 'v1.1', '1.1-rc2', '1.1.0.0.2', '1.-1', '1.2\n'):
            with self.assertRaises(ValueError): u.version_number(value)
        for public, state in [('1.0', 'ahead'), ('1.1.0', 'current'), ('1.2', 'newer')]:
            result = u.check_version('1.1', fetch=lambda: dict(version=public, download_url=u.WEBSITE))
            self.assertEqual(result['state'], state)
        self.assertNotIn('aktuell', u.check_version(fetch=lambda: dict(version='1.0', download_url=u.WEBSITE))['message'])

    def test_official_download_allowlist(self):
        for value in (u.WEBSITE, 'https://github.com/Stigliz81/FilmKompass/releases',
                      'https://github.com/Stigliz81/FilmKompass/releases/tag/v1.0.0',
                      'https://github.com/Stigliz81/FilmKompass/releases/download/v1.0.0/FilmKompass-1.0-Windows-portabel.zip'):
            self.assertEqual(u.official_download(value), value)
        for value in ('http://stigliz81.github.io/FilmKompass/', u.WEBSITE+'evil',
                      'https://github.com/other/FilmKompass/releases',
                      'https://github.com@evil.com/Stigliz81/FilmKompass/releases',
                      'https://github.com/Stigliz81/FilmKompass/releases/../issues',
                      'https://github.com/Stigliz81/FilmKompass/releases?redirect=evil',
                      'https://github.com:443/Stigliz81/FilmKompass/releases'):
            with self.assertRaises(ValueError): u.official_download(value)

    def test_offline_missing_malformed_never_current(self):
        for error in (URLError('offline'), HTTPError(u.VERSION_URL, 404, 'missing', {}, None),
                      TimeoutError(), ValueError('malformed')):
            def fail(): raise error
            result = u.check_version(fetch=fail)
            self.assertEqual(result['state'], 'unavailable')
            self.assertEqual(result['message'], u.UNAVAILABLE)
        for data in ([], {}, dict(version='1.2', download_url='https://evil.com/')):
            self.assertEqual(u.check_version(fetch=lambda: data)['state'], 'unavailable')

    def test_bounded_https_no_redirect(self):
        response = MagicMock()
        response.__enter__.return_value = response
        response.status = 200
        response.geturl.return_value = u.VERSION_URL
        response.read.return_value = json.dumps(dict(version='1.0', download_url=u.WEBSITE)).encode()
        opener = MagicMock(); opener.open.return_value = response
        with patch.object(u, 'build_opener', return_value=opener):
            self.assertEqual(u.fetch_version()['version'], '1.0')
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 5)
        self.assertEqual(opener.open.call_args.args[0].full_url, u.VERSION_URL)
        response.read.assert_called_with(u.LIMIT+1)
        response.read.return_value = b'x'*(u.LIMIT+1)
        with patch.object(u, 'build_opener', return_value=opener), self.assertRaises(ValueError):
            u.fetch_version()
        with self.assertRaises(ValueError):
            u.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.com')

    def test_automatic_daily_and_default_off(self):
        self.assertFalse(u.automatic_due({}, 100000))
        self.assertTrue(u.automatic_due(dict(automatic=True), 100000))
        settings = dict(automatic=True, last_attempt=100000)
        self.assertFalse(u.automatic_due(settings, 100000+u.DAY-1))
        self.assertTrue(u.automatic_due(settings, 100000+u.DAY))
        self.assertFalse(u.automatic_due(settings, 99999))


if __name__ == '__main__': unittest.main()
