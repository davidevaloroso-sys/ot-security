"""Fail if a pinned Grafana base changes without its verified dependency inventory."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(root=ROOT):
    folder = root / 'platform/grafana'
    provenance = json.loads((folder / 'security/provenance.json').read_text())
    images = [line.split()[1] for line in (folder / 'Dockerfile').read_text().splitlines()
              if line.startswith('FROM ')]
    if images[-1] != provenance['image'] or provenance['platform'] != 'linux/amd64':
        raise ValueError('Refresh and verify the Grafana base SBOM for this image/platform')
    path = folder / 'security/base-sbom.spdx.json'
    if hashlib.sha256(path.read_bytes()).hexdigest() != provenance['sbom_sha256']:
        raise ValueError('Grafana base SBOM checksum mismatch')
    document = json.loads(path.read_bytes())
    if not document.get('spdxVersion', '').startswith('SPDX-') or len(document.get('packages', [])) < 2:
        raise ValueError('Missing Grafana dependency inventory')
    return path


if __name__ == '__main__':
    print(verify())
