from pathlib import Path
import importlib.util
import yaml
from conftest import ROOT


def test_manifests_secure_and_probe_ready():
    for name in ('ot-consumer','raspi-simulator','ia-consumer'):
        documents=list(yaml.safe_load_all((ROOT/'k3s'/f'{name}-deploy.yaml').read_text()))
        assert len(documents)==1
        deployment=documents[0];pod=deployment['spec']['template']['spec'];container=pod['containers'][0]
        assert deployment['spec']['strategy']['type']=='Recreate'
        assert pod['automountServiceAccountToken'] is False
        assert pod['securityContext']['fsGroup']==10001
        env={item['name']:item for item in container['env']}
        assert env['MQTT_TLS']['value']=='true'
        assert env['MQTT_PORT']['value']=='8883'
        assert 'startupProbe' in container and 'readinessProbe' in container
        assert 'livenessProbe' not in container
        assert container['securityContext']['readOnlyRootFilesystem']


def test_ci_pr_has_no_write_permissions_and_scan_precedes_publish():
    workflow=yaml.safe_load((ROOT/'.github/workflows/cicd-k3s.yml').read_text())
    assert workflow['permissions']=={'contents':'read'}
    assert workflow['jobs']['publish']['needs']==['build', 'security_scan', 'integration']
    deploy=workflow['jobs']['deploy_k3s']
    assert deploy['needs']=='publish'
    assert deploy['if']=="github.event_name == 'push' && github.ref == 'refs/heads/main'"
    assert deploy['environment']=='lab'
    assert deploy['concurrency']=={'group':'ot-lab-deployment','cancel-in-progress':False}
    configure=next(step for step in deploy['steps'] if step.get('name')=='Configure VPN and kubeconfig')
    assert '192.168.1.21 k3s--lab.cloud-ip.cc' in configure['run']
    assert 'AllowedIPs = 192.168.1.21/32' in configure['run']
    assert "github.event_name == 'push'" in workflow['jobs']['publish']['if']
    assert 'permissions' not in workflow['jobs']['build']
    for job in workflow['jobs'].values():
        for step in job['steps']:
            if step.get('uses','').startswith('actions/checkout@'):
                assert step['with']['persist-credentials'] is False
    build=workflow['jobs']['build']['steps']
    assert not any('docker push' in s.get('run','') for s in build)


def test_node_red_does_not_receive_admin_token():
    docs=list(yaml.safe_load_all((ROOT/'k3s/nodered-deploy.yaml').read_text()))
    env=next(d for d in docs if d['kind']=='Deployment')['spec']['template']['spec']['containers'][0]['env']
    token=next(e for e in env if e['name']=='INFLUXDB_TOKEN')
    assert token['valueFrom']['secretKeyRef']['key']=='INFLUXDB_WRITE_TOKEN'


def test_release_renderer_changes_only_output(tmp_path):
    path=ROOT/'scripts/render_release.py'
    spec=importlib.util.spec_from_file_location('render_release',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.render('a'*40,tmp_path)
    for p in tmp_path.glob('*.yaml'):
        assert 'RELEASE_SHA' not in p.read_text()
    for name in ('ia-consumer', 'raspi-simulator', 'ot-consumer', 'nodered', 'grafana', 'influxdb'):
        assert 'a'*40 in (tmp_path/f'{name}-deploy.yaml').read_text()
    assert (tmp_path/'grafana-dashboard.yaml').exists()
    assert 'RELEASE_SHA' in (ROOT/'k3s/ia-consumer-deploy.yaml').read_text()
