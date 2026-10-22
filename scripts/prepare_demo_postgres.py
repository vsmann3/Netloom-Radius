"""Prepare portable PostgreSQL16 for the synthetic laptop demo. Windows only.
Official upstream archive stays under ignored .tools; no Windows service is installed.
"""
import hashlib
import urllib.request
import zipfile
import json,os,secrets,subprocess
from pathlib import Path
root=Path(__file__).resolve().parent.parent/'.tools'/'integration-demo'
root.mkdir(parents=True,exist_ok=True)
bins=root.parent/'postgresql-16.15'/'pgsql'/'bin'
if os.name != 'nt':
 raise SystemExit('This portable helper is Windows-only; use an isolated PostgreSQL16 database on other systems.')
archive=bins.parent.parent/'postgresql-16.15-5-windows-x64-binaries.zip'
if not (bins/'initdb.exe').exists():
 archive.parent.mkdir(parents=True,exist_ok=True)
 if not archive.exists():
  print('Downloading official EDB PostgreSQL16.15 portable archive (373MB).',flush=True)
  urllib.request.urlretrieve('https://get.enterprisedb.com/postgresql/postgresql-16.15-5-windows-x64-binaries.zip',archive)
 with archive.open('rb') as f: checksum=hashlib.file_digest(f,'sha256').hexdigest()
 if checksum!='43bb45f173a6f08cf1d29a97a6d8deb119e8e8093a24c00d2d1001a0ccaa8281':
  raise SystemExit('PostgreSQL archive digest mismatch; refusing extraction.')
 with zipfile.ZipFile(archive) as z:
  for item in z.infolist():
   if item.filename.startswith(('pgsql/bin/','pgsql/lib/','pgsql/share/')):
    dest=(archive.parent/item.filename).resolve()
    if archive.parent.resolve() not in dest.parents:raise SystemExit('Unsafe archive path')
    z.extract(item,archive.parent)
config=root/'postgres-private.json'
if config.exists():
 private=json.loads(config.read_text())
else:
 private={'admin_password':secrets.token_urlsafe(32),'app_password':secrets.token_urlsafe(32)}
 fd=os.open(config,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(private,f)
env=dict(os.environ,PGPASSWORD=private['admin_password'])
flags=getattr(subprocess,'CREATE_NO_WINDOW',0)
def run(args,**kwargs):
 return subprocess.run([str(bins/args[0])]+args[1:],env=env,check=True,creationflags=flags,**kwargs)
data=root/'postgres-data'
if not (data/'PG_VERSION').exists():
 pw=root/'postgres-init-password'
 fd=os.open(pw,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as f:f.write(private['admin_password'])
 run(['initdb.exe','-D',str(data),'-U','caf_demo_admin','-A','scram-sha-256','--encoding=UTF8','--locale=C','--pwfile='+str(pw)])
 pw.unlink()
 with (data/'postgresql.conf').open('a') as f:f.write("\nlisten_addresses='127.0.0.1'\nport=18130\nmax_connections=30\nshared_buffers='64MB'\n")
status=subprocess.run([str(bins/'pg_ctl.exe'),'-D',str(data),'status'],capture_output=True,creationflags=flags)
if status.returncode:
 run(['pg_ctl.exe','-D',str(data),'-l',str(root/'postgres.log'),'-w','-t','30','start'])
base=['psql.exe','-h','127.0.0.1','-p','18130','-U','caf_demo_admin','-d','postgres','-v','ON_ERROR_STOP=1','-At']
r=run(base+['-c',"SELECT 1 FROM pg_roles WHERE rolname='caf_demo'"],capture_output=True,text=True)
if r.stdout.strip()!='1':run(base,input="CREATE ROLE caf_demo LOGIN PASSWORD '"+private['app_password']+"';",text=True,capture_output=True)
r=run(base+['-c',"SELECT 1 FROM pg_database WHERE datname='caf_demo_netloom'"],capture_output=True,text=True)
if r.stdout.strip()!='1':run(base+['-c','CREATE DATABASE caf_demo_netloom OWNER caf_demo'],capture_output=True,text=True)
shared=root/'caf-database.json'
fd=os.open(shared,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
with os.fdopen(fd,'w') as f:json.dump({'DATABASE_URL':'postgresql://caf_demo:'+private['app_password']+'@127.0.0.1:18130/caf_demo_netloom?schema=public'},f)
print('Portable PostgreSQL16 running on127.0.0.1:18130; dedicated caf_demo_netloom database ready; connection in private caf-database.json.')
