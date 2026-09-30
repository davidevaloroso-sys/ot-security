import base64
import subprocess
import pytest
from test_release import module


def audit(username='audit', password='existing-test-password'):
    return {'data': {k: base64.b64encode(v.encode()).decode() for k, v in
                     [('username', username), ('password', password)]}}


def test_accounts_preserve_audit_and_isolate_roles():
    helper = module('prepare_mqtt_tls')
    users = helper.accounts(audit())
    assert users['mqtt-credentials'] == {'username': 'audit', 'password': 'existing-test-password'}
    assert len({u['username'] for u in users.values()}) == 4
    assert len({u['password'] for u in users.values()}) == 4
    permissions = helper.acl(users)
    assert 'user audit\ntopic read lab/#' in permissions
    assert 'topic write lab/raspi1/temperature' in permissions
    assert 'topic write lab/raspi1/anomaly' in permissions
    nodered = permissions.split('user ot-nodered-tls\n')[1]
    assert 'write' not in nodered and nodered.count('topic read') == 3
    simulator = permissions.split('user ot-simulator-tls\n')[1].split('user ')[0]
    assert 'read' not in simulator and 'anomaly' not in simulator


@pytest.mark.parametrize(('username', 'password'), [
    ('audit\nuser injected', 'secret'), ('bad:name', 'secret'),
    ('ot-ia-tls', 'secret'), ('audit', 'secret\nline'), ('audit', ''),
])
def test_accounts_refuse_unsafe_or_conflicting_values(username, password):
    helper = module('prepare_mqtt_tls')
    with pytest.raises(helper.SetupError) as error:
        helper.accounts(audit(username, password))
    assert 'secret' not in str(error.value)


def layout(tmp_path):
    (tmp_path/'conf.d').mkdir()
    (tmp_path/'mosquitto.conf').write_text('persistence true\ninclude_dir /etc/mosquitto/conf.d\n')
    (tmp_path/'conf.d/ot.conf').write_text(
        'listener 1883 0.0.0.0\nallow_anonymous false\npassword_file /etc/mosquitto/passwd\n')


@pytest.mark.parametrize('change', ['none', 'legacy', 'extra', 'main', 'include'])
def test_only_inspected_broker_layout_is_accepted(tmp_path, change):
    helper = module('prepare_mqtt_tls')
    layout(tmp_path)
    if change == 'legacy':
        (tmp_path/'conf.d/ot.conf').write_text('listener 8883\n')
    if change == 'extra':
        (tmp_path/'conf.d/other.conf').write_text('listener 1884\n')
    if change == 'main':
        (tmp_path/'mosquitto.conf').write_text('per_listener_settings true\ninclude_dir /etc/mosquitto/conf.d\n')
    if change == 'include':
        (tmp_path/'mosquitto.conf').write_text('include_dir /other\n')
    if change == 'none':
        assert helper.check_layout(tmp_path) == (tmp_path/'mosquitto.conf').read_bytes()
    else:
        with pytest.raises(helper.SetupError):
            helper.check_layout(tmp_path)


def test_private_files_never_overwrite(tmp_path):
    helper = module('prepare_mqtt_tls')
    path = tmp_path/'credentials'
    helper.private_file(path, 'preserve-me')
    with pytest.raises(FileExistsError):
        helper.private_file(path, 'replacement')
    assert path.read_text() == 'preserve-me'


def test_failed_commands_do_not_leak_credentials(monkeypatch):
    helper = module('prepare_mqtt_tls')
    monkeypatch.setattr(helper.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, 'private-value', 'private-value'))
    with pytest.raises(helper.SetupError) as error:
        helper.kubectl('create', '-f', '-', data='private-value')
    assert 'private-value' not in str(error.value)


def test_broker_restart_failure_restores_only_its_configuration(tmp_path, monkeypatch):
    helper = module('prepare_mqtt_tls')
    main = tmp_path/'mosquitto.conf'
    original = b'original configuration\n'
    main.write_bytes(original)
    extra = tmp_path/'ot-tls.conf'
    preserved = tmp_path/'credentials.json'
    preserved.write_text('protected-backup')
    calls = []
    def run(command, data=None):
        calls.append(command)
        if len(calls) == 1:
            raise helper.SetupError('restart failed')
    monkeypatch.setattr(helper, 'run', run)
    monkeypatch.setattr(helper.os, 'chown', lambda *args: None, raising=False)
    with pytest.raises(helper.SetupError, match='restored'):
        helper.activate(main, original, extra, {}, tmp_path/'ca.crt', 0)
    assert main.read_bytes() == original
    assert not extra.exists()
    assert preserved.read_text() == 'protected-backup'
    assert calls == [['systemctl', 'restart', 'mosquitto']] * 2


def test_concurrent_config_change_stops_before_activation(tmp_path):
    helper = module('prepare_mqtt_tls')
    main = tmp_path/'mosquitto.conf'
    main.write_bytes(b'operator change')
    extra = tmp_path/'ot-tls.conf'
    with pytest.raises(helper.SetupError, match='changed'):
        helper.activate(main, b'old config', extra, {}, tmp_path/'ca.crt', 0)
    assert main.read_bytes() == b'operator change'
    assert not extra.exists()
