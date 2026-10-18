"""Serial, persisted tiered workflow. All control input belongs to the operator."""
from contextlib import contextmanager
import copy
import difflib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time

from .adapters import ADAPTERS, AdapterError, CATEGORIES
from .safety import atomic_json, canonical, content_hash, digest, execute, relative, resolve_executable, snapshot

STAGES = {'lint', 'typecheck', 'test', 'build'}
TERMINAL = {'success', 'failed', 'blocked', 'cancelled'}
LIMITS = {'calls', 'tokens', 'seconds', 'usd'}


def number(value, name, zero=False, integer=False):
    try:
        finite = isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        finite = False
    if isinstance(value, bool) or not finite:
        raise ValueError(f'{name}: expected a finite number')
    if value < 0 or (not zero and value == 0) or (integer and not isinstance(value, int)):
        raise ValueError(f'{name}: invalid limit')
    return value


def strings(value, name, empty=True):
    if not isinstance(value, list) or (not empty and not value) or not all(isinstance(x, str) and x for x in value):
        raise ValueError(f'{name}: expected a string array')
    if len(set(value)) != len(value):
        raise ValueError(f'{name}: duplicate values')
    return value


def budget(value):
    if not isinstance(value, dict) or set(value) != LIMITS:
        raise ValueError('Budget requires calls, tokens, seconds and usd (null means no money cap)')
    for key in LIMITS:
        if key == 'usd' and value[key] is None:
            continue
        number(value[key], key, zero=key == 'usd', integer=key in {'calls', 'tokens'})


