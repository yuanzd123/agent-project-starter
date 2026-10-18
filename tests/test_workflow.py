"""Behavioral regression and CLI protocol tests; every model response is offline or mocked."""
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'template'))
from tools.workflow_demo import prepare
from workflow.adapters import AdapterError, CliAdapter, FakeAdapter
from workflow.engine import Workflow, validate
from workflow.safety import canonical, digest, execute, relative, resolve_executable


class Crash(BaseException):
    pass


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'project with spaces'
        self.config, self.contract = prepare(self.root)
        self.task = self.contract['tasks'][0]

    def workflow(self, **kwargs):
        return Workflow(self.root, self.config, self.contract, **kwargs)

    def run_workflow(self, **kwargs):
        return self.workflow(**kwargs).run()

    def scenario(self, values):
        self.task['simulation']['attempts'] = [{'changes': [{'path': 'app.py', 'before': '$current',
            'content': f'def answer():\n    return {value}\n'}]} for value in values]

    def change_check(self, command):
        path = self.root / 'harness/config.json'
        data = json.loads(path.read_text())
        data['projects'][0]['checks']['test']['commands'] = [command]
        path.write_text(json.dumps(data))

    def test_invalid_configs_and_unregistered_models(self):
        cases = [lambda c: c['providers']['offline'].update(kind='unknown'),
                 lambda c: c['tiers']['standard'].update(provider='missing'),
                 lambda c: c['tiers']['standard'].update(model='unregistered-model'),
                 lambda c: c['tiers']['standard'].update(max_input_tokens=-1),
                 lambda c: c['tiers']['standard'].update(timeout_seconds=float('nan')),
                 lambda c: c['run_budget'].update(usd=-1),
                 lambda c: c['run_budget'].update(tokens=True),
                 lambda c: c.update(roles=[]),
                 lambda c: c['policy'].update(same_tier_repairs=-1),
                 lambda c: c.update(schema_version=True)]
        for mutate in cases:
            with self.subTest(mutate=mutate):
                config = copy.deepcopy(self.config)
                mutate(config)
                with self.assertRaises((ValueError, TypeError)):
                    Workflow(self.root, config, self.contract)
        self.task['budget']['seconds'] = 0
        with self.assertRaises(ValueError):
            self.workflow()

    def test_missing_checks_and_unexplained_not_applicable_fail_preflight(self):
        self.config['not_applicable']['app'].pop('lint')
        with self.assertRaises(ValueError):
            self.workflow()
        self.config['not_applicable']['app']['lint'] = 'No linter configured for fixture'
        data = json.loads((self.root / 'harness/config.json').read_text())
        data['projects'][0]['checks'] = {}
        (self.root / 'harness/config.json').write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, 'missing required'):
            self.workflow()
        self.assertFalse((self.root / '.local/workflow').exists())

    def test_task_contract_missing_reference_cycle_and_duplicate(self):
        for dependencies in [['missing'], ['answer']]:
            self.task['depends_on'] = dependencies
            with self.assertRaises(ValueError):
                self.workflow()
        self.task['depends_on'] = []
        self.contract['tasks'].append(copy.deepcopy(self.task))
        with self.assertRaises(ValueError):
            self.workflow()

    def test_success_runs_real_checks_and_binds_report(self):
        before = subprocess.run([sys.executable, 'harness/run.py', 'test'], cwd=self.root, capture_output=True)
        self.assertEqual(before.returncode, 1)
        report = self.run_workflow()
        self.assertEqual(report['status'], 'success')
        self.assertEqual([e['role'] for e in report['ledger']], ['implementer', 'reviewer'])
        self.assertEqual(report['totals']['calls'], 2)
        self.assertEqual(report['totals']['usage'], {'input_tokens': 24, 'output_tokens': 16})
        self.assertTrue(report['simulation'])
        self.assertNotEqual(report['base_content_hash'], report['final_content_hash'])
        self.assertTrue(all(c['exit_code'] == 0 for c in report['checks']))
        self.assertTrue(self.workflow().verify())
        self.assertIn('@@', report['tasks']['answer']['change_refs'][0]['diff'])
        self.assertEqual(set(report['not_applicable']['app']), {'lint', 'typecheck', 'build'})

    def test_repair_and_strong_upgrade_have_bounded_calls(self):
        self.scenario([1, 2, 42])
        report = self.run_workflow()
        self.assertEqual(report['status'], 'success')
        self.assertEqual([e['tier'] for e in report['ledger'] if e['role'] == 'implementer'],
                         ['standard', 'standard', 'strong'])
        history = [h['status'] for h in report['tasks']['answer']['history']]
        self.assertIn('repairing', history)
        self.assertIn('escalating', history)
        self.assertEqual(sum(c['exit_code'] == 1 for c in report['checks']), 2)

    def test_retry_exhaustion_blocks_dependent_task(self):
        self.scenario([1, 2, 3])
        child = copy.deepcopy(self.task)
        child.update(id='dependent', depends_on=['answer'])
        self.contract['tasks'].append(child)
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'retry_exhausted')
        self.assertEqual(report['tasks']['dependent']['reason'], 'dependency_failed')
        self.assertEqual(report['totals']['calls'], 3)
        self.assertFalse(any(e['role'] == 'reviewer' for e in report['ledger']))

    def test_dependency_order_and_final_integrated_acceptance(self):
        child = copy.deepcopy(self.task)
        child.update(id='dependent', depends_on=['answer'], allowed_files=['helper.py'])
        child['simulation']['attempts'] = [{'changes': [{'path': 'helper.py', 'before': None, 'content': 'VALUE = 1\n'}]}]
        self.contract['tasks'].insert(0, child)  # Deliberately reverse input order.
        report = self.run_workflow()
        self.assertEqual(report['status'], 'success')
        self.assertEqual(report['tasks']['answer']['acceptance'], report['tasks']['dependent']['acceptance'])
        self.assertEqual([e['task_id'] for e in report['ledger']][:2], ['answer', 'dependent'])
        finals = [c for c in report['checks'] if c['final']]
        self.assertTrue(all(c['content_hash'] == report['final_content_hash'] for c in finals))

    def test_high_risk_escalates_directly_and_architect_is_separate(self):
        self.task['requirements'] = 'Fix payment authorization and return 42'
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['risk'], 'high')
        self.assertEqual([e['role'] for e in report['ledger']], ['architect', 'implementer', 'reviewer'])
        self.assertTrue(all(e['tier'] == 'strong' for e in report['ledger']))

    def test_documentation_uses_fast_tier(self):
        self.task['kind'] = 'documentation'
        report = self.run_workflow()
        self.assertEqual(report['ledger'][0]['tier'], 'fast')

    def test_architect_ambiguity_blocks_without_implementation(self):
        self.task['risk'] = 'standard'
        original = FakeAdapter.call
        def ambiguous(adapter, request, *args):
            response = original(adapter, request, *args)
            if request['role'] == 'architect':
                response['ambiguities'] = ['Which public interface is intended?']
            return response
        with mock.patch.object(FakeAdapter, 'call', ambiguous):
            report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'ambiguity')
        self.assertEqual(report['totals']['calls'], 1)

    def test_infrastructure_and_dependency_errors_do_not_upgrade(self):
        for category in ('infrastructure', 'dependency', 'ambiguity'):
            with self.subTest(category=category):
                self.contract['run_id'] = category
                self.task['simulation']['attempts'] = [{'error': {'category': category}}]
                report = self.run_workflow()
                self.assertEqual(report['tasks']['answer']['reason'], category)
                self.assertEqual(report['totals']['calls'], 1)

    def test_unknown_check_failure_is_infrastructure_not_code(self):
        self.config['check_failure_categories'] = {}
        self.change_check(['{python}', '-c', 'raise SystemExit(8)'])
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'infrastructure')
        self.assertEqual(report['totals']['calls'], 1)

    def test_missing_executable_does_not_consume_upgrade(self):
        self.change_check(['nonexistent-workflow-executable-42'])
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'infrastructure')
        self.assertEqual(report['totals']['calls'], 1)

    def test_budget_reserves_final_review_before_first_call(self):
        self.task['budget']['calls'] = 1
        report = self.run_workflow()
        self.assertEqual(report['totals']['calls'], 0)
        self.assertEqual(report['tasks']['answer']['reason'], 'budget_exhausted')
        self.assertIn('return 0', (self.root / 'app.py').read_text())

    def test_token_and_money_caps_fail_before_call(self):
        for field, amount in [('tokens', 1), ('usd', 0)]:
            self.contract['run_id'] = field
            self.task['budget'] = {'calls': 6, 'tokens': 200000, 'seconds': 180, 'usd': 10}
            self.config['run_budget']['usd'] = 10
            self.task['budget'][field] = amount
            for tier in self.config['tiers'].values():
                tier['price_per_million'] = {'input': 1, 'output': 2}
            report = self.run_workflow()
            self.assertEqual(report['totals']['calls'], 0)
            self.assertEqual(report['tasks']['answer']['reason'], 'budget_exhausted')

    def test_unknown_usage_is_not_zero_and_strict_blocks(self):
        self.task['simulation']['attempts'][0]['usage'] = None
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'unknown_usage')
        self.assertEqual(report['totals']['usage'], 'unknown')
        self.assertEqual(report['totals']['estimated_cost_usd'], 'unknown')
        self.assertEqual(report['totals']['tokens'], 28000)
        self.assertIn('return 0', (self.root / 'app.py').read_text())
        self.contract['run_id'] = 'unknown-permitted'
        self.config['strict_money'] = False
        report = self.run_workflow()
        self.assertEqual(report['status'], 'success')
        self.assertEqual(report['totals']['usage'], 'unknown')

    def test_usage_reconciliation_counts_architecture_and_failed_attempts(self):
        self.task['risk'] = 'standard'
        self.scenario([1, 42])
        for tier in self.config['tiers'].values():
            tier['price_per_million'] = {'input': 1, 'output': 2}
        self.task['budget']['usd'] = 2
        self.config['run_budget']['usd'] = 2
        report = self.run_workflow()
        self.assertEqual(report['totals']['calls'], 4)
        self.assertAlmostEqual(report['totals']['estimated_cost_usd'], 4 * 28 / 1e6)
        self.assertEqual(report['totals']['tokens'], 80)
        self.assertGreater(sum(e['cost_upper_usd'] for e in report['ledger']), report['totals']['estimated_cost_usd'])

    def test_successful_resume_is_idempotent(self):
        first = self.run_workflow()
        before = (self.root / 'app.py').stat().st_mtime_ns
        with mock.patch.object(FakeAdapter, 'call', side_effect=AssertionError('duplicate call')):
            second = self.run_workflow()
        self.assertEqual(first['ledger'], second['ledger'])
        self.assertEqual(first['checks'], second['checks'])
        self.assertEqual(before, (self.root / 'app.py').stat().st_mtime_ns)

    def test_completed_response_recovery_for_every_role(self):
        self.task['risk'] = 'standard'
        original_save = Workflow.save
        for role in ('architect', 'implementer', 'reviewer'):
            with self.subTest(role=role):
                self.contract['run_id'] = 'crash-' + role
                fired = []
                def crash_after_response(workflow):
                    original_save(workflow)
                    ledger = workflow.state['ledger']
                    if not fired and ledger and ledger[-1]['role'] == role and ledger[-1]['status'] == 'completed':
                        fired.append(True)
                        raise Crash()
                with mock.patch.object(Workflow, 'save', crash_after_response):
                    with self.assertRaises(Crash):
                        self.run_workflow()
                report = self.run_workflow()
                self.assertEqual(report['status'], 'success')
                self.assertEqual(report['totals']['calls'], 3)
                self.assertEqual(report['tasks']['answer']['attempts'], 1)

    def test_partial_patch_recovers_without_duplicate_application(self):
        original = os.replace
        fired = []
        def crash_after_replace(source, target):
            original(source, target)
            if Path(target) == self.root / 'app.py' and not fired:
                fired.append(True)
                raise Crash()
        with mock.patch('workflow.engine.os.replace', crash_after_replace):
            with self.assertRaises(Crash):
                self.run_workflow()
        modified = (self.root / 'app.py').stat().st_mtime_ns
        report = self.run_workflow()
        self.assertEqual(report['status'], 'success')
        self.assertEqual(report['totals']['calls'], 2)
        self.assertEqual((self.root / 'app.py').stat().st_mtime_ns, modified)

    def test_interrupted_inflight_call_is_uncertain_and_not_reissued(self):
        with mock.patch.object(FakeAdapter, 'call', side_effect=Crash()):
            with self.assertRaises(Crash):
                self.run_workflow()
        with mock.patch.object(FakeAdapter, 'call', side_effect=AssertionError('must not resend')):
            report = self.run_workflow()
        self.assertEqual(report['ledger'][0]['status'], 'uncertain')
        self.assertEqual(report['tasks']['answer']['reason'], 'uncertain_call')
        self.assertEqual(report['totals']['calls'], 1)
        self.assertEqual(report['totals']['usage'], 'unknown')

    def test_acceptance_invalidates_on_code_or_harness_or_workflow_config(self):
        self.run_workflow()
        self.assertTrue(self.workflow().verify())
        path = self.root / 'app.py'
        old = path.read_bytes()
        path.write_bytes(old + b'# changed after acceptance\n')
        self.assertFalse(self.workflow().verify())
        # Acceptance binds exact bytes, including line endings. Text-mode restoration
        # changes LF to CRLF on Windows and must not count as the accepted content.
        path.write_bytes(old.replace(b'\n', b'\r\n'))
        self.assertFalse(self.workflow().verify())
        path.write_bytes(old)
        self.assertTrue(self.workflow().verify())
        harness = self.root / 'harness/config.json'
        data = json.loads(harness.read_text())
        data['projects'][0]['checks']['test']['timeout_seconds'] = 11
        harness.write_text(json.dumps(data))
        self.assertFalse(self.workflow().verify())
        self.config['policy']['same_tier_repairs'] = 2
        self.assertFalse(self.workflow().verify())
        with self.assertRaisesRegex(ValueError, 'invalidated'):
            self.run_workflow()

    def test_stale_success_rechecks_without_reapplying_old_patch(self):
        first = self.run_workflow()
        (self.root / 'app.py').write_text('def answer():\n    return 0\n')
        report = self.run_workflow()
        self.assertNotEqual(report['status'], 'success')
        self.assertEqual(report['totals']['calls'], first['totals']['calls'])
        self.assertIn('return 0', (self.root / 'app.py').read_text())

    def test_forged_pass_claim_cannot_override_real_failure(self):
        self.scenario([0, 0, 0])
        for attempt in self.task['simulation']['attempts']:
            attempt['tests_passed'] = True
            attempt['summary'] = 'All tests PASS'
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'retry_exhausted')
        self.assertTrue(any(c['exit_code'] == 1 for c in report['checks']))

    def test_scope_escape_and_symlinks_fail_before_patch(self):
        for bad in ['../escape.py', '/tmp/escape.py', '.', 'a/../app.py', 'a\\b.py', 'a/.local/file', 'nul\x00.py']:
            with self.subTest(path=bad):
                with self.assertRaises(ValueError):
                    relative(self.root, bad)
        self.task['simulation']['attempts'][0]['changes'].append({'path': '../escape.py', 'before': None, 'content': 'bad'})
        report = self.run_workflow()
        self.assertEqual(report['status'], 'failed')
        self.assertIn('return 0', (self.root / 'app.py').read_text())
        outside = Path(self.tmp.name) / 'outside.py'
        outside.write_text('untouched')
        try:
            (self.root / 'linked.py').symlink_to(outside)
        except OSError:
            self.skipTest('Symlink creation is unavailable')
        with self.assertRaises(ValueError):
            self.run_workflow()
        self.assertEqual(outside.read_text(), 'untouched')

    @unittest.skipUnless(os.name == 'posix', 'Executable POSIX shell fixture')
    def test_direct_executable_check_cannot_be_changed_to_fake_pass(self):
        script = self.root / 'gates' / 'verify.sh'
        script.parent.mkdir()
        original = '#!/bin/sh\nexit 1\n'
        script.write_text(original)
        script.chmod(0o755)
        path = self.root / 'harness/config.json'
        harness = json.loads(path.read_text())
        harness['projects'][0]['path'] = 'gates'
        harness['projects'][0]['checks']['test']['commands'] = [['./verify.sh']]
        path.write_text(json.dumps(harness))
        self.task['allowed_files'] = ['gates/verify.sh']
        self.task['simulation']['attempts'] = [{'changes': [{'path': 'gates/verify.sh',
            'before': '$current', 'content': '#!/bin/sh\nexit 0\n'}]}]
        baseline = execute(['./verify.sh'], script.parent, 5)
        self.assertEqual(baseline['exit_code'], 1)
        report = self.run_workflow()
        self.assertEqual(report['status'], 'failed', 'Implementation must not replace its own acceptance executable')
        self.assertEqual(report['tasks']['answer']['reason'], 'protected_rule')
        self.assertEqual(script.read_text(), original)
        self.assertEqual(report['totals']['calls'], 1)
        self.assertFalse(any(e['role'] == 'reviewer' for e in report['ledger']))

    @unittest.skipUnless(os.name == 'posix', 'Executable POSIX shell fixture')
    def test_path_resolved_check_executable_is_protected(self):
        script = self.root / 'checkbin' / 'accept-gate'
        script.parent.mkdir()
        script.write_text('#!/bin/sh\nexit 1\n')
        script.chmod(0o755)
        self.change_check(['accept-gate'])
        self.task['allowed_files'] = ['checkbin/accept-gate']
        self.task['simulation']['attempts'] = [{'changes': [{'path': 'checkbin/accept-gate',
            'before': '$current', 'content': '#!/bin/sh\nexit 0\n'}]}]
        # A relative PATH entry belongs to the check cwd, not this test runner's cwd.
        with mock.patch.dict(os.environ, {'PATH': 'checkbin' + os.pathsep + os.environ.get('PATH', '')}):
            report = self.run_workflow()
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['tasks']['answer']['reason'], 'protected_rule')
        self.assertIn('exit 1', script.read_text())

    def test_interpreter_check_argument_is_canonicalized(self):
        (self.root / 'gates').mkdir()
        script = self.root / 'verify.py'
        script.write_text('raise SystemExit(1)\n')
        path = self.root / 'harness/config.json'
        harness = json.loads(path.read_text())
        harness['projects'][0]['path'] = 'gates'
        harness['projects'][0]['checks']['test']['commands'] = [['{python}', '../verify.py']]
        path.write_text(json.dumps(harness))
        self.task['allowed_files'] = ['verify.py']
        self.task['simulation']['attempts'] = [{'changes': [{'path': 'verify.py',
            'before': '$current', 'content': 'pass\n'}]}]
        report = self.run_workflow()
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['tasks']['answer']['reason'], 'protected_rule')
        self.assertEqual(script.read_text(), 'raise SystemExit(1)\n')

    @unittest.skipUnless(os.name == 'posix', 'Executable POSIX shell fixture')
    def test_absolute_check_executable_requires_explicit_reviewed_rule_change(self):
        script = self.root / 'verify.sh'
        script.write_text('#!/bin/sh\nexit 1\n')
        script.chmod(0o755)
        self.change_check([str(script)])
        self.task['allowed_files'] = ['verify.sh']
        self.config['allow_rule_changes'] = ['verify.sh']
        self.task['simulation']['attempts'] = [{'changes': [{'path': 'verify.sh',
            'before': '$current', 'content': '#!/bin/sh\nexit 0\n'}]}]
        rejected = self.run_workflow()
        self.assertEqual(rejected['tasks']['answer']['reason'], 'review_rejected')
        self.assertTrue(rejected['tasks']['answer']['change_refs'][0]['rule_change'])
        self.contract['run_id'] = 'explicit-reviewed-executable'
        self.task['simulation']['approved_rule_changes'] = ['verify.sh']
        accepted = self.run_workflow()
        self.assertEqual(accepted['status'], 'success')

    @unittest.skipUnless(os.name == 'posix', 'Executable POSIX shell fixture')
    def test_external_path_check_does_not_protect_unexecuted_same_name_file(self):
        external = Path(self.tmp.name) / 'external-bin' / 'accept-gate'
        external.parent.mkdir()
        external.write_text('#!/bin/sh\nexit 0\n')
        external.chmod(0o755)
        decoy = self.root / 'accept-gate'
        decoy.write_text('#!/bin/sh\nexit 1\n')
        decoy.chmod(0o755)
        self.change_check(['accept-gate'])
        self.task['allowed_files'] = ['accept-gate']
        self.task['simulation']['attempts'] = [{'changes': [{'path': 'accept-gate',
            'before': '$current', 'content': '#!/bin/sh\nexit 7\n'}]}]
        with mock.patch.dict(os.environ, {'PATH': str(external.parent) + os.pathsep + os.environ.get('PATH', '')}):
            workflow = self.workflow()
            self.assertNotIn('accept-gate', workflow.check_sources)
            report = workflow.run()
        self.assertEqual(report['status'], 'success')
        checks = [c for c in report['checks'] if c['label'] == 'app/test']
        self.assertTrue(all(c['executable'] == str(external) for c in checks))
        self.assertTrue(all(c['exit_code'] == 0 for c in checks))
        self.assertFalse(report['tasks']['answer']['change_refs'][0]['rule_change'])

    @unittest.skipUnless(os.name == 'posix', 'Executable POSIX shell fixture')
    def test_path_target_change_invalidates_acceptance(self):
        executables = []
        for directory in ('first-bin', 'second-bin'):
            executable = Path(self.tmp.name) / directory / 'accept-gate'
            executable.parent.mkdir()
            executable.write_text('#!/bin/sh\nexit 0\n')
            executable.chmod(0o755)
            executables.append(executable)
        self.change_check(['accept-gate'])
        old_path = os.environ.get('PATH', '')
        with mock.patch.dict(os.environ, {'PATH': str(executables[0].parent) + os.pathsep + old_path}):
            self.assertEqual(self.run_workflow()['status'], 'success')
            self.assertTrue(self.workflow().verify())
        with mock.patch.dict(os.environ, {'PATH': str(executables[1].parent) + os.pathsep + old_path}):
            self.assertFalse(self.workflow().verify())
            with self.assertRaisesRegex(ValueError, 'configuration changed'):
                self.run_workflow()

    def test_tests_and_control_files_cannot_be_weakened(self):
        for name in ['check_answer.py', 'harness/config.json', '.github/workflows/ci.yml']:
            with self.subTest(path=name):
                self.contract['run_id'] = 'protect-' + str(len(name))
                self.task['allowed_files'] = [name]
                self.task['simulation']['attempts'] = [{'changes': [{'path': name, 'before': '$current', 'content': 'pass\n'}]}]
                report = self.run_workflow()
                self.assertEqual(report['status'], 'failed')
                self.assertIn(report['tasks']['answer']['reason'], {'protected_rule', 'file_scope'})

    def test_explicit_rule_change_requires_independent_approval(self):
        self.task['allowed_files'].append('check_answer.py')
        self.config['allow_rule_changes'] = ['check_answer.py']
        self.task['simulation']['attempts'][0]['changes'].append({'path': 'check_answer.py', 'before': '$current',
            'content': 'from app import answer\nassert isinstance(answer(), int)\nassert answer() == 42\n'})
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'review_rejected')
        self.contract['run_id'] = 'reviewed-rule'
        self.task['simulation']['approved_rule_changes'] = ['check_answer.py']
        report = self.run_workflow()
        self.assertEqual(report['status'], 'success')
        self.assertTrue(any(ref['rule_change'] for ref in report['tasks']['answer']['change_refs']))

    def test_reviewer_read_only_and_rejection_blocks_dependents(self):
        self.task['simulation']['verdict'] = 'reject'
        child = copy.deepcopy(self.task)
        child.update(id='dependent', depends_on=['answer'])
        child['simulation']['verdict'] = 'approve'
        self.contract['tasks'].append(child)
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['status'], 'failed')
        self.assertEqual(report['tasks']['dependent']['reason'], 'dependency_failed')
        self.assertEqual(sum(e['role'] == 'reviewer' for e in report['ledger']), 1)

    def test_reviewer_patch_and_direct_side_effect_rejected(self):
        original = FakeAdapter.call
        for mode in ('patch', 'side_effect'):
            self.contract['run_id'] = mode
            def tamper(adapter, request, *args):
                response = original(adapter, request, *args)
                if request['role'] == 'reviewer':
                    if mode == 'patch':
                        response['changes'] = [{'path': 'app.py', 'content': 'evil', 'before': None}]
                    else:
                        (self.root / 'app.py').write_text('changed during review')
                return response
            with mock.patch.object(FakeAdapter, 'call', tamper):
                report = self.run_workflow()
            self.assertNotEqual(report['status'], 'success')

    def test_checks_cannot_modify_source_and_evidence_tamper_invalidates(self):
        self.change_check(['{python}', '-c', "from pathlib import Path; Path('app.py').write_text('bad')"])
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'checks_modified_content')
        self.assertEqual(report['totals']['calls'], 1)

    def test_saved_log_tampering_invalidates_acceptance(self):
        report = self.run_workflow()
        log = self.root / '.local/workflow/success' / report['checks'][0]['log']
        log.write_text('FAKE PASS')
        self.assertFalse(self.workflow().verify())

    def test_cancel_and_deadline_prevent_model_calls(self):
        report = self.run_workflow(cancel=lambda: True)
        self.assertEqual(report['status'], 'cancelled')
        self.assertEqual(report['totals']['calls'], 0)
        self.contract['run_id'] = 'deadline'
        self.task['budget']['seconds'] = 0.001
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'deadline')
        self.assertEqual(report['totals']['calls'], 0)

    def test_default_has_no_real_calls_or_network(self):
        with mock.patch.object(CliAdapter, 'call', side_effect=AssertionError('real call')), \
             mock.patch('socket.create_connection', side_effect=AssertionError('network')):
            self.assertEqual(self.run_workflow()['status'], 'success')
        self.contract['run_id'] = 'real-denied'
        self.config['providers']['offline'].update(kind='cli', argv=[sys.executable, '-c', 'raise RuntimeError()'])
        with mock.patch.object(CliAdapter, 'call', side_effect=AssertionError('unauthorized real call')):
            report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'real_calls_disabled')
        self.assertEqual(report['totals']['calls'], 0)

    def test_strict_real_path_rejects_unreliable_usage_before_launch(self):
        self.config['providers']['offline'].update(kind='cli', argv=[sys.executable, '-c', 'pass'])
        self.config['tiers']['standard']['reliable_usage'] = False
        with mock.patch.object(CliAdapter, 'call', side_effect=AssertionError('must not launch')):
            report = self.run_workflow(allow_real=True)
        self.assertEqual(report['tasks']['answer']['reason'], 'unmetered_strict_budget')

    def test_chinese_workflow_uses_shared_runtime(self):
        target = Path(self.tmp.name).resolve() / '中文项目'
        config, contract = prepare(target, 'repair', 'zh-CN')
        report = Workflow(target, config, contract).run()
        self.assertEqual(report['status'], 'success')
        self.assertEqual((target / 'workflow/engine.py').read_bytes(), (ROOT / 'template/workflow/engine.py').read_bytes())


    def test_actual_cli_bridge_end_to_end_without_service_call(self):
        bridge = Path(self.tmp.name) / 'bridge.py'
        bridge.write_text("""import json,sys
r=json.load(sys.stdin)
assert r['model']=='contract-test-model'
assert r['mode'] == ('propose_changes' if r['role']=='implementer' else 'read_only')
if r['role']=='architect':
    out={'plan':'Use the allowed app file and preserve tests', 'ambiguities':[]}
elif r['role']=='implementer':
    assert r['plan'] and r['files']['app.py']['sha256']
    out={'changes':[{'path':'app.py','before':r['files']['app.py']['sha256'],'content':'def answer():\\n    return 42\\n'}]}
else:
    assert r['changes'][0]['diff'] and r['evidence'][0]['log_excerpt']
    assert all(item['exit_code']==0 for item in r['evidence'])
    assert r['acceptance_rules']['projects'][0]['required']==['test']
    out={'verdict':'approve','approved_rule_changes':[]}
out.update(protocol_version=1,usage={'input_tokens':31,'output_tokens':17})
print(json.dumps(out))
""", encoding='utf-8')
        self.task['risk'] = 'standard'
        self.config['providers'] = {'bridge': {'kind': 'cli', 'models': ['contract-test-model'],
            'argv': [sys.executable, str(bridge)], 'env_allowlist': []}}
        for tier in self.config['tiers'].values():
            tier.update(provider='bridge', model='contract-test-model')
        report = self.run_workflow(allow_real=True)
        self.assertEqual(report['status'], 'success')
        self.assertFalse(report['simulation'])  # Real local process protocol, no service contacted.
        self.assertEqual(report['totals']['usage'], {'input_tokens': 93, 'output_tokens': 51})

    def test_harness_change_requires_new_run_and_rule_review(self):
        self.run_workflow()
        self.change_check(['{python}', '-c', 'pass'])
        with self.assertRaisesRegex(ValueError, 'harness configuration changed'):
            self.run_workflow()
        self.assertFalse(self.workflow().verify())

    def test_base_revision_mismatch_and_stale_lock(self):
        self.contract['base_revision'] = 'not-the-checkout'
        with self.assertRaisesRegex(ValueError, 'base_revision'):
            self.run_workflow()
        self.contract['base_revision'] = None
        lock = self.root / '.local/workflow/lock'
        lock.parent.mkdir(parents=True, exist_ok=True)
        lock.write_text('stale owner; manual inspection required')
        with self.assertRaisesRegex(ValueError, 'locked'):
            self.run_workflow()
        self.assertTrue(lock.exists())

    def test_command_timeout_does_not_upgrade(self):
        self.change_check(['{python}', '-c', 'import time; time.sleep(5)'])
        self.config['policy']['check_timeout_seconds'] = 0.1
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'timeout')
        self.assertEqual(report['totals']['calls'], 1)

    def test_final_review_reserve_is_available_after_repair_budget(self):
        self.scenario([1, 42])
        self.task['budget']['calls'] = 3
        self.config['run_budget']['calls'] = 3
        report = self.run_workflow()
        self.assertEqual(report['status'], 'success')
        self.assertEqual(report['totals']['calls'], 3)
        self.assertEqual(report['ledger'][-1]['role'], 'reviewer')

    def test_benchmark_rejects_mismatched_rules_and_counts_failed_costs(self):
        from tools.workflow_benchmark import compare
        passed = self.run_workflow()
        failed = copy.deepcopy(passed)
        failed['tasks']['answer']['status'] = 'blocked'
        failed['tasks']['answer']['attempts'] = 3
        failed['totals']['estimated_cost_usd'] = 2
        passed['totals']['estimated_cost_usd'] = 1
        result = compare({'a': [passed, failed], 'b': [passed, failed]})
        self.assertEqual(result['strategies']['a']['cost_per_final_success_usd'], 3)
        self.assertEqual(result['strategies']['a']['success_rate'], 0.5)
        different = copy.deepcopy(passed)
        different['benchmark_key'] = 'different-rules'
        with self.assertRaises(ValueError):
            compare({'a': [passed], 'b': [different]})
        different['benchmark_key'] = passed['benchmark_key']
        different['simulation'] = False
        with self.assertRaises(ValueError):
            compare({'a': [passed], 'b': [different]})
        failed['totals']['estimated_cost_usd'] = 'unknown'
        self.assertEqual(compare({'a': [failed], 'b': [failed]})['strategies']['a']['cost_per_final_success_usd'], 'unknown')

    def test_cli_cancel_marker_preserves_state_and_default_gate(self):
        result = subprocess.run([sys.executable, 'workflow/run.py', 'cancel'], cwd=self.root,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([sys.executable, 'workflow/run.py', 'run'], cwd=self.root,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 1)
        saved = json.loads((self.root / '.local/workflow/success/report.json').read_text())
        self.assertEqual(saved['status'], 'cancelled')
        self.assertEqual(saved['totals']['calls'], 0)

    def test_usage_above_cap_is_uncertain_and_blocks(self):
        self.task['simulation']['attempts'][0]['usage'] = {'input_tokens': 999999, 'output_tokens': 1}
        report = self.run_workflow()
        self.assertEqual(report['ledger'][0]['status'], 'uncertain')
        self.assertEqual(report['tasks']['answer']['reason'], 'usage_exceeds_limit')
        self.assertEqual(report['totals']['usage'], 'unknown')
        self.assertIn('return 0', (self.root / 'app.py').read_text())

    def test_runtime_cache_is_not_a_source_authority(self):
        self.run_workflow()
        (self.root / 'unused.pyc').write_bytes(b'disposable cache')
        self.assertTrue(self.workflow().verify())
        with self.assertRaises(ValueError):
            relative(self.root, 'unused.pyc')

    def test_test_file_change_invalidates_acceptance(self):
        self.run_workflow()
        (self.root / 'check_answer.py').write_text('pass\n')
        self.assertFalse(self.workflow().verify())

    def test_run_wall_clock_budget_limits_calls(self):
        self.config['run_budget']['seconds'] = 0.001
        report = self.run_workflow()
        self.assertEqual(report['tasks']['answer']['reason'], 'deadline')
        self.assertEqual(report['totals']['calls'], 0)

    def test_completed_elapsed_time_is_frozen_on_noop_resume(self):
        first = self.run_workflow()
        second = self.run_workflow()
        self.assertEqual(first['elapsed_seconds'], second['elapsed_seconds'])


class CliContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.script = self.root / 'mock bridge.py'
        self.provider = {'kind': 'cli', 'models': ['operator-verified-model'],
                         'argv': [sys.executable, str(self.script)], 'env_allowlist': []}
        self.request = {'protocol_version': 1, 'call_id': 'id-1', 'role': 'implementer',
                        'mode': 'propose_changes', 'model': 'operator-verified-model', 'effort': 'supported-effort',
                        'max_input_tokens': 1000, 'max_output_tokens': 200, 'task': {'requirements': 'literal $(unsafe)'}}

    def script_text(self, source):
        self.script.write_text(source, encoding='utf-8')

    def test_cli_actual_process_validates_parameters_and_usage(self):
        self.script_text('''import json, os, sys
r = json.load(sys.stdin)
assert r['model'] == 'operator-verified-model'
assert r['effort'] == 'supported-effort'
assert r['max_input_tokens'] == 1000 and r['max_output_tokens'] == 200
assert r['task']['requirements'] == 'literal $(unsafe)'
assert not os.path.exists('app.py')
assert 'WORKFLOW_TEST_SECRET' not in os.environ
print(json.dumps({'protocol_version': 1, 'changes': [], 'usage': {'input_tokens': 7, 'output_tokens': 9}}))
''')
        with mock.patch.dict(os.environ, {'WORKFLOW_TEST_SECRET': 'never-inherit'}):
            result = CliAdapter().call(self.request, self.provider, 5, lambda: False)
        self.assertEqual(result['usage'], {'input_tokens': 7, 'output_tokens': 9})

    def test_cli_error_protocol_and_secret_response_are_uncertain(self):
        for source in ['raise SystemExit(7)', 'print("not JSON")', 'print("{}")']:
            self.script_text(source)
            with self.assertRaises(AdapterError) as caught:
                CliAdapter().call(self.request, self.provider, 5, lambda: False)
            self.assertTrue(caught.exception.uncertain)
        self.provider['env_allowlist'] = ['WORKFLOW_TEST_SECRET']
        self.script_text("import json,os; print(json.dumps({'protocol_version':1,'message':os.environ['WORKFLOW_TEST_SECRET']}))")
        with mock.patch.dict(os.environ, {'WORKFLOW_TEST_SECRET': 'unique-secret-\n占位'}):
            with self.assertRaises(AdapterError) as caught:
                CliAdapter().call(self.request, self.provider, 5, lambda: False)
        self.assertNotIn('unique-secret-', str(caught.exception))

    def test_cli_timeout_and_cancel_are_uncertain(self):
        self.script_text('import time; time.sleep(20)')
        with self.assertRaises(AdapterError) as caught:
            CliAdapter().call(self.request, self.provider, 0.1, lambda: False)
        self.assertEqual(caught.exception.category, 'timeout')
        self.assertTrue(caught.exception.uncertain)
        event = threading.Event()
        timer = threading.Timer(0.1, event.set)
        timer.start()
        try:
            with self.assertRaises(AdapterError) as caught:
                CliAdapter().call(self.request, self.provider, 5, event.is_set)
        finally:
            timer.cancel()
        self.assertEqual(caught.exception.category, 'cancelled')
        self.assertTrue(caught.exception.uncertain)

    def test_output_limit_and_missing_cli_are_bounded(self):
        self.script_text("print('x' * 1100000)")
        with self.assertRaises(AdapterError) as caught:
            CliAdapter().call(self.request, self.provider, 5, lambda: False)
        self.assertEqual(caught.exception.category, 'output_limit')
        self.provider['argv'] = [str(self.root / 'missing-executable')]
        with self.assertRaises(AdapterError) as caught:
            CliAdapter().call(self.request, self.provider, 5, lambda: False)
        self.assertFalse(caught.exception.uncertain)

    @unittest.skipUnless(os.name == 'posix', 'POSIX interpreter symlink fixture')
    def test_executable_lookup_preserves_interpreter_launch_alias(self):
        alias = self.root / 'python-alias'
        alias.symlink_to(sys.executable)
        self.assertEqual(resolve_executable(str(alias), self.root), alias)
        command = [str(alias), '-c', 'import sys; print(sys.executable)']
        expected = subprocess.run(command, capture_output=True, text=True, timeout=5)
        actual = execute(command, self.root, 5)
        self.assertEqual(actual['exit_code'], 0)
        self.assertEqual(actual['stdout'], expected.stdout)
        self.assertEqual(actual['executable'], str(alias))

    @unittest.skipUnless(os.name == 'posix', 'POSIX process-group cleanup assertion')
    def test_timeout_cancel_and_normal_exit_clean_descendants(self):
        for mode in ('timeout', 'cancel', 'completed'):
            marker = self.root / ('survived-' + mode)
            child = 'import pathlib,time; time.sleep(0.5); pathlib.Path(' + repr(str(marker)) + ').write_text("leaked")'
            parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",' + repr(child) + ']); '
            parent += 'time.sleep(10)' if mode != 'completed' else 'time.sleep(0.05)'
            started = time.monotonic()
            result = execute([sys.executable, '-c', parent], self.root, 0.15 if mode == 'timeout' else 2,
                             cancel=lambda: mode == 'cancel' and time.monotonic() - started > 0.15)
            self.assertEqual(result['kind'], {'timeout': 'timeout', 'cancel': 'cancelled', 'completed': 'completed'}[mode])
            time.sleep(0.6)
            self.assertFalse(marker.exists(), 'A child escaped ordinary process-group cleanup')


if __name__ == '__main__':
    unittest.main()
