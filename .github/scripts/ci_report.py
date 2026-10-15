"""Bounded, fail-closed CI evidence. Neither skips nor partial XML imply success."""
import argparse
import json
import os
import xml.etree.ElementTree as ET
from pathlib import Path


def build_report(suite,junit=Path('junit.xml'),execution=Path('ci-execution.json')):
    result={'suite':suite,'source_commit':os.environ.get('GITHUB_SHA'),'run_url':f"https://github.com/{os.environ.get('GITHUB_REPOSITORY')}/actions/runs/{os.environ.get('GITHUB_RUN_ID')}",'status':'failed','tests':0,'passed':0,'failed':0,'skipped':0,'failed_cases':[],'execution_completed':False,'pytest_exit_code':None}
    try:
        record=json.loads(execution.read_text())
        result['execution_completed']=record.get('status')=='completed' and record.get('source_commit')==result['source_commit']
        result['pytest_exit_code']=record.get('exit_code')
        root=ET.parse(junit).getroot()
        suites=[root] if root.tag=='testsuite' else root.findall('testsuite')
        for item in suites:
            result['tests']+=int(item.get('tests',0))
            result['failed']+=int(item.get('failures',0))+int(item.get('errors',0))
            result['skipped']+=int(item.get('skipped',0))
        for case in root.iter('testcase'):
            for child in case:
                if child.tag in ('failure','error') and len(result['failed_cases'])<5:
                    result['failed_cases'].append({'name':case.get('name'),'class':case.get('classname'),'message':child.get('message','')[:1200]})
        if result['tests']<result['failed']+result['skipped'] or min(result['tests'],result['failed'],result['skipped'])<0:
            raise ValueError('Inconsistent JUnit counts')
        result['passed']=result['tests']-result['failed']-result['skipped']
        if result['execution_completed'] and result['pytest_exit_code']==0 and result['passed']>0 and result['failed']==0:
            result['status']='passed'
    except (OSError,ValueError,TypeError,AttributeError,ET.ParseError):
        result['evidence_error']='Missing or invalid execution/JUnit evidence; not a passing run.'
    return result


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--suite',required=True);parser.add_argument('--output',default='ci-result.json')
    args=parser.parse_args();result=build_report(args.suite)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))


if __name__=='__main__':main()
