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
        target.write_text(target.read_text().replace('192.168.1.21', '192.168.1.12') if damage=='wrong-ip' else target.read_text().replace('b'*40,'RELEASE_SHA'))
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


def test_cluster_accepts_verified_private_api(monkeypatch):
    preflight = module('preflight')
    monkeypatch.setattr(preflight, 'kubectl_json', lambda *args: {
        'clusters': [{'cluster': {'server': 'https://192.168.1.21:6443'}}],
    })
    preflight.check_cluster()


@pytest.mark.parametrize('server', [
    'https://k3s--lab.cloud-ip.cc:6443',
    'http://192.168.1.21:6443',
    'https://192.168.1.12:6443',
    'https://192.168.1.21:443',
    'https://192.168.1.21:6443/path',
])
def test_cluster_rejects_wrong_api_endpoint(monkeypatch, server):
    preflight = module('preflight')
    monkeypatch.setattr(preflight, 'kubectl_json', lambda *args: {
        'clusters': [{'cluster': {'server': server}}],
    })
    with pytest.raises(ValueError, match='192.168.1.21:6443'):
        preflight.check_cluster()


@pytest.mark.parametrize('override', [
    {'insecure-skip-tls-verify': True},
    {'tls-server-name': 'k3s--lab.cloud-ip.cc'},
    {'proxy-url': 'http://unintended-proxy:8080'},
])
def test_cluster_rejects_insecure_or_redirected_connection(monkeypatch, override):
    preflight = module('preflight')
    monkeypatch.setattr(preflight, 'kubectl_json', lambda *args: {
        'clusters': [{'cluster': {'server': 'https://192.168.1.21:6443', **override}}],
    })
    with pytest.raises(ValueError):
        preflight.check_cluster()


def kubeconfig():
    return {
        'apiVersion': 'v1', 'kind': 'Config', 'current-context': 'lab',
        'contexts': [{'name': 'lab', 'context': {'cluster': 'lab-cluster', 'user': 'operator'}}],
        'clusters': [
            {'name': 'unrelated', 'cluster': {'server': 'https://elsewhere:6443'}},
            {'name': 'lab-cluster', 'cluster': {
                'server': 'https://k3s--lab.cloud-ip.cc:6443',
                'tls-server-name': 'k3s--lab.cloud-ip.cc',
                'certificate-authority-data': 'test-ca-data',
            }},
        ],
        'users': [{'name': 'operator', 'user': {
            'client-certificate-data': 'test-cert-data', 'client-key-data': 'test-key-data',
        }}],
    }


def test_prepare_preserves_credentials_and_unrelated_contexts(tmp_path, capsys):
    config = kubeconfig()
    path = tmp_path/'kubeconfig'
    path.write_text(yaml.safe_dump(config))
    module('preflight').prepare_kubeconfig(path)
    result = yaml.safe_load(path.read_text())
    assert result['users'] == config['users']
    assert result['contexts'] == config['contexts']
    assert result['current-context'] == config['current-context']
    assert result['clusters'][0] == config['clusters'][0]
    assert result['clusters'][1]['cluster'] == {
        'server': 'https://192.168.1.21:6443', 'certificate-authority-data': 'test-ca-data',
    }
    before = path.read_bytes()
    module('preflight').prepare_kubeconfig(path)
    assert path.read_bytes() == before
    assert capsys.readouterr().out == ''


@pytest.mark.parametrize('damage', ['insecure', 'proxy', 'context', 'cluster', 'duplicate', 'yaml'])
def test_prepare_rejects_bad_config_without_writing_or_leaking(tmp_path, damage):
    config = kubeconfig()
    cluster = config['clusters'][1]['cluster']
    if damage == 'insecure':
        cluster['insecure-skip-tls-verify'] = True
    elif damage == 'proxy':
        cluster['proxy-url'] = 'http://test-key-data:secret@proxy:8080'
    elif damage == 'context':
        config['current-context'] = 'missing'
    elif damage == 'cluster':
        config['contexts'][0]['context']['cluster'] = 'missing'
    elif damage == 'duplicate':
        config['clusters'].append(config['clusters'][1])
    path = tmp_path/'kubeconfig'
    path.write_text('users: [test-key-data' if damage == 'yaml' else yaml.safe_dump(config))
    before = path.read_bytes()
    with pytest.raises(ValueError) as error:
        module('preflight').prepare_kubeconfig(path)
    assert 'test-key-data' not in str(error.value)
    assert path.read_bytes() == before
