"""Record the actual pytest exit status; partial JUnit is not a passing run."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main(args=None):
    args=sys.argv[1:] if args is None else args
    output=Path('ci-execution.json')
    Path('junit.xml').unlink(missing_ok=True)
    record={'source_commit':os.environ.get('GITHUB_SHA'),'status':'running','exit_code':None}
    output.write_text(json.dumps(record)+'\n')
    start=time.monotonic()
    try:
        result=subprocess.run([sys.executable,'-m','pytest','-q',*args,'--junitxml=junit.xml'])
        record.update(status='completed',exit_code=result.returncode)
        return result.returncode
    finally:
        record['duration_seconds']=round(time.monotonic()-start,2)
        output.write_text(json.dumps(record)+'\n')


if __name__=='__main__':raise SystemExit(main())
