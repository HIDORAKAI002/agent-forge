"""Publish bounded test evidence; never dump environment or tokens."""
import argparse,json,os,xml.etree.ElementTree as ET
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--suite',required=True);p.add_argument('--output',default='ci-result.json');a=p.parse_args()
result={'suite':a.suite,'source_commit':os.environ.get('GITHUB_SHA'),'run_url':f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}",'status':'failed','tests':0,'passed':0,'failed':0,'skipped':0}
if Path('junit.xml').exists():
 root=ET.parse('junit.xml').getroot();suites=[root] if root.tag=='testsuite' else root.findall('testsuite')
 for s in suites:
  result['tests']+=int(s.get('tests',0));result['failed']+=int(s.get('failures',0))+int(s.get('errors',0));result['skipped']+=int(s.get('skipped',0))
 result['failed_cases']=[]
 for case in root.iter('testcase'):
  for child in case:
   if child.tag in ('failure','error') and len(result['failed_cases'])<5:result['failed_cases'].append({'name':case.get('name'),'class':case.get('classname'),'message':child.get('message','')[:1200]})
 result['passed']=result['tests']-result['failed']-result['skipped'];result['status']='passed' if result['tests']>0 and result['failed']==0 else 'failed'
Path(a.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
