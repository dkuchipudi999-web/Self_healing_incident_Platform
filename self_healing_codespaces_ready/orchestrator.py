#!/usr/bin/env python3
"""Demo orchestrator. Run on host, requires Docker CLI and compose plugin."""
import json, os, subprocess, threading, time, urllib.request, urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
ROOT=Path(__file__).resolve().parent
INCIDENTS={}
LOCK=threading.Lock()
ALLOWED={'orders','inventory','payments'}
SERVICENOW_URL=os.getenv('SERVICENOW_URL','').rstrip('/')
SERVICENOW_USER=os.getenv('SERVICENOW_USER','')
SERVICENOW_PASSWORD=os.getenv('SERVICENOW_PASSWORD','')
def now():return datetime.now(timezone.utc).isoformat()
def classify(service,summary):
 text=(service+' '+summary).lower()
 try:
  from sklearn.feature_extraction.text import TfidfVectorizer
  from sklearn.naive_bayes import MultinomialNB
  examples=['payment transaction timeout','inventory service unavailable','orders api error','payment declined timeout','inventory connection refused','order service crashed','payment service healthy','inventory running normally']
  labels=['PAYMENT','INFRASTRUCTURE','APPLICATION','PAYMENT','INFRASTRUCTURE','APPLICATION','NORMAL','NORMAL']
  v=TfidfVectorizer();x=v.fit_transform(examples);model=MultinomialNB().fit(x,labels)
  category=model.predict(v.transform([text]))[0]
 except ImportError:
  category='PAYMENT' if 'payment' in text else 'INFRASTRUCTURE' if 'inventory' in text else 'APPLICATION'
 return {'category':category,'priority':'P1' if 'unavailable' in text or 'critical' in text or 'down' in text else 'P2','anomaly':True}
def sn_create(rec):
 if not SERVICENOW_URL:return 'SIM-'+rec['id']
 import base64
 data=json.dumps({'short_description':rec['summary'],'description':json.dumps(rec['classification']),'impact':'1','urgency':'1','category':'software'}).encode()
 req=urllib.request.Request(SERVICENOW_URL+'/api/now/table/incident',data=data,headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((SERVICENOW_USER+':'+SERVICENOW_PASSWORD).encode()).decode()},method='POST')
 with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)['result']['sys_id']
def sn_resolve(rec):
 if not SERVICENOW_URL:return
 import base64
 data=json.dumps({'state':'6','close_code':'Solved (Permanently)','close_notes':'Automatically recovered and verified'}).encode()
 req=urllib.request.Request(SERVICENOW_URL+'/api/now/table/incident/'+rec['ticket'],data=data,headers={'Content-Type':'application/json','Authorization':'Basic '+base64.b64encode((SERVICENOW_USER+':'+SERVICENOW_PASSWORD).encode()).decode()},method='PATCH')
 with urllib.request.urlopen(req,timeout=10):pass
def healthy(service):
 try:
  with urllib.request.urlopen('http://'+service+':8080/actuator/health',timeout=3) as r:
   return json.load(r).get('status')=='UP'
 except Exception:return False
def recover(service,incident_id):
 with LOCK:rec=INCIDENTS[incident_id];rec['status']='REMEDIATING'
 try:
  # Restart a known, allowlisted Compose service only. Never execute alert-supplied shell.
  subprocess.run(['docker','restart','selfheal-'+service],check=True,timeout=90,capture_output=True,text=True)
  for _ in range(25):
   if healthy(service):
    with LOCK:rec['status']='RESOLVED';rec['resolved_at']=now()
    try:sn_resolve(rec)
    except Exception as ex:rec['servicenow_error']=str(ex)
    print('RESOLVED',incident_id,service,flush=True);return
   time.sleep(2)
  raise RuntimeError('health verification timed out')
 except Exception as ex:
  with LOCK:rec['status']='NEEDS_HUMAN';rec['error']=str(ex)
  print('ESCALATION',incident_id,str(ex),flush=True)
class Handler(BaseHTTPRequestHandler):
 def respond(self,obj,status=200):
  raw=json.dumps(obj,indent=2).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
 def do_GET(self):
  if self.path=='/incidents':
   with LOCK:self.respond(list(INCIDENTS.values()))
  elif self.path=='/health':self.respond({'status':'UP'})
  else:self.respond({'error':'not found'},404)
 def do_POST(self):
  if self.path!='/alert':return self.respond({'error':'not found'},404)
  try:
   body=json.loads(self.rfile.read(min(int(self.headers.get('Content-Length','0')),100000)))
   results=[]
   for alert in body.get('alerts',[]):
    if alert.get('status')!='firing':continue
    instance=alert.get('labels',{}).get('instance','')
    service=instance.split(':')[0]
    if service not in ALLOWED:continue
    with LOCK:
     existing=next((r for r in INCIDENTS.values() if r['service']==service and r['status'] in ('OPEN','REMEDIATING')),None)
     if existing:results.append(existing['id']);continue
     iid=str(len(INCIDENTS)+1).zfill(4)
     summary='critical '+service+' service unavailable'
     rec={'id':iid,'service':service,'summary':summary,'classification':classify(service,summary),'status':'OPEN','created_at':now()}
     INCIDENTS[iid]=rec
    try:rec['ticket']=sn_create(rec)
    except Exception as ex:rec['ticket']='SNOW_ERROR';rec['servicenow_error']=str(ex)
    print('INCIDENT',iid,service,rec['classification'],flush=True)
    threading.Thread(target=recover,args=(service,iid),daemon=True).start();results.append(iid)
   self.respond({'accepted':results})
  except Exception as ex:self.respond({'error':str(ex)},400)
if __name__=='__main__':
 print('Orchestrator listening on http://localhost:8090',flush=True)
 ThreadingHTTPServer(('0.0.0.0',8090),Handler).serve_forever()
