"""Deterministic simulation and an opt-in JSON agent CLI protocol, version 1."""
import copy
import json
import os
import tempfile

from .safety import clean_env, execute

CATEGORIES = {'infrastructure', 'dependency', 'code', 'ambiguity'}


class AdapterError(Exception):
    def __init__(self, category, uncertain=False):
        super().__init__(category)
        self.category, self.uncertain = category, uncertain


class FakeAdapter:
    """Only this adapter interprets simulation fixtures. No external requests."""
    def call(self, request, provider, timeout, cancel):
        if cancel():
            raise AdapterError('cancelled')
        task, role = request['task'], request['role']
        simulation = task.get('simulation', {})
        if role == 'architect':
            result = {'plan': 'SIMULATION: implement allowed files, run independent checks.', 'ambiguities': []}
        elif role == 'reviewer':
            result = {'verdict': simulation.get('verdict', 'approve'),
                      'approved_rule_changes': simulation.get('approved_rule_changes', [])}
        else:
            attempts = simulation.get('attempts', [{'changes': []}])
            result = copy.deepcopy(attempts[min(request['attempt'] - 1, len(attempts) - 1)])
            for change in result.get('changes', []):
                if change.get('before') == '$current':
                    change['before'] = request['files'].get(change['path'], {}).get('sha256')
        result.setdefault('usage', {'input_tokens': 12, 'output_tokens': 8})
        result['simulation'] = True
        return result


class CliAdapter:
    """Execute an installed, operator-configured bridge; stdin/stdout are one JSON object."""
    def call(self, request, provider, timeout, cancel):
        argv = provider['argv']
        # A disposable cwd supplies only the explicit request; no repository cwd or inherited secrets.
        with tempfile.TemporaryDirectory(prefix='agent-cli-') as cwd:
            result = execute(argv, cwd, timeout, request, cancel,
                             clean_env(provider.get('env_allowlist', [])))
        if result['kind'] != 'completed':
            raise AdapterError(result['kind'], uncertain=result['kind'] != 'infrastructure')
        if result['exit_code'] != 0:
            # Never persist raw CLI stderr, which can contain credentials. Billing outcome is unknown.
            raise AdapterError('infrastructure', uncertain=True)
        try:
            response = json.loads(result['stdout'])
            if (not isinstance(response, dict) or type(response.get('protocol_version')) is not int
                    or response.get('protocol_version') != 1):
                raise ValueError('Invalid response protocol')
            def contains(value, secret):
                if isinstance(value, str):
                    return secret in value
                if isinstance(value, list):
                    return any(contains(item, secret) for item in value)
                if isinstance(value, dict):
                    return any(contains(key, secret) or contains(item, secret) for key, item in value.items())
                return False
            for name in provider.get('env_allowlist', []):
                secret = os.environ.get(name)
                if secret and contains(response, secret):
                    raise ValueError('Response contains an injected environment value')
            return response
        except (ValueError, TypeError):
            raise AdapterError('protocol', uncertain=True) from None


ADAPTERS = {'fake': FakeAdapter, 'cli': CliAdapter}
