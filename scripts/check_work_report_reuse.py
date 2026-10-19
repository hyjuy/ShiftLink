"""Run deterministic reuse scenarios and connected API contracts; save machine-readable evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone
from uuid import uuid4
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    'tests/test_work_report_reuse_harness.py', 'tests/test_work_report_api.py', 'tests/test_mes_query.py',
    'tests/test_field_draft.py', 'tests/test_field_card_promote.py', 'tests/test_mes_storage.py',
    'tests/test_mes_handover_http.py', 'tests/test_judge_unavailable.py', 'tests/test_card_loader.py',
    'tests/test_typed_work_reports.py', 'tests/test_mes_uploader.py']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coverage', action='store_true', help='Use the installed coverage module as well')
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
    directory = ROOT / 'artifacts/work-report-reuse-harness' / run_id
    directory.mkdir(parents=True)
    xml_path = directory / 'tests.xml'
    environment = os.environ.copy()
    search = [str(ROOT)]
    if (ROOT / '.test-deps').is_dir():
        search.append(str(ROOT / '.test-deps'))
    if environment.get('PYTHONPATH'):
        search.append(environment['PYTHONPATH'])
    environment['PYTHONPATH'] = os.pathsep.join(search)
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    command = [sys.executable, '-m']
    if args.coverage:
        command += ['coverage', 'run', '--branch', '--data-file=' + str(directory / '.coverage'),
                    '--source=shiftlink.mes.work_reports,shiftlink.mes.query,shiftlink.mes.storage,shiftlink.mes.server,shiftlink.mes.field_draft,shiftlink.mes.uploader', '-m']
    command += ['pytest', '-p', 'no:cacheprovider', '-q', '--tb=short', '--junitxml=' + str(xml_path), *TARGETS]
    result = subprocess.run(command, cwd=ROOT, env=environment)
    tests = []
    if xml_path.exists():
        for case in ElementTree.parse(xml_path).iter('testcase'):
            status = next((name for name in ('failure', 'error', 'skipped') if case.find(name) is not None), 'passed')
            tests.append({'name':case.attrib['name'], 'class':case.attrib.get('classname'), 'status':status})
    coverage_code = None
    if args.coverage:
        coverage_code = subprocess.run([sys.executable, '-m', 'coverage', 'json',
            '--data-file=' + str(directory / '.coverage'), '-o', str(directory / 'coverage.json')],
            cwd=ROOT, env=environment).returncode
    fixtures = ROOT / 'tests/fixtures/work_report_reuse_cases.json'
    report = {'run_id':run_id, 'exit_code':result.returncode, 'coverage_exit_code':coverage_code,
              'external_llm':False, 'real_equipment':False,
              'scenario_fixture_sha256':hashlib.sha256(fixtures.read_bytes()).hexdigest(),
              'scenarios':json.loads(fixtures.read_text(encoding='utf-8')),
              'tests':tests, 'passed':sum(test['status'] == 'passed' for test in tests),
              'junit_xml':str(xml_path), 'coverage_json':str(directory / 'coverage.json') if args.coverage else None}
    report_path = directory.parent / 'latest.json'
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print('Harness report:', report_path)
    return result.returncode or coverage_code or (0 if tests else 1)


if __name__ == '__main__':
    raise SystemExit(main())
