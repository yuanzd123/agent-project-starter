#!/usr/bin/env python3
"""Compare equivalent workflow reports, or run a clearly labelled offline simulated suite."""
import argparse
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'template'))
from tools.workflow_demo import SCENARIOS, prepare
from workflow.engine import Workflow


def compare(groups):
    """Import extension point: report sets must cover identical case/source/acceptance fingerprints."""
    if len(groups) < 2 or any(not reports for reports in groups.values()):
        raise ValueError('Supply at least two nonempty strategy report sets')
    reference = None
    modes = set()
    rows = {}
    for name, reports in groups.items():
        fingerprints = sorted(r['benchmark_key'] for r in reports)
        if reference is not None and fingerprints != reference:
            raise ValueError('Task sets, starting source or acceptance rules differ; comparison rejected')
        reference = fingerprints
        modes.update(r['simulation'] for r in reports)
        tasks = [task for report in reports for task in report['tasks'].values()]
        successes = sum(t['status'] == 'success' for t in tasks)
        costs = [r['totals']['estimated_cost_usd'] for r in reports]
        known = all(isinstance(cost, (int, float)) for cost in costs)
        escalated = 0
        for report in reports:
            for ident in report['tasks']:
                tiers = [e['tier'] for e in report['ledger'] if e['task_id'] == ident and e['role'] == 'implementer']
                escalated += bool(tiers and any(tier != tiers[0] for tier in tiers[1:]))
        rows[name] = {'tasks': len(tasks), 'successes': successes, 'success_rate': successes / len(tasks),
                      'total_estimated_cost_usd': sum(costs) if known else 'unknown',
                      # Include failed tasks, architects, repairs and reviews in the numerator.
                      'cost_per_final_success_usd': sum(costs) / successes if known and successes else 'unknown',
                      'elapsed_seconds': sum(r['elapsed_seconds'] for r in reports),
                      'calls': sum(r['totals']['calls'] for r in reports),
                      'rework_attempts': sum(max(0, t['attempts'] - 1) for t in tasks),
                      'rework_rate': sum(t['attempts'] > 1 for t in tasks) / len(tasks),
                      'upgrade_rate': escalated / len(tasks)}
    if len(modes) != 1:
        raise ValueError('Do not mix simulated and real CLI reports')
    return {'schema_version': 1, 'simulation': modes == {True}, 'strategies': rows,
            'note': 'Configured-rate estimates, not invoices. No optimal-router or real-world savings claim.'}


def offline_suite():
    groups = {}
    with tempfile.TemporaryDirectory(prefix='workflow-benchmark-') as temporary:
        for strategy in ('all_strong', 'single_practical', 'tiered'):
            reports = []
            for scenario in SCENARIOS:
                root = Path(temporary).resolve() / strategy / scenario
                config, contract = prepare(root, scenario)
                contract['benchmark_case'] = scenario
                contract['tasks'][0]['risk'] = 'standard' if scenario == 'escalation' else 'low'
                # Artificial rates only; not prices or claims about any commercial model.
                for tier, rate in [('fast', 0.1), ('standard', 1), ('strong', 5)]:
                    config['tiers'][tier]['price_per_million'] = {'input': rate, 'output': rate * 2}
                config['run_budget']['usd'] = 100
                contract['tasks'][0]['budget']['usd'] = 100
                if strategy != 'tiered':
                    tier = 'strong' if strategy == 'all_strong' else 'standard'
                    config['roles'] = {role: tier for role in config['roles']}
                    config['policy'].update(fast_tier=tier, strong_tier=tier)
                reports.append(Workflow(root, config, contract).run())
            groups[strategy] = reports
    result = compare(groups)
    result['note'] = ('OFFLINE FIXED SIMULATION: scripted outcomes do not vary by model; rates are artificial. '
                      'Elapsed time measures local orchestration/checks, not service latency. '
                      'This exercises the comparison interface and cannot establish model quality or savings.')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', action='append', default=[], metavar='STRATEGY=PATH',
                        help='Repeat for each saved report; omit to run the fixed offline suite')
    parser.add_argument('--output', type=Path, help='New JSON file for the comparison')
    args = parser.parse_args()
    try:
        if args.report:
            groups = {}
            for value in args.report:
                strategy, path = value.split('=', 1)
                groups.setdefault(strategy, []).append(json.loads(Path(path).read_text(encoding='utf-8')))
            result = compare(groups)
        else:
            result = offline_suite()
        encoded = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('x', encoding='utf-8') as stream:
                stream.write(encoded)
        print(encoded, end='')
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(2, f'Cannot compare reports: {type(exc).__name__}; check task/rule parity and input files.\n')


if __name__ == '__main__':
    main()
