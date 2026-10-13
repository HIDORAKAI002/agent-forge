"""Write validation-only records to a non-running branch, using the CI-scoped token."""
import base64,json,os,time,urllib.request,urllib.error
from pathlib import Path
repo=os.environ['GITHUB_REPOSITORY'];token=os.environ['GITHUB_TOKEN'];data=json.loads(Path('ci-result.json').read_text());branch='validation';base=f'https://api.github.com/repos/{repo}'
def request(method,path,payload=None):
 raw=None if payload is None else json.dumps(payload).encode()
 req=urllib.request.Request(base+path,data=raw,method=method,headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28'})
 with urllib.request.urlopen(req,timeout=20) as r:return json.load(r)
try:request('GET','/git/ref/heads/'+branch)
except urllib.error.HTTPError as error:
 if error.code!=404:raise
 try:request('POST','/git/refs',{'ref':'refs/heads/'+branch,'sha':os.environ['GITHUB_SHA']})
 except urllib.error.HTTPError as conflict:
  if conflict.code!=422:raise
path='/contents/docs/ci/'+data['suite']+'.json';body={'message':'ci: record '+data['suite']+' validation','branch':branch,'content':base64.b64encode(json.dumps(data,indent=2).encode()).decode()}
for attempt in range(5):
 try:
  old=request('GET',path+'?ref='+branch);body['sha']=old['sha']
 except urllib.error.HTTPError as error:
  if error.code!=404:raise
 try:request('PUT',path,body);print('Published bounded validation record');break
 except urllib.error.HTTPError as error:
  if error.code not in (409,422) or attempt==4:raise
  time.sleep(2)
