"""Test the REAL isolated CAF/Radius HTTP pair with synthetic customer data only.
Creates a synthetic CAF/new connection; never targets production or prints credentials.
"""
import argparse
import base64,http.cookiejar,json,re,sqlite3,time,urllib.request,urllib.error,uuid
from pathlib import Path
root=Path(__file__).resolve().parent.parent/'.tools'/'integration-demo'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--caf-demo-dir',type=Path,required=True)
parser.add_argument('--existing-customer-id',default=None)
args=parser.parse_args()
caf=args.caf_demo_dir.resolve()
private=json.loads((caf/'runtime.json').read_text(encoding='utf-8-sig'))
state=json.loads((caf/'state.json').read_text(encoding='utf-8-sig'))
assert state['cafUrl']=='http://127.0.0.1:18110'
assert state['radiusUrl']=='http://127.0.0.1:18120'
assert state['companyId']=='netloom-demo-company'
base=state['cafUrl']
def session(email):
 c=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
 code,_=api(c,'/api/auth/login','POST',{'email':email,'password':private['adminPassword']})
 assert code==200,'Synthetic demo login failed'
 return c
def api(client,path,method='GET',body=None,bearer=None,multipart=False):
 headers={}
 if bearer:headers['Authorization']='Bearer '+bearer
 if body is not None and not multipart:
  body=json.dumps(body).encode();headers['Content-Type']='application/json'
 elif multipart:
  body,boundary=body;headers['Content-Type']='multipart/form-data; boundary='+boundary
 req=urllib.request.Request(base+path,data=body,method=method,headers=headers)
 try:r=client.open(req,timeout=45)
 except urllib.error.HTTPError as e:r=e
 raw=r.read()
 try:data=json.loads(raw)
 except Exception:data={}
 return r.status,data
def expect(client,path,method='GET',body=None,status=200,**kwargs):
 code,data=api(client,path,method,body,**kwargs)
 if code!=status:raise RuntimeError('Unexpected status '+str(code)+' at '+path)
 return data
def multipart(payload):
 boundary='NetloomDemo'+uuid.uuid4().hex
 parts=[]
 def part(headers,value):
  parts.append(('--'+boundary+'\r\n'+headers+'\r\n\r\n').encode()+value+b'\r\n')
 part('Content-Disposition: form-data; name="data"',json.dumps(payload).encode())
 image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a1S8AAAAASUVORK5CYII=')
 for kind in ['PASSPORT_PHOTO','ID_PROOF','ADDRESS_PROOF']:
  part('Content-Disposition: form-data; name="files"; filename="'+kind+'.png"\r\nContent-Type: image/png',image)
  part('Content-Disposition: form-data; name="docType"',kind.encode())
 return b''.join(parts)+('--'+boundary+'--\r\n').encode(),boundary
def radius_rows(customer):
 assert re.fullmatch(r'[1-9][0-9]{9}',customer)
 db=sqlite3.connect('file:'+(root/'radius-demo.sqlite3').as_posix()+'?mode=ro',uri=True)
 try:return db.execute('SELECT r.service_request_id,s.username,s.status,s.password_hash,s.expires_at FROM core_cafservicerequest r LEFT JOIN core_subscriber s ON s.id=r.subscriber_id WHERE r.customer_id=? AND r.credential_accepted=1',(customer,)).fetchall()
 finally:db.close()
baseline=radius_rows(args.existing_customer_id) if args.existing_customer_id else []
print('Starting real local CAF-to-Radius HTTP journey with synthetic data only.',flush=True)
staff=session('demo-counter@caf.example.test');reviewer=session('demo-company@caf.example.test')
plans=expect(staff,'/api/radius-demo/plans?franchiseId='+state['franchiseId'])['items']
assert len(plans)==2
print('PASS real CAF proxy fetched real Radius plans.',flush=True)
username='joint.demo.'+uuid.uuid4().hex[:10]
payload={'franchiseId':state['franchiseId'],'customerName':'JOINT DEMO - synthetic test only','mobile':'9876543210',
 'addressLine1':'12 Synthetic Demo Street','city':'Delhi','state':'Delhi','pincode':'110001',
 'billingAddressLine1':'12 Synthetic Demo Street','billingCity':'Delhi','billingState':'Delhi','billingPincode':'110001',
 'idProofType':'PAN','idNumber':'AAAAA0000A','connectionType':'NEW','customerType':'RESIDENTIAL','declarationAccepted':True}
