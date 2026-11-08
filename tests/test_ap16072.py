import unittest
from fanart_covers import Credentials,CoverError,FanartClient,external_id

class Keys(unittest.TestCase):
 def test_personal_only_headers(self):
  self.assertEqual(Credentials('', 'synthetic_personal_123').headers(),{'client-key':'synthetic_personal_123'})
 def test_legacy_both_and_missing(self):
  self.assertEqual(Credentials('synthetic_project_123').headers(),{'api-key':'synthetic_project_123'})
  self.assertEqual(len(Credentials('synthetic_project_123','synthetic_personal_123').headers()),2)
  with self.assertRaises(CoverError):Credentials('').headers()
  with self.assertRaises(CoverError):Credentials('','bad\nheader').headers()
 def test_personal_request_and_no_key_disclosure(self):
  seen=[]
  def request(url,headers):seen.append((url,headers));return {'name':'QA','movieposter':[]}
  c=Credentials('','synthetic_personal_123');FanartClient(c,request).posters(external_id('imdb','tt0137523','Film'))
  self.assertNotIn('synthetic_personal_123',seen[0][0]);self.assertNotIn('synthetic_personal_123',repr(c))
  self.assertEqual(seen[0][1],{'client-key':'synthetic_personal_123'})
