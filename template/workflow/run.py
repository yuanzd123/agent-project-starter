#!/usr/bin/env python3
"""Optional tiered workflow. Default fake adapter is offline; real CLI requires --allow-real."""
import argparse
import json
from pathlib import Path
import signal
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from workflow.engine import Workflow  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'verify', 'cancel'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--config', default='workflow/config.json')
    parser.add_argument('--tasks', default='workflow/tasks.example.json')
    parser.add_argument('--allow-real', action='store_true', help='Explicitly authorize configured external CLI calls')
    args = parser.parse_args()
    cancelled = False

    def stop(signum, frame):
        nonlocal cancelled
        cancelled = True

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        root = args.root.absolute()
        from workflow.safety import relative
        config_path, tasks_path = relative(root, args.config), relative(root, args.tasks)
        config = json.loads(config_path.read_text(encoding='utf-8'))
        contract = json.loads(tasks_path.read_text(encoding='utf-8'))
        config['control_files'] = sorted(set(config.get('control_files', []) + [args.config, args.tasks]))
        workflow = Workflow(root, config, contract, allow_real=args.allow_real, cancel=lambda: cancelled)
        if args.action == 'cancel':
            workflow.directory.mkdir(parents=True, exist_ok=True)
            (workflow.directory / 'cancel').touch()
            print('Cancellation requested; in-flight external outcomes may be uncertain.')
            return 0
        if args.action == 'verify':
            accepted = workflow.verify()
            print('VALID: saved acceptance matches current content and configuration' if accepted else 'INVALID: acceptance is absent or stale')
            return 0 if accepted else 1
        report = workflow.run()
        print((workflow.directory / 'summary.txt').read_text(encoding='utf-8'), end='')
        print(f'Report: {workflow.directory / "report.json"}')
        return 0 if report['status'] == 'success' else 1
    except (OSError, ValueError, TypeError, KeyError, ImportError):
        # Do not print arbitrary config content or subprocess errors that could contain secrets.
        print('ERROR: invalid or unavailable config/state. Check the workflow guide and local configuration.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
