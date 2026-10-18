#!/usr/bin/env python3
"""Offline simulation with real checks: success, repair, escalation and exhausted retries."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import bootstrap

SCENARIOS = {'success': [42], 'repair': [1, 42], 'escalation': [1, 2, 42], 'failure': [1, 2, 3]}


def prepare(project, scenario='success', lang='en'):
    """Create a disposable, deterministic project; never call a model or install dependencies."""
    with redirect_stdout(io.StringIO()):
        if bootstrap.install(project, apply=True, lang=lang):
            raise ValueError('Demo target conflicts with existing files')
    (project / 'app.py').write_text('def answer():\n    return 0\n', encoding='utf-8')
    (project / 'check_answer.py').write_text(
        'from app import answer\nassert answer() == 42, "answer() must equal 42"\n', encoding='utf-8')
    harness = {'schema_version': 1, 'projects': [{'name': 'app', 'path': '.', 'required': ['test'],
               'checks': {'test': {'commands': [['{python}', 'check_answer.py']], 'timeout_seconds': 10}}}]}
    (project / 'harness/config.json').write_text(json.dumps(harness, indent=2), encoding='utf-8')
    config = json.loads((project / 'workflow/config.json').read_text(encoding='utf-8'))
    config['not_applicable'] = {'app': {'lint': 'No lint tool in this tiny fixture',
        'typecheck': 'No static type checker in this tiny fixture', 'build': 'Python source needs no build'}}
    config['check_failure_categories'] = {'app/test': {'1': 'code'}}
    contract = json.loads((project / 'workflow/tasks.example.json').read_text(encoding='utf-8'))
    contract['run_id'] = scenario
    task = contract['tasks'][0]
    task['id'] = 'answer'
    task['simulation']['attempts'] = [{'changes': [{'path': 'app.py', 'before': '$current',
        'content': f'def answer():\n    return {value}\n'}]} for value in SCENARIOS[scenario]]
    for name, value in [('config.json', config), ('tasks.example.json', contract)]:
        (project / 'workflow' / name).write_text(json.dumps(value, indent=2), encoding='utf-8')
    return config, contract


def run_scenario(project, scenario, lang='en'):
    prepare(project, scenario, lang)
    baseline = subprocess.run([sys.executable, 'harness/run.py', 'test'], cwd=project,
                              capture_output=True, text=True, timeout=20)
    if baseline.returncode != 1:
        raise AssertionError('The actual acceptance check must fail before implementation')
    result = subprocess.run([sys.executable, 'workflow/run.py', 'run'], cwd=project,
                            capture_output=True, text=True, timeout=60)
    if result.returncode != (1 if scenario == 'failure' else 0):
        raise AssertionError(result.stdout + result.stderr)
    directory = project / '.local/workflow' / scenario
    report = json.loads((directory / 'report.json').read_text(encoding='utf-8'))
    expected = 'blocked' if scenario == 'failure' else 'success'
    if report['status'] != expected or not report['simulation']:
        raise AssertionError('Unexpected simulated workflow result')
    tiers = [e['tier'] for e in report['ledger'] if e['role'] == 'implementer']
    print(f'SIMULATION {scenario}: {report["status"]}; implementer tiers={tiers}; '
          f'calls={report["totals"]["calls"]}; old acceptance exit={baseline.returncode}; workflow exit={result.returncode}')
    print(f'  Evidence: {directory / "report.json"}')
    if expected == 'success':
        verified = subprocess.run([sys.executable, 'workflow/run.py', 'verify'], cwd=project,
                                  capture_output=True, text=True, timeout=20)
        if verified.returncode:
            raise AssertionError(verified.stdout + verified.stderr)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scenario', choices=['all', *SCENARIOS], default='all')
    parser.add_argument('--output', type=Path, help='New directory to keep projects, state, logs and reports')
    parser.add_argument('--lang', choices=['en', 'zh-CN'], default='en')
    args = parser.parse_args()
    names = list(SCENARIOS) if args.scenario == 'all' else [args.scenario]
    print('OFFLINE SIMULATION: fake model responses; real subprocess checks. No accounts or external calls.')
    if args.output:
        target = args.output.absolute()
        if target.exists():
            parser.error('--output must be a new directory; existing evidence is preserved')
        target.mkdir(parents=True)
        for scenario in names:
            run_scenario(target / scenario, scenario, args.lang)
    else:
        with tempfile.TemporaryDirectory(prefix='tiered-demo-') as temporary:
            for scenario in names:
                run_scenario(Path(temporary).resolve() / scenario, scenario, args.lang)
        print('Temporary demo projects removed. Use --output to retain evidence.')


if __name__ == '__main__':
    main()
