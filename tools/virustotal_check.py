"""Explicit release-only VirusTotal v3 check. Never imported by the application."""
from pathlib import Path
import argparse,hashlib,json,os,time,uuid,zipfile,sys
from datetime import datetime,timezone
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError,URLError
from urllib.parse import urlsplit,quote

BASE='https://www.virustotal.com/api/v3/'
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
class ScanError(Exception):pass
class NoRedirect(HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ScanError('Unerwartete API-Weiterleitung')
class Client:
 def __init__(self,key):self.key=key;self.last=None;self.opener=build_opener(NoRedirect());self.calls=0
 def call(self,path,body=None,content_type=None):
  if self.calls>=30:raise ScanError('Lokales Anfragelimit erreicht; später erneut aufrufen')
  if self.last is not None:time.sleep(max(0,16-(time.monotonic()-self.last)))
  self.last=time.monotonic();self.calls+=1
  url=path if path.startswith('https://') else BASE+path
  if urlsplit(url).netloc!='www.virustotal.com' or urlsplit(url).scheme!='https':raise ScanError('Unzulässiger API-Host')
  headers={'x-apikey':self.key,'Accept':'application/json'}
  if content_type:headers['Content-Type']=content_type
  try:
   with self.opener.open(Request(url,data=body,headers=headers),timeout=40) as response:
    raw=response.read(8*1024*1024+1)
    if len(raw)>8*1024*1024:raise ScanError('API-Antwort zu groß')
    return json.loads(raw)
  except HTTPError as e:
   if e.code==404:return None
   retry=e.headers.get('Retry-After','')
   raise ScanError('HTTP '+str(e.code)+(f'; Retry-After {retry}' if retry.isdigit() else '')) from None
  except (URLError,OSError,ValueError):raise ScanError('API-/Verbindungsfehler; keine erfolgreiche Prüfung') from None

def verdict(data,sha,max_age_days=7,now=None):
 now=time.time() if now is None else now
 if not isinstance(data,dict) or data.get('data',{}).get('id')!=sha:return None
 a=data['data'].get('attributes',{});date=a.get('last_analysis_date');stats=a.get('last_analysis_stats',{});results=a.get('last_analysis_results',{})
 if type(date) is not int or date>now+300 or now-date>max_age_days*86400 or not results:return None
 keys=('malicious','suspicious','harmless','undetected','timeout','confirmed-timeout','failure','type-unsupported')
 if any(type(stats.get(k)) is not int or stats[k]<0 for k in keys):return None
 categories=[v.get('category') for v in results.values() if isinstance(v,dict)]
 if len(categories)!=len(results) or any(categories.count(k)!=stats[k] for k in keys) or sum(stats.values())!=len(results):return None
 total=sum(stats[k] for k in keys[:4])
 if not total:return None
 return dict(status='completed',malicious=stats['malicious'],suspicious=stats['suspicious'],evaluated_engines=total,excluded_engines=len(results)-total,analysis_utc=datetime.fromtimestamp(date,timezone.utc).isoformat(),sha256=sha,report_url='https://www.virustotal.com/gui/file/'+sha)

def privacy_gate(exe,archive,gate,secrets=()):
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
 from package_release import check_public_path
 expected=json.loads(Path(gate).read_text(encoding='utf-8'))
 if expected.get('privacy_reviewed') is not True or expected.get('files')!={p.name:digest(p) for p in (exe,archive)}:raise ScanError('Hashgebundene Paketfreigabe fehlt oder ist veraltet')
 with zipfile.ZipFile(archive) as z:
  if z.testzip():raise ScanError('ZIP beschädigt')
  names=z.namelist();manifests=[n for n in names if n.endswith('/MANIFEST.sha256.json')]
  if len(manifests)!=1 or len(names)!=len(set(names)):raise ScanError('Unklarer ZIP-Payload')
  prefix=manifests[0].removesuffix('MANIFEST.sha256.json');manifest=json.loads(z.read(manifests[0]))
  if set(names)!={prefix+n for n in manifest}|set(manifests):raise ScanError('Unbestätigte ZIP-Einträge')
  exe_matches=0
  for name,h in manifest.items():
   if name.startswith(('/', '\\')) or '..' in Path(name).parts:raise ScanError('Unsicherer Paketpfad')
   try:check_public_path(name)
   except ValueError:raise ScanError('Private Dateikategorie im Paket') from None
   data=z.read(prefix+name)
   if hashlib.sha256(data).hexdigest()!=h:raise ScanError('Payload-Hash falsch')
   for secret in secrets:
    if secret and any(secret.encode(enc) in data for enc in ('utf-8','utf-16-le')):raise ScanError('Privater Schlüssel im Payload')
   if Path(name).name==exe.name:
    if data!=exe.read_bytes():raise ScanError('EXE entspricht nicht dem ZIP')
    exe_matches+=1
  if exe_matches!=1:raise ScanError('Eindeutige Paket-EXE fehlt')

def inspect(path,client,upload=False,gate_check=None,max_age_days=7,wait_seconds=300):
 sha=digest(path);base=dict(file=path.name,bytes=path.stat().st_size,sha256=sha,report_url='https://www.virustotal.com/gui/file/'+sha)
 if client is None:return dict(base,status='missing_api_key',message='VIRUSTOTAL_API_KEY lokal setzen; keine Anfrage und kein Upload ausgeführt')
 value=verdict(client.call('files/'+sha),sha,max_age_days)
 if value:return dict(base,**value)
 if not upload:return dict(base,status='pending',message='Kein aktueller vollständiger Bericht; kein Upload freigegeben')
 if gate_check is None:raise ScanError('Privacyfreigabe erforderlich')
 gate_check() # Recheck all exact bytes immediately before every upload.
 data=path.read_bytes()
 if hashlib.sha256(data).hexdigest()!=sha:raise ScanError('Datei während der Prüfung verändert')
 boundary='FilmKompass'+uuid.uuid4().hex
 body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{quote(path.name)}"\r\nContent-Type: application/octet-stream\r\n\r\n'.encode()+data+f'\r\n--{boundary}--\r\n'.encode())
 target='files'
 if len(data)>32_000_000:
  if len(data)>650_000_000:raise ScanError('Datei überschreitet Uploadlimit')
  result=client.call('files/upload_url');target=result.get('data','') if result else ''
  if not isinstance(target,str) or not target.startswith('https://www.virustotal.com/'):raise ScanError('Ungültige Uploadadresse')
 response=client.call(target,body,'multipart/form-data; boundary='+boundary)
 try:analysis=response['data']['id']
 except (KeyError,TypeError):raise ScanError('Analyse-ID fehlt') from None
 deadline=time.monotonic()+wait_seconds
 while time.monotonic()<deadline:
  result=client.call('analyses/'+quote(analysis,safe=''))
  if result and result.get('data',{}).get('attributes',{}).get('status')=='completed':
   value=verdict(client.call('files/'+sha),sha,max_age_days)
   if value and digest(path)==sha:return dict(base,**value)
   return dict(base,status='incomplete',message='Abgeschlossene Analyse ohne eindeutig vollständigen Hashbericht')
 return dict(base,status='pending',message='Analyse noch nicht abgeschlossen; später erneut prüfen')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--exe',type=Path,required=True);p.add_argument('--zip',type=Path,required=True);p.add_argument('--report',type=Path,required=True);p.add_argument('--upload',action='store_true');p.add_argument('--gate',type=Path);p.add_argument('--max-age-days',type=int,default=7);a=p.parse_args()
 if a.max_age_days<1:p.error('--max-age-days muss mindestens 1 sein')
 key=os.environ.get('VIRUSTOTAL_API_KEY','').strip();client=Client(key) if key else None
 secrets=[key,os.environ.get('FANART_TV_PROJECT_KEY','')]
 config=Path(__file__).resolve().parents[1]/'fanart.local.json'
 if config.exists():secrets.append(json.loads(config.read_text()).get('project_key',''))
 paths=(a.exe,a.zip);identities=[]
 for path in paths:
  try:identities.append(dict(file=path.name,bytes=path.stat().st_size,sha256=digest(path)))
  except OSError:identities.append(dict(file=path.name,status='error',message='Datei nicht lesbar'))
 results=[]
 if any(v.get('status')=='error' for v in identities):
  results=[dict(v,status='error',message='Vorprüfung fehlgeschlagen; keine API-Anfrage') for v in identities]
 for index,path in enumerate(paths):
  if results and len(results)==len(paths):break
  try:
   if digest(path)!=identities[index]['sha256']:raise ScanError('Datei seit Hashberechnung verändert')
   gate=(lambda:privacy_gate(a.exe,a.zip,a.gate,secrets)) if a.gate else None
   results.append(inspect(path,client,a.upload,gate,a.max_age_days))
  except ScanError as error:
   results.append(dict(file=path.name,status='error',message=str(error)))
   break
  except (OSError,ValueError):
   # No response bodies, request headers, keys or full exception strings in reports.
   results.append(dict(file=path.name,status='error',message='Prüfung fehlgeschlagen; API-Limit, Verbindung oder Paketfreigabe prüfen'))
   break # Stop on API/privacy errors rather than consuming more quota.
 while len(results)<len(paths):
  results.append(dict(identities[len(results)],status='not_checked',message='Wegen vorherigem Fehler nicht angefragt'))
 for index,result in enumerate(results):
  for field,value in identities[index].items():
   if field not in ('status','message'):result.setdefault(field,value)
 a.report.parent.mkdir(parents=True,exist_ok=True)
 a.report.write_text(json.dumps(dict(created_utc=datetime.now(timezone.utc).isoformat(),results=results),indent=2),encoding='utf-8')
 print('VirusTotal-Bericht gespeichert; Status: '+', '.join(r['status'] for r in results))
 return 0 if len(results)==2 and all(r['status']=='completed' and not r['malicious'] and not r['suspicious'] for r in results) else 2
if __name__=='__main__':raise SystemExit(main())
