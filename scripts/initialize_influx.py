"""Initialize an empty InfluxDB through a verified local/HTTPS API, once only."""
import argparse
import base64
import json
import os
import subprocess
import time
from urllib.error import URLError
from urllib.parse import urlencode

from provision_influx_tokens import api


def initialize(base, username, password, token, org, bucket):
    """Preserve an initialized database and verify the supplied operator identity."""
    state = api(base, token, '/api/v2/setup')
    allowed = state.get('allowed')
    if not isinstance(allowed, bool):
        raise ValueError('Invalid InfluxDB setup response')
    if allowed:
        if not all((username, password, token, org, bucket)):
            raise ValueError('Initial InfluxDB credentials must be nonempty')
        api(base, token, '/api/v2/setup', {
            'username': username, 'password': password, 'token': token,
            'org': org, 'bucket': bucket,
        })
    # Fail if an existing database has different credentials or configuration.
    # Never reset it, create substitute organizations, or rotate tokens implicitly.
    organizations = api(base, token, '/api/v2/orgs?' + urlencode({'org': org}))['orgs']
    if len(organizations) != 1:
        raise ValueError('Expected exactly one existing InfluxDB organization')
    buckets = api(base, token, '/api/v2/buckets?' + urlencode({
        'orgID': organizations[0]['id'], 'name': bucket,
    }))['buckets']
    if len(buckets) != 1:
        raise ValueError('Expected exactly one existing InfluxDB bucket')
    return allowed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', default=os.environ.get('INFLUXDB_URL'))
    parser.add_argument('--from-kubernetes-secret', action='store_true',
                        help='Read the existing observability-secrets in ot-namespace')
    args = parser.parse_args()
    if not args.url:
        parser.error('Set INFLUXDB_URL or --url to the local port-forward/HTTPS endpoint')
    credentials = os.environ
    if args.from_kubernetes_secret:
        result = subprocess.run([
            'kubectl', '-n', 'ot-namespace', 'get', 'secret',
            'observability-secrets', '-o', 'json',
        ], capture_output=True, text=True, timeout=30, check=True)
        credentials = {key: base64.b64decode(value, validate=True).decode('utf-8')
                       for key, value in json.loads(result.stdout)['data'].items()}
    # The port-forward is started by bootstrap and may still be binding locally.
    for attempt in range(30):
        try:
            api(args.url, credentials['INFLUXDB_ADMIN_TOKEN'], '/health')
            break
        except URLError:
            if attempt == 29:
                raise
            time.sleep(1)
    created = initialize(args.url, *(credentials[key] for key in (
        'INFLUXDB_ADMIN_USER', 'INFLUXDB_ADMIN_PASSWORD', 'INFLUXDB_ADMIN_TOKEN',
        'INFLUXDB_ORG', 'INFLUXDB_BUCKET',
    )))
    print('InfluxDB initialized' if created else 'Existing InfluxDB credentials and bucket verified')


if __name__ == '__main__':
    main()
