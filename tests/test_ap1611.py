import unittest,tempfile,json,time,sys
from pathlib import Path
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from virustotal_check import verdict,inspect,ScanError,privacy_gate,digest,Client
from urllib.error import HTTPError

def report(sha,**values):
 stats=dict(malicious=0,suspicious=0,harmless=0,undetected=2,timeout=0,**{'confirmed-timeout':0,'failure':0,'type-unsupported':0});stats.update(values)
 results={};i=0
 for key,count in stats.items():
  for _ in range(count):results[str(i)]={'category':key};i+=1
 return {'data':{'id':sha,'attributes':{'last_analysis_date':int(time.time()),'last_analysis_stats':stats,'last_analysis_results':results}}}
class SecurityTests(unittest.TestCase):
 def test_exact_hash_and_complete_engine_counts(self):
  data=report('a',malicious=1,suspicious=1,timeout=2)
  v=verdict(data,'a');self.assertEqual((v['malicious'],v['suspicious'],v['evaluated_engines'],v['excluded_engines']),(1,1,4,2));self.assertIsNone(verdict(data,'b'))
 def test_partial_stale_and_empty_are_not_success(self):
  d=report('a');d['data']['attributes']['last_analysis_stats']['undetected']=3;self.assertIsNone(verdict(d,'a'))
  d=report('a');d['data']['attributes']['last_analysis_date']=1;self.assertIsNone(verdict(d,'a'));self.assertIsNone(verdict({},'a'))
 def test_no_key_performs_no_upload(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'demo.exe';p.write_bytes(b'synthetic');v=inspect(p,None,True);self.assertEqual(v['status'],'missing_api_key');self.assertNotIn('malicious',v)
 def test_lookup_first_and_no_upload_by_default(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'demo.exe';p.write_bytes(b'synthetic');c=Mock();c.call.return_value=report(digest(p));self.assertEqual(inspect(p,c)['status'],'completed');self.assertEqual(c.call.call_count,1)
   c.call.return_value=None;self.assertEqual(inspect(p,c)['status'],'pending')
 def test_upload_requires_gate_and_propagates_429(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'demo.exe';p.write_bytes(b'synthetic');c=Mock();c.call.return_value=None
   with self.assertRaises(ScanError):inspect(p,c,True)
   c.call.side_effect=ScanError('HTTP 429; Retry-After 60')
   with self.assertRaisesRegex(ScanError,'429'):inspect(p,c)
 def test_pending_analysis_is_not_success(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'demo.exe';p.write_bytes(b'synthetic');c=Mock();c.call.side_effect=[None,{'data':{'id':'analysis'}}];gate=Mock()
   v=inspect(p,c,True,gate,wait_seconds=0);self.assertEqual(v['status'],'pending');gate.assert_called_once()
 def test_completed_upload_is_bound_to_final_hash(self):
  with tempfile.TemporaryDirectory() as td:
   p=Path(td)/'demo.exe';p.write_bytes(b'synthetic');c=Mock();c.call.side_effect=[None,{'data':{'id':'analysis'}},{'data':{'attributes':{'status':'completed'}}},report(digest(p))]
   gate=Mock();v=inspect(p,c,True,gate);self.assertEqual(v['status'],'completed');self.assertEqual(v['sha256'],digest(p));gate.assert_called_once()
 def test_unauthorized_error_does_not_expose_key(self):
  c=Client('SYNTHETIC_PRIVATE_TOKEN');c.opener=Mock();c.opener.open.side_effect=HTTPError('https://www.virustotal.com/api/v3/files/test',401,'Unauthorized',{},None)
  with self.assertRaises(ScanError) as error:c.call('files/test')
  self.assertEqual(str(error.exception),'HTTP 401');self.assertNotIn(c.key,str(error.exception))
  request=c.opener.open.call_args.args[0];self.assertNotIn(c.key,request.full_url);self.assertEqual(request.get_header('X-apikey'),c.key)
