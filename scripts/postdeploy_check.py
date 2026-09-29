"""Read-only K3s smoke check through localhost port-forwards; never log secrets."""
import argparse
import base64
from contextlib import contextmanager
import json
import math
from pathlib import Path
import re
import subprocess
import tempfile
import time
from urllib.request import Request, build_opener

from preflight import check_cluster, kubectl_json
from provision_influx_tokens import NoRedirect


@contextmanager
def forward(service, port):
    with tempfile.TemporaryFile(mode='w+') as output:
        process = subprocess.Popen(
            ['kubectl', '-n', 'ot-namespace', 'port-forward',
             'service/' + service, ':' + str(port), '--address=127.0.0.1'],
            stdout=output, stderr=output, text=True)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                output.seek(0)
                match = re.search(r'Forwarding from 127\.0\.0\.1:(\d+)', output.read())
                if match:
                    yield 'http://127.0.0.1:' + match[1]
                    return
                if process.poll() is not None:
                    raise RuntimeError('Port-forward failed for ' + service)
                time.sleep(0.2)
            raise TimeoutError('Port-forward startup for ' + service)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


def request(base, path, auth=None, data=None):
    headers = {'Content-Type': 'application/json'}
    if auth:
        headers['Authorization'] = 'Basic ' + base64.b64encode(auth.encode()).decode()
    body = None if data is None else json.dumps(data).encode()
    with build_opener(NoRedirect()).open(
            Request(base + path, data=body, headers=headers), timeout=15) as response:
        return json.load(response)


def query(base, auth, flux):
    now = int(time.time() * 1000)
    response = request(base, '/api/ds/query', auth, {
        'from': str(now - 300_000), 'to': str(now),
        'queries': [{'refId': 'A', 'datasource': {'uid': 'ot-influxdb', 'type': 'influxdb'},
                     'query': flux, 'intervalMs': 1000, 'maxDataPoints': 1000}]})
    result = response.get('results', {}).get('A')
    if not isinstance(result, dict) or result.get('error') or result.get('status', 200) >= 400:
        raise RuntimeError('Grafana query failed (response body withheld)')
    return result.get('frames', [])


def has_recent_reading(frames, now_ms):
    # Require an actual time/value row, not merely a returned empty frame.
    for frame in frames:
        fields = frame.get('schema', {}).get('fields', [])
        values = frame.get('data', {}).get('values', [])
        times = next((i for i, field in enumerate(fields) if field.get('type') == 'time'), None)
        numbers = [i for i, field in enumerate(fields) if field.get('type') == 'number']
        if times is None or times >= len(values):
            continue
        for row, timestamp in enumerate(values[times]):
            if not isinstance(timestamp, (int, float)) or isinstance(timestamp, bool):
                continue
            if not now_ms - 300_000 <= timestamp <= now_ms + 30_000:
                continue
            if any(i < len(values) and row < len(values[i])
                   and isinstance(values[i][row], (int, float))
                   and not isinstance(values[i][row], bool)
                   and math.isfinite(values[i][row]) for i in numbers):
                return True
    return False


def check_grafana(base, auth):
    if request(base, '/api/health').get('database') != 'ok':
        raise RuntimeError('Grafana database is not ready')
    dashboard = request(base, '/api/dashboards/uid/ot-security', auth)['dashboard']
    if dashboard.get('uid') != 'ot-security' or len(dashboard.get('panels', [])) != 6:
        raise RuntimeError('Expected provisioned OT dashboard with six panels')
    expected = json.loads((Path(__file__).resolve().parents[1] /
                           'platform/grafana/ot-security.json').read_text(encoding='utf-8'))
    def queries(document):
        return {p['id']: [t.get('query') for t in p.get('targets', [])]
                for p in document['panels']}
    if queries(dashboard) != queries(expected):
        raise RuntimeError('Deployed dashboard queries differ from this release')
    if request(base, '/api/datasources/uid/ot-influxdb/health', auth).get('status') != 'OK':
        raise RuntimeError('Grafana datasource is not ready')
    count = 0
    for panel in dashboard['panels']:
        for target in panel.get('targets', []):
            query(base, auth, target['query'])
            count += 1
    if count != 5:
        raise RuntimeError('Expected five provisioned data queries')
    for kind in ('temperature', 'humidity'):
        flux = ('from(bucket: v.defaultBucket) |> range(start: -5m) '
                '|> filter(fn: (r) => r._measurement == "ot_telemetry" '
                'and r._field == "value" and r.kind == "' + kind + '") |> last()')
        if not has_recent_reading(query(base, auth, flux), int(time.time() * 1000)):
            raise RuntimeError('No recent persisted ' + kind + ' reading')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    check_cluster()
    credentials = kubectl_json('-n', 'ot-namespace', 'get', 'secret', 'observability-secrets')['data']
    auth = ':'.join(base64.b64decode(credentials[key], validate=True).decode()
                    for key in ('GRAFANA_ADMIN_USER', 'GRAFANA_ADMIN_PASSWORD'))
    with forward('nodered', 1880) as base:
        request(base, '/ot-health')
    with forward('influxdb', 8086) as base:
        if request(base, '/health').get('status') != 'pass':
            raise RuntimeError('InfluxDB is not healthy')
    with forward('grafana', 3000) as base:
        check_grafana(base, auth)
    print('PASS: K3s Node-RED/InfluxDB health, Grafana datasource, five dashboard queries, '
          'and temperature/humidity persisted within five minutes')


if __name__ == '__main__':
    main()