def validate(root, config, contract):
    if not isinstance(config, dict) or not isinstance(contract, dict):
        raise ValueError('Config and contract must be objects')
    if any(type(value.get('schema_version')) is not int or value['schema_version'] != 1 for value in (config, contract)):
        raise ValueError('Expected workflow schema_version=1')
    if not isinstance(contract.get('run_id'), str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', contract['run_id']):
        raise ValueError('Invalid run_id')
    providers, tiers, roles = config['providers'], config['tiers'], config['roles']
    if not isinstance(providers, dict) or not providers or not isinstance(tiers, dict) or not tiers:
        raise ValueError('Providers and tiers must be nonempty objects')
    for spec in providers.values():
        if not isinstance(spec, dict) or spec.get('kind') not in ADAPTERS:
            raise ValueError('Unknown provider kind')
        strings(spec.get('models'), 'provider models', empty=False)
        if spec['kind'] == 'cli':
            argv = spec.get('argv')
            if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and '\x00' not in a for a in argv):
                raise ValueError('CLI argv must be an argument array')
            if not Path(spec['argv'][0]).is_absolute():
                raise ValueError('CLI executable must be an explicit absolute path')
            strings(spec.get('env_allowlist', []), 'env_allowlist')
            if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', s) for s in spec.get('env_allowlist', [])):
                raise ValueError('Invalid environment variable name')
    for tier in tiers.values():
        if not isinstance(tier, dict):
            raise ValueError('Tier must be an object')
        provider = providers.get(tier.get('provider'))
        if provider is None or tier.get('model') not in provider['models']:
            raise ValueError('Unknown provider/model; operator must register exact supported model IDs')
        for key in ('max_input_tokens', 'max_output_tokens'):
            number(tier.get(key), key, integer=True)
        number(tier.get('timeout_seconds'), 'timeout')
        if tier.get('effort') is not None and not isinstance(tier['effort'], str):
            raise ValueError('effort must be null or a supported provider string')
        if not isinstance(tier.get('reliable_usage'), bool):
            raise ValueError('reliable_usage must be explicit')
        prices = tier.get('price_per_million')
        if prices is not None:
            if not isinstance(prices, dict) or set(prices) != {'input', 'output'}:
                raise ValueError('Price requires input and output rates or null')
            for rate in prices.values():
                number(rate, 'price', zero=True)
    if not isinstance(roles, dict) or set(roles) != {'architect', 'implementer', 'reviewer'} or not all(v in tiers for v in roles.values()):
        raise ValueError('All three roles must map to registered tiers')
    policy = config['policy']
    if not isinstance(policy, dict):
        raise ValueError('Policy must be an object')
    if policy.get('strong_tier') not in tiers or policy.get('fast_tier') not in tiers:
        raise ValueError('Register fast and strong tier mappings')
    for key in ('same_tier_repairs', 'strong_upgrades'):
        number(policy.get(key), key, zero=True, integer=True)
    for key in ('final_check_reserve_seconds', 'check_timeout_seconds'):
        number(policy.get(key), key)
    if not isinstance(config.get('strict_money'), bool):
        raise ValueError('strict_money must be explicit')
    budget(config['run_budget'])
    if config['strict_money'] and config['run_budget']['usd'] is None:
        raise ValueError('Strict money requires a finite run USD cap')
    approved = strings(config.get('allow_rule_changes', []), 'allow_rule_changes')
    for name in approved + strings(config.get('control_files', []), 'control_files'):
        relative(root, name)
    categories = config.get('check_failure_categories', {})
    if not isinstance(categories, dict):
        raise ValueError('check_failure_categories must be an object')
    for label, mapping in categories.items():
        if not isinstance(label, str) or not isinstance(mapping, dict):
            raise ValueError('Invalid check failure mapping')
        if any(not isinstance(code, str) or not code.isdigit() or int(code) == 0 or category not in CATEGORIES
               for code, category in mapping.items()):
            raise ValueError('Map positive exit codes to explicit failure categories')
    tasks = contract.get('tasks')
    if not isinstance(tasks, list) or not tasks:
        raise ValueError('Tasks must be nonempty')
    ids = set()
    for task in tasks:
        if not isinstance(task, dict):
            raise ValueError('Task must be an object')
        ident = task.get('id', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', ident) or ident in ids:
            raise ValueError('Task IDs must be unique safe identifiers')
        ids.add(ident)
        if not isinstance(task.get('requirements'), str) or not task['requirements'].strip():
            raise ValueError('Task requires requirements')
        if task.get('risk') not in {'low', 'standard', 'high'}:
            raise ValueError('Task requires low, standard or high risk')
        if task.get('kind') not in {'documentation', 'mechanical', 'code'}:
            raise ValueError('Task requires documentation, mechanical or code kind')
        for field in ('depends_on', 'interfaces', 'acceptance'):
            strings(task.get(field), field, empty=field != 'acceptance')
        if not set(task['acceptance']) <= STAGES:
            raise ValueError('Acceptance must name deterministic harness stages')
        strings(task.get('allowed_files'), 'allowed_files', empty=False)
        strings(task.get('context_files', []), 'context_files')
        for name in task['allowed_files'] + task.get('context_files', []):
            relative(root, name)
        budget(task['budget'])
        if config['strict_money'] and task['budget']['usd'] is None:
            raise ValueError('Strict money requires a finite task USD cap')
        if 'simulation' in task:
            sim = task['simulation']
            if (not isinstance(sim, dict) or not isinstance(sim.get('attempts', [{}]), list) or not sim.get('attempts', [{}])
                    or not all(isinstance(item, dict) for item in sim.get('attempts', [{}]))):
                raise ValueError('Simulation requires a nonempty attempts array')
    lookup = {t['id']: t for t in tasks}
    ordered, visiting, visited = [], set(), set()

    def visit(ident):
        if ident not in lookup:
            raise ValueError('Missing dependency reference')
        if ident in visiting:
            raise ValueError('Cyclic task dependencies')
        if ident in visited:
            return
        visiting.add(ident)
        for dep in lookup[ident]['depends_on']:
            visit(dep)
        visiting.remove(ident)
        visited.add(ident)
        ordered.append(lookup[ident])
    for ident in lookup:
        visit(ident)
    return ordered


def revision(root):
    result = execute(['git', 'rev-parse', 'HEAD'], root, 5)
    return result['stdout'].strip() if result['kind'] == 'completed' and result['exit_code'] == 0 else None


def risk(task):
    # Explicit high risk is never downgraded. Sensitive paths/interfaces raise the minimum.
    sensitive = r'auth|secur|credential|payment|migration|deploy|production|权限|密钥|支付|迁移|生产|安全'
    if task['risk'] == 'high' or re.search(sensitive, ' '.join(
            [task['requirements'], *task['allowed_files'], *task['interfaces']]), re.I):
        return 'high'
    return task['risk']


@contextmanager
def lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'lock'
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise ValueError('Run is locked; confirm the former process stopped before removing its lock') from None
    try:
        os.write(fd, str(os.getpid()).encode('ascii'))
        os.close(fd)
        yield
    finally:
        path.unlink(missing_ok=True)


class Workflow:
    def __init__(self, root, config, contract, allow_real=False, cancel=lambda: False):
        self.root = Path(root).absolute()
        if self.root.is_symlink() or any(p.is_symlink() for p in self.root.parents):
            raise ValueError('Working root cannot contain symlinks')
        self.root = self.root.resolve()
        if not self.root.is_dir():
            raise ValueError('Working root must exist')
        self.config, self.contract = copy.deepcopy(config), copy.deepcopy(contract)
        self.tasks = validate(self.root, self.config, self.contract)
        self.allow_real, self.cancel_signal = allow_real, cancel
        self.directory = self.root / '.local' / 'workflow' / contract['run_id']
        if any(p.is_symlink() for p in (self.directory, *self.directory.parents)):
            raise ValueError('State path contains symlink')
        self.signature = digest(canonical({'config': config, 'contract': contract}))
        self.checker = self.load_harness()
        self.initial_acceptance_signature = self.acceptance_signature()
        self.state = None

    def load_harness(self):
        # Runtime code is operator-owned. Model patches may never modify harness/workflow controls.
        path = relative(self.root, 'harness/run.py')
        relative(self.root, 'harness/config.json')
        spec = importlib.util.spec_from_file_location('workflow_harness', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        harness = module.load_config(self.root)
        if not harness['projects']:
            raise ValueError('NOT_CONFIGURED: workflow requires real application checks')
        na = self.config['not_applicable']
        if not isinstance(na, dict) or set(na) != {p['name'] for p in harness['projects']}:
            raise ValueError('not_applicable requires each configured project')
        required = set()
        for project in harness['projects']:
            stages = set(project['required'])
            skipped = na[project['name']]
            if not isinstance(skipped, dict) or stages & set(skipped) or stages | set(skipped) != STAGES:
                raise ValueError('Each check must be required or explicitly not applicable')
            if any(not isinstance(reason, str) or not reason.strip() for reason in skipped.values()):
                raise ValueError('Not applicable checks require reasons')
            if not stages <= set(project['checks']):
                raise ValueError('NOT_CONFIGURED: missing required check')
            required |= stages
        for task in self.tasks:
            if not set(task['acceptance']) <= required:
                raise ValueError('Task acceptance check is not required by the harness')
        labels = {f"{p['name']}/{stage}" for p in harness['projects'] for stage in p['required']}
        if not set(self.config.get('check_failure_categories', {})) <= labels:
            raise ValueError('Unknown check failure category label')
        self.check_sources, self.check_executables = set(), []
        for project in harness['projects']:
            cwd = (self.root / project['path']).resolve()
            for stage in project['required']:
                for index, command in enumerate(project['checks'][stage]['commands']):
                    program = sys.executable if command[0] == '{python}' else command[0]
                    executable = resolve_executable(program, cwd)
                    identity = None
                    candidates = [cwd / arg for arg in command[1:]]
                    if executable is not None:
                        candidates.append(executable)
                        identity = {key: (path.relative_to(self.root).as_posix() if path.is_relative_to(self.root)
                                          else str(path))
                                    for key, path in [('launch', executable), ('target', executable.resolve())]}
                    self.check_executables.append({'project': project['name'], 'stage': stage,
                                                   'command': index, 'executable': identity})
                    for candidate in candidates:
                        candidate = candidate.resolve()
                        if candidate.is_file() and candidate.is_relative_to(self.root):
                            self.check_sources.add(candidate.relative_to(self.root).as_posix())
        return harness

    def acceptance_signature(self):
        harness = self.load_harness()
        return digest(canonical({'workflow': self.config, 'contract': self.contract,
                                 'harness': harness, 'executables': self.check_executables,
                                 'runner': digest((self.root / 'harness/run.py').read_bytes())}))

    def save(self):
        self.state['elapsed_seconds'] = self.state.get('ended_at', time.time()) - self.state['started_at']
        atomic_json(self.directory / 'state.json', self.state)

    def transition(self, task, status, reason=None):
        current = self.state['tasks'][task['id']]
        current['status'] = status
        if reason:
            current['reason'] = reason
        else:
            current.pop('reason', None)
        current.setdefault('history', []).append({'status': status, 'at': time.time(), 'reason': reason})
        self.save()

    def cancelled(self):
        return self.cancel_signal() or (self.directory / 'cancel').exists()

    def charge(self, entry, field):
        if field == 'calls':
            return 1
        if field == 'tokens':
            usage = entry.get('usage')
            return sum(usage.values()) if usage is not None else entry['token_upper']
        return entry.get('cost_usd') if entry.get('cost_usd') is not None else entry['cost_upper_usd']

    def totals(self, entries):
        result = {field: sum(self.charge(e, field) or 0 for e in entries) for field in ('calls', 'tokens', 'usd')}
        result['usage'] = {'input_tokens': sum(e['usage']['input_tokens'] for e in entries),
                           'output_tokens': sum(e['usage']['output_tokens'] for e in entries)} if all(
                               e.get('usage') is not None for e in entries) else 'unknown'
        result['estimated_cost_usd'] = sum(e['cost_usd'] for e in entries) if all(
            e.get('cost_usd') is not None for e in entries) else 'unknown'
        result['reserved_or_estimated_usd'] = result.pop('usd') if all(
            self.charge(e, 'usd') is not None for e in entries) else 'unknown'
        return result

    def upper(self, tier):
        prices = tier['price_per_million']
        cost = ((tier['max_input_tokens'] * prices['input'] + tier['max_output_tokens'] * prices['output']) / 1e6
                if prices is not None else None)
        return {'calls': 1, 'tokens': tier['max_input_tokens'] + tier['max_output_tokens'], 'usd': cost}

    def seconds_left(self, task):
        now = time.time()
        current = self.state['tasks'][task['id']]
        return min(self.config['run_budget']['seconds'] - (now - self.state['started_at']),
                   task['budget']['seconds'] - (now - current['started_at']))

    def review_reserve(self, task, role):
        reviewer = self.config['tiers'][self.config['roles']['reviewer']]
        unfinished = sum(t['status'] not in TERMINAL for t in self.state['tasks'].values())
        count = max(0, unfinished - int(role == 'reviewer'))
        return reviewer, count

    def reserve(self, task, tier, role):
        upper = self.upper(tier)
        provider = self.config['providers'][tier['provider']]
        if provider['kind'] == 'cli':
            if not self.allow_real:
                raise AdapterError('real_calls_disabled')
            if self.config['strict_money'] and (not tier['reliable_usage'] or upper['usd'] is None):
                raise AdapterError('unmetered_strict_budget')
        reviewer, count = self.review_reserve(task, role)
        reviewer_upper = self.upper(reviewer)
        for scope, limits, reviews in [('run', self.config['run_budget'], count),
                                       ('task', task['budget'], int(role != 'reviewer'))]:
            entries = [e for e in self.state['ledger'] if scope == 'run' or e['task_id'] == task['id']]
            for field in ('calls', 'tokens', 'usd'):
                if limits[field] is None:
                    continue
                used = [self.charge(e, field) for e in entries]
                extra = reviewer_upper[field] * reviews if reviews and reviewer_upper[field] is not None else 0
                unknown = upper[field] is None or any(v is None for v in used) or (reviews and reviewer_upper[field] is None)
                if unknown:
                    if field == 'usd' and not self.config['strict_money']:
                        continue  # An explicit non-strict USD cap is advisory when metering is unknown.
                    raise AdapterError('unknown_budget')
                if sum(used) + upper[field] + extra > limits[field] + 1e-12:
                    raise AdapterError('budget_exhausted')
        check_reserve = self.config['policy']['final_check_reserve_seconds'] if role != 'reviewer' else 0
        run_left = self.config['run_budget']['seconds'] - (time.time() - self.state['started_at'])
        task_left = task['budget']['seconds'] - (time.time() - self.state['tasks'][task['id']]['started_at'])
        available = min(run_left - count * reviewer['timeout_seconds'],
                        task_left - (reviewer['timeout_seconds'] if role != 'reviewer' else 0)) - check_reserve
        if available <= 0:
            raise AdapterError('deadline')
        return min(tier['timeout_seconds'], available)

    def request(self, task, role, tier_name, attempt, operation):
        tier = self.config['tiers'][tier_name]
        files = {}
        for name in dict.fromkeys(task['allowed_files'] + task.get('context_files', [])):
            path = relative(self.root, name)
            if path.exists():
                if not path.is_file() or path.stat().st_size > tier['max_input_tokens']:
                    raise AdapterError('context_limit')
                data = path.read_bytes()
                files[name] = {'sha256': digest(data), 'text': data.decode('utf-8')}
        current = self.state['tasks'][task['id']]
        remaining = self.seconds_left(task)
        if remaining <= 0:
            raise AdapterError('deadline')
        selected = execute([sys.executable, 'scripts/memory.py', 'brief', '--task', task['requirements'],
                            '--budget', '2000'], self.root, min(10, remaining), cancel=self.cancelled)
        if selected['kind'] != 'completed' or selected['exit_code'] != 0:
            raise AdapterError('cancelled' if selected['kind'] == 'cancelled' else 'dependency')
        evidence = []
        # Include the last verification batch, its real exit codes and bounded logs.
        latest_batch = self.state['checks'][-1]['batch'] if self.state['checks'] else None
        for check in self.state['checks']:
            if check['batch'] == latest_batch:
                item = {k: check[k] for k in ('label', 'kind', 'exit_code', 'log_sha256')}
                item['log_excerpt'] = (self.directory / check['log']).read_text(encoding='utf-8')[-1500:]
                evidence.append(item)
        request = {'protocol_version': 1, 'call_id': operation,
                   'role': role, 'mode': 'read_only' if role != 'implementer' else 'propose_changes',
                   'model': tier['model'], 'effort': tier['effort'],
                   'max_input_tokens': tier['max_input_tokens'], 'max_output_tokens': tier['max_output_tokens'],
                   'task': copy.deepcopy(task), 'risk': current['risk'], 'attempt': attempt, 'files': files,
                   'base_revision': self.state['base_revision'], 'memory_brief': selected['stdout'],
                   'plan': current.get('plan'), 'feedback': current.get('feedback'), 'evidence': evidence,
                   'changes': current.get('change_refs', []), 'interfaces': task['interfaces'],
                   'dependencies': {d: self.state['tasks'][d]['status'] for d in task['depends_on']},
                   'content_hash': content_hash(self.root), 'configuration_hash': self.acceptance_signature(),
                   'acceptance_rules': self.checker, 'not_applicable': self.config['not_applicable']}
        if self.config['providers'][tier['provider']]['kind'] != 'fake':
            request['task'].pop('simulation', None)
        # Bytes conservatively bound ordinary tokenizer input. Bridges must enforce their tokenizer cap too.
        if len(canonical(request)) > tier['max_input_tokens']:
            raise AdapterError('context_limit')
        return request

    def validate_response(self, entry):
        response = entry['response']
        if entry.get('error'):
            raise AdapterError(entry['error'], uncertain=entry['status'] == 'uncertain')
        if entry['usage'] is None and self.config['strict_money']:
            raise AdapterError('unknown_usage')
        error = response.get('error')
        if error:
            category = error.get('category') if isinstance(error, dict) else None
            if category not in CATEGORIES:
                raise AdapterError('protocol')
            raise AdapterError(category)
        role = entry['role']
        if role != 'implementer' and response.get('changes'):
            raise AdapterError('read_only_violation')
        if role == 'architect':
            if not isinstance(response.get('plan'), str) or not response['plan'].strip():
                raise AdapterError('protocol')
            if not isinstance(response.get('ambiguities', []), list):
                raise AdapterError('protocol')
            if response.get('ambiguities'):
                raise AdapterError('ambiguity')
        if role == 'reviewer':
            if response.get('verdict') not in {'approve', 'reject'}:
                raise AdapterError('protocol')
            strings(response.get('approved_rule_changes', []), 'approved_rule_changes')
        return entry

    def invoke(self, task, role, tier_name, attempt=0, binding=''):
        operation = f"{self.contract['run_id']}:{task['id']}:{role}:{attempt}:{binding}"
        existing = next((e for e in self.state['ledger'] if e['id'] == operation), None)
        if existing:
            if existing['status'] in {'pending', 'uncertain'}:
                raise AdapterError('uncertain_call', uncertain=True)
            return self.validate_response(existing)
        if self.cancelled():
            raise AdapterError('cancelled')
        tier = self.config['tiers'][tier_name]
        timeout = self.reserve(task, tier, role)
        request = self.request(task, role, tier_name, attempt, operation)
        # Request preparation consumes the same wall-clock deadline.
        timeout = min(timeout, self.reserve(task, tier, role))
        before = snapshot(self.root)
        provider = self.config['providers'][tier['provider']]
        entry = {'id': operation, 'task_id': task['id'], 'role': role,
                 'tier': tier_name, 'model_config': copy.deepcopy(tier), 'attempt': attempt,
                 'status': 'pending', 'token_upper': self.upper(tier)['tokens'],
                 'cost_upper_usd': self.upper(tier)['usd'], 'cost_usd': None, 'usage': None,
                 'started_at': time.time(), 'timeout_seconds': timeout, 'simulation': provider['kind'] == 'fake'}
        self.state['ledger'].append(entry)
        if role == 'implementer':
            self.state['tasks'][task['id']]['attempts'] += 1
        self.save()  # Durable reservation and idempotency key BEFORE the external boundary.
        try:
            response = ADAPTERS[provider['kind']]().call(request, provider, timeout, self.cancelled)
            if snapshot(self.root) != before:
                raise AdapterError('unauthorized_side_effect', uncertain=True)
            if not isinstance(response, dict) or len(canonical(response)) > 1048576:
                raise AdapterError('protocol', uncertain=True)
            usage = response.get('usage')
            if usage is not None:
                if not isinstance(usage, dict) or set(usage) != {'input_tokens', 'output_tokens'}:
                    raise AdapterError('protocol', uncertain=True)
                for name, maximum in [('input_tokens', tier['max_input_tokens']), ('output_tokens', tier['max_output_tokens'])]:
                    number(usage[name], name, zero=True, integer=True)
                    if usage[name] > maximum:
                        raise AdapterError('usage_exceeds_limit', uncertain=True)
            entry['usage'] = usage
            if usage is not None and tier['price_per_million'] is not None:
                entry['cost_usd'] = (usage['input_tokens'] * tier['price_per_million']['input'] +
                                     usage['output_tokens'] * tier['price_per_million']['output']) / 1e6
            entry['status'], entry['response'] = 'completed', response
            entry['seconds'] = time.time() - entry['started_at']
            self.save()  # Completed responses are reused after interruption, for ALL three roles.
            return self.validate_response(entry)
        except Exception as exc:
            error = exc if isinstance(exc, AdapterError) else AdapterError('protocol', uncertain=True)
            if error.uncertain:
                entry['status'] = 'uncertain'
            elif entry['status'] == 'pending':
                entry['status'] = 'failed'
            entry['error'] = error.category
            entry['error_type'] = type(exc).__name__
            entry['seconds'] = time.time() - entry['started_at']
            self.save()
            raise error

    def control_file(self, name):
        return (name.startswith(('harness/', 'workflow/', '.github/')) or name in {
            'AGENTS.md', 'CLAUDE.md', 'scripts/memory.py'} or name in self.config.get('control_files', []))

    def rule_file(self, name):
        path = Path(name)
        return (name in self.check_sources or 'tests' in path.parts or 'test' in path.parts or path.name.startswith('test_') or
                path.name.endswith(('_test.py', '.test.js', '.spec.ts')) or path.name in {
                    'pyproject.toml', 'package.json', 'Makefile', 'tox.ini', 'setup.cfg'})

    def apply(self, task, entry):
        if entry.get('patch_applied'):
            return
        if 'patch_journal' not in entry:
            changes = entry['response'].get('changes')
            if not isinstance(changes, list):
                raise AdapterError('protocol')
            journal, paths = [], set()
            for change in changes:
                if not isinstance(change, dict) or set(change) != {'path', 'before', 'content'}:
                    raise AdapterError('protocol')
                name = change['path']
                path = relative(self.root, name)
                if name in paths or name not in task['allowed_files'] or self.control_file(name):
                    raise AdapterError('file_scope')
                if self.rule_file(name) and name not in self.config.get('allow_rule_changes', []):
                    raise AdapterError('protected_rule')
                if not isinstance(change['content'], str) or len(change['content'].encode('utf-8')) > 1048576:
                    raise AdapterError('patch_limit')
                expected = change['before']
                if expected is not None and (not isinstance(expected, str) or not re.fullmatch(r'[a-f0-9]{64}', expected)):
                    raise AdapterError('protocol')
                old = path.read_text(encoding='utf-8') if path.is_file() else None
                actual = digest(path.read_bytes()) if path.is_file() else None
                if path.exists() and not path.is_file() or actual != expected:
                    raise AdapterError('patch_conflict')
                after = digest(change['content'].encode('utf-8'))
                diff = ''.join(difflib.unified_diff((old or '').splitlines(keepends=True),
                                                   change['content'].splitlines(keepends=True),
                                                   fromfile=name, tofile=name))
                journal.append(dict(change, after=after, diff=diff, rule_change=self.rule_file(name)))
                paths.add(name)
            entry['patch_journal'] = journal
            self.save()  # Every preimage/diff is durable before the first replacement.
        current = self.state['tasks'][task['id']]
        for change in entry['patch_journal']:
            path = relative(self.root, change['path'])
            actual = digest(path.read_bytes()) if path.is_file() else None
            if actual not in {change['before'], change['after']}:
                raise AdapterError('patch_conflict')
            if actual != change['after']:
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = self.directory / ('patch-' + digest(canonical([entry['id'], change['path']])))
                if temporary.is_symlink():
                    raise AdapterError('file_scope')
                with temporary.open('wb') as stream:
                    stream.write(change['content'].encode('utf-8'))
                    stream.flush()
                    os.fsync(stream.fileno())
                if path.exists():
                    os.chmod(temporary, path.stat().st_mode & 0o777)
                os.replace(temporary, path)
            reference = {key: change[key] for key in ('path', 'before', 'after', 'diff', 'rule_change')}
            reference['call_id'] = entry['id']
            if reference not in current.setdefault('change_refs', []):
                current['change_refs'].append(reference)
        entry['patch_applied'] = True
        self.save()

    def evidence_intact(self):
        return all((self.directory / c['log']).is_file() and
                   digest((self.directory / c['log']).read_bytes()) == c['log_sha256'] for c in self.state['checks'])

    def checks(self, task, final=False):
        before = content_hash(self.root)
        signature = self.acceptance_signature()
        if signature != self.initial_acceptance_signature:
            return 'acceptance_invalidated'
        harness = self.load_harness()
        plan = [('memory', '.', [sys.executable, 'scripts/memory.py', 'check'], 30)]
        for project in harness['projects']:
            for stage in project['required']:
                spec = project['checks'][stage]
                for command in spec['commands']:
                    plan.append((f"{project['name']}/{stage}", project['path'],
                                 [sys.executable if a == '{python}' else a for a in command],
                                 spec.get('timeout_seconds', 300)))
        batch = len(self.state['checks']) + 1
        reviewer, count = self.review_reserve(task, 'check')
        for label, directory, argv, timeout in plan:
            run_left = self.config['run_budget']['seconds'] - (time.time() - self.state['started_at'])
            task_left = task['budget']['seconds'] - (time.time() - self.state['tasks'][task['id']]['started_at'])
            remaining = min(run_left - count * reviewer['timeout_seconds'], task_left - reviewer['timeout_seconds'])
            if not final:
                remaining -= self.config['policy']['final_check_reserve_seconds']
            if remaining <= 0:
                return 'deadline'
            result = execute(argv, (self.root / directory).resolve(),
                             min(timeout, self.config['policy']['check_timeout_seconds'], remaining),
                             cancel=self.cancelled)
            log_text = result.pop('stdout') + '\n' + result.pop('stderr')
            for provider in self.config['providers'].values():
                for name in provider.get('env_allowlist', []):
                    if os.environ.get(name):
                        log_text = log_text.replace(os.environ[name], '[REDACTED]')
            log = log_text.encode('utf-8')
            log_name = f"check-{len(self.state['checks']) + 1}.log"
            (self.directory / log_name).write_bytes(log)
            evidence = dict(result, task_id=task['id'], label=label, argv=argv, cwd=directory, batch=batch,
                            log=log_name, log_sha256=digest(log), content_hash=before,
                            acceptance_signature=signature, final=final)
            self.state['checks'].append(evidence)
            self.save()
            if content_hash(self.root) != before or self.acceptance_signature() != signature:
                return 'checks_modified_content'
            if result['kind'] != 'completed':
                return 'infrastructure' if result['kind'] in {'infrastructure', 'output_limit'} else result['kind']
            if result['exit_code'] != 0:
                return ('dependency' if label == 'memory' else self.config.get('check_failure_categories', {}).get(
                    label, {}).get(str(result['exit_code']), 'infrastructure'))
        if not self.evidence_intact():
            return 'evidence_modified'
        binding = {'content_hash': before, 'configuration_hash': signature}
        if final:
            self.state['final_checks'] = dict(binding, batch=batch)
        else:
            self.state['tasks'][task['id']]['provisional'] = binding
        self.save()
        return None

    def implementation_tier(self, task, attempt):
        if self.state['tasks'][task['id']]['risk'] == 'high' or attempt > 1 + self.config['policy']['same_tier_repairs']:
            return self.config['policy']['strong_tier']
        if task['kind'] in {'documentation', 'mechanical'} and risk(task) == 'low':
            return self.config['policy']['fast_tier']
        return self.config['roles']['implementer']

    def stop(self, task, category):
        failures = {'protocol', 'file_scope', 'protected_rule', 'read_only_violation', 'review_rejected',
                    'invalid_change', 'invalid_review', 'unauthorized_side_effect', 'checks_modified_content', 'evidence_modified'}
        status = 'cancelled' if category == 'cancelled' else 'failed' if category in failures else 'blocked'
        self.transition(task, status, category)

    def implement(self, task):
        current = self.state['tasks'][task['id']]
        current.setdefault('started_at', time.time())
        if current['status'] in TERMINAL or current.get('provisional'):
            return
        try:
            if current['risk'] != 'low' and not current.get('plan'):
                self.transition(task, 'running')
                tier = (self.config['policy']['strong_tier'] if current['risk'] == 'high'
                        else self.config['roles']['architect'])
                entry = self.invoke(task, 'architect', tier)
                current['plan'] = entry['response']['plan']
                self.save()
            max_attempts = 1 + self.config['policy']['same_tier_repairs'] + self.config['policy']['strong_upgrades']
            while current.get('next_attempt', 1) <= max_attempts:
                attempt = current.get('next_attempt', 1)
                tier = self.implementation_tier(task, attempt)
                phase = 'running' if attempt == 1 else ('repairing' if attempt <=
                        1 + self.config['policy']['same_tier_repairs'] else 'escalating')
                self.transition(task, phase)
                try:
                    entry = self.invoke(task, 'implementer', tier, attempt)
                    self.apply(task, entry)
                    self.transition(task, 'awaiting_verification')
                    error = self.checks(task)
                except AdapterError as exc:
                    if exc.category != 'code' or exc.uncertain:
                        raise
                    error = 'code'
                current['feedback'] = error
                if error is None:
                    self.save()
                    return
                if error != 'code':
                    raise AdapterError(error)
                current['next_attempt'] = attempt + 1
                self.save()
            raise AdapterError('retry_exhausted')
        except (AdapterError, ValueError, OSError, TypeError, KeyError) as exc:
            self.stop(task, exc.category if isinstance(exc, AdapterError) else 'invalid_change')

    def binding(self):
        return {'content_hash': content_hash(self.root), 'configuration_hash': self.acceptance_signature()}

    def start(self):
        path = self.directory / 'state.json'
        if path.exists():
            self.state = json.loads(path.read_text(encoding='utf-8'))
            if self.state['input_signature'] != self.signature:
                raise ValueError('Acceptance invalidated: run ID has a different config/contract; use a new run ID')
            if self.state['acceptance_configuration'] != self.initial_acceptance_signature:
                raise ValueError('Acceptance invalidated: harness configuration changed; use a new run ID')
            for entry in self.state['ledger']:
                if entry['status'] == 'pending':
                    entry['status'], entry['error'] = 'uncertain', 'interrupted_call'
                    entry['seconds'] = 'unknown'
                if entry['status'] == 'uncertain':
                    task = next(t for t in self.tasks if t['id'] == entry['task_id'])
                    self.transition(task, 'blocked', 'uncertain_call')
            binding = self.binding()
            for task in self.tasks:
                current = self.state['tasks'][task['id']]
                if current['status'] == 'success' and (current.get('acceptance') != binding or not self.evidence_intact()):
                    self.transition(task, 'awaiting_verification', 'acceptance_invalidated')
        else:
            baseline = content_hash(self.root)
            base_revision = revision(self.root)
            expected = self.contract.get('base_revision')
            if expected is not None and expected != base_revision:
                raise ValueError('Task contract base_revision does not match the working checkout')
            self.state = {'schema_version': 1, 'run_id': self.contract['run_id'],
                          'input_signature': self.signature, 'contract': self.contract,
                          'acceptance_configuration': self.initial_acceptance_signature,
                          'configuration': self.config, 'base_revision': base_revision,
                          'base_content_hash': baseline, 'started_at': time.time(),
                          'tasks': {t['id']: {'status': 'pending', 'risk': risk(t), 'attempts': 0,
                                   'budget': t['budget'], 'history': []} for t in self.tasks},
                          'ledger': [], 'checks': [], 'status': 'pending'}
            benchmark = {'case': self.contract.get('benchmark_case', self.contract['run_id']),
                'tasks': [{k: t[k] for k in ('id', 'requirements', 'risk', 'kind', 'depends_on', 'allowed_files', 'interfaces', 'acceptance', 'budget')} for t in self.tasks],
                'source': {name: value for name, value in snapshot(self.root).items()
                           if not name.startswith('workflow/') and name not in self.config.get('control_files', [])},
                'checks': self.checker, 'not_applicable': self.config['not_applicable'],
                'failure_categories': self.config.get('check_failure_categories', {}),
                'run_budget': self.config['run_budget'], 'retry_limits': {k: self.config['policy'][k]
                for k in ('same_tier_repairs', 'strong_upgrades', 'final_check_reserve_seconds', 'check_timeout_seconds')}}
            self.state['benchmark_key'] = digest(canonical(benchmark))
        self.save()

    def finish(self):
        try:
            binding = self.binding()
        except (OSError, ValueError, TypeError, KeyError):
            binding = {'content_hash': 'unknown', 'configuration_hash': 'unknown'}
        for task in self.tasks:
            current = self.state['tasks'][task['id']]
            if current['status'] == 'success' and (current.get('acceptance') != binding or not self.evidence_intact()):
                self.stop(task, 'acceptance_invalidated')
        self.state['final_revision'] = revision(self.root)
        self.state['final_content_hash'] = binding['content_hash']
        self.state['acceptance_configuration_hash'] = binding['configuration_hash']
        self.state['required_checks'] = {p['name']: p['required'] for p in self.checker['projects']}
        statuses = [t['status'] for t in self.state['tasks'].values()]
        self.state['status'] = ('success' if all(s == 'success' for s in statuses) else
                                'cancelled' if 'cancelled' in statuses else 'failed' if 'failed' in statuses else 'blocked')
        self.state['totals'] = self.totals(self.state['ledger'])
        self.state['cost_note'] = 'Configured-rate estimates, not a provider invoice. Unknown usage/cost is never zero.'
        self.state['simulation'] = all(e['simulation'] for e in self.state['ledger'])
        self.state['not_applicable'] = self.config['not_applicable']
        self.state.setdefault('ended_at', time.time())
        for ident, current in self.state['tasks'].items():
            current['totals'] = self.totals([e for e in self.state['ledger'] if e['task_id'] == ident])
        self.save()
        report = {k: v for k, v in self.state.items() if k not in {'configuration'}}
        report['contract'] = copy.deepcopy(self.contract)
        for task in report['contract']['tasks']:
            task.pop('simulation', None)
        report['ledger'] = [{k: v for k, v in entry.items() if k not in {'response', 'patch_journal'}} for entry in self.state['ledger']]
        atomic_json(self.directory / 'report.json', report)
        summary = [f"{'SIMULATION / 离线模拟' if self.state['simulation'] else 'REAL CLI / 真实 CLI'}: {self.state['status']}",
                   f"Base: {self.state['base_revision']} / {self.state['base_content_hash']}",
                   f"Final: {self.state['final_revision']} / {self.state['final_content_hash']}",
                   f"Totals: {json.dumps(self.state['totals'], ensure_ascii=False)}",
                   f"Elapsed seconds: {self.state['elapsed_seconds']:.3f}", self.state['cost_note']]
        summary += [f"{ident}: {data['status']} ({data.get('reason', '')}); attempts={data['attempts']}"
                    for ident, data in self.state['tasks'].items()]
        summary += [f"{e['role']} tier={e['tier']} provider={e['model_config']['provider']} model={e['model_config']['model']} "
                    f"effort={e['model_config']['effort']} usage={e.get('usage') or 'unknown'} "
                    f"estimated_usd={e['cost_usd'] if e['cost_usd'] is not None else 'unknown'} seconds={e.get('seconds', 'unknown')}"
                    for e in self.state['ledger']]
        summary += [f"Required checks: {self.state['required_checks']}; acceptance config: {binding['configuration_hash']}"]
        summary += [f"{c['label']}: {c['kind']} exit={c['exit_code']} log={c['log']} sha256={c['log_sha256']}" for c in self.state['checks']]
        summary += [f"Not applicable: {json.dumps(self.config['not_applicable'], ensure_ascii=False)}"]
        (self.directory / 'summary.txt').write_text('\n'.join(summary) + '\n', encoding='utf-8')
        return report

    def run(self):
        # One writer per working tree, including distinct run IDs. A worktree is not a sandbox.
        with lock(self.directory.parent):
            self.start()
            if any(t['status'] not in TERMINAL for t in self.state['tasks'].values()):
                self.state.pop('ended_at', None)
            self.state['status'] = 'running'
            for task in self.tasks:
                current = self.state['tasks'][task['id']]
                if current['status'] in TERMINAL:
                    continue
                if self.cancelled():
                    self.stop(task, 'cancelled')
                    continue
                if any(self.state['tasks'][d]['status'] not in {'success', 'awaiting_verification'} for d in task['depends_on']):
                    self.stop(task, 'dependency_failed')
                    continue
                self.implement(task)
            candidates = [t for t in self.tasks if self.state['tasks'][t['id']]['status'] == 'awaiting_verification']
            if candidates:
                try:
                    error = self.checks(candidates[-1], final=True)
                    binding = self.binding()
                except (ValueError, OSError, TypeError, KeyError):
                    error, binding = 'acceptance_invalidated', None
                for task in candidates:
                    try:
                        if error:
                            raise AdapterError(error)
                        if any(self.state['tasks'][d]['status'] != 'success' for d in task['depends_on']):
                            raise AdapterError('dependency_failed')
                        entry = self.invoke(task, 'reviewer', self.config['roles']['reviewer'], binding=digest(canonical(binding)))
                        response = entry['response']
                        rules = {r['path'] for r in self.state['tasks'][task['id']].get('change_refs', []) if r['rule_change']}
                        if response['verdict'] != 'approve' or not rules <= set(response.get('approved_rule_changes', [])):
                            raise AdapterError('review_rejected')
                        if self.seconds_left(task) <= 0:
                            raise AdapterError('deadline')
                        if self.binding() != binding or not self.evidence_intact():
                            raise AdapterError('acceptance_invalidated')
                        self.state['tasks'][task['id']]['acceptance'] = binding
                        self.transition(task, 'success')
                    except (AdapterError, ValueError, OSError, TypeError, KeyError) as exc:
                        self.stop(task, exc.category if isinstance(exc, AdapterError) else 'invalid_review')
            for task in self.tasks:
                if any(self.state['tasks'][d]['status'] != 'success' for d in task['depends_on']):
                    self.stop(task, 'dependency_failed')
            return self.finish()

    def verify(self):
        """Check a saved acceptance against current content/config and evidence, without model calls."""
        self.state = json.loads((self.directory / 'state.json').read_text(encoding='utf-8'))
        if self.state['input_signature'] != self.signature or self.state['status'] != 'success':
            return False
        binding = self.binding()
        return (self.evidence_intact() and all(t.get('acceptance') == binding for t in self.state['tasks'].values())
                and all(self.state.get('final_checks', {}).get(k) == v for k, v in binding.items()))
