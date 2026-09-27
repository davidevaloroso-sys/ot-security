"""Check rendered resource references and required Secret keys before deployment."""
import argparse
import json
from pathlib import Path
import subprocess
from urllib.parse import urlsplit
import yaml


def inspect(directory):
    documents = [doc for path in sorted(directory.glob('*.yaml')) for doc in yaml.safe_load_all(path.read_text(encoding='utf-8')) if doc]
    available = {(d['kind'], d['metadata']['name']): d for d in documents}
    secrets = {}
    external_maps = {'mqtt-ca': {'ca.crt'}}
    for doc in documents:
        if doc['kind'] != 'Deployment':
            continue
        pod = doc['spec']['template']['spec']
        for container in pod['containers']:
            if 'RELEASE_SHA' in container['image'] or 'SELECT_' in container['image'] or container['image'].endswith(':latest'):
                raise ValueError('Unresolved or mutable application image')
            for item in container.get('env', []):
                source = item.get('valueFrom', {})
                if 'secretKeyRef' in source:
                    ref = source['secretKeyRef'];secrets.setdefault(ref['name'], set()).add(ref['key'])
                if 'configMapKeyRef' in source:
                    ref = source['configMapKeyRef']
                    if ref['key'] not in available.get(('ConfigMap', ref['name']), {}).get('data', {}):
                        raise ValueError('Missing ConfigMap key: ' + ref['name'] + '/' + ref['key'])
        for volume in pod.get('volumes', []):
            if 'persistentVolumeClaim' in volume and ('PersistentVolumeClaim', volume['persistentVolumeClaim']['claimName']) not in available:
                raise ValueError('Unresolved PVC')
            if 'configMap' in volume:
                name = volume['configMap']['name']
                if ('ConfigMap', name) not in available and name not in external_maps:
                    raise ValueError('Unresolved ConfigMap: ' + name)
    if available[('ConfigMap', 'mqtt-config')]['data']['broker'] != '192.168.1.12':
        raise ValueError('Expected fixed laboratory broker 192.168.1.12')
    return secrets, external_maps


def kubectl_json(*args):
    result = subprocess.run(['kubectl', *args, '-o', 'json'], check=True, capture_output=True, text=True, timeout=30)
    return json.loads(result.stdout)


def check_cluster():
    config = kubectl_json('config', 'view', '--minify')
    cluster = config['clusters'][0]['cluster']
    endpoint = urlsplit(cluster['server'])
    if endpoint.scheme != 'https' or endpoint.hostname != '192.168.1.12' or cluster.get('insecure-skip-tls-verify'):
        raise ValueError('Expected verified K3s API on 192.168.1.12')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path, nargs='?')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--cluster-only', action='store_true')
    args = parser.parse_args()
    if args.cluster_only:
        check_cluster()
        print('Cluster endpoint validated')
        return
    if args.directory is None:
        parser.error('Rendered directory required')
    secrets, maps = inspect(args.directory)
    if not args.offline:
        check_cluster()
        for kind, expected in [('secret', secrets), ('configmap', maps)]:
            for name, keys in expected.items():
                resource = kubectl_json('-n', 'ot-namespace', 'get', kind, name)
                missing = keys - resource.get('data', {}).keys()
                if missing:
                    raise ValueError(f'Missing keys in {kind} {name}: {sorted(missing)}')
    for name, keys in sorted(secrets.items()):
        print(f'{name}: {", ".join(sorted(keys))}')
    print('Preflight passed' + (' (offline: cluster contents not checked)' if args.offline else ''))


if __name__ == '__main__':
    main()
