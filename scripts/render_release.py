"""Render commit-versioned application image tags without mutating source manifests."""
import argparse
import re
import hashlib
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def render(revision, output):
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected the full 40-character release commit SHA")
    output.mkdir(parents=True, exist_ok=True)
    for source in sorted((ROOT / 'k3s').glob('*.yaml')):
        docs = list(yaml.safe_load_all(source.read_text()))
        for doc in docs:
            if doc['kind'] == 'Deployment':
                container = doc['spec']['template']['spec']['containers'][0]
                container['image'] = container['image'].replace('RELEASE_SHA', revision)
                if doc['metadata']['name'] == 'grafana':
                    content = ''.join((ROOT/'platform/grafana'/name).read_text(encoding='utf-8')
                                      for name in ('datasource.yaml', 'provider.yaml', 'ot-security.json'))
                    doc['spec']['template']['metadata'].setdefault('annotations', {})['checksum/provisioning'] = hashlib.sha256(content.encode()).hexdigest()
        (output / source.name).write_text(yaml.safe_dump_all(docs, sort_keys=False), encoding='utf-8')
    maps = [
        ('grafana-datasource', {'datasource.yaml': 'platform/grafana/datasource.yaml'}),
        ('grafana-provider', {'provider.yaml': 'platform/grafana/provider.yaml'}),
        ('grafana-dashboard', {'ot-security.json': 'platform/grafana/ot-security.json'}),
    ]
    for name, files in maps:
        document = {'apiVersion': 'v1', 'kind': 'ConfigMap', 'metadata': {'name': name, 'namespace': 'ot-namespace'},
                    'data': {key: (ROOT/path).read_text(encoding='utf-8') for key, path in files.items()}}
        (output / f'{name}.yaml').write_text(yaml.safe_dump(document, sort_keys=False), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('revision')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    render(args.revision, args.output)