draft=expect(staff,'/api/caf-drafts','POST',{'payload':{**payload,'declarationAccepted':False}},status=201)['draft']
reservation=expect(staff,'/api/radius-demo/intents','POST',{'draftId':draft['id'],'draftVersion':draft['version'],
 'planId':plans[0]['plan_id'],'planVersion':plans[0]['version'],'username':username,
 **({'existingCustomerId':args.existing_customer_id} if args.existing_customer_id else {})})
customer=reservation['intent']['customerId'];assert len(radius_rows(customer))==len(baseline)
if args.existing_customer_id:assert customer==args.existing_customer_id
draft=reservation['draft']
created=expect(staff,'/api/applications','POST',multipart({**payload,'draftId':draft['id'],'draftVersion':draft['version'],
 'radiusDemoIntentId':reservation['intent']['id']}),status=201,multipart=True)['application']
assert created['customerId']==customer and created['broadbandUsername']==username
assert len(radius_rows(customer))==len(baseline)
print('PASS real CAF draft/reservation/submission; no new Radius subscriber before approval.',flush=True)
code,_=api(staff,'/api/applications/'+created['id']+'/status','PATCH',{'action':'APPROVE'})
assert code==403,'Franchise submitter must not self-approve'
expect(reviewer,'/api/applications/'+created['id']+'/status','PATCH',{'action':'APPROVE'})
status=None
for _ in range(30):
 status=expect(staff,'/api/radius-demo/status?applicationId='+created['id'])
 if status.get('state')=='STAGED':break
 time.sleep(2)
assert status and status['state']=='STAGED','Worker did not reach STAGED'
assert status['credentialAccepted'] is True and status['networkActive'] is False
rows=radius_rows(customer);assert len(rows)==len(baseline)+1
selected=[r for r in rows if r[1]==username];assert len(selected)==1 and selected[0][2]=='suspended'
hash_before=selected[0][3];expiry_before=selected[0][4]
assert hash_before.startswith('pbkdf2_sha256$')
print('PASS approved CAF automatically provisioned exactly one suspended Radius account with same 10-digit customer ID.',flush=True)
# A repeated worker scan may not reset accepted credentials or duplicate a service.
expect(urllib.request.build_opener(),'/api/internal/radius-demo/run','POST',bearer=private['workerToken'])
time.sleep(2)
rows=radius_rows(customer);selected=[r for r in rows if r[1]==username]
assert len(rows)==len(baseline)+1 and len(selected)==1 and selected[0][3]==hash_before and selected[0][4]==expiry_before
read=expect(urllib.request.build_opener(),'/api/integrations/radius/v1/customers/'+customer,bearer=private['readToken'])
assert read['customer_id']==customer
result={'result':'PASS','caf_url':base,'radius_url':state['radiusUrl'],'customer_id':customer,'application_id':created['id'],
 'username':username,'plan_id':plans[0]['plan_id'],'service_id':status['serviceId'],'delivery_id':status['deliveryId'],
 'state':'STAGED','credential_accepted':True,'network_active':False,'duplicate_count':len(selected),'customer_connection_count':len(rows),'additional_connection':bool(args.existing_customer_id),'expiry_unchanged':True,
 'checks':['real plan proxy','real draft and reservation','no provision before approval','franchise approval denied',
 'company approval accepted','automatic worker delivery','same permanent ID','durable hash acceptance','retry no duplicate/reset','scoped CAF customer read']}
(root/'joint-http-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('JOINT REAL HTTP MODEL PASS. Safe outcome recorded in joint-http-result.json; no credentials printed.',flush=True)
