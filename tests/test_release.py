import importlib.util
from pathlib import Path
import pytest
import yaml
from conftest import ROOT


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'scripts'/f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_rendered_references_and_original_secret_names(tmp_path):
    module('render_release').render('b'*40, tmp_path)
    secrets, maps = module('preflight').inspect(tmp_path)
    assert secrets['mqtt-credentials'] == {'username', 'password'}
    assert secrets['grafana-influxdb'] == {'INFLUXDB_READ_TOKEN'}
    assert 'INFLUXDB_ADMIN_TOKEN' not in secrets['nodered-auth']
    assert maps == {'mqtt-ca': {'ca.crt'}}


@pytest.mark.parametrize('damage', ['missing-dashboard', 'wrong-ip', 'unresolved-image'])
def test_preflight_rejects_broken_release(tmp_path, damage):
    module('render_release').render('b'*40, tmp_path)
    if damage == 'missing-dashboard':
        (tmp_path/'grafana-dashboard.yaml').unlink()
    else:
        target=tmp_path/('mqtt-config.yaml' if damage=='wrong-ip' else 'nodered-deploy.yaml')
        target.write_text(target.read_text().replace('192.168.1.12', '192.168.1.21') if damage=='wrong-ip' else target.read_text().replace('b'*40,'RELEASE_SHA'))
    with pytest.raises(ValueError):
        module('preflight').inspect(tmp_path)


def test_tokens_have_one_action_on_one_bucket(monkeypatch):
    helper = module('provision_influx_tokens')
    created = []
    def api(base, token, path, data=None):
        if path.startswith('/api/v2/orgs?'):return {'orgs':[{'id':'org-id'}]}
        if path.startswith('/api/v2/buckets?'):return {'buckets':[{'id':'bucket-id'}]}
        created.append(data)
        return {'token':'test-only-token'}
    monkeypatch.setattr(helper, 'api', api)
    assert set(helper.scoped_tokens('http://localhost:8086','test-only','lab','ot')) == {'nodered','grafana'}
    assert [item['permissions'] for item in created] == [
        [{'action': action, 'resource': {'type':'buckets','id':'bucket-id','orgID':'org-id'}}]
        for action in ('write','read')]


def node(architecture='amd64', operating_system='linux', ready=True, cordoned=False):
    return {'spec': {'unschedulable': cordoned}, 'status': {
        'nodeInfo': {'architecture': architecture, 'operatingSystem': operating_system},
        'conditions': [{'type': 'Ready', 'status': 'True' if ready else 'False'}],
    }}


@pytest.mark.parametrize('nodes', [
    [], [node(cordoned=True)], [node(ready=False)], [node(architecture='arm64')],
    [node(), node(architecture='arm64')], [node(operating_system='windows')],
    [{'spec': {}, 'status': {}}],
])
def test_release_rejects_unschedulable_or_incompatible_nodes(monkeypatch, nodes):
    preflight = module('preflight')
    monkeypatch.setattr(preflight, 'kubectl_json', lambda *args: {'items': nodes})
    with pytest.raises(ValueError):
        preflight.check_nodes()


def test_release_accepts_ready_linux_amd64_and_ignores_cordoned_nodes(monkeypatch):
    preflight = module('preflight')
    nodes = [node(), node(architecture='arm64', cordoned=True)]
    monkeypatch.setattr(preflight, 'kubectl_json', lambda *args: {'items': nodes})
    preflight.check_nodes()


@pytest.mark.parametrize('server', [
    'https://k3s--lab.cloud-ip.cc:6443',
    'http://k3s--lab.cloud-ip.cc:6443',
    'https://192.168.1.12:6443',
])
def test_cluster_requires_verified_ddns_api_endpoint(monkeypatch, server):
    preflight = module('preflight')
    monkeypatch.setattr(preflight, 'kubectl_json', lambda *args: {
        'clusters': [{'cluster': {'server': server}}],
    })
    if server.startswith('https://k3s--lab.cloud-ip.cc:'):
        preflight.check_cluster()
    else:
        with pytest.raises(ValueError, match='k3s--lab.cloud-ip.cc'):
            preflight.check_cluster()
