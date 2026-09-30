"""Disposable Docker integration: real Influx API and Node-RED bcrypt; fake Kubernetes."""
from contextlib import nullcontext
import json
from pathlib import Path
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_observability as helper


def docker(*args, data=None):
    result = subprocess.run(['docker', *args], input=data, text=True, capture_output=True,
                            timeout=90, check=False)
    if result.returncode:
        raise RuntimeError('Disposable Docker operation failed; raw output withheld')
    return result.stdout.strip()


def node_fixture(settings='module.exports={};', encrypted=True, key='legacy-test-key'):
    setup = 'const fixtureFs=require("fs");fixtureFs.mkdirSync("/data",{recursive:true});'
    files = {'settings.js': settings, '.config.runtime.json': json.dumps(
        {'_credentialSecret': key} if key else {}), 'flows_cred.json': json.dumps({'$': 'fixture'} if encrypted else {})}
    for name, content in files.items():
        setup += 'fixtureFs.writeFileSync(' + json.dumps('/data/' + name) + ',' + json.dumps(content) + ');'
    return setup + helper.NODE_AUTH


def main():
    container = 'ot-observability-test-' + uuid.uuid4().hex[:12]
    image = 'ghcr.io/davidevaloroso-sys/ot-security:influxdb-82184140b9826a46d177068d5bcb1282d05beea1'
    node_image = 'ot-security-nodered:runtime-no-installer-test'
    try:
        docker('run', '-d', '--name', container, '-p', '127.0.0.1::8086',
               '--tmpfs', '/var/lib/influxdb2:uid=1000,gid=1000',
               '--tmpfs', '/etc/influxdb2:uid=1000,gid=1000', image)
        port = docker('inspect', '--format', '{{(index (index .NetworkSettings.Ports "8086/tcp") 0).HostPort}}', container)
        helper.BASE = 'http://127.0.0.1:' + port
        for _ in range(60):
            try:
                helper.api(helper.BASE, 'fixture-admin-token', '/health')
                break
            except (URLError, OSError):
                time.sleep(0.5)
        else:
            raise AssertionError('Temporary InfluxDB not ready')
        helper.api(helper.BASE, 'fixture-admin-token', '/api/v2/setup', {
            'username': 'fixture-admin', 'password': 'fixture-password-long',
            'org': 'fixture-org', 'bucket': 'fixture-bucket', 'token': 'fixture-admin-token',
        })
        resources = {'observability-secrets': {'INFLUXDB_ADMIN_TOKEN': 'fixture-admin-token',
                    'INFLUXDB_ORG': 'fixture-org', 'INFLUXDB_BUCKET': 'fixture-bucket'}}
        helper.read_secret = resources.get
        helper.forward = nullcontext
        def kubectl(*args, data=None):
            if args[:2] == ('exec', '-i'):
                result = docker('run', '--rm', '-i', '--user', '0', '--entrypoint', 'node',
                                node_image, '-e', node_fixture(), data=data)
                assert json.loads(result)['NODE_RED_CREDENTIAL_SECRET'] == 'legacy-test-key'
                return result
            assert args == ('create', '-f', '-')
            resource = json.loads(data)
            name = resource['metadata']['name']
            assert name not in resources
            resources[name] = resource['stringData']
            return ''
        helper.kubectl = kubectl
        helper.prepare(False)
        assert len(resources) == 1
        helper.prepare(True)
        assert len(resources) == 3
        saved = json.dumps(resources, sort_keys=True)
        helper.prepare(True)
        assert json.dumps(resources, sort_keys=True) == saved
        for role, action in [('grafana-influxdb', 'read'), ('nodered-auth', 'write')]:
            org, bucket = helper.bucket_identity(resources['observability-secrets'])
            before = helper.api(helper.BASE, 'fixture-admin-token', '/api/v2/authorizations')['authorizations']
            try:
                recovered = helper.scoped_token('fixture-admin-token', org, bucket, role, action)
                assert recovered == resources[role]['INFLUXDB_READ_TOKEN' if action == 'read' else 'INFLUXDB_WRITE_TOKEN']
            except helper.PreparationError as error:
                # InfluxDB 2.9 does not return plaintext tokens a second time.
                assert 'token is unavailable' in str(error)
            after = helper.api(helper.BASE, 'fixture-admin-token', '/api/v2/authorizations')['authorizations']
            assert len(before) == len(after), 'Never rotate/duplicate an unrecoverable token'
        query = json.dumps({'query': 'from(bucket:"fixture-bucket") |> range(start:-1h)'}).encode()
        for role, expected_write, expected_read in [('grafana-influxdb', False, True), ('nodered-auth', True, False)]:
            token = resources[role]['INFLUXDB_READ_TOKEN' if role == 'grafana-influxdb' else 'INFLUXDB_WRITE_TOKEN']
            for path, body, content_type, expected in [
                ('/api/v2/write?org=fixture-org&bucket=fixture-bucket', b'fixture value=1', 'text/plain', expected_write),
                ('/api/v2/query?org=fixture-org', query, 'application/json', expected_read),
            ]:
                request = Request(helper.BASE + path, data=body, headers={
                    'Authorization': 'Token ' + token, 'Content-Type': content_type})
                try:
                    with urlopen(request, timeout=15) as response:
                        assert expected and response.status in (200, 204)
                except HTTPError as error:
                    assert not expected and error.code in (401, 403, 404), f'{role}: HTTP {error.code}; expected access={expected}'
        for settings, key in [('module.exports={credentialSecret:"custom"};', 'legacy-test-key'),
                              ('module.exports={};', None)]:
            try:
                docker('run', '--rm', '-i', '--user', '0', '--entrypoint', 'node', node_image,
                       '-e', node_fixture(settings=settings, key=key),
                       data=json.dumps({'password': 'fixture-password', 'key': 'new-fixture-key'}))
            except RuntimeError:
                pass
            else:
                raise AssertionError('Unknown existing encryption must be rejected')
        print('Observability smoke passed: real token scopes, no duplicate tokens, bcrypt, preserved encryption key, rerun and refusal checks.')
    finally:
        docker('rm', '-f', container)


if __name__ == '__main__':
    main()
