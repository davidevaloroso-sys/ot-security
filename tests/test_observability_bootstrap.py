from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import pytest
from test_release import module


@pytest.fixture
def helper(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    return module('prepare_observability')


def existing_auth():
    return {'orgID': 'org', 'description': 'ot-security-bootstrap/grafana-influxdb',
            'status': 'active', 'token': 'existing-token',
            'permissions': [{'action': 'read', 'resource': {'type': 'buckets', 'id': 'bucket', 'orgID': 'org'}}]}


def test_existing_secrets_require_no_database_or_pod_access(helper, monkeypatch):
    resources = {name: {key: 'preserved' for key in keys} for name, keys in helper.REQUIRED.items()}
    monkeypatch.setattr(helper, 'read_secret', resources.get)
    monkeypatch.setattr(helper, 'node_auth', lambda: pytest.fail('Existing authentication must not change'))
    monkeypatch.setattr(helper, 'forward', lambda: pytest.fail('No forwarding needed'))
    helper.prepare(True)


def test_invalid_existing_secret_is_not_replaced(helper, monkeypatch):
    monkeypatch.setattr(helper, 'read_secret', lambda name: {'INFLUXDB_READ_TOKEN': ''})
    with pytest.raises(helper.PreparationError, match='missing/empty'):
        helper.prepare(True)


@pytest.mark.parametrize('apply', [False, True])
def test_preparation_preserves_original_and_only_creates_missing(helper, monkeypatch, apply):
    original = {'INFLUXDB_ADMIN_TOKEN': 'admin-test', 'INFLUXDB_ORG': 'lab', 'INFLUXDB_BUCKET': 'ot'}
    resources = {'observability-secrets': original.copy(),
                 'grafana-influxdb': {'INFLUXDB_READ_TOKEN': 'keep-read'}}
    monkeypatch.setattr(helper, 'read_secret', resources.get)
    monkeypatch.setattr(helper, 'node_auth', lambda: {'NODE_RED_CREDENTIAL_SECRET': 'old-key'})
    monkeypatch.setattr(helper, 'forward', nullcontext)
    monkeypatch.setattr(helper, 'bucket_identity', lambda _: ('org', 'bucket'))
    calls = []
    def issue(*args):
        calls.append(args)
        return 'scoped-write'
    monkeypatch.setattr(helper, 'scoped_token', issue)
    monkeypatch.setattr(helper, 'create_secret', lambda name, data: resources.setdefault(name, data))
    helper.prepare(apply)
    assert resources['observability-secrets'] == original
    assert resources['grafana-influxdb']['INFLUXDB_READ_TOKEN'] == 'keep-read'
    assert bool(calls) == apply
    if apply:
        assert calls == [('admin-test', 'org', 'bucket', 'nodered-auth', 'write')]
        assert resources['nodered-auth'] == {'NODE_RED_CREDENTIAL_SECRET': 'old-key', 'INFLUXDB_WRITE_TOKEN': 'scoped-write'}
    else:
        assert 'nodered-auth' not in resources


def test_unknown_node_encryption_stops_before_database_mutation(helper, monkeypatch):
    monkeypatch.setattr(helper, 'read_secret', lambda name:
                        {'INFLUXDB_ADMIN_TOKEN': 'x', 'INFLUXDB_ORG': 'x', 'INFLUXDB_BUCKET': 'x'}
                        if name == 'observability-secrets' else None)
    def node():
        raise helper.PreparationError('Needs review')
    monkeypatch.setattr(helper, 'node_auth', node)
    monkeypatch.setattr(helper, 'forward', lambda: pytest.fail('Must fail before database access'))
    with pytest.raises(helper.PreparationError, match='Needs review'):
        helper.prepare(True)


def test_existing_authorization_recovers_partial_create_without_rotation(helper, monkeypatch):
    calls = []
    def api(*args):
        calls.append(args)
        return {'authorizations': [existing_auth()]}
    monkeypatch.setattr(helper, 'api', api)
    assert helper.scoped_token('admin', 'org', 'bucket', 'grafana-influxdb', 'read') == 'existing-token'
    assert len(calls) == 1 and len(calls[0]) == 3


@pytest.mark.parametrize('damage', ['scope', 'org', 'status', 'token', 'duplicate', 'extra-permission'])
def test_incompatible_authorization_is_never_replaced(helper, monkeypatch, damage):
    auth = existing_auth()
    if damage == 'scope':
        auth['permissions'][0]['resource']['id'] = 'other-bucket'
    elif damage == 'org':
        auth['orgID'] = 'other-org'
    elif damage == 'status':
        auth['status'] = 'inactive'
    elif damage == 'token':
        del auth['token']
    elif damage == 'extra-permission':
        auth['permissions'].append({'action': 'write'})
    def api(*args):
        assert len(args) == 3, 'Must not create another token'
        return {'authorizations': [auth, auth] if damage == 'duplicate' else [auth]}
    monkeypatch.setattr(helper, 'api', api)
    with pytest.raises(helper.PreparationError):
        helper.scoped_token('admin', 'org', 'bucket', 'grafana-influxdb', 'read')


@pytest.mark.parametrize('action', ['read', 'write'])
def test_new_authorization_is_bucket_scoped(helper, monkeypatch, action):
    calls = []
    def api(*args):
        calls.append(args)
        return {'authorizations': []} if len(args) == 3 else {'token': 'scoped'}
    monkeypatch.setattr(helper, 'api', api)
    assert helper.scoped_token('admin', 'org', 'bucket', 'role', action) == 'scoped'
    assert calls[1][3]['permissions'] == [
        {'action': action, 'resource': {'type': 'buckets', 'id': 'bucket', 'orgID': 'org'}}]


def test_empty_database_is_never_initialized(helper, monkeypatch):
    monkeypatch.setattr(helper, 'api', lambda *args: {'allowed': True})
    with pytest.raises(helper.PreparationError, match='no setup/reset'):
        helper.bucket_identity({'INFLUXDB_ADMIN_TOKEN': 'x'})


def test_secret_creation_uses_stdin_and_does_not_print_values(helper, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(helper, 'kubectl', lambda *args, **kw: calls.append((args, kw)))
    helper.create_secret('nodered-auth', {'key': 'private-test'})
    assert calls[0][0] == ('create', '-f', '-')
    assert json.loads(calls[0][1]['data'])['stringData']['key'] == 'private-test'
    assert 'private-test' not in capsys.readouterr().out


def test_failed_exec_hides_raw_output(helper, monkeypatch):
    monkeypatch.setattr(helper.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, 'secret-output', 'secret-error'))
    with pytest.raises(helper.PreparationError) as error:
        helper.kubectl('exec', 'deployment/nodered')
    assert 'secret-output' not in str(error.value) and 'secret-error' not in str(error.value)
